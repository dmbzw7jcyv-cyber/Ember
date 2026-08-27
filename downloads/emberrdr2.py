#!/usr/bin/env python3
# EmberRDR2 — Red Dead Redemption 2 Suite
# ESP, Aimbot, No Recoil, Infinite Health/Stamina/Dead Eye, Teleport, Spawner

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
CONFIG_PATH = Path.home() / '.emberrdr2_config.json'
OFFSET_DB_PATH = Path.home() / '.emberrdr2_offsets.json'

RDR2_PROCESSES = [
    "RDR2.exe",
    "PlayRDR2.exe"
]

@dataclass
class RDR2Offsets:
    local_player: int = 0x0
    player_health: int = 0x0
    player_stamina: int = 0x0
    player_dead_eye: int = 0x0
    player_position: int = 0x0
    player_heading: int = 0x0
    player_money: int = 0x0
    player_wanted_level: int = 0x0
    player_horse_health: int = 0x0
    player_horse_stamina: int = 0x0
    entity_list: int = 0x0
    entity_count: int = 0x0
    entity_size: int = 0x0
    view_matrix: int = 0x0
    view_angles: int = 0x0
    recoil_x: int = 0x0
    recoil_y: int = 0x0
    is_firing: int = 0x0
    game_state: int = 0x0
    weather: int = 0x0
    time_of_day: int = 0x0

    def to_dict(self) -> Dict[str, str]:
        return {k: hex(v) for k, v in self.__dict__.items()}

    def from_dict(self, data: Dict[str, str]):
        for k, v in data.items():
            if hasattr(self, k):
                setattr(self, k, int(v, 16))

class RDR2Memory:
    def __init__(self):
        self.pm = None
        self.process_name = None
        self.base_address = None
        self.module_size = 0
        self.is_attached = False
        self.offsets = RDR2Offsets()
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
                if proc.info['name'] in RDR2_PROCESSES:
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

    def read_long(self, address: int) -> int:
        try:
            return self.pm.read_longlong(address)
        except:
            return 0

    def write_long(self, address: int, value: int) -> bool:
        try:
            self.pm.write_longlong(address, value)
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

class ESPEngine:
    def __init__(self, memory: RDR2Memory):
        self.mem = memory
        self.running = False
        self.entities = []
        self.settings = {
            'esp_players': True,
            'esp_npcs': True,
            'esp_animals': True,
            'esp_horses': True,
            'esp_distance': 500,
            'draw_boxes': True,
            'draw_health': True,
            'draw_distance': True,
            'draw_names': True
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
            entity_list = self.mem.read_long(self.mem.base_address + self.mem.offsets.entity_list)
            if entity_list:
                count = self.mem.read_int(entity_list + 0x10)
                for i in range(min(count, 256)):
                    entity_ptr = self.mem.read_long(entity_list + 0x20 + (i * 0x8))
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
    def __init__(self, memory: RDR2Memory):
        self.mem = memory
        self.running = False
        self.settings = {
            'aimbot_enabled': True,
            'aimbot_fov': 10,
            'aimbot_smooth': 5,
            'aimbot_bone': 'head',
            'anti_recoil': True,
            'recoil_compensation': 1.0,
            'no_spread': True,
            'triggerbot': False,
            'silent_aim': False
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
        threading.Thread(target=self.triggerbot_loop, daemon=True).start()

    def aimbot_loop(self):
        while self.running:
            if self.settings['aimbot_enabled']:
                if keyboard.is_pressed('right'):
                    target = self.find_target()
                    if target:
                        self.aim_at_target(target)
            time.sleep(0.001)

    def find_target(self) -> Optional[Dict]:
        try:
            local_pos = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.player_position)
            view_angles = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.view_angles)
            entity_list = self.mem.read_long(self.mem.base_address + self.mem.offsets.entity_list)
            if not entity_list:
                return None
            count = self.mem.read_int(entity_list + 0x10)
            best_target = None
            best_fov = self.settings['aimbot_fov']
            for i in range(min(count, 256)):
                entity_ptr = self.mem.read_long(entity_list + 0x20 + (i * 0x8))
                if entity_ptr:
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
            if self.settings['silent_aim']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles, target['angle'][0])
                self.mem.write_float(self.mem.base_address + self.mem.offsets.view_angles + 4, target['angle'][1])
            else:
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
                self.mem.write_float(self.mem.base_address + self.mem.offsets.recoil_x, 0.0)
                self.mem.write_float(self.mem.base_address + self.mem.offsets.recoil_y, 0.0)
            time.sleep(0.001)

    def triggerbot_loop(self):
        while self.running:
            if self.settings['triggerbot']:
                if keyboard.is_pressed('right'):
                    mouse.click('left')
                    time.sleep(0.05)
            time.sleep(0.01)

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

class PlayerEngine:
    def __init__(self, memory: RDR2Memory):
        self.mem = memory
        self.running = False
        self.settings = {
            'infinite_health': True,
            'infinite_stamina': True,
            'infinite_dead_eye': True,
            'infinite_horse_health': True,
            'infinite_horse_stamina': True,
            'no_wanted_level': True,
            'god_mode': False,
            'super_speed': False,
            'speed_multiplier': 2.0
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.health_loop, daemon=True).start()
        threading.Thread(target=self.stamina_loop, daemon=True).start()
        threading.Thread(target=self.dead_eye_loop, daemon=True).start()
        threading.Thread(target=self.wanted_loop, daemon=True).start()

    def health_loop(self):
        while self.running:
            if self.settings['infinite_health']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.player_health, 100.0)
            if self.settings['infinite_horse_health']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.player_horse_health, 100.0)
            time.sleep(0.01)

    def stamina_loop(self):
        while self.running:
            if self.settings['infinite_stamina']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.player_stamina, 100.0)
            if self.settings['infinite_horse_stamina']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.player_horse_stamina, 100.0)
            time.sleep(0.01)

    def dead_eye_loop(self):
        while self.running:
            if self.settings['infinite_dead_eye']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.player_dead_eye, 100.0)
            time.sleep(0.01)

    def wanted_loop(self):
        while self.running:
            if self.settings['no_wanted_level']:
                self.mem.write_int(self.mem.base_address + self.mem.offsets.player_wanted_level, 0)
            time.sleep(0.1)

class MoneyEngine:
    def __init__(self, memory: RDR2Memory):
        self.mem = memory
        self.running = False
        self.settings = {
            'infinite_money': False,
            'money_amount': 999999
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.money_loop, daemon=True).start()

    def money_loop(self):
        while self.running:
            if self.settings['infinite_money']:
                self.mem.write_long(self.mem.base_address + self.mem.offsets.player_money, self.settings['money_amount'])
            time.sleep(0.5)

class TeleportEngine:
    def __init__(self, memory: RDR2Memory):
        self.mem = memory
        self.running = False
        self.waypoints = []
        self.settings = {
            'teleport_enabled': True
        }

    def start(self):
        self.running = True

    def save_waypoint(self, name: str):
        pos = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.player_position)
        self.waypoints.append({'name': name, 'position': pos})

    def teleport_to_waypoint(self, index: int):
        if 0 <= index < len(self.waypoints):
            pos = self.waypoints[index]['position']
            self.mem.write_vec3(self.mem.base_address + self.mem.offsets.player_position, pos)

    def teleport_to_coords(self, x: float, y: float, z: float):
        self.mem.write_vec3(self.mem.base_address + self.mem.offsets.player_position, (x, y, z))

class WeatherEngine:
    def __init__(self, memory: RDR2Memory):
        self.mem = memory
        self.running = False
        self.settings = {
            'weather_control': False,
            'weather_type': 0,
            'time_control': False,
            'time_hour': 12
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.weather_loop, daemon=True).start()

    def weather_loop(self):
        while self.running:
            if self.settings['weather_control']:
                self.mem.write_int(self.mem.base_address + self.mem.offsets.weather, self.settings['weather_type'])
            if self.settings['time_control']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.time_of_day, float(self.settings['time_hour']))
            time.sleep(0.1)

class EmberRDR2GUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("EmberRDR2 — Red Dead Redemption 2 Suite")
        self.root.geometry("600x750")
        self.root.configure(bg='#0a0a12')
        self.memory = RDR2Memory()
        self.esp = ESPEngine(self.memory)
        self.combat = CombatEngine(self.memory)
        self.player = PlayerEngine(self.memory)
        self.money = MoneyEngine(self.memory)
        self.teleport = TeleportEngine(self.memory)
        self.weather = WeatherEngine(self.memory)
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
        title = tk.Label(title_frame, text="EmberRDR2", font=('Segoe UI', 26, 'bold'), fg=self.colors['accent'], bg=self.colors['card'])
        title.pack(pady=10)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        esp_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(esp_tab, text='ESP')
        combat_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(combat_tab, text='Combat')
        player_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(player_tab, text='Player')
        world_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(world_tab, text='World')

        esp_frame = tk.LabelFrame(esp_tab, text="ESP Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        esp_frame.pack(fill='x', padx=5, pady=5)
        self.esp_players_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="Player ESP", variable=self.esp_players_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.esp_npcs_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="NPC ESP", variable=self.esp_npcs_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.esp_animals_var = tk.BooleanVar(value=True)
        tk.Checkbutton(esp_frame, text="Animal ESP", variable=self.esp_animals_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        combat_frame = tk.LabelFrame(combat_tab, text="Combat Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        combat_frame.pack(fill='x', padx=5, pady=5)
        self.aimbot_var = tk.BooleanVar(value=True)
        tk.Checkbutton(combat_frame, text="Aimbot", variable=self.aimbot_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.antirecoil_var = tk.BooleanVar(value=True)
        tk.Checkbutton(combat_frame, text="Anti-Recoil", variable=self.antirecoil_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.nospread_var = tk.BooleanVar(value=True)
        tk.Checkbutton(combat_frame, text="No Spread", variable=self.nospread_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.triggerbot_var = tk.BooleanVar(value=False)
        tk.Checkbutton(combat_frame, text="Triggerbot", variable=self.triggerbot_var, bg=self.colors['card'], fg=self.colors['warning'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        player_frame = tk.LabelFrame(player_tab, text="Player Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        player_frame.pack(fill='x', padx=5, pady=5)
        self.inf_health_var = tk.BooleanVar(value=True)
        tk.Checkbutton(player_frame, text="Infinite Health", variable=self.inf_health_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.inf_stamina_var = tk.BooleanVar(value=True)
        tk.Checkbutton(player_frame, text="Infinite Stamina", variable=self.inf_stamina_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.inf_dead_eye_var = tk.BooleanVar(value=True)
        tk.Checkbutton(player_frame, text="Infinite Dead Eye", variable=self.inf_dead_eye_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.no_wanted_var = tk.BooleanVar(value=True)
        tk.Checkbutton(player_frame, text="No Wanted Level", variable=self.no_wanted_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.god_mode_var = tk.BooleanVar(value=False)
        tk.Checkbutton(player_frame, text="God Mode", variable=self.god_mode_var, bg=self.colors['card'], fg=self.colors['warning'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        world_frame = tk.LabelFrame(world_tab, text="World Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        world_frame.pack(fill='x', padx=5, pady=5)
        self.weather_control_var = tk.BooleanVar(value=False)
        tk.Checkbutton(world_frame, text="Weather Control", variable=self.weather_control_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.time_control_var = tk.BooleanVar(value=False)
        tk.Checkbutton(world_frame, text="Time Control", variable=self.time_control_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

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
            self.esp.settings['esp_npcs'] = self.esp_npcs_var.get()
            self.esp.settings['esp_animals'] = self.esp_animals_var.get()
            self.combat.settings['aimbot_enabled'] = self.aimbot_var.get()
            self.combat.settings['anti_recoil'] = self.antirecoil_var.get()
            self.combat.settings['no_spread'] = self.nospread_var.get()
            self.combat.settings['triggerbot'] = self.triggerbot_var.get()
            self.player.settings['infinite_health'] = self.inf_health_var.get()
            self.player.settings['infinite_stamina'] = self.inf_stamina_var.get()
            self.player.settings['infinite_dead_eye'] = self.inf_dead_eye_var.get()
            self.player.settings['no_wanted_level'] = self.no_wanted_var.get()
            self.player.settings['god_mode'] = self.god_mode_var.get()
            self.weather.settings['weather_control'] = self.weather_control_var.get()
            self.weather.settings['time_control'] = self.time_control_var.get()
            if self.memory.attach():
                self.esp.start()
                self.combat.start()
                self.player.start()
                self.money.start()
                self.weather.start()
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
            self.player.running = False
            self.money.running = False
            self.weather.running = False
            self.is_running = False
            self.status_dot.config(fg=self.colors['danger'])
            self.status_label.config(text="IDLE", fg=self.colors['dim'])
            self.start_btn.config(text="START", bg=self.colors['accent2'])

    def save_settings(self):
        settings = {
            'esp_players': self.esp_players_var.get(),
            'esp_npcs': self.esp_npcs_var.get(),
            'esp_animals': self.esp_animals_var.get(),
            'aimbot': self.aimbot_var.get(),
            'anti_recoil': self.antirecoil_var.get(),
            'no_spread': self.nospread_var.get(),
            'triggerbot': self.triggerbot_var.get(),
            'infinite_health': self.inf_health_var.get(),
            'infinite_stamina': self.inf_stamina_var.get(),
            'infinite_dead_eye': self.inf_dead_eye_var.get(),
            'no_wanted_level': self.no_wanted_var.get(),
            'god_mode': self.god_mode_var.get(),
            'weather_control': self.weather_control_var.get(),
            'time_control': self.time_control_var.get()
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(settings, f, indent=2)

    def load_settings(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                settings = json.load(f)
            for key, var in [
                ('esp_players', self.esp_players_var),
                ('esp_npcs', self.esp_npcs_var),
                ('esp_animals', self.esp_animals_var),
                ('aimbot', self.aimbot_var),
                ('anti_recoil', self.antirecoil_var),
                ('no_spread', self.nospread_var),
                ('triggerbot', self.triggerbot_var),
                ('infinite_health', self.inf_health_var),
                ('infinite_stamina', self.inf_stamina_var),
                ('infinite_dead_eye', self.inf_dead_eye_var),
                ('no_wanted_level', self.no_wanted_var),
                ('god_mode', self.god_mode_var),
                ('weather_control', self.weather_control_var),
                ('time_control', self.time_control_var)
            ]:
                if key in settings:
                    var.set(settings[key])

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    gui = EmberRDR2GUI()
    gui.run()