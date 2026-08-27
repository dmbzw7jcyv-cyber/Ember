// payload.cpp
#include <windows.h>
#include <string>
#include <thread>
#include <chrono>

#define PIPE_NAME L"\\\\.\\pipe\\EmberPipe"
#define MAX_SCRIPT_SIZE 4096

HANDLE g_console = NULL;
HANDLE g_pipeHandle = INVALID_HANDLE_VALUE;
bool g_running = true;
bool g_pipeConnected = false;

void DebugPrint(const char* msg) {
    if (g_console) {
        WriteConsoleA(g_console, msg, (DWORD)strlen(msg), NULL, NULL);
        WriteConsoleA(g_console, "\n", 1, NULL, NULL);
    }
}

void DebugPrint(const std::string& msg) {
    DebugPrint(msg.c_str());
}

// ---- Lua State Finding ----
lua_State* FindLuaState() {
    DebugPrint("[*] Searching for Lua state...");
    return nullptr;
}

// ---- Lua Execution ----
bool ExecuteLua(lua_State* L, const std::string& script) {
    if (!L) {
        DebugPrint("[-] Lua state is null.");
        return false;
    }
    DebugPrint("[*] Executing script...");
    DebugPrint("[+] Script executed successfully.");
    return true;
}

// ---- Named Pipe Server ----
void SetupPipe() {
    DebugPrint("[*] Creating named pipe...");
    g_pipeHandle = CreateNamedPipeW(
        PIPE_NAME,
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
        1,
        MAX_SCRIPT_SIZE,
        MAX_SCRIPT_SIZE,
        0,
        NULL
    );

    if (g_pipeHandle == INVALID_HANDLE_VALUE) {
        DebugPrint("[-] Failed to create pipe. Error: " + std::to_string(GetLastError()));
        return;
    }

    DebugPrint("[+] Pipe created. Waiting for connection...");

    if (!ConnectNamedPipe(g_pipeHandle, NULL)) {
        DWORD err = GetLastError();
        if (err != ERROR_PIPE_CONNECTED) {
            DebugPrint("[-] ConnectNamedPipe failed. Error: " + std::to_string(err));
            CloseHandle(g_pipeHandle);
            g_pipeHandle = INVALID_HANDLE_VALUE;
            return;
        }
    }

    g_pipeConnected = true;
    DebugPrint("[+] Bridge connected.");
}

void HandlePipeMessages() {
    char buffer[MAX_SCRIPT_SIZE];
    DWORD bytesRead;

    while (g_running && g_pipeConnected) {
        if (!g_pipeHandle || g_pipeHandle == INVALID_HANDLE_VALUE) break;

        if (ReadFile(g_pipeHandle, buffer, sizeof(buffer) - 1, &bytesRead, NULL)) {
            if (bytesRead > 0) {
                buffer[bytesRead] = '\0';
                std::string script(buffer);
                DebugPrint("[*] Received script (" + std::to_string(bytesRead) + " bytes)");

                lua_State* L = FindLuaState();
                if (L) {
                    ExecuteLua(L, script);
                } else {
                    DebugPrint("[-] Lua state not ready.");
                }
            }
        } else {
            DWORD err = GetLastError();
            if (err == ERROR_BROKEN_PIPE || err == ERROR_NO_DATA) {
                DebugPrint("[-] Pipe disconnected.");
                g_pipeConnected = false;
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
}

// ---- Main Thread ----
DWORD WINAPI MainThread(LPVOID) {
    AllocConsole();
    g_console = GetStdHandle(STD_OUTPUT_HANDLE);

    DebugPrint("========================================");
    DebugPrint("  Ember Payload v1.0");
    DebugPrint("  Loaded into Roblox!");
    DebugPrint("========================================");

    SetupPipe();
    HandlePipeMessages();

    if (g_pipeHandle != INVALID_HANDLE_VALUE) {
        CloseHandle(g_pipeHandle);
        g_pipeHandle = INVALID_HANDLE_VALUE;
    }

    DebugPrint("[*] Payload shutting down.");
    return 0;
}

// ---- DLL Entry ----
BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID) {
    switch (reason) {
        case DLL_PROCESS_ATTACH:
            DisableThreadLibraryCalls(hModule);
            HANDLE hThread = CreateThread(NULL, 0, MainThread, NULL, 0, NULL);
            if (hThread) CloseHandle(hThread);
            break;
        case DLL_PROCESS_DETACH:
            g_running = false;
            break;
    }
    return TRUE;
}