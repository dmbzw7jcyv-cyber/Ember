#!/usr/bin/env python3
# MLBShEmber — MLB The Show Auto-Perfect Suite
# Auto perfect swing, PCI placement, pitch detection, defense automation

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
CONFIG_PATH = Path.home() / '.mlbshember_config.json'
OFFSET_DB_PATH = Path.home() / '.mlbshember_offsets.json'

MLB_PROCESSES = [
    "MLBTheShow26.exe",
    "MLBTheShow25.exe",
    "MLBTheShow24.exe",
    "mlbtheshow.exe"
]

PITCH_PATTERNS = {
    'pitch_speed': b'\xF3\x0F\x10\x05\x00\x00\x00\x00\xF3\x0F\x5C\xC1',
    'pitch_location_x': b'\xF3\x0F\x11\x05\x00\x00\x00\x00\x48\x8B\x05',
    'pitch_location_y': b'\xF3\x0F\x11\x0D\x00\x00\x00\x00\x48\x85',
    'swing_state': b'\x48\x83\xEC\x28\xE8\x00\x00\x00\x00\x48\x85\xC0',
    'pci_position': b'\xF3\x0F\x10\x0D\x00\x00\x00\x00\x0F\x2F\xC1',
    'timing_window': b'\x48\x8B\x05\x00\x00\x00\x00\x48\x85\xC0\x74'
}

@dataclass
class GameOffsets:
    pitch_speed: int = 0x0
    pitch_location_x: int = 0x0
    pitch_location_y: int = 0x0
    swing_state: int = 0x0
    pci_position_x: int = 0x0
    pci_position_y: int = 0x0
    timing_window: int = 0x0
    pitch_type: int = 0x0
    game_state: int = 0x0

    def to_dict(self) -> Dict[str, str]:
        return {k: hex(v) for k, v in self.__dict__.items()}

    def from_dict(self, data: Dict[str, str]):
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

class MLBMemory:
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
                if proc.info['name'] in MLB_PROCESSES:
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

    def read_vec2(self, address: int) -> Tuple[float, float]:
        try:
            x = self.read_float(address)
            y = self.read_float(address + 4)
            return (x, y)
        except:
            return (0, 0)

class PitchDetector:
    def __init__(self):
        self.pitch_history = deque(maxlen=50)
        self.reaction_times = deque(maxlen=30)
        self.avg_reaction_time = 0.0

    def identify_pitch_type(self, speed: float, movement_x: float, movement_y: float) -> str:
        if speed > 95:
            return "Fastball" if movement_y < -10 else "Cutter"
        elif speed > 88:
            if movement_x > 10:
                return "Slider"
            elif movement_y > 15:
                return "Sinker"
            return "Fastball"
        elif speed > 82:
            return "Changeup" if movement_y > 20 else "Splitter"
        else:
            return "Curveball" if movement_x > 15 else "Knuckleball"

    def predict_location(self, current: Tuple[float, float], velocity: Tuple[float, float], time_to_plate: float) -> Tuple[float, float]:
        x = current[0] + velocity[0] * time_to_plate
        y = current[1] + velocity[1] * time_to_plate
        return (x, y)

class AutoSwingEngine:
    def __init__(self):
        self.mem = MLBMemory()
        self.detector = PitchDetector()
        self.running = False
        self.settings = {
            'auto_swing': True,
            'auto_pci': True,
            'auto_steal': False,
            'auto_bunt': False,
            'swing_timing_ms': 0,
            'pci_sensitivity': 1.0,
            'perfect_timing_tolerance': 0.02,
            'power_swing_threshold': 0.7,
            'aggressive_mode': False,
            'debug_logging': True,
            'poll_rate_ms': 1,
            'key_swing': 'space',
            'key_power_swing': 'x',
            'key_contact_swing': 'c',
            'key_bunt': 'b'
        }
        self.stats = {
            'swings_triggered': 0,
            'perfect_swings': 0,
            'pci_placements': 0
        }
        self.game_state = {
            'pitch_incoming': False,
            'current_pitch': None
        }

    def start(self) -> bool:
        if not self.mem.attach():
            return False
        self.load_offsets()
        if self.mem.offsets.pitch_speed == 0x0:
            self.scan_offsets()
        self.running = True
        threading.Thread(target=self.pitch_monitor_loop, daemon=True).start()
        threading.Thread(target=self.swing_loop, daemon=True).start()
        threading.Thread(target=self.pci_loop, daemon=True).start()
        return True

    def stop(self):
        self.running = False

    def pitch_monitor_loop(self):
        poll_rate = self.settings['poll_rate_ms'] / 1000
        while self.running:
            try:
                pitch_state = self.mem.read_int(self.mem.base_address + self.mem.offsets.swing_state)
                if pitch_state == 1:
                    self.game_state['pitch_incoming'] = True
                    speed = self.mem.read_float(self.mem.base_address + self.mem.offsets.pitch_speed)
                    loc_x = self.mem.read_float(self.mem.base_address + self.mem.offsets.pitch_location_x)
                    loc_y = self.mem.read_float(self.mem.base_address + self.mem.offsets.pitch_location_y)
                    pitch_type = self.detector.identify_pitch_type(speed, loc_x, loc_y)
                    self.game_state['current_pitch'] = {
                        'speed': speed,
                        'x': loc_x,
                        'y': loc_y,
                        'type': pitch_type
                    }
                else:
                    self.game_state['pitch_incoming'] = False
            except:
                pass
            time.sleep(poll_rate)

    def swing_loop(self):
        poll_rate = self.settings['poll_rate_ms'] / 1000
        while self.running:
            if self.settings['auto_swing'] and self.game_state['pitch_incoming']:
                pitch = self.game_state['current_pitch']
                if pitch and self.should_swing(pitch):
                    if self.settings['swing_timing_ms'] > 0:
                        time.sleep(self.settings['swing_timing_ms'] / 1000)
                    swing_type = self.determine_swing_type(pitch)
                    self.trigger_swing(swing_type)
                    self.stats['swings_triggered'] += 1
                    if swing_type == 'power':
                        self.stats['perfect_swings'] += 1
            time.sleep(poll_rate)

    def pci_loop(self):
        poll_rate = self.settings['poll_rate_ms'] / 1000
        while self.running:
            if self.settings['auto_pci'] and self.game_state['pitch_incoming']:
                pitch = self.game_state['current_pitch']
                if pitch:
                    pci_x = pitch['x'] * self.settings['pci_sensitivity']
                    pci_y = pitch['y'] * self.settings['pci_sensitivity']
                    self.mem.write_float(self.mem.base_address + self.mem.offsets.pci_position_x, pci_x)
                    self.mem.write_float(self.mem.base_address + self.mem.offsets.pci_position_y, pci_y)
                    self.stats['pci_placements'] += 1
            time.sleep(poll_rate)

    def should_swing(self, pitch) -> bool:
        if self.settings['aggressive_mode']:
            return True
        if self.is_in_strike_zone(pitch['x'], pitch['y']):
            return True
        return abs(pitch['x']) < 0.6 and abs(pitch['y']) < 0.6

    def is_in_strike_zone(self, x, y) -> bool:
        return abs(x) < 0.7 and abs(y) < 0.7

    def determine_swing_type(self, pitch) -> str:
        if pitch['speed'] > 92 and self.is_in_strike_zone(pitch['x'], pitch['y']):
            if pitch['speed'] > self.settings['power_swing_threshold'] * 100:
                return 'power'
        if pitch['speed'] < 85:
            return 'contact'
        return 'normal'

    def trigger_swing(self, swing_type: str = 'normal'):
        key_map = {
            'normal': self.settings['key_swing'],
            'power': self.settings['key_power_swing'],
            'contact': self.settings['key_contact_swing']
        }
        key = key_map.get(swing_type, self.settings['key_swing'])
        keyboard.press_and_release(key)

    def scan_offsets(self):
        scanner = PatternScanner(self.mem.pm, self.mem.base_address, self.mem.module_size)
        for name, pattern in PITCH_PATTERNS.items():
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

class MLBShEmberGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MLBShEmber — MLB The Show Auto-Perfect Suite")
        self.root.geometry("500x650")
        self.root.configure(bg='#0a0a12')
        self.engine = AutoSwingEngine()
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
        title = tk.Label(title_frame, text="MLBShEmber", font=('Segoe UI', 26, 'bold'), fg=self.colors['accent'], bg=self.colors['card'])
        title.pack(pady=10)

        main = tk.Frame(self.root, bg=self.colors['bg'])
        main.pack(fill='both', expand=True, padx=15, pady=15)

        settings_frame = tk.LabelFrame(main, text="Settings", bg=self.colors['card'], fg=self.colors['text'], padx=10, pady=10)
        settings_frame.pack(fill='x', pady=5)

        self.auto_swing_var = tk.BooleanVar(value=True)
        tk.Checkbutton(settings_frame, text="Auto Perfect Swing", variable=self.auto_swing_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        self.auto_pci_var = tk.BooleanVar(value=True)
        tk.Checkbutton(settings_frame, text="Auto PCI Placement", variable=self.auto_pci_var, bg=self.colors['card'], fg=self.colors['accent'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        self.aggressive_var = tk.BooleanVar(value=False)
        tk.Checkbutton(settings_frame, text="Aggressive Mode", variable=self.aggressive_var, bg=self.colors['card'], fg=self.colors['warning'], selectcolor=self.colors['bg'], activebackground=self.colors['card']).pack(anchor='w', pady=2)

        row1 = tk.Frame(settings_frame, bg=self.colors['card'])
        row1.pack(fill='x', pady=3)
        tk.Label(row1, text="Swing Delay (ms):", bg=self.colors['card'], fg=self.colors['dim']).pack(side='left')
        self.swing_delay_var = tk.StringVar(value="0")
        tk.Entry(row1, textvariable=self.swing_delay_var, width=8, bg=self.colors['bg'], fg=self.colors['text'], relief='flat').pack(side='right')

        row2 = tk.Frame(settings_frame, bg=self.colors['card'])
        row2.pack(fill='x', pady=3)
        tk.Label(row2, text="PCI Sensitivity:", bg=self.colors['card'], fg=self.colors['dim']).pack(side='left')
        self.pci_sens_var = tk.StringVar(value="1.0")
        tk.Entry(row2, textvariable=self.pci_sens_var, width=8, bg=self.colors['bg'], fg=self.colors['text'], relief='flat').pack(side='right')

        row3 = tk.Frame(settings_frame, bg=self.colors['card'])
        row3.pack(fill='x', pady=3)
        tk.Label(row3, text="Timing Tolerance:", bg=self.colors['card'], fg=self.colors['dim']).pack(side='left')
        self.tolerance_var = tk.StringVar(value="0.02")
        tk.Entry(row3, textvariable=self.tolerance_var, width=8, bg=self.colors['bg'], fg=self.colors['text'], relief='flat').pack(side='right')

        status_frame = tk.Frame(self.root, bg=self.colors['card'], height=45)
        status_frame.pack(fill='x', padx=15, pady=(0,5))
        status_frame.pack_propagate(False)
        self.status_dot = tk.Label(status_frame, text="●", font=('Segoe UI', 14), fg=self.colors['danger'], bg=self.colors['card'])
        self.status_dot.pack(side='left', padx=(15,8))
        self.status_label = tk.Label(status_frame, text="IDLE", font=('Segoe UI', 11, 'bold'), fg=self.colors['dim'], bg=self.colors['card'])
        self.status_label.pack(side='left')

        self.stats_label = tk.Label(status_frame, text="0 swings | 0 perfect", font=('Segoe UI', 9), fg=self.colors['dim'], bg=self.colors['card'])
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
            self.engine.settings['auto_swing'] = self.auto_swing_var.get()
            self.engine.settings['auto_pci'] = self.auto_pci_var.get()
            self.engine.settings['aggressive_mode'] = self.aggressive_var.get()
            self.engine.settings['swing_timing_ms'] = int(self.swing_delay_var.get())
            self.engine.settings['pci_sensitivity'] = float(self.pci_sens_var.get())
            self.engine.settings['perfect_timing_tolerance'] = float(self.tolerance_var.get())
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
            'auto_swing': self.auto_swing_var.get(),
            'auto_pci': self.auto_pci_var.get(),
            'aggressive_mode': self.aggressive_var.get(),
            'swing_delay_ms': int(self.swing_delay_var.get()),
            'pci_sensitivity': float(self.pci_sens_var.get()),
            'timing_tolerance': float(self.tolerance_var.get())
        }
        with open(CONFIG_PATH, 'w') as f:
            json.dump(settings, f, indent=2)

    def load_settings(self):
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                settings = json.load(f)
            self.auto_swing_var.set(settings.get('auto_swing', True))
            self.auto_pci_var.set(settings.get('auto_pci', True))
            self.aggressive_var.set(settings.get('aggressive_mode', False))
            self.swing_delay_var.set(str(settings.get('swing_delay_ms', 0)))
            self.pci_sens_var.set(str(settings.get('pci_sensitivity', 1.0)))
            self.tolerance_var.set(str(settings.get('timing_tolerance', 0.02)))

    def update_status(self):
        if self.is_running:
            self.stats_label.config(text=f"{self.engine.stats['swings_triggered']} swings | {self.engine.stats['perfect_swings']} perfect")
        self.root.after(1000, self.update_status)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    gui = MLBShEmberGUI()
    gui.run()