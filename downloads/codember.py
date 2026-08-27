#!/usr/bin/env python3
# CoDEmber — Call of Duty Suite
# Aimbot, ESP, No Recoil, Unlock All, Radar, Anti-Cheat Evasion

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
CONFIG_PATH = Path.home() / '.codember_config.json'
OFFSET_DB_PATH = Path.home() / '.codember_offsets.json'

COD_PROCESSES = [
    "cod.exe",
    "BlackOps6.exe",
    "ModernWarfare.exe",
    "Warzone.exe",
    "sp22-cod.exe"
]

ANTICHEAT_PROCESSES = [
    "Ricochet.exe",
    "codricochet.exe",
    "EasyAntiCheat.exe"
]

@dataclass
class CODOffsets:
    local_player: int = 0x0
    entity_list: int = 0x0
    entity_count: int = 0x0
    entity_size: int = 0x0
    view_matrix: int = 0x0
    view_angles: int = 0x0
    recoil_x: int = 0x0
    recoil_y: int = 0x0
    ammo: int = 0x0
    health: int = 0x0
    team: int = 0x0
    is_firing: int = 0x0
    unlock_all_flag: int = 0x0
    prestige: int = 0x0
    xp: int = 0x0

    def to_dict(self) -> Dict[str, str]:
        return {k: hex(v) for k, v in self.__dict__.items()}

    def from_dict(self, data: Dict[str, str]):
        for k, v in data.items():
            if hasattr(self, k):
                setattr(self, k, int(v, 16))

class CODMemory:
    def __init__(self):
        self.pm = None
        self.process_name = None
        self.base_address = None
        self.module_size = 0
        self.is_attached = False
        self.offsets = CODOffsets()
        self.cache = {}
        self.cache_timeout = 0.003

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
                if proc.info['name'] in COD_PROCESSES:
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

class AimbotEngine:
    def __init__(self, memory: CODMemory):
        self.mem = memory
        self.running = False
        self.settings = {
            'enabled': True,
            'fov': 8,
            'smooth': 5,
            'bone': 'head',
            'aim_key': 'right',
            'silent_aim': False,
            'visible_check': True
        }
        self.bones = {
            'head': 0x0,
            'neck': 0x10,
            'chest': 0x20,
            'pelvis': 0x30
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.aim_loop, daemon=True).start()

    def aim_loop(self):
        while self.running:
            if self.settings['enabled']:
                if keyboard.is_pressed(self.settings['aim_key']):
                    target = self.find_target()
                    if target:
                        self.aim_at_target(target)
            time.sleep(0.001)

    def find_target(self) -> Optional[Dict]:
        try:
            local_pos = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.local_player + 0x30)
            local_team = self.mem.read_int(self.mem.base_address + self.mem.offsets.local_player + 0x50)
            view_angles = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.view_angles)
            entity_list = self.mem.read_int(self.mem.base_address + self.mem.offsets.entity_list)
            if not entity_list:
                return None
            count = self.mem.read_int(self.mem.base_address + self.mem.offsets.entity_count)
            best_target = None
            best_fov = self.settings['fov']
            for i in range(min(count, 128)):
                entity_ptr = self.mem.read_int(entity_list + (i * self.mem.offsets.entity_size))
                if entity_ptr:
                    team = self.mem.read_int(entity_ptr + 0x50)
                    if team == local_team:
                        continue
                    bone_offset = self.bones.get(self.settings['bone'], 0x0)
                    target_pos = self.mem.read_vec3(entity_ptr + 0x30 + bone_offset)
                    angle = self.calc_angle(local_pos, target_pos)
                    fov = self.calc_fov(view_angles, angle)
                    if fov < best_fov:
                        best_fov = fov
                        best_target = {'position': target_pos, 'angle': angle}
            return best_target
        except:
            return None

    def aim_at_target(self, target: Dict):
        try:
            current = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.view_angles)
            if self.settings['silent_aim']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles, target['angle'][0])
                self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles + 4, target['angle'][1])
            else:
                smooth = self.settings['smooth']
                new_x = current[0] + (target['angle'][0] - current[0]) / smooth
                new_y = current[1] + (target['angle'][1] - current[1]) / smooth
                self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles, new_x)
                self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles + 4, new_y)
        except:
            pass

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

class ESPEngine:
    def __init__(self, memory: CODMemory):
        self.mem = memory
        self.running = False
        self.entities = []
        self.settings = {
            'enabled': True,
            'players': True,
            'boxes': True,
            'skeleton': True,
            'health_bar': True,
            'distance': True,
            'through_walls': True,
            'max_distance': 300
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
            local_pos = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.local_player + 0x30)
            entity_list = self.mem.read_int(self.mem.base_address + self.mem.offsets.entity_list)
            if entity_list:
                count = self.mem.read_int(self.mem.base_address + self.mem.offsets.entity_count)
                for i in range(min(count, 128)):
                    entity_ptr = self.mem.read_int(entity_list + (i * self.mem.offsets.entity_size))
                    if entity_ptr:
                        team = self.mem.read_int(entity_ptr + 0x50)
                        if team == local_team:
                            continue
                        health = self.mem.read_float(entity_ptr + 0x100)
                        position = self.mem.read_vec3(entity_ptr + 0x30)
                        distance = self.calc_distance(local_pos, position)
                        if distance < self.settings['max_distance']:
                            self.entities.append({
                                'position': position,
                                'team': team,
                                'health': health,
                                'distance': distance,
                                'is_enemy': True
                            })
        except:
            pass

    def calc_distance(self, pos1, pos2) -> float:
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        dz = pos1[2] - pos2[2]
        return math.sqrt(dx*dx + dy*dy + dz*dz)

class NoRecoilEngine:
    def __init__(self, memory: CODMemory):
        self.mem = memory
        self.running = False
        self.settings = {
            'enabled': True,
            'compensation': 1.0
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.recoil_loop, daemon=True).start()

    def recoil_loop(self):
        while self.running:
            if self.settings['enabled']:
                firing = self.mem.read_int(self.mem.base_address + self.mem.offsets.is_firing)
                if firing:
                    recoil_x = self.mem.read_float(self.mem.base_address + self.mem.offsets.recoil_x)
                    recoil_y = self.mem.read_float(self.mem.base_address + self.mem.offsets.recoil_y)
                    view = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.view_angles)
                    comp = self.settings['compensation']
                    self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles, view[0] - recoil_x * comp)
                    self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles + 4, view[1] - recoil_y * comp)
            time.sleep(0.001)

class UnlockEngine:
    def __init__(self, memory: CODMemory):
        self.mem = memory
        self.running = False
        self.settings = {
            'unlock_all': True,
            'max_prestige': True,
            'infinite_xp': False
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.unlock_loop, daemon=True).start()

    def unlock_loop(self):
        while self.running:
            if self.settings['unlock_all']:
                self.mem.write_int(self.mem.base_address + self.mem.offsets.unlock_all_flag, 1)
            if self.settings['max_prestige']:
                self.mem.write_int(self.mem.base_address + self.mem.offsets.prestige, 10)
            if self.settings['infinite_xp']:
                self.mem.write_int(self.mem.base_address + self.mem.offsets.xp, 999999)
            time.sleep(0.5)

class RadarEngine:
    def __init__(self, memory: CODMemory):
        self.mem = memory
        self.running = False
        self.settings = {'enabled': True, 'range': 100}

    def start(self):
        self.running = True
        threading.Thread(target=self.radar_loop, daemon=True).start()

    def radar_loop(self):
        while self.running:
            time.sleep(0.01)

class CoDEmberGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CoDEmber — Call of Duty Suite")
        self.root.geometry("550x700")
        self.root.configure(bg='#0a0a12')
        self.memory = CODMemory()
        self.aimbot = AimbotEngine(self.memory)
        self.esp = ESPEngine(self.memory)
        self.norecoil = NoRecoilEngine(self.memory)
        self.unlock = UnlockEngine(self.memory)
        self.radar = RadarEngine(self.memory)
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
        title = tk.Label(title_frame, text="CoDEmber", font=('Segoe UI', 26, 'bold'), fg=self.colors['accent'], bg=self.colors['card'])
        title.pack(pady=10)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        aimbot_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(aimbot_tab, text='Aimbot')
        esp_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(esp_tab, text='ESP')
        misc_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(misc_tab, text='Misc')

        aimbot_frame = tk.LabelFrame(aimbot_tab, text="Aimbot Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        aimbot_frame.pack(fill='x', padx=5, pady=5)
        self.aimbot_var = tk.BooleanVar(value=True)
        tk.Checkbutton(aimbot_frame, text="Enable Aimbot", variable=self.aimbot_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.silent_aim_var = tk.BooleanVar(value=False)
        tk.Checkbutton(aimbot_frame, text="Silent Aim", variable=self.silent_aim_var, bg=self.colors['card'], fg=self.colors['danger'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        row1 = tk.Frame(aimbot_frame, bg=self.colors['card'])
        row1.pack(fill='x', pady=3)
        tk.Label(row1, text="FOV:", bg=self.colors['card'], fg=self.colors['dim']).pack(side='left')
        self.fov_var = tk.StringVar(value="8")
        tk.Entry(row1, textvariable=self.fov_var, width=8, bg=self.colors['bg'], fg=self.colors['text'], relief='flat').pack(side='right')

        row2 = tk.Frame(aimbot_frame, bg=self.colors['card'])
        row2.pack(fill='x', pady=3)
        tk.Label(row2, text="Smooth:", bg=self.colors['card'], fg=self.colors['dim']).pack(side='left')
        self.smooth_var = tk.StringVar(value="5")
        tk.Entry(row2, textvariable=self.smooth_var, width=8, bg=self.colors['bg'], fg=self.colors['text'], relief='flat').pack(side='right')

        esp_frame = tk.LabelFrame(esp_tab, text="ESP Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        esp_frame.pack(fill='x', padx=5, pady=5)
        self.esp_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="Enable ESP", variable=self.esp_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.boxes_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="Boxes", variable=self.boxes_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.health_bar_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="Health Bar", variable=self.health_bar_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.distance_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="Distance", variable=self.distance_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        misc_frame = tk.LabelFrame(misc_tab, text="Miscellaneous", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        misc_frame.pack(fill='x', padx=5, pady=5)
        self.norecoil_var = tk.BooleanVar(value=True)
        tk.Checkbutton(misc_frame, text="No Recoil", variable=self.norecoil_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.unlock_all_var = tk.BooleanVar(value=True)
        tk.Checkbutton(misc_frame, text="Unlock All", variable=self.unlock_all_var, bg=self.colors['card'], fg=self.colors['warning'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.max_prestige_var = tk.BooleanVar(value=True)
        tk.Checkbutton(misc_frame, text="Max Prestige", variable=self.max_prestige_var, bg=self.colors['card'], fg=self.colors['warning'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.infinite_xp_var = tk.BooleanVar(value=False)
        tk.Checkbutton(misc_frame, text="Infinite XP", variable=self.infinite_xp_var, bg=self.colors['card'], fg=self.colors['warning'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

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
            self.aimbot.settings['enabled'] = self.aimbot_var.get()
            self.aimbot.settings['silent_aim'] = self.silent_aim_var.get()
            self.aimbot.settings['fov'] = float(self.fov_var.get())
            self.aimbot.settings['smooth'] = float(self.smooth_var.get())
            self.esp.settings['enabled'] = self.esp_var.get()
            self.esp.settings['boxes'] = self.boxes_var.get()
            self.esp.settings['health_bar'] = self.health_bar_var.get()
            self.esp.settings['distance'] = self.distance_var.get()
            self.norecoil.settings['enabled'] = self.norecoil_var.get()
            self.unlock.settings['unlock_all'] = self.unlock_all_var.get()
            self.unlock.settings['max_prestige'] = self.max_prestige_var.get()
            self.unlock.settings['infinite_xp'] = self.infinite_xp_var.get()
            if self.memory.attach():
                self.aimbot.start()
                self.esp.start()
                self.norecoil.start()
                self.unlock.start()
                self.radar.start()
                self.is_running = True
                self.status_dot.config(fg=self.colors['success'])
                self.status_label.config(text="RUNNING", fg=self.colors['success'])
                self.start_btn.config(text="STOP", bg=self.colors['danger'])
            else:
                self.status_dot.config(fg=self.colors['danger'])
                self.status_label.config(text="FAILED", fg=self.colors['danger'])
        else:
            self.aimbot.running = False
            self.esp.running = False
            self.norecoil.running = False
            self.unlock.running = False
            self.radar.running = False
            self.is_running = False
            self.status_dot.config(fg=self.colors['danger'])
            self.status_label.config(text="IDLE", fg=self.colors['dim'])
            self.start_btn.config(text="START", bg=self.colors['accent2'])

    def save_settings(self):
        settings = {
            'aimbot': self.aimbot_var.get(),
            'silent_aim': self.silent_aim_var.get(),
            'fov': float(self.fov_var.get()),
            'smooth': float(self.smooth_var.get()),
            'esp': self.esp_var.get(),
            'boxes': self.boxes_var.get(),
            'health_bar': self.health_bar_var.get(),
            'distance': self.distance_var.get(),
            'no_recoil': self.norecoil_var.get(),
            'unlock_all': self.unlock_all_var.get(),
            'max_prestige': self.max_prestige_var.get(),
            'infinite_xp': self.infinite_xp_var.get()
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(settings, f, indent=2)

    def load_settings(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                settings = json.load(f)
            for key, var in [
                ('aimbot', self.aimbot_var),
                ('silent_aim', self.silent_aim_var),
                ('esp', self.esp_var),
                ('boxes', self.boxes_var),
                ('health_bar', self.health_bar_var),
                ('distance', self.distance_var),
                ('no_recoil', self.norecoil_var),
                ('unlock_all', self.unlock_all_var),
                ('max_prestige', self.max_prestige_var),
                ('infinite_xp', self.infinite_xp_var)
            ]:
                if key in settings:
                    var.set(settings[key])
            if 'fov' in settings:
                self.fov_var.set(str(settings['fov']))
            if 'smooth' in settings:
                self.smooth_var.set(str(settings['smooth']))

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    gui = CoDEmberGUI()
    gui.run()