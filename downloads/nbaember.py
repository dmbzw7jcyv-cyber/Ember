#!/usr/bin/env python3
# NBAEmber — NBA 2K Suite
# Auto-green shots, defensive assists, stamina mods, stats boost

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
CONFIG_PATH = Path.home() / '.nbaember_config.json'
OFFSET_DB_PATH = Path.home() / '.nbaember_offsets.json'

NBA_PROCESSES = [
    "NBA2K26.exe",
    "NBA2K25.exe",
    "NBA2K24.exe",
    "nba2k.exe"
]

@dataclass
class NBAOffsets:
    local_player: int = 0x0
    player_energy: int = 0x0
    player_takeover: int = 0x0
    player_position: int = 0x0
    shot_meter_active: int = 0x0
    shot_meter_position: int = 0x0
    shot_meter_green_zone: int = 0x0
    shot_clock: int = 0x0
    game_clock: int = 0x0
    game_state: int = 0x0
    ball_position: int = 0x0

    def to_dict(self) -> Dict[str, str]:
        return {k: hex(v) for k, v in self.__dict__.items()}

    def from_dict(self, data: Dict[str, str]):
        for k, v in data.items():
            if hasattr(self, k):
                setattr(self, k, int(v, 16))

class NBAMemory:
    def __init__(self):
        self.pm = None
        self.process_name = None
        self.base_address = None
        self.module_size = 0
        self.is_attached = False
        self.offsets = NBAOffsets()
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
                if proc.info['name'] in NBA_PROCESSES:
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

class ShotEngine:
    def __init__(self, memory: NBAMemory):
        self.mem = memory
        self.running = False
        self.shot_history = deque(maxlen=50)
        self.green_percentage = 0.0
        self.settings = {
            'auto_green': True,
            'perfect_release': True,
            'shot_timing_ms': 0,
            'green_tolerance': 0.02,
            'auto_shot': False
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.shot_loop, daemon=True).start()
        threading.Thread(target=self.auto_shot_loop, daemon=True).start()

    def shot_loop(self):
        while self.running:
            if self.settings['auto_green']:
                meter_active = self.mem.read_int(self.mem.base_address + self.mem.offsets.shot_meter_active)
                if meter_active == 1:
                    position = self.mem.read_float(self.mem.base_address + self.mem.offsets.shot_meter_position)
                    green_zone = self.mem.read_float(self.mem.base_address + self.mem.offsets.shot_meter_green_zone)
                    if self.is_in_green(position, green_zone):
                        if self.settings['shot_timing_ms'] > 0:
                            time.sleep(self.settings['shot_timing_ms'] / 1000)
                        keyboard.release('space')
                        mouse.release('left')
                        self.shot_history.append({'perfect': True})
                        self.update_green_percentage()
            time.sleep(0.001)

    def auto_shot_loop(self):
        while self.running:
            if self.settings['auto_shot']:
                game_state = self.mem.read_int(self.mem.base_address + self.mem.offsets.game_state)
                if game_state == 2:
                    shot_clock = self.mem.read_float(self.mem.base_address + self.mem.offsets.shot_clock)
                    if shot_clock < 5:
                        keyboard.release('space')
                        mouse.release('left')
            time.sleep(0.01)

    def is_in_green(self, position, green_zone) -> bool:
        tolerance = self.settings['green_tolerance']
        return (green_zone - tolerance) <= position <= (green_zone + tolerance)

    def update_green_percentage(self):
        if self.shot_history:
            perfect = sum(1 for s in self.shot_history if s['perfect'])
            self.green_percentage = perfect / len(self.shot_history)

class DefenseEngine:
    def __init__(self, memory: NBAMemory):
        self.mem = memory
        self.running = False
        self.settings = {
            'auto_steal': True,
            'auto_block': True,
            'auto_rebound': True,
            'steal_timing_ms': 50,
            'block_timing_ms': 100,
            'rebound_distance': 5
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.steal_loop, daemon=True).start()
        threading.Thread(target=self.block_loop, daemon=True).start()
        threading.Thread(target=self.rebound_loop, daemon=True).start()

    def steal_loop(self):
        while self.running:
            if self.settings['auto_steal']:
                game_state = self.mem.read_int(self.mem.base_address + self.mem.offsets.game_state)
                if game_state == 3:
                    time.sleep(self.settings['steal_timing_ms'] / 1000)
                    keyboard.press_and_release('s')
            time.sleep(0.01)

    def block_loop(self):
        while self.running:
            if self.settings['auto_block']:
                shot_active = self.mem.read_int(self.mem.base_address + self.mem.offsets.shot_meter_active)
                if shot_active == 1:
                    time.sleep(self.settings['block_timing_ms'] / 1000)
                    keyboard.press_and_release('b')
            time.sleep(0.01)

    def rebound_loop(self):
        while self.running:
            if self.settings['auto_rebound']:
                ball_pos = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.ball_position)
                player_pos = self.mem.read_vec3(self.mem.base_address + self.mem.offsets.player_position)
                distance = self.calc_distance(player_pos, ball_pos)
                if distance < self.settings['rebound_distance']:
                    keyboard.press_and_release('r')
            time.sleep(0.01)

    def calc_distance(self, pos1, pos2) -> float:
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        dz = pos1[2] - pos2[2]
        return math.sqrt(dx*dx + dy*dy + dz*dz)

class StaminaEngine:
    def __init__(self, memory: NBAMemory):
        self.mem = memory
        self.running = False
        self.settings = {
            'infinite_energy': True,
            'energy_level': 100,
            'infinite_takeover': True,
            'takeover_level': 100,
            'no_fatigue': True
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.energy_loop, daemon=True).start()
        threading.Thread(target=self.takeover_loop, daemon=True).start()

    def energy_loop(self):
        while self.running:
            if self.settings['infinite_energy']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.player_energy, float(self.settings['energy_level']))
            time.sleep(0.01)

    def takeover_loop(self):
        while self.running:
            if self.settings['infinite_takeover']:
                self.mem.write_float(self.mem.base_address + self.mem.offsets.player_takeover, float(self.settings['takeover_level']))
            time.sleep(0.01)

class StatsEngine:
    def __init__(self, memory: NBAMemory):
        self.mem = memory
        self.running = False
        self.settings = {
            'boost_stats': True,
            'three_point': 99,
            'mid_range': 99,
            'dunk': 99,
            'speed': 99,
            'ball_handle': 99
        }

    def start(self):
        self.running = True
        threading.Thread(target=self.stats_loop, daemon=True).start()

    def stats_loop(self):
        while self.running:
            if self.settings['boost_stats']:
                for stat_name, value in self.settings.items():
                    if stat_name != 'boost_stats':
                        stat_offset = getattr(self.mem.offsets, stat_name, 0x0)
                        if stat_offset:
                            self.mem.write_int(self.mem.base_address + stat_offset, value)
            time.sleep(0.05)

class NBAEmberGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("NBAEmber — NBA 2K Suite")
        self.root.geometry("550x700")
        self.root.configure(bg='#0a0a12')
        self.memory = NBAMemory()
        self.shot_engine = ShotEngine(self.memory)
        self.defense_engine = DefenseEngine(self.memory)
        self.stamina_engine = StaminaEngine(self.memory)
        self.stats_engine = StatsEngine(self.memory)
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
        title = tk.Label(title_frame, text="NBAEmber", font=('Segoe UI', 26, 'bold'), fg=self.colors['accent'], bg=self.colors['card'])
        title.pack(pady=10)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        shot_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(shot_tab, text='Shooting')
        defense_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(defense_tab, text='Defense')
        stamina_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(stamina_tab, text='Stamina')
        stats_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(stats_tab, text='Stats')

        shot_frame = tk.LabelFrame(shot_tab, text="Shot Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        shot_frame.pack(fill='x', padx=5, pady=5)
        self.auto_green_var = tk.BooleanVar(value=True)
        tk.Checkbutton(shot_frame, text="Auto-Green Shots", variable=self.auto_green_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.auto_shot_var = tk.BooleanVar(value=False)
        tk.Checkbutton(shot_frame, text="Auto Shot", variable=self.auto_shot_var, bg=self.colors['card'], fg=self.colors['warning'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        row1 = tk.Frame(shot_frame, bg=self.colors['card'])
        row1.pack(fill='x', pady=3)
        tk.Label(row1, text="Shot Timing (ms):", bg=self.colors['card'], fg=self.colors['dim']).pack(side='left')
        self.shot_timing_var = tk.StringVar(value="0")
        tk.Entry(row1, textvariable=self.shot_timing_var, width=8, bg=self.colors['bg'], fg=self.colors['text'], relief='flat').pack(side='right')

        defense_frame = tk.LabelFrame(defense_tab, text="Defense Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        defense_frame.pack(fill='x', padx=5, pady=5)
        self.auto_steal_var = tk.BooleanVar(value=True)
        tk.Checkbutton(defense_frame, text="Auto Steal", variable=self.auto_steal_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.auto_block_var = tk.BooleanVar(value=True)
        tk.Checkbutton(defense_frame, text="Auto Block", variable=self.auto_block_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.auto_rebound_var = tk.BooleanVar(value=True)
        tk.Checkbutton(defense_frame, text="Auto Rebound", variable=self.auto_rebound_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        stamina_frame = tk.LabelFrame(stamina_tab, text="Stamina Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        stamina_frame.pack(fill='x', padx=5, pady=5)
        self.inf_energy_var = tk.BooleanVar(value=True)
        tk.Checkbutton(stamina_frame, text="Infinite Energy", variable=self.inf_energy_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)
        self.inf_takeover_var = tk.BooleanVar(value=True)
        tk.Checkbutton(stamina_frame, text="Infinite Takeover", variable=self.inf_takeover_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        stats_frame = tk.LabelFrame(stats_tab, text="Stats Boost", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        stats_frame.pack(fill='x', padx=5, pady=5)
        self.boost_stats_var = tk.BooleanVar(value=True)
        tk.Checkbutton(stats_frame, text="Boost All Stats", variable=self.boost_stats_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        status_frame = tk.Frame(self.root, bg=self.colors['card'], height=45)
        status_frame.pack(fill='x', padx=10, pady=(0,5))
        status_frame.pack_propagate(False)
        self.status_dot = tk.Label(status_frame, text="●", font=('Segoe UI', 14), fg=self.colors['danger'], bg=self.colors['card'])
        self.status_dot.pack(side='left', padx=(15,8))
        self.status_label = tk.Label(status_frame, text="IDLE", font=('Segoe UI', 11, 'bold'), fg=self.colors['dim'], bg=self.colors['card'])
        self.status_label.pack(side='left')

        self.green_label = tk.Label(status_frame, text="0% green", font=('Segoe UI', 9), fg=self.colors['success'], bg=self.colors['card'])
        self.green_label.pack(side='right', padx=15)

        btn_frame = tk.Frame(self.root, bg=self.colors['bg'])
        btn_frame.pack(fill='x', padx=10, pady=10)
        self.start_btn = tk.Button(btn_frame, text="START", font=('Segoe UI', 13, 'bold'), bg=self.colors['accent2'], fg='white', relief='flat', padx=20, pady=10, command=self.toggle_engine)
        self.start_btn.pack(side='left', padx=5, expand=True, fill='x')
        tk.Button(btn_frame, text="SAVE", font=('Segoe UI', 11, 'bold'), bg='#ff6f00', fg='white', relief='flat', padx=12, pady=10, command=self.save_settings).pack(side='left', padx=5)

        self.update_status()

    def toggle_engine(self):
        if not self.is_running:
            self.shot_engine.settings['auto_green'] = self.auto_green_var.get()
            self.shot_engine.settings['auto_shot'] = self.auto_shot_var.get()
            self.shot_engine.settings['shot_timing_ms'] = int(self.shot_timing_var.get())
            self.defense_engine.settings['auto_steal'] = self.auto_steal_var.get()
            self.defense_engine.settings['auto_block'] = self.auto_block_var.get()
            self.defense_engine.settings['auto_rebound'] = self.auto_rebound_var.get()
            self.stamina_engine.settings['infinite_energy'] = self.inf_energy_var.get()
            self.stamina_engine.settings['infinite_takeover'] = self.inf_takeover_var.get()
            self.stats_engine.settings['boost_stats'] = self.boost_stats_var.get()
            if self.memory.attach():
                self.shot_engine.start()
                self.defense_engine.start()
                self.stamina_engine.start()
                self.stats_engine.start()
                self.is_running = True
                self.status_dot.config(fg=self.colors['success'])
                self.status_label.config(text="RUNNING", fg=self.colors['success'])
                self.start_btn.config(text="STOP", bg=self.colors['danger'])
            else:
                self.status_dot.config(fg=self.colors['danger'])
                self.status_label.config(text="FAILED", fg=self.colors['danger'])
        else:
            self.shot_engine.running = False
            self.defense_engine.running = False
            self.stamina_engine.running = False
            self.stats_engine.running = False
            self.is_running = False
            self.status_dot.config(fg=self.colors['danger'])
            self.status_label.config(text="IDLE", fg=self.colors['dim'])
            self.start_btn.config(text="START", bg=self.colors['accent2'])

    def save_settings(self):
        settings = {
            'auto_green': self.auto_green_var.get(),
            'auto_shot': self.auto_shot_var.get(),
            'shot_timing_ms': int(self.shot_timing_var.get()),
            'auto_steal': self.auto_steal_var.get(),
            'auto_block': self.auto_block_var.get(),
            'auto_rebound': self.auto_rebound_var.get(),
            'infinite_energy': self.inf_energy_var.get(),
            'infinite_takeover': self.inf_takeover_var.get(),
            'boost_stats': self.boost_stats_var.get()
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(settings, f, indent=2)

    def load_settings(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                settings = json.load(f)
            for key, var in [
                ('auto_green', self.auto_green_var),
                ('auto_shot', self.auto_shot_var),
                ('auto_steal', self.auto_steal_var),
                ('auto_block', self.auto_block_var),
                ('auto_rebound', self.auto_rebound_var),
                ('infinite_energy', self.inf_energy_var),
                ('infinite_takeover', self.inf_takeover_var),
                ('boost_stats', self.boost_stats_var)
            ]:
                if key in settings:
                    var.set(settings[key])
            if 'shot_timing_ms' in settings:
                self.shot_timing_var.set(str(settings['shot_timing_ms']))

    def update_status(self):
        if self.is_running:
            self.green_label.config(text=f"{self.shot_engine.green_percentage*100:.0f}% green")
        self.root.after(1000, self.update_status)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    gui = NBAEmberGUI()
    gui.run()