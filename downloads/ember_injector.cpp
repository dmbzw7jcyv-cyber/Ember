// ember_injector.cpp
#include <windows.h>
#include <tlhelp32.h>
#include <string>
#include <iostream>
#include <fstream>

#define TARGET_PROCESS L"RobloxPlayerBeta.exe"

void Log(const std::string& msg, bool success = true) {
    std::cout << (success ? "[+] " : "[-] ") << msg << std::endl;
}

DWORD FindProcessId(const std::wstring& processName) {
    DWORD pid = 0;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return 0;

    PROCESSENTRY32W entry;
    entry.dwSize = sizeof(entry);

    if (Process32FirstW(snap, &entry)) {
        do {
            if (entry.szExeFile == processName) {
                pid = entry.th32ProcessID;
                break;
            }
        } while (Process32NextW(snap, &entry));
    }

    CloseHandle(snap);
    return pid;
}

bool InjectDLL(DWORD pid, const std::string& dllPath) {
    HANDLE hProcess = OpenProcess(
        PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION |
        PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ,
        FALSE, pid
    );
    if (!hProcess) {
        Log("Failed to open process. Error: " + std::to_string(GetLastError()), false);
        return false;
    }

    size_t pathSize = dllPath.size() + 1;
    LPVOID remoteMem = VirtualAllocEx(hProcess, NULL, pathSize,
                                       MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!remoteMem) {
        Log("VirtualAllocEx failed. Error: " + std::to_string(GetLastError()), false);
        CloseHandle(hProcess);
        return false;
    }

    if (!WriteProcessMemory(hProcess, remoteMem, dllPath.c_str(), pathSize, NULL)) {
        Log("WriteProcessMemory failed. Error: " + std::to_string(GetLastError()), false);
        VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return false;
    }

    HMODULE kernel32 = GetModuleHandleW(L"kernel32.dll");
    FARPROC loadLib = GetProcAddress(kernel32, "LoadLibraryA");
    if (!loadLib) {
        Log("GetProcAddress failed. Error: " + std::to_string(GetLastError()), false);
        VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return false;
    }

    HANDLE hThread = CreateRemoteThread(hProcess, NULL, 0,
                                        (LPTHREAD_START_ROUTINE)loadLib,
                                        remoteMem, 0, NULL);
    if (!hThread) {
        Log("CreateRemoteThread failed. Error: " + std::to_string(GetLastError()), false);
        VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
        CloseHandle(hProcess);
        return false;
    }

    WaitForSingleObject(hThread, INFINITE);

    VirtualFreeEx(hProcess, remoteMem, 0, MEM_RELEASE);
    CloseHandle(hThread);
    CloseHandle(hProcess);

    return true;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cout << "Usage: ember_injector.exe <dll_path> [pid]" << std::endl;
        return 1;
    }

    std::string dllPath = argv[1];
    DWORD targetPid = 0;

    if (argc >= 3) {
        targetPid = std::stoul(argv[2]);
        Log("Target PID provided: " + std::to_string(targetPid));
    }

    if (targetPid == 0) {
        Log("Searching for Roblox process...");
        targetPid = FindProcessId(TARGET_PROCESS);
        if (targetPid == 0) {
            Log("Roblox not running.", false);
            return 1;
        }
        Log("Found Roblox at PID: " + std::to_string(targetPid));
    }

    if (!std::ifstream(dllPath).good()) {
        Log("DLL file not found: " + dllPath, false);
        return 1;
    }

    Log("Injecting...");
    if (InjectDLL(targetPid, dllPath)) {
        Log("Injection successful.");
        return 0;
    } else {
        Log("Injection failed.", false);
        return 1;
    }
}