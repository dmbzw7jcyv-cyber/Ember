// embernite_scripts.cpp
// built-in scripts and config system
// compile with embernite_usermode.cpp

#include <Windows.h>
#include <fstream>
#include <sstream>
#include "imgui.h"

// ---------------------------------------------------------------------------
// config system
// ---------------------------------------------------------------------------
struct Config {
    bool aimbot = false;
    float aim_fov = 180.f;
    float aim_smooth = 5.f;
    int aim_bone = 0;
    bool triggerbot = false;
    bool prediction = true;
    bool hitbox_override = false;

    bool esp = true;
    bool esp_box = true;
    bool esp_skeleton = false;
    bool esp_loot = false;
    bool chams = false;
    bool no_fog = true;
    float brightness = 1.2f;

    bool fly = false;
    float fly_speed = 500.f;
    bool no_clip = false;
    bool speed_hack = false;
    bool teleport = false;

    bool auto_drop = false;
    bool auto_pickup = false;
    bool instant_edit = false;
    bool auto_mantle = false;
    bool quick_build = false;
    bool streamer_mode = false;
};

Config g_config;

void SaveConfig(const char* filename = "embernite_config.json") {
    std::ofstream file(filename);
    if (!file.is_open()) return;

    file << "{\n";
    file << "  \"combat\": {\n";
    file << "    \"aimbot\": " << (g_config.aimbot ? "true" : "false") << ",\n";
    file << "    \"aim_fov\": " << g_config.aim_fov << ",\n";
    file << "    \"aim_smooth\": " << g_config.aim_smooth << ",\n";
    file << "    \"aim_bone\": " << g_config.aim_bone << ",\n";
    file << "    \"triggerbot\": " << (g_config.triggerbot ? "true" : "false") << ",\n";
    file << "    \"prediction\": " << (g_config.prediction ? "true" : "false") << ",\n";
    file << "    \"hitbox_override\": " << (g_config.hitbox_override ? "true" : "false") << "\n";
    file << "  },\n";
    file << "  \"visual\": {\n";
    file << "    \"esp\": " << (g_config.esp ? "true" : "false") << ",\n";
    file << "    \"esp_box\": " << (g_config.esp_box ? "true" : "false") << ",\n";
    file << "    \"esp_skeleton\": " << (g_config.esp_skeleton ? "true" : "false") << ",\n";
    file << "    \"esp_loot\": " << (g_config.esp_loot ? "true" : "false") << ",\n";
    file << "    \"chams\": " << (g_config.chams ? "true" : "false") << ",\n";
    file << "    \"no_fog\": " << (g_config.no_fog ? "true" : "false") << ",\n";
    file << "    \"brightness\": " << g_config.brightness << "\n";
    file << "  },\n";
    file << "  \"movement\": {\n";
    file << "    \"fly\": " << (g_config.fly ? "true" : "false") << ",\n";
    file << "    \"fly_speed\": " << g_config.fly_speed << ",\n";
    file << "    \"no_clip\": " << (g_config.no_clip ? "true" : "false") << ",\n";
    file << "    \"speed_hack\": " << (g_config.speed_hack ? "true" : "false") << ",\n";
    file << "    \"teleport\": " << (g_config.teleport ? "true" : "false") << "\n";
    file << "  },\n";
    file << "  \"scripts\": {\n";
    file << "    \"auto_drop\": " << (g_config.auto_drop ? "true" : "false") << ",\n";
    file << "    \"auto_pickup\": " << (g_config.auto_pickup ? "true" : "false") << ",\n";
    file << "    \"instant_edit\": " << (g_config.instant_edit ? "true" : "false") << ",\n";
    file << "    \"auto_mantle\": " << (g_config.auto_mantle ? "true" : "false") << ",\n";
    file << "    \"quick_build\": " << (g_config.quick_build ? "true" : "false") << ",\n";
    file << "    \"streamer_mode\": " << (g_config.streamer_mode ? "true" : "false") << "\n";
    file << "  }\n";
    file << "}\n";
    file.close();
}

void LoadConfig(const char* filename = "embernite_config.json") {
    std::ifstream file(filename);
    if (!file.is_open()) return;

    std::stringstream ss;
    ss << file.rdbuf();
    file.close();

    std::string content = ss.str();

    g_config.aimbot = content.find("\"aimbot\": true") != std::string::npos;
    g_config.triggerbot = content.find("\"triggerbot\": true") != std::string::npos;
    g_config.prediction = content.find("\"prediction\": true") != std::string::npos;
    g_config.hitbox_override = content.find("\"hitbox_override\": true") != std::string::npos;
    g_config.esp = content.find("\"esp\": true") != std::string::npos;
    g_config.esp_box = content.find("\"esp_box\": true") != std::string::npos;
    g_config.esp_skeleton = content.find("\"esp_skeleton\": true") != std::string::npos;
    g_config.esp_loot = content.find("\"esp_loot\": true") != std::string::npos;
    g_config.chams = content.find("\"chams\": true") != std::string::npos;
    g_config.no_fog = content.find("\"no_fog\": true") != std::string::npos;
    g_config.fly = content.find("\"fly\": true") != std::string::npos;
    g_config.no_clip = content.find("\"no_clip\": true") != std::string::npos;
    g_config.speed_hack = content.find("\"speed_hack\": true") != std::string::npos;
    g_config.teleport = content.find("\"teleport\": true") != std::string::npos;
    g_config.auto_drop = content.find("\"auto_drop\": true") != std::string::npos;
    g_config.auto_pickup = content.find("\"auto_pickup\": true") != std::string::npos;
    g_config.instant_edit = content.find("\"instant_edit\": true") != std::string::npos;
    g_config.auto_mantle = content.find("\"auto_mantle\": true") != std::string::npos;
    g_config.quick_build = content.find("\"quick_build\": true") != std::string::npos;
    g_config.streamer_mode = content.find("\"streamer_mode\": true") != std::string::npos;

    g_aimbot = g_config.aimbot;
    g_aim_fov = g_config.aim_fov;
    g_aim_smooth = g_config.aim_smooth;
    g_aim_bone = g_config.aim_bone;
    g_triggerbot = g_config.triggerbot;
    g_prediction = g_config.prediction;
    g_hitbox_override = g_config.hitbox_override;
    g_esp = g_config.esp;
    g_esp_box = g_config.esp_box;
    g_esp_skeleton = g_config.esp_skeleton;
    g_esp_loot = g_config.esp_loot;
    g_chams = g_config.chams;
    g_no_fog = g_config.no_fog;
    g_brightness = g_config.brightness;
    g_fly = g_config.fly;
    g_fly_speed = g_config.fly_speed;
    g_no_clip = g_config.no_clip;
    g_speed_hack = g_config.speed_hack;
    g_teleport = g_config.teleport;
    g_auto_drop = g_config.auto_drop;
    g_auto_pickup = g_config.auto_pickup;
    g_instant_edit = g_config.instant_edit;
    g_auto_mantle = g_config.auto_mantle;
    g_quick_build = g_config.quick_build;
    g_streamer_mode = g_config.streamer_mode;
}

// ---------------------------------------------------------------------------
// instant edit
// ---------------------------------------------------------------------------
void RunInstantEdit() {
    if (!g_instant_edit || !g_game_pid) return;

    if (GetAsyncKeyState('G') & 0x8000) {
        ULONG_PTR uworld = DriverRead<ULONG_PTR>(g_game_pid, g_game_base + offsets::UWORLD);
        if (!uworld) return;
        ULONG_PTR game_instance = DriverRead<ULONG_PTR>(g_game_pid, uworld + offsets::GAME_INSTANCE);
        ULONG_PTR local_players = DriverRead<ULONG_PTR>(g_game_pid, game_instance + offsets::LOCAL_PLAYERS);
        ULONG_PTR local_player = DriverRead<ULONG_PTR>(g_game_pid, local_players);
        ULONG_PTR player_controller = DriverRead<ULONG_PTR>(g_game_pid, local_player + offsets::PLAYER_CONTROLLER);

        ULONG_PTR edit_state = DriverRead<ULONG_PTR>(g_game_pid, player_controller + 0x1234);
        DriverWrite<uint8_t>(g_game_pid, edit_state + 0x10, 1);
    }
}

// ---------------------------------------------------------------------------
// auto mantle
// ---------------------------------------------------------------------------
void RunAutoMantle() {
    if (!g_auto_mantle || !g_game_pid) return;

    ULONG_PTR uworld = DriverRead<ULONG_PTR>(g_game_pid, g_game_base + offsets::UWORLD);
    if (!uworld) return;
    ULONG_PTR game_instance = DriverRead<ULONG_PTR>(g_game_pid, uworld + offsets::GAME_INSTANCE);
    ULONG_PTR local_players = DriverRead<ULONG_PTR>(g_game_pid, game_instance + offsets::LOCAL_PLAYERS);
    ULONG_PTR local_player = DriverRead<ULONG_PTR>(g_game_pid, local_players);
    ULONG_PTR player_controller = DriverRead<ULONG_PTR>(g_game_pid, local_player + offsets::PLAYER_CONTROLLER);
    ULONG_PTR acknowledged_pawn = DriverRead<ULONG_PTR>(g_game_pid, player_controller + offsets::ACKNOWLEDGED_PAWN);
    ULONG_PTR root = DriverRead<ULONG_PTR>(g_game_pid, acknowledged_pawn + offsets::ROOT_COMPONENT);

    if (!root) return;

    Vec3 pos = DriverRead<Vec3>(g_game_pid, root + offsets::RELATIVE_LOCATION);
    Vec3 velocity = DriverRead<Vec3>(g_game_pid, root + offsets::VELOCITY);

    if (Length(velocity) > 100.f) {
        ULONG_PTR mantle_state = DriverRead<ULONG_PTR>(g_game_pid, acknowledged_pawn + 0x9B0);
        if (mantle_state) {
            DriverWrite<uint8_t>(g_game_pid, mantle_state + 0x18, 1);
        }
    }
}

// ---------------------------------------------------------------------------
// quick build
// ---------------------------------------------------------------------------
void RunQuickBuild() {
    if (!g_quick_build || !g_game_pid) return;

    static bool was_pressed = false;
    bool is_pressed = GetAsyncKeyState(VK_XBUTTON2) & 0x8000;

    if (is_pressed && !was_pressed) {
        keybd_event('Q', 0, 0, 0);
        keybd_event('Q', 0, KEYEVENTF_KEYUP, 0);
        Sleep(20);
        keybd_event('F', 0, 0, 0);
        keybd_event('F', 0, KEYEVENTF_KEYUP, 0);
        Sleep(20);
        keybd_event('C', 0, 0, 0);
        keybd_event('C', 0, KEYEVENTF_KEYUP, 0);
        Sleep(20);
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
    }
    was_pressed = is_pressed;
}

// ---------------------------------------------------------------------------
// auto drop
// ---------------------------------------------------------------------------
void RunAutoDrop() {
    if (!g_auto_drop || !g_game_pid) return;

    static bool was_pressed = false;
    bool is_pressed = GetAsyncKeyState('X') & 0x8000;

    if (is_pressed && !was_pressed) {
        ULONG_PTR uworld = DriverRead<ULONG_PTR>(g_game_pid, g_game_base + offsets::UWORLD);
        if (!uworld) return;
        ULONG_PTR game_instance = DriverRead<ULONG_PTR>(g_game_pid, uworld + offsets::GAME_INSTANCE);
        ULONG_PTR local_players = DriverRead<ULONG_PTR>(g_game_pid, game_instance + offsets::LOCAL_PLAYERS);
        ULONG_PTR local_player = DriverRead<ULONG_PTR>(g_game_pid, local_players);
        ULONG_PTR player_controller = DriverRead<ULONG_PTR>(g_game_pid, local_player + offsets::PLAYER_CONTROLLER);
        ULONG_PTR acknowledged_pawn = DriverRead<ULONG_PTR>(g_game_pid, player_controller + offsets::ACKNOWLEDGED_PAWN);

        ULONG_PTR current_weapon = DriverRead<ULONG_PTR>(g_game_pid, acknowledged_pawn + offsets::CURRENT_WEAPON);
        if (current_weapon) {
            DriverWrite<uint8_t>(g_game_pid, current_weapon + 0x2C8, 1);
        }
    }
    was_pressed = is_pressed;
}

// ---------------------------------------------------------------------------
// auto pickup filter
// ---------------------------------------------------------------------------
void RunAutoPickupFilter() {
    if (!g_auto_pickup || !g_game_pid) return;

    ULONG_PTR uworld = DriverRead<ULONG_PTR>(g_game_pid, g_game_base + offsets::UWORLD);
    if (!uworld) return;

    ULONG_PTR actor_array = DriverRead<ULONG_PTR>(g_game_pid, uworld + offsets::ACTOR_LIST);
    int actor_count = DriverRead<int>(g_game_pid, uworld + offsets::ACTOR_COUNT);

    Vec3 cam_pos = DriverRead<Vec3>(g_game_pid, g_game_base + offsets::CAMERA_LOCATION);

    for (int i = 0; i < min(actor_count, 512); ++i) {
        ULONG_PTR actor = DriverRead<ULONG_PTR>(g_game_pid, actor_array + i * 8);
        if (!actor) continue;

        ULONG_PTR root = DriverRead<ULONG_PTR>(g_game_pid, actor + offsets::ROOT_COMPONENT);
        if (!root) continue;
        Vec3 pos = DriverRead<Vec3>(g_game_pid, root + offsets::RELATIVE_LOCATION);
        float dist = Length(pos - cam_pos) / 100.f;

        if (dist < 5.f) {
            int rarity = DriverRead<int>(g_game_pid, actor + 0x9A0);
            if (rarity >= 3) {
                keybd_event('E', 0, 0, 0);
                keybd_event('E', 0, KEYEVENTF_KEYUP, 0);
                break;
            }
        }
    }
}

// ---------------------------------------------------------------------------
// streamer mode
// ---------------------------------------------------------------------------
void RunStreamerMode() {
    if (!g_streamer_mode) return;

    g_esp = false;
    g_esp_box = false;
    g_esp_skeleton = false;
    g_esp_loot = false;
    g_chams = false;
}

// ---------------------------------------------------------------------------
// anti-detection
// ---------------------------------------------------------------------------
class AntiDetection {
private:
    std::thread scan_thread;
    bool running = true;

    void RandomizeWindowTitle() {
        static const char* titles[] = {
            "System Monitor",
            "Performance Overview",
            "Task Manager",
            "Resource Usage",
            "Network Status"
        };
        int idx = rand() % 5;
        SetWindowTextA(g_overlay, titles[idx]);
    }

    bool DetectScan() {
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        PROCESSENTRY32 pe = { sizeof(PROCESSENTRY32) };
        if (Process32First(snap, &pe)) {
            do {
                if (_wcsicmp(pe.szExeFile, L"BEService.exe") == 0 ||
                    _wcsicmp(pe.szExeFile, L"EasyAntiCheat.exe") == 0) {
                    CloseHandle(snap);
                    return true;
                }
            } while (Process32Next(snap, &pe));
        }
        CloseHandle(snap);
        return false;
    }

    void ScanLoop() {
        while (running) {
            if (DetectScan()) {
                g_esp = false;
                g_aimbot = false;
                Sleep(1000);
                g_esp = g_config.esp;
                g_aimbot = g_config.aimbot;
            }
            Sleep(500);
        }
    }

public:
    void Start() {
        RandomizeWindowTitle();
        scan_thread = std::thread(&AntiDetection::ScanLoop, this);
    }

    void Stop() {
        running = false;
        if (scan_thread.joinable()) scan_thread.join();
    }
};

AntiDetection g_antidetect;

// ---------------------------------------------------------------------------
// run all scripts
// ---------------------------------------------------------------------------
void RunAllScripts() {
    RunInstantEdit();
    RunAutoMantle();
    RunQuickBuild();
    RunAutoDrop();
    RunAutoPickupFilter();
    RunStreamerMode();
}