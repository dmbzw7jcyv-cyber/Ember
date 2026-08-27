// embernite_advanced.cpp
// skeleton esp, chams, loot esp, triggerbot, prediction, speed hack, teleport

#include <Windows.h>
#include <cmath>
#include <algorithm>
#include "imgui.h"

// ---------------------------------------------------------------------------
// skeleton esp
// ---------------------------------------------------------------------------
void RunSkeletonESP() {
    if (!g_esp_skeleton || !g_game_pid) return;

    Vec3 cam_pos = DriverRead<Vec3>(g_game_pid, g_game_base + offsets::CAMERA_LOCATION);
    FRotator cam_rot = DriverRead<FRotator>(g_game_pid, g_game_base + offsets::CAMERA_ROTATION);

    auto actors = GetActors();
    for (auto& a : actors) {
        if (!a.valid) continue;

        ULONG_PTR mesh = DriverRead<ULONG_PTR>(g_game_pid, a.address + offsets::MESH);
        if (!mesh) continue;

        ULONG_PTR bone_array = DriverRead<ULONG_PTR>(g_game_pid, mesh + offsets::BONE_ARRAY);
        int bone_count = DriverRead<int>(g_game_pid, mesh + offsets::BONE_COUNT);

        if (!bone_array || bone_count <= 0 || bone_count > 200) continue;

        static const int bone_pairs[][2] = {
            {0, 1},   // root to spine
            {1, 2},   // spine to neck
            {2, 3},   // neck to head
            {1, 4},   // spine to left shoulder
            {4, 5},   // left shoulder to left elbow
            {5, 6},   // left elbow to left hand
            {1, 7},   // spine to right shoulder
            {7, 8},   // right shoulder to right elbow
            {8, 9},   // right elbow to right hand
            {0, 10},  // root to left hip
            {10, 11}, // left hip to left knee
            {11, 12}, // left knee to left foot
            {0, 13},  // root to right hip
            {13, 14}, // right hip to right knee
            {14, 15}, // right knee to right foot
        };

        for (auto& pair : bone_pairs) {
            if (pair[0] >= bone_count || pair[1] >= bone_count) continue;

            ULONG_PTR bone1 = bone_array + pair[0] * 0x60;
            ULONG_PTR bone2 = bone_array + pair[1] * 0x60;

            Vec3 pos1 = DriverRead<Vec3>(g_game_pid, bone1 + 0x10);
            Vec3 pos2 = DriverRead<Vec3>(g_game_pid, bone2 + 0x10);

            Vec2 screen1, screen2;
            if (WorldToScreen(pos1, cam_pos, cam_rot, screen1) &&
                WorldToScreen(pos2, cam_pos, cam_rot, screen2)) {
                ImGui::GetBackgroundDrawList()->AddLine(
                    ImVec2(screen1.x, screen1.y),
                    ImVec2(screen2.x, screen2.y),
                    IM_COL32(255, 255, 255, 200), 1.5f
                );
            }
        }
    }
}

// ---------------------------------------------------------------------------
// loot esp
// ---------------------------------------------------------------------------
void RunLootESP() {
    if (!g_esp_loot || !g_game_pid) return;

    Vec3 cam_pos = DriverRead<Vec3>(g_game_pid, g_game_base + offsets::CAMERA_LOCATION);
    FRotator cam_rot = DriverRead<FRotator>(g_game_pid, g_game_base + offsets::CAMERA_ROTATION);

    ULONG_PTR uworld = DriverRead<ULONG_PTR>(g_game_pid, g_game_base + offsets::UWORLD);
    if (!uworld) return;

    ULONG_PTR actor_array = DriverRead<ULONG_PTR>(g_game_pid, uworld + offsets::ACTOR_LIST);
    int actor_count = DriverRead<int>(g_game_pid, uworld + offsets::ACTOR_COUNT);

    for (int i = 0; i < min(actor_count, 1024); ++i) {
        ULONG_PTR actor = DriverRead<ULONG_PTR>(g_game_pid, actor_array + i * 8);
        if (!actor) continue;

        ULONG_PTR root = DriverRead<ULONG_PTR>(g_game_pid, actor + offsets::ROOT_COMPONENT);
        if (!root) continue;

        Vec3 pos = DriverRead<Vec3>(g_game_pid, root + offsets::RELATIVE_LOCATION);
        float dist = Length(pos - cam_pos) / 100.f;

        if (dist > 100.f) continue;

        int rarity = DriverRead<int>(g_game_pid, actor + 0x9A0);

        ImU32 color;
        switch (rarity) {
            case 0: color = IM_COL32(150, 150, 150, 180); break;
            case 1: color = IM_COL32(80, 200, 80, 180); break;
            case 2: color = IM_COL32(80, 150, 255, 180); break;
            case 3: color = IM_COL32(180, 80, 255, 180); break;
            case 4: color = IM_COL32(255, 180, 40, 180); break;
            default: color = IM_COL32(255, 255, 255, 150); break;
        }

        Vec2 screen;
        if (WorldToScreen(pos, cam_pos, cam_rot, screen)) {
            ImGui::GetBackgroundDrawList()->AddText(
                ImVec2(screen.x - 10, screen.y),
                color, "Loot"
            );
        }
    }
}

// ---------------------------------------------------------------------------
// triggerbot
// ---------------------------------------------------------------------------
void RunTriggerbot() {
    if (!g_triggerbot || !g_game_pid) return;

    int screen_x = g_width / 2;
    int screen_y = g_height / 2;

    Vec3 cam_pos = DriverRead<Vec3>(g_game_pid, g_game_base + offsets::CAMERA_LOCATION);
    FRotator cam_rot = DriverRead<FRotator>(g_game_pid, g_game_base + offsets::CAMERA_ROTATION);

    auto actors = GetActors();
    for (auto& a : actors) {
        if (!a.valid) continue;

        Vec2 screen;
        if (WorldToScreen(a.position, cam_pos, cam_rot, screen)) {
            float dx = screen.x - screen_x;
            float dy = screen.y - screen_y;
            if (sqrtf(dx*dx + dy*dy) < 15.f) {
                mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0);
                Sleep(20);
                mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
                break;
            }
        }
    }
}

// ---------------------------------------------------------------------------
// prediction
// ---------------------------------------------------------------------------
Vec3 PredictTarget(const Vec3& target_pos, const Vec3& target_velocity, float distance) {
    if (!g_prediction) return target_pos;

    float bullet_speed = 25000.f;
    float travel_time = distance / bullet_speed;

    return target_pos + target_velocity * travel_time;
}

// ---------------------------------------------------------------------------
// chams
// ---------------------------------------------------------------------------
void RunChams() {
    if (!g_chams || !g_game_pid) return;

    auto actors = GetActors();
    for (auto& a : actors) {
        if (!a.valid) continue;

        ULONG_PTR mesh = DriverRead<ULONG_PTR>(g_game_pid, a.address + offsets::MESH);
        if (!mesh) continue;

        DriverWrite<uint8_t>(g_game_pid, mesh + 0x1A8, 1);
        DriverWrite<uint8_t>(g_game_pid, mesh + 0x1A9, 1);
    }
}

// ---------------------------------------------------------------------------
// speed hack
// ---------------------------------------------------------------------------
void RunSpeedHack() {
    if (!g_speed_hack || !g_game_pid) return;

    ULONG_PTR uworld = DriverRead<ULONG_PTR>(g_game_pid, g_game_base + offsets::UWORLD);
    if (!uworld) return;
    ULONG_PTR game_instance = DriverRead<ULONG_PTR>(g_game_pid, uworld + offsets::GAME_INSTANCE);
    ULONG_PTR local_players = DriverRead<ULONG_PTR>(g_game_pid, game_instance + offsets::LOCAL_PLAYERS);
    ULONG_PTR local_player = DriverRead<ULONG_PTR>(g_game_pid, local_players);
    ULONG_PTR player_controller = DriverRead<ULONG_PTR>(g_game_pid, local_player + offsets::PLAYER_CONTROLLER);
    ULONG_PTR acknowledged_pawn = DriverRead<ULONG_PTR>(g_game_pid, player_controller + offsets::ACKNOWLEDGED_PAWN);
    ULONG_PTR root = DriverRead<ULONG_PTR>(g_game_pid, acknowledged_pawn + offsets::ROOT_COMPONENT);

    if (!root) return;

    Vec3 velocity = DriverRead<Vec3>(g_game_pid, root + offsets::VELOCITY);
    velocity = velocity * 1.5f;
    DriverWrite(g_game_pid, root + offsets::VELOCITY, velocity);
}

// ---------------------------------------------------------------------------
// teleport
// ---------------------------------------------------------------------------
void RunTeleport() {
    if (!g_teleport || !g_game_pid) return;

    static bool was_pressed = false;
    bool is_pressed = GetAsyncKeyState('T') & 0x8000;

    if (is_pressed && !was_pressed) {
        ULONG_PTR uworld = DriverRead<ULONG_PTR>(g_game_pid, g_game_base + offsets::UWORLD);
        if (!uworld) return;
        ULONG_PTR game_instance = DriverRead<ULONG_PTR>(g_game_pid, uworld + offsets::GAME_INSTANCE);
        ULONG_PTR local_players = DriverRead<ULONG_PTR>(g_game_pid, game_instance + offsets::LOCAL_PLAYERS);
        ULONG_PTR local_player = DriverRead<ULONG_PTR>(g_game_pid, local_players);
        ULONG_PTR player_controller = DriverRead<ULONG_PTR>(g_game_pid, local_player + offsets::PLAYER_CONTROLLER);
        ULONG_PTR acknowledged_pawn = DriverRead<ULONG_PTR>(g_game_pid, player_controller + offsets::ACKNOWLEDGED_PAWN);
        ULONG_PTR root = DriverRead<ULONG_PTR>(g_game_pid, acknowledged_pawn + offsets::ROOT_COMPONENT);

        if (!root) return;

        Vec3 marker_pos = DriverRead<Vec3>(g_game_pid, player_controller + 0x1A8);

        DriverWrite(g_game_pid, root + offsets::RELATIVE_LOCATION, marker_pos);
    }
    was_pressed = is_pressed;
}

// ---------------------------------------------------------------------------
// no fog
// ---------------------------------------------------------------------------
void RunNoFog() {
    if (!g_no_fog || !g_game_pid) return;

    // example: write fog density to 0
    ULONG_PTR uworld = DriverRead<ULONG_PTR>(g_game_pid, g_game_base + offsets::UWORLD);
    if (!uworld) return;

    // fog settings typically in world or level
    ULONG_PTR fog_addr = uworld + 0x1C8; // example offset
    DriverWrite<float>(g_game_pid, fog_addr, 0.0f);
}

// ---------------------------------------------------------------------------
// hitbox override
// ---------------------------------------------------------------------------
void RunHitboxOverride() {
    if (!g_hitbox_override || !g_game_pid) return;

    auto actors = GetActors();
    for (auto& a : actors) {
        if (!a.valid) continue;

        ULONG_PTR mesh = DriverRead<ULONG_PTR>(g_game_pid, a.address + offsets::MESH);
        if (!mesh) continue;

        // expand hitbox scale
        DriverWrite<float>(g_game_pid, mesh + 0x1B0, 2.0f);
    }
}

// ---------------------------------------------------------------------------
// brightness
// ---------------------------------------------------------------------------
void RunBrightness() {
    if (!g_game_pid) return;

    // write brightness/gamma value
    ULONG_PTR uworld = DriverRead<ULONG_PTR>(g_game_pid, g_game_base + offsets::UWORLD);
    if (!uworld) return;

    ULONG_PTR brightness_addr = uworld + 0x1D0; // example offset
    DriverWrite<float>(g_game_pid, brightness_addr, g_brightness);
}

// ---------------------------------------------------------------------------
// run all advanced features
// ---------------------------------------------------------------------------
void RunAllAdvanced() {
    RunSkeletonESP();
    RunLootESP();
    RunTriggerbot();
    RunChams();
    RunSpeedHack();
    RunTeleport();
    RunNoFog();
    RunHitboxOverride();
    RunBrightness();
}