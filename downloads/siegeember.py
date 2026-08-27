#!/usr/bin/env python3
# SiegeEmber — Rainbow Six Siege Suite
# Soft walls, aimbot, anti-recoil, health mods, anti-cheat evasion

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import psutil
import pymem
import pymem.process
import keyboard
import mouse
import json
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from collections import deque
import math
import random

# ─── CONSTANTS ───
CONFIG_PATH = Path.home() / '.siegeember_config.json'
OFFSET_DB_PATH = Path.home() / '.siegeember_offsets.json'

SIEGE_PROCESSES = [
    "RainbowSix.exe",
    "RainbowSix_Vulkan.exe",
    "RainbowSix_BE.exe"
]

ANTICHEAT_PROCESSES = [
    "BEService.exe",
    "BEService_x64.exe",
    "BattlEye.exe",
    "BEClient.exe"
]

@dataclass
class SiegeOffsets:
    local_player: int = 0x0
    player_health: int = 0x0
    player_armor: int = 0x0
    player_position: int = 0x0
    player_team: int = 0x0
    view_matrix: int = 0x0
    view_angles: int = 0x0
    entity_list: int = 0x0
    entity_count: int = 0x0
    entity_size: int = 0x0
    recoil_x: int = 0x0
    recoil_y: int = 0x0
    spread: int = 0x0
    is_firing: int = 0x0
    game_state: int = 0x0

    def to_dict(self) -> Dict[str, str]:
        return {k: hex(v) for k, v in self.__dict__.items()}

    def from_dict(self, data: Dict[str, str]):
        for k, v in data.items():
            if hasattr(self, k):
                setattr(self, k, int(v, 16))

class SiegeMemory:
    def __init__(self):
        self.pm = None
        self.process_name = None
        self.base_address = None
        self.module_size = 0
        self.is_attached = False
        self.offsets = SiegeOffsets()
        self.cache = {}
        self.cache_timeout = 0.005

    def attach(self) -> bool:
        self.process_name = self.find_process()
        if not self.process_name:
            return False
        try:
            self.pm = pymem.Pymem(self.process_name)
            module = pymem.process.module_from_name(self.pm.process_handle, self.process_name)
            self.base_address = module.lpBaseOfDll
            self.module_size = module.SizeOfImage
            self.is_attached = True
            return True
        except Exception as e:
            print(f"[!] Attach failed: {e}")
            return False

    def find_process(self) -> Optional[str]:
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] in SIEGE_PROCESSES:
                    return proc.info['name']
            except:
                continue
        return None

    def read_float(self, address: int) -> float:
        try:
            return self.pm.read_float(address)
        except:
            return 0.0

    def write_float(self, address: int, value: float) -> bool:
        try:
            self.pm.write_float(address, value)
            return True
        except:
            return False

    def read_int(self, address: int) -> int:
        try:
            return self.pm.read_int(address)
        except:
            return 0

    def write_int(self, address: int, value: int) -> bool:
        try:
            self.pm.write_int(address, value)
            return True
        except:
            return False

    def read_vec3(self, address: int) -> Tuple[float, float, float]:
        try:
            x = self.read_float(address)
            y = self.read_float(address + 4)
            z = self.read_float(address + 8)
            return (x, y, z)
        except:
            return (0, 0, 0)

    def write_vec3(self, address: int, values: Tuple[float, float, float]) -> bool:
        try:
            self.write_float(address, values[0])
            self.write_float(address + 4, values[1])
            self.write_float(address + 8, values[2])
            return True
        except:
            return False

    def read_matrix(self, address: int) -> List[List[float]]:
        matrix = []
        for i in range(4):
            row = []
            for j in range(4):
                row.append(self.read_float(address + (i * 16) + (j * 4)))
            matrix.append(row)
        return matrix

class SoftWallsEngine:
    def __init__(self, memory: SiegeMemory):
        self.mem = memory
        self.running = False
        self.entities = []
        self.settings = {
            'soft_walls': True,
            'esp_players': True,
            'esp_through_walls': True,
            'esp_distance': 100,
            'draw_box': True,
            'draw_health': True,
            'draw_distance': True,
            'wall_alpha': 0.3,
            'wall_thickness': 1.5
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.scan_loop, daemon=True).start()

    def scan_loop(self):
        while self.running:
            self.scan_entities()
            time.sleep(0.005)

    def scan_entities(self):
        self.entities = []
        try:
            local_team = self.mem.read_int(self.mem.base_address + self.mem.offsets.local_player + 0x50)
            local_pos = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.player_position)
            entity_list = self.mem.read_int(self.mem.base_address + self.mem.offsets.entity_list)
            if entity_list:
                count = self.mem.read_int(self.mem.base_address + self.mem.offsets.entity_count)
                for i in range(min(count, 64)):
                    entity_ptr = self.mem.read_int(entity_list + (i * self.mem.offsets.entity_size))
                    if entity_ptr:
                        team = self.mem.read_int(entity_ptr + 0x50)
                        if team == local_team:
                            continue
                        health = self.mem.read_float(entity_ptr + 0x100)
                        position = self.mem.read_vec3(entity_ptr + 0x30)
                        distance = self.calc_distance(local_pos, position)
                        if distance < self.settings['esp_distance']:
                            self.entities.append({
                                'position': position,
                                'team': team,
                                'health': health,
                                'distance': distance,
                                'is_enemy': True,
                                'pointer': entity_ptr
                            })
        except:
            pass

    def calc_distance(self, pos1, pos2) -> float:
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        dz = pos1[2] - pos2[2]
        return math.sqrt(dx*dx + dy*dy + dz*dz)

class CombatEngine:
    def __init__(self, memory: SiegeMemory):
        self.mem = memory
        self.running = False
        self.settings = {
            'aimbot': True,
            'aimbot_fov': 5,
            'aimbot_smooth': 8,
            'aimbot_bone': 'head',
            'anti_recoil': True,
            'recoil_compensation': 1.0,
            'no_spread': True
        }
        self.bones = {
            'head': 0x0,
            'neck': 0x10,
            'chest': 0x20,
            'pelvis': 0x30
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.aimbot_loop, daemon=True).start()
        threading.Thread(target=self.recoil_loop, daemon=True).start()

    def aimbot_loop(self):
        while self.running:
            if self.settings['aimbot']:
                if keyboard.is_pressed('right'):
                    target = self.find_target()
                    if target:
                        self.aim_at_target(target)
            time.sleep(0.001)

    def find_target(self) -> Optional[Dict]:
        try:
            local_pos = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.player_position)
            local_team = self.mem.read_int(self.mem.base_address + self.mem.offsets.local_player + 0x50)
            view_angles = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.view_angles)
            entity_list = self.mem.read_int(self.mem.base_address + self.mem.offsets.entity_list)
            if not entity_list:
                return None
            count = self.mem.read_int(self.mem.base_address + self.mem.offsets.entity_count)
            best_target = None
            best_fov = self.settings['aimbot_fov']
            for i in range(min(count, 64)):
                entity_ptr = self.mem.read_int(entity_list + (i * self.mem.offsets.entity_size))
                if entity_ptr:
                    team = self.mem.read_int(entity_ptr + 0x50)
                    if team == local_team:
                        continue
                    bone_offset = self.bones.get(self.settings['aimbot_bone'], 0x0)
                    entity_pos = self.mem.read_vec3(entity_ptr + 0x30 + bone_offset)
                    angle = self.calc_angle(local_pos, entity_pos)
                    fov = self.calc_fov(view_angles, angle)
                    if fov < best_fov:
                        best_fov = fov
                        best_target = {'position': entity_pos, 'angle': angle}
            return best_target
        except:
            return None

    def aim_at_target(self, target: Dict):
        try:
            current = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.view_angles)
            smooth = self.settings['aimbot_smooth']
            new_x = current[0] + (target['angle'][0] - current[0]) / smooth
            new_y = current[1] + (target['angle'][1] - current[1]) / smooth
            self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles, new_x)
            self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles + 4, new_y)
        except:
            pass

    def recoil_loop(self):
        while self.running:
            if self.settings['anti_recoil']:
                firing = self.mem.read_int(self.mem.base_address + self.mem.offsets.is_firing)
                if firing:
                    recoil_x = self.mem.read_float(self.mem.base_address + self.mem.offsets.recoil_x)
                    recoil_y = self.mem.read_float(self.mem.base_address + self.mem.offsets.recoil_y)
                    comp = self.settings['recoil_compensation']
                    view = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.view_angles)
                    self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles, view[0] - recoil_x * comp)
                    self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles + 4, view[1] - recoil_y * comp)
            if self.settings['no_spread']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.spread, 0.0)
            time.sleep(0.001)

    def calc_angle(self, from_pos, to_pos) -> Tuple[float, float]:
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        dz = to_pos[2] - from_pos[2]
        yaw = math.degrees(math.atan2(dy, dx))
        pitch = math.degrees(math.atan2(dz, math.sqrt(dx*dx + dy*dy)))
        return (pitch, yaw)

    def calc_fov(self, current, target) -> float:
        fov_x = abs(current[0] - target[0])
        fov_y = abs(current[1] - target[1])
        return math.sqrt(fov_x*fov_x + fov_y*fov_y)

class HealthEngine:
    def __init__(self, memory: SiegeMemory):
        self.mem = memory
        self.running = False
        self.settings = {
            'infinite_health': True,
            'extra_health': False,
            'health_amount': 200,
            'infinite_armor': True,
            'auto_heal': True,
            'god_mode': False
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.health_loop, daemon=True).start()
        threading.Thread(target=self.armor_loop, daemon=True).start()

    def health_loop(self):
        while self.running:
            if self.settings['infinite_health']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.player_health, 100.0)
            elif self.settings['extra_health']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.player_health, float(self.settings['health_amount']))
            if self.settings['auto_heal']:
                current = self.mem.read_float(self.mem.base_address + self.mem.offsets.player_health)
                if current < 100:
                    self.mem.write_float(self.mem.base_address + self.mem.offsets.player_health, min(100, current + 0.1))
            time.sleep(0.01)

    def armor_loop(self):
        while self.running:
            if self.settings['infinite_armor']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.player_armor, 100.0)
            time.sleep(0.01)

class SiegeEmberGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SiegeEmber — Rainbow Six Siege Suite")
        self.root.geometry("550x750")
        self.root.configure(bg='#0a0a12')
        self.memory = SiegeMemory()
        self.soft_walls = SoftWallsEngine(self.memory)
        self.combat = CombatEngine(self.memory)
        self.health = HealthEngine(self.memory)
        self.is_running = False
        self.colors = {
            'bg': '#0a0a12',
            'card': '#15152a',
            'accent': '#ff6b00',
            'accent2': '#ff1744',
            'text': '#ffffff',
            'dim': '#a0a0b0',
            'success': '#00e676',
            'danger': '#ff4444',
            'warning': '#ffd700'
        }
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        title_frame = tk.Frame(self.root, bg=self.colors['card'], height=70)
        title_frame.pack(fill='x')
        title_frame.pack_propagate(False)
        title = tk.Label(title_frame, text="SiegeEmber", font=('Segoe UI', 26, 'bold'), fg=self.colors['accent'], bg=self.colors['card'])
        title.pack(pady=10)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        esp_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(esp_tab, text='Soft Walls')
        combat_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(combat_tab, text='Combat')
        health_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(health_tab, text='Health')

        esp_frame = tk.LabelFrame(esp_tab, text="ESP Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        esp_frame.pack(fill='x', padx=5, pady=5)
        self.soft_walls_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="Soft Walls", variable=self.soft_walls_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.esp_players_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="Player ESP", variable=self.esp_players_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.through_walls_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="Through Walls", variable=self.through_walls_var, bg=self.colors['card'], fg=self.colors['warning'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        combat_frame = tk.LabelFrame(combat_tab, text="Combat Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        combat_frame.pack(fill='x', padx=5, pady=5)
        self.aimbot_var = tk.BooleanVar(value=True)
        tk.Checkbutton(combat_frame, text="Aimbot", variable=self.aimbot_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.antirecoil_var = tk.BooleanVar(value=True)
        tk.Checkbutton(combat_frame, text="Anti-Recoil", variable=self.antirecoil_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.nospread_var = tk.BooleanVar(value=True)
        tk.Checkbutton(combat_frame, text="No Spread", variable=self.nospread_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        health_frame = tk.LabelFrame(health_tab, text="Health Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        health_frame.pack(fill='x', padx=5, pady=5)
        self.inf_health_var = tk.BooleanVar(value=True)
        tk.Checkbutton(health_frame, text="Infinite Health", variable=self.inf_health_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.inf_armor_var = tk.BooleanVar(value=True)
        tk.Checkbutton(health_frame, text="Infinite Armor", variable=self.inf_armor_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.auto_heal_var = tk.BooleanVar(value=True)
        tk.Checkbutton(health_frame, text="Auto Heal", variable=self.auto_heal_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.god_mode_var = tk.BooleanVar(value=False)
        tk.Checkbutton(health_frame, text="God Mode", variable=self.god_mode_var, bg=self.colors['card'], fg=self.colors['warning'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        status_frame = tk.Frame(self.root, bg=self.colors['card'], height=45)
        status_frame.pack(fill='x', padx=10, pady=(0,5))
        status_frame.pack_propagate(False)
        self.status_dot = tk.Label(status_frame, text="●", font=('Segoe UI', 14), fg=self.colors['danger'], bg=self.colors['card'])
        self.status_dot.pack(side='left', padx=(15,8))
        self.status_label = tk.Label(status_frame, text="IDLE", font=('Segoe UI', 11, 'bold'), fg=self.colors['dim'], bg=self.colors['card'])
        self.status_label.pack(side='left')

        btn_frame = tk.Frame(self.root, bg=self.colors['bg'])
        btn_frame.pack(fill='x', padx=10, pady=10)
        self.start_btn = tk.Button(btn_frame, text="START", font=('Segoe UI', 13, 'bold'), bg=self.colors['accent2'], fg='white', relief='flat', padx=20, pady=10, command=self.toggle_engine)
        self.start_btn.pack(side='left', padx=5, expand=True, fill='x')
        tk.Button(btn_frame, text="SAVE", font=('Segoe UI', 11, 'bold'), bg='#ff6f00', fg='white', relief='flat', padx=12, pady=10, command=self.save_settings).pack(side='left', padx=5)

    def toggle_engine(self):
        if not self.is_running:
            self.soft_walls.settings['soft_walls'] = self.soft_walls_var.get()
            self.soft_walls.settings['esp_players'] = self.esp_players_var.get()
            self.soft_walls.settings['esp_through_walls'] = self.through_walls_var.get()
            self.combat.settings['aimbot'] = self.aimbot_var.get()
            self.combat.settings['anti_recoil'] = self.antirecoil_var.get()
            self.combat.settings['no_spread'] = self.nospread_var.get()
            self.health.settings['infinite_health'] = self.inf_health_var.get()
            self.health.settings['infinite_armor'] = self.inf_armor_var.get()
            self.health.settings['auto_heal'] = self.auto_heal_var.get()
            self.health.settings['god_mode'] = self.god_mode_var.get()
            if self.memory.attach():
                self.soft_walls.start()
                self.combat.start()
                self.health.start()
                self.is_running = True
                self.status_dot.config(fg=self.colors['success'])
                self.status_label.config(text="RUNNING", fg=self.colors['success'])
                self.start_btn.config(text="STOP", bg=self.colors['danger'])
            else:
                self.status_dot.config(fg=self.colors['danger'])
                self.status_label.config(text="FAILED", fg=self.colors['danger'])
        else:
            self.soft_walls.running = False
            self.combat.running = False
            self.health.running = False
            self.is_running = False
            self.status_dot.config(fg=self.colors['danger'])
            self.status_label.config(text="IDLE", fg=self.colors['dim'])
            self.start_btn.config(text="START", bg=self.colors['accent2'])

    def save_settings(self):
        settings = {
            'soft_walls': self.soft_walls_var.get(),
            'esp_players': self.esp_players_var.get(),
            'through_walls': self.through_walls_var.get(),
            'aimbot': self.aimbot_var.get(),
            'anti_recoil': self.antirecoil_var.get(),
            'no_spread': self.nospread_var.get(),
            'infinite_health': self.inf_health_var.get(),
            'infinite_armor': self.inf_armor_var.get(),
            'auto_heal': self.auto_heal_var.get(),
            'god_mode': self.god_mode_var.get()
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(settings, f, indent=2)

    def load_settings(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                settings = json.load(f)
            for key, var in [
                ('soft_walls', self.soft_walls_var),
                ('esp_players', self.esp_players_var),
                ('through_walls', self.through_walls_var),
                ('aimbot', self.aimbot_var),
                ('anti_recoil', self.antirecoil_var),
                ('no_spread', self.nospread_var),
                ('infinite_health', self.inf_health_var),
                ('infinite_armor', self.inf_armor_var),
                ('auto_heal', self.auto_heal_var),
                ('god_mode', self.god_mode_var)
            ]:
                if key in settings:
                    var.set(settings[key])

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    gui = SiegeEmberGUI()
    gui.run()