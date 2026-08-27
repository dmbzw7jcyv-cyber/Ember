// embernite_main.cpp
// complete main loop with all features

#include <Windows.h>
#include <d3d11.h>
#include <thread>
#include "imgui.h"
#include "imgui_impl_dx11.h"
#include "imgui_impl_win32.h"

// ---------------------------------------------------------------------------
// run all features
// ---------------------------------------------------------------------------
void RunAllFeatures() {
    RunESP();
    RunSkeletonESP();
    RunLootESP();
    RunAimbot();
    RunTriggerbot();
    RunChams();
    RunFly();
    RunNoClip();
    RunSpeedHack();
    RunTeleport();
    RunInstantEdit();
    RunAutoMantle();
    RunQuickBuild();
    RunAutoDrop();
    RunAutoPickupFilter();
    RunStreamerMode();
    RunNoFog();
    RunHitboxOverride();
    RunBrightness();
}

int main() {
    g_game_pid = GetPid(L"FortniteClient-Win64-Shipping.exe");
    if (!g_game_pid) return 1;

    if (!DriverInit()) return 1;

    BASE_REQUEST req = { g_game_pid, 0 };
    DWORD bytes = 0;
    DeviceIoControl(g_driver, IOCTL_GET_BASE, &req, sizeof(req), &req, sizeof(req), &bytes, NULL);
    g_game_base = req.base_address;

    ULONG_PTR our_pid = GetCurrentProcessId();
    DeviceIoControl(g_driver, IOCTL_HIDE_PROC, &our_pid, sizeof(our_pid), NULL, 0, &bytes, NULL);

    g_antidetect.Start();

    LoadConfig();

    CreateOverlay();
    InitD3D11();

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGui::StyleColorsDark();
    ImGui_ImplWin32_Init(g_overlay);
    ImGui_ImplDX11_Init(g_device, g_context);

    MSG msg = {};
    while (g_running) {
        if (PeekMessage(&msg, nullptr, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
            if (msg.message == WM_QUIT) break;
        }

        if (GetAsyncKeyState(VK_INSERT) & 0x8000) g_menu_open = !g_menu_open;
        if (GetAsyncKeyState(VK_F1) & 0x8000) g_aimbot = !g_aimbot;
        if (GetAsyncKeyState(VK_F2) & 0x8000) g_fly = !g_fly;
        if (GetAsyncKeyState(VK_F3) & 0x8000) g_esp = !g_esp;
        if (GetAsyncKeyState(VK_F4) & 0x8000) g_triggerbot = !g_triggerbot;
        if (GetAsyncKeyState(VK_F5) & 0x8000) g_no_clip = !g_no_clip;
        if (GetAsyncKeyState(VK_F6) & 0x8000) g_esp_loot = !g_esp_loot;
        if (GetAsyncKeyState(VK_F7) & 0x8000) g_instant_edit = !g_instant_edit;
        if (GetAsyncKeyState(VK_F8) & 0x8000) g_quick_build = !g_quick_build;
        if (GetAsyncKeyState(VK_END) & 0x8000) break;

        RunAllFeatures();

        ImGui_ImplDX11_NewFrame();
        ImGui_ImplWin32_NewFrame();
        ImGui::NewFrame();

        if (g_menu_open) {
            RenderGUI();
        }

        ImGui::Render();
        g_context->OMSetRenderTargets(1, &g_rtv, nullptr);
        ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());
        g_swapchain->Present(1, 0);

        Sleep(1);
    }

    SaveConfig();
    g_antidetect.Stop();
    ImGui_ImplDX11_Shutdown();
    ImGui_ImplWin32_Shutdown();
    ImGui::DestroyContext();
    CloseHandle(g_driver);

    return 0;
}