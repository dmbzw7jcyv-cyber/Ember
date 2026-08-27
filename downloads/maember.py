#!/usr/bin/env python3
# MaEmber — Madden Auto-Green Suite
# Auto-green catches and auto hit sticks for Madden 26/27

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
from typing import Optional, List, Tuple
import math
import random

# ─── CONSTANTS ───
CONFIG_PATH = Path.home() / '.maember_config.json'
OFFSET_DB_PATH = Path.home() / '.maember_offsets.json'

MADDEN_PROCESSES = [
    "Madden26.exe",
    "Madden27.exe",
    "Madden25.exe",
    "madden.exe"
]

CATCH_METER_PATTERNS = {
    'catch_meter_active': b'\x48\x83\xEC\x28\xE8\x00\x00\x00\x00\x48\x85\xC0\x74\x00',
    'catch_meter_position': b'\xF3\x0F\x10\x05\x00\x00\x00\x00\xF3\x0F\x5C\xC1',
    'catch_meter_green': b'\xF3\x0F\x10\x0D\x00\x00\x00\x00\x0F\x2F\xC1',
    'hit_stick_state': b'\x48\x8B\x05\x00\x00\x00\x00\x48\x85\xC0\x74\x00\xC6'
}

@dataclass
class GameOffsets:
    catch_meter_active: int = 0x0
    catch_meter_position: int = 0x0
    catch_meter_green: int = 0x0
    hit_stick_state: int = 0x0
    player_state: int = 0x0
    game_state: int = 0x0

    def to_dict(self) -> dict:
        return {k: hex(v) for k, v in self.__dict__.items()}

    def from_dict(self, data: dict):
        for k, v in data.items():
            if hasattr(self, k):
                setattr(self, k, int(v, 16))

class PatternScanner:
    def __init__(self, pm, module_base, module_size):
        self.pm = pm
        self.module_base = module_base
        self.module_size = module_size

    def find_pattern(self, pattern: bytes, mask: Optional[bytes] = None) -> List[int]:
        results = []
        module_bytes = self.pm.read_bytes(self.module_base, self.module_size)
        if mask is None:
            mask = b'\xFF' * len(pattern)
        for i in range(len(module_bytes) - len(pattern)):
            match = True
            for j in range(len(pattern)):
                if mask[j] == 0xFF and module_bytes[i + j] != pattern[j]:
                    match = False
                    break
            if match:
                results.append(self.module_base + i)
        return results

class MaddenMemory:
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
                if proc.info['name'] in MADDEN_PROCESSES:
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

class AutoGreenEngine:
    def __init__(self):
        self.mem = MaddenMemory()
        self.running = False
        self.settings = {
            'auto_catch': True,
            'auto_hit_stick': True,
            'catch_timing_ms': 0,
            'hit_stick_delay_ms': 150,
            'green_zone_tolerance': 0.15,
            'aggressive_mode': False,
            'debug_logging': True
        }
        self.stats = {
            'catches_triggered': 0,
            'hit_sticks_triggered': 0,
            'perfect_timings': 0
        }

    def start(self) -> bool:
        if not self.mem.attach():
            return False
        self.load_offsets()
        if self.mem.offsets.catch_meter_active == 0x0:
            self.scan_offsets()
        self.running = True
        threading.Thread(target=self.catch_loop, daemon=True).start()
        threading.Thread(target=self.hit_stick_loop, daemon=True).start()
        return True

    def stop(self):
        self.running = False

    def catch_loop(self):
        poll_rate = 0.001
        while self.running:
            if self.settings['auto_catch']:
                meter_active = self.mem.read_int(self.mem.base_address + self.mem.offsets.catch_meter_active)
                if meter_active == 1:
                    position = self.mem.read_float(self.mem.base_address + self.mem.offsets.catch_meter_position)
                    green_zone = self.mem.read_float(self.mem.base_address + self.mem.offsets.catch_meter_green)
                    if self.is_in_green(position, green_zone):
                        if self.settings['catch_timing_ms'] > 0:
                            time.sleep(self.settings['catch_timing_ms'] / 1000)
                        keyboard.press_and_release('r')
                        self.stats['catches_triggered'] += 1
                        self.stats['perfect_timings'] += 1
            time.sleep(poll_rate)

    def hit_stick_loop(self):
        poll_rate = 0.001
        while self.running:
            if self.settings['auto_hit_stick']:
                hit_state = self.mem.read_int(self.mem.base_address + self.mem.offsets.hit_stick_state)
                if hit_state == 1:
                    if self.settings['hit_stick_delay_ms'] > 0:
                        time.sleep(self.settings['hit_stick_delay_ms'] / 1000)
                    keyboard.press_and_release('f')
                    self.stats['hit_sticks_triggered'] += 1
            time.sleep(poll_rate)

    def is_in_green(self, position, green_zone) -> bool:
        tolerance = self.settings['green_zone_tolerance']
        return (green_zone - tolerance) <= position <= (green_zone + tolerance)

    def scan_offsets(self):
        scanner = PatternScanner(self.mem.pm, self.mem.base_address, self.mem.module_size)
        for name, pattern in CATCH_METER_PATTERNS.items():
            addresses = scanner.find_pattern(pattern)
            if addresses:
                setattr(self.mem.offsets, name, addresses[0] - self.mem.base_address)
        self.save_offsets()

    def save_offsets(self):
        data = {'process': self.mem.process_name, 'offsets': self.mem.offsets.to_dict()}
        with open(OFFSET_DB_PATH, 'w') as f:
            json.dump(data, f, indent=2)

    def load_offsets(self) -> bool:
        if not OFFSET_DB_PATH.exists():
            return False
        with open(OFFSET_DB_PATH, 'r') as f:
            data = json.load(f)
        if data.get('process') == self.mem.process_name:
            self.mem.offsets.from_dict(data['offsets'])
            return True
        return False

class MaEmberGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MaEmber — Madden Auto-Green Suite")
        self.root.geometry("500x600")
        self.root.configure(bg='#0a0a12')
        self.engine = AutoGreenEngine()
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
        title = tk.Label(title_frame, text="MaEmber", font=('Segoe UI', 28, 'bold'), fg=self.colors['accent'], bg=self.colors['card'])
        title.pack(pady=10)

        main = tk.Frame(self.root, bg=self.colors['bg'])
        main.pack(fill='both', expand=True, padx=15, pady=15)

        settings_frame = tk.LabelFrame(main, text="Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        settings_frame.pack(fill='x', pady=5)

        self.auto_catch_var = tk.BooleanVar(value=True)
        tk.Checkbutton(settings_frame, text="Auto-Green Catches", variable=self.auto_catch_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        self.auto_hit_var = tk.BooleanVar(value=True)
        tk.Checkbutton(settings_frame, text="Auto Hit Sticks", variable=self.auto_hit_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        self.aggressive_var = tk.BooleanVar(value=False)
        tk.Checkbutton(settings_frame, text="Aggressive Mode", variable=self.aggressive_var, bg=self.colors['card'], fg=self.colors['warning'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        row1 = tk.Frame(settings_frame, bg=self.colors['card'])
        row1.pack(fill='x', pady=3)
        tk.Label(row1, text="Catch Delay (ms):", bg=self.colors['card'], fg=self.colors['dim']).pack(side='left')
        self.catch_delay_var = tk.StringVar(value="0")
        tk.Entry(row1, textvariable=self.catch_delay_var, width=8, bg=self.colors['bg'], fg=self.colors['text'], relief='flat').pack(side='right')

        row2 = tk.Frame(settings_frame, bg=self.colors['card'])
        row2.pack(fill='x', pady=3)
        tk.Label(row2, text="Hit Stick Delay (ms):", bg=self.colors['card'], fg=self.colors['dim']).pack(side='left')
        self.hit_delay_var = tk.StringVar(value="150")
        tk.Entry(row2, textvariable=self.hit_delay_var, width=8, bg=self.colors['bg'], fg=self.colors['text'], relief='flat').pack(side='right')

        row3 = tk.Frame(settings_frame, bg=self.colors['card'])
        row3.pack(fill='x', pady=3)
        tk.Label(row3, text="Green Tolerance:", bg=self.colors['card'], fg=self.colors['dim']).pack(side='left')
        self.tolerance_var = tk.StringVar(value="0.15")
        tk.Entry(row3, textvariable=self.tolerance_var, width=8, bg=self.colors['bg'], fg=self.colors['text'], relief='flat').pack(side='right')

        status_frame = tk.Frame(self.root, bg=self.colors['card'], height=45)
        status_frame.pack(fill='x', padx=15, pady=(0,5))
        status_frame.pack_propagate(False)
        self.status_dot = tk.Label(status_frame, text="●", font=('Segoe UI', 14), fg=self.colors['danger'], bg=self.colors['card'])
        self.status_dot.pack(side='left', padx=(15,8))
        self.status_label = tk.Label(status_frame, text="IDLE", font=('Segoe UI', 11, 'bold'), fg=self.colors['dim'], bg=self.colors['card'])
        self.status_label.pack(side='left')

        self.stats_label = tk.Label(status_frame, text="0 catches | 0 hit sticks", font=('Segoe UI', 9), fg=self.colors['dim'], bg=self.colors['card'])
        self.stats_label.pack(side='right', padx=15)

        btn_frame = tk.Frame(self.root, bg=self.colors['bg'])
        btn_frame.pack(fill='x', padx=15, pady=10)

        self.start_btn = tk.Button(btn_frame, text="START", font=('Segoe UI', 13, 'bold'), bg=self.colors['accent2'], fg='white', relief='flat', padx=20, pady=10, command=self.toggle_engine)
        self.start_btn.pack(side='left', padx=5, expand=True, fill='x')

        tk.Button(btn_frame, text="SCAN", font=('Segoe UI', 11, 'bold'), bg='#2962ff', fg='white', relief='flat', padx=12, pady=10, command=self.scan_offsets).pack(side='left', padx=5)

        tk.Button(btn_frame, text="SAVE", font=('Segoe UI', 11, 'bold'), bg='#ff6f00', fg='white', relief='flat', padx=12, pady=10, command=self.save_settings).pack(side='left', padx=5)

        self.update_status()

    def toggle_engine(self):
        if not self.is_running:
            self.engine.settings['auto_catch'] = self.auto_catch_var.get()
            self.engine.settings['auto_hit_stick'] = self.auto_hit_var.get()
            self.engine.settings['aggressive_mode'] = self.aggressive_var.get()
            self.engine.settings['catch_timing_ms'] = int(self.catch_delay_var.get())
            self.engine.settings['hit_stick_delay_ms'] = int(self.hit_delay_var.get())
            self.engine.settings['green_zone_tolerance'] = float(self.tolerance_var.get())
            if self.engine.start():
                self.is_running = True
                self.status_dot.config(fg=self.colors['success'])
                self.status_label.config(text="RUNNING", fg=self.colors['success'])
                self.start_btn.config(text="STOP", bg=self.colors['danger'])
            else:
                self.status_dot.config(fg=self.colors['danger'])
                self.status_label.config(text="FAILED", fg=self.colors['danger'])
        else:
            self.engine.stop()
            self.is_running = False
            self.status_dot.config(fg=self.colors['danger'])
            self.status_label.config(text="IDLE", fg=self.colors['dim'])
            self.start_btn.config(text="START", bg=self.colors['accent2'])

    def scan_offsets(self):
        if not self.engine.mem.is_attached:
            self.engine.mem.attach()
        self.engine.scan_offsets()
        self.status_label.config(text="OFFSETS SCANNED", fg=self.colors['warning'])

    def save_settings(self):
        settings = {
            'auto_catch': self.auto_catch_var.get(),
            'auto_hit_stick': self.auto_hit_var.get(),
            'aggressive_mode': self.aggressive_var.get(),
            'catch_delay_ms': int(self.catch_delay_var.get()),
            'hit_stick_delay_ms': int(self.hit_delay_var.get()),
            'green_zone_tolerance': float(self.tolerance_var.get())
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(settings, f, indent=2)

    def load_settings(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                settings = json.load(f)
            self.auto_catch_var.set(settings.get('auto_catch', True))
            self.auto_hit_var.set(settings.get('auto_hit_stick', True))
            self.aggressive_var.set(settings.get('aggressive_mode', False))
            self.catch_delay_var.set(str(settings.get('catch_delay_ms', 0)))
            self.hit_delay_var.set(str(settings.get('hit_stick_delay_ms', 150)))
            self.tolerance_var.set(str(settings.get('green_zone_tolerance', 0.15)))

    def update_status(self):
        if self.is_running:
            self.stats_label.config(text=f"{self.engine.stats['catches_triggered']} catches | {self.engine.stats['hit_sticks_triggered']} hit sticks")
        self.root.after(1000, self.update_status)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    gui = MaEmberGUI()
    gui.run()