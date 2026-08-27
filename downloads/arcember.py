#!/usr/bin/env python3
# ArcEmber — Arc Raiders Full Suite
# ESP, Aimbot, Anti-Recoil, Stamina, Health, Looting, Movement

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
CONFIG_PATH = Path.home() / '.arcember_config.json'
OFFSET_DB_PATH = Path.home() / '.arcember_offsets.json'

ARC_PROCESSES = [
    "ArcRaiders.exe",
    "ArcRaiders-Win64-Shipping.exe",
    "arc_raiders.exe"
]

ANTICHEAT_PROCESSES = [
    "EAC.exe",
    "EasyAntiCheat.exe",
    "BEService.exe",
    "BattlEye.exe"
]

@dataclass
class GameOffsets:
    entity_list: int = 0x0
    entity_count: int = 0x0
    entity_size: int = 0x0
    local_player: int = 0x0
    player_position: int = 0x0
    player_health: int = 0x0
    player_stamina: int = 0x0
    view_angles: int = 0x0
    view_matrix: int = 0x0
    recoil_x: int = 0x0
    recoil_y: int = 0x0
    is_firing: int = 0x0
    loot_time: int = 0x0
    loot_radius: int = 0x0
    game_state: int = 0x0

    def to_dict(self) -> Dict[str, str]:
        return {k: hex(v) for k, v in self.__dict__.items()}

    def from_dict(self, data: Dict[str, str]):
        for k, v in data.items():
            if hasattr(self, k):
                setattr(self, k, int(v, 16))

class ArcMemory:
    def __init__(self):
        self.pm = None
        self.process_name = None
        self.base_address = None
        self.module_size = 0
        self.is_attached = False
        self.offsets = GameOffsets()
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
                if proc.info['name'] in ARC_PROCESSES:
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

class ESPEngine:
    def __init__(self, memory: ArcMemory):
        self.mem = memory
        self.running = False
        self.entities = []
        self.settings = {
            'esp_players': True,
            'esp_loot': True,
            'esp_distance': 500,
            'draw_boxes': True,
            'draw_health': True,
            'draw_distance': True
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.scan_loop, daemon=True).start()

    def scan_loop(self):
        while self.running:
            self.scan_entities()
            time.sleep(0.01)

    def scan_entities(self):
        self.entities = []
        try:
            entity_list = self.mem.read_int(self.mem.base_address + self.mem.offsets.entity_list)
            if entity_list:
                count = self.mem.read_int(entity_list + 0x10)
                for i in range(min(count, 256)):
                    entity_ptr = self.mem.read_int(entity_list + 0x20 + (i * 0x8))
                    if entity_ptr:
                        entity_type = self.mem.read_int(entity_ptr + 0x8)
                        position = self.mem.read_vec3(entity_ptr + 0x30)
                        health = self.mem.read_float(entity_ptr + 0x100)
                        self.entities.append({
                            'type': entity_type,
                            'position': position,
                            'health': health,
                            'pointer': entity_ptr
                        })
        except:
            pass

class CombatEngine:
    def __init__(self, memory: ArcMemory):
        self.mem = memory
        self.running = False
        self.settings = {
            'aimbot_enabled': True,
            'aimbot_fov': 10,
            'aimbot_smooth': 5,
            'anti_recoil': True,
            'recoil_compensation': 1.0
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.aimbot_loop, daemon=True).start()
        threading.Thread(target=self.recoil_loop, daemon=True).start()

    def aimbot_loop(self):
        while self.running:
            if self.settings['aimbot_enabled']:
                target = self.find_target()
                if target:
                    self.aim_at_target(target)
            time.sleep(0.001)

    def find_target(self) -> Optional[Dict]:
        try:
            local_pos = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.player_position)
            view_angles = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.view_angles)
            entity_list = self.mem.read_int(self.mem.base_address + self.mem.offsets.entity_list)
            if not entity_list:
                return None
            count = self.mem.read_int(entity_list + 0x10)
            best_target = None
            best_fov = self.settings['aimbot_fov']
            for i in range(min(count, 256)):
                entity_ptr = self.mem.read_int(entity_list + 0x20 + (i * 0x8))
                if entity_ptr:
                    entity_pos = self.mem.read_vec3(entity_ptr + 0x30)
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

class MovementEngine:
    def __init__(self, memory: ArcMemory):
        self.mem = memory
        self.running = False
        self.settings = {
            'infinite_stamina': True,
            'infinite_health': True,
            'fast_loot': True,
            'large_loot_area': True,
            'loot_radius': 100,
            'flying': False,
            'fly_speed': 2.0,
            'god_mode': False
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.stamina_loop, daemon=True).start()
        threading.Thread(target=self.health_loop, daemon=True).start()
        threading.Thread(target=self.loot_loop, daemon=True).start()
        threading.Thread(target=self.fly_loop, daemon=True).start()

    def stamina_loop(self):
        while self.running:
            if self.settings['infinite_stamina']:
                addr = self.mem.base_address + self.mem.offsets.player_stamina
                self.mem.write_float(addr, 100.0)
            time.sleep(0.01)

    def health_loop(self):
        while self.running:
            if self.settings['infinite_health']:
                addr = self.mem.base_address + self.mem.offsets.player_health
                self.mem.write_float(addr, 100.0)
            time.sleep(0.01)

    def loot_loop(self):
        while self.running:
            if self.settings['fast_loot']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.loot_time, 0.0)
            if self.settings['large_loot_area']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.loot_radius, float(self.settings['loot_radius']))
            time.sleep(0.01)

    def fly_loop(self):
        while self.running:
            if self.settings['flying']:
                pos = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.player_position)
                if keyboard.is_pressed('space'):
                    self.mem.write_float(self.mem.base_address + self.mem.offsets.player_position + 8, pos[2] + self.settings['fly_speed'])
                elif keyboard.is_pressed('ctrl'):
                    self.mem.write_float(self.mem.base_address + self.mem.offsets.player_position + 8, pos[2] - self.settings['fly_speed'])
            time.sleep(0.01)

class ArcEmberGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ArcEmber — Arc Raiders Suite")
        self.root.geometry("550x700")
        self.root.configure(bg='#0a0a12')
        self.memory = ArcMemory()
        self.esp = ESPEngine(self.memory)
        self.combat = CombatEngine(self.memory)
        self.movement = MovementEngine(self.memory)
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
        title = tk.Label(title_frame, text="ArcEmber", font=('Segoe UI', 26, 'bold'), fg=self.colors['accent'], bg=self.colors['card'])
        title.pack(pady=10)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        esp_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(esp_tab, text='ESP')
        combat_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(combat_tab, text='Combat')
        move_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(move_tab, text='Movement')

        esp_frame = tk.LabelFrame(esp_tab, text="ESP Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        esp_frame.pack(fill='x', padx=5, pady=5)
        self.esp_players_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="Player ESP", variable=self.esp_players_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.esp_loot_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="Loot ESP", variable=self.esp_loot_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        combat_frame = tk.LabelFrame(combat_tab, text="Combat Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        combat_frame.pack(fill='x', padx=5, pady=5)
        self.aimbot_var = tk.BooleanVar(value=True)
        tk.Checkbutton(combat_frame, text="Aimbot", variable=self.aimbot_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.antirecoil_var = tk.BooleanVar(value=True)
        tk.Checkbutton(combat_frame, text="Anti-Recoil", variable=self.antirecoil_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        move_frame = tk.LabelFrame(move_tab, text="Movement Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        move_frame.pack(fill='x', padx=5, pady=5)
        self.stamina_var = tk.BooleanVar(value=True)
        tk.Checkbutton(move_frame, text="Infinite Stamina", variable=self.stamina_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.health_var = tk.BooleanVar(value=True)
        tk.Checkbutton(move_frame, text="Infinite Health", variable=self.health_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.fast_loot_var = tk.BooleanVar(value=True)
        tk.Checkbutton(move_frame, text="Fast Loot", variable=self.fast_loot_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.large_loot_var = tk.BooleanVar(value=True)
        tk.Checkbutton(move_frame, text="Large Loot Area", variable=self.large_loot_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.fly_var = tk.BooleanVar(value=False)
        tk.Checkbutton(move_frame, text="Flying", variable=self.fly_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.god_var = tk.BooleanVar(value=False)
        tk.Checkbutton(move_frame, text="God Mode", variable=self.god_var, bg=self.colors['card'], fg=self.colors['warning'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

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
            self.esp.settings['esp_players'] = self.esp_players_var.get()
            self.esp.settings['esp_loot'] = self.esp_loot_var.get()
            self.combat.settings['aimbot_enabled'] = self.aimbot_var.get()
            self.combat.settings['anti_recoil'] = self.antirecoil_var.get()
            self.movement.settings['infinite_stamina'] = self.stamina_var.get()
            self.movement.settings['infinite_health'] = self.health_var.get()
            self.movement.settings['fast_loot'] = self.fast_loot_var.get()
            self.movement.settings['large_loot_area'] = self.large_loot_var.get()
            self.movement.settings['flying'] = self.fly_var.get()
            self.movement.settings['god_mode'] = self.god_var.get()
            if self.memory.attach():
                self.esp.start()
                self.combat.start()
                self.movement.start()
                self.is_running = True
                self.status_dot.config(fg=self.colors['success'])
                self.status_label.config(text="RUNNING", fg=self.colors['success'])
                self.start_btn.config(text="STOP", bg=self.colors['danger'])
            else:
                self.status_dot.config(fg=self.colors['danger'])
                self.status_label.config(text="FAILED", fg=self.colors['danger'])
        else:
            self.esp.running = False
            self.combat.running = False
            self.movement.running = False
            self.is_running = False
            self.status_dot.config(fg=self.colors['danger'])
            self.status_label.config(text="IDLE", fg=self.colors['dim'])
            self.start_btn.config(text="START", bg=self.colors['accent2'])

    def save_settings(self):
        settings = {
            'esp_players': self.esp_players_var.get(),
            'esp_loot': self.esp_loot_var.get(),
            'aimbot': self.aimbot_var.get(),
            'anti_recoil': self.antirecoil_var.get(),
            'infinite_stamina': self.stamina_var.get(),
            'infinite_health': self.health_var.get(),
            'fast_loot': self.fast_loot_var.get(),
            'large_loot_area': self.large_loot_var.get(),
            'flying': self.fly_var.get(),
            'god_mode': self.god_var.get()
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(settings, f, indent=2)

    def load_settings(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                settings = json.load(f)
            for key, var in [
                ('esp_players', self.esp_players_var),
                ('esp_loot', self.esp_loot_var),
                ('aimbot', self.aimbot_var),
                ('anti_recoil', self.antirecoil_var),
                ('infinite_stamina', self.stamina_var),
                ('infinite_health', self.health_var),
                ('fast_loot', self.fast_loot_var),
                ('large_loot_area', self.large_loot_var),
                ('flying', self.fly_var),
                ('god_mode', self.god_var)
            ]:
                if key in settings:
                    var.set(settings[key])

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    gui = ArcEmberGUI()
    gui.run()