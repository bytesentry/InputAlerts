#!/usr/bin/env python3

import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import subprocess
from evdev import InputDevice, categorize, ecodes
import time
import select

CONFIG_FILE = "alerts_config.json"

class AlertTimer:
    def __init__(self, alert, gui_callback):
        self.alert = alert
        self.gui_callback = gui_callback
        self.thread = None
        self.cancel_event = threading.Event()
        self.start_time = None

    def start(self):
        self.cancel()
        self.cancel_event.clear()
        self.start_time = time.time()

        def run():
            self.gui_callback(self, "start")
            if self.cancel_event.wait(self.alert["delay"]):
                self.gui_callback(self, "end")
                return
            sound_path = self.alert["sound"]
            subprocess.Popen(["aplay", sound_path])
            self.gui_callback(self, "end")

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def cancel(self):
        if self.thread and self.thread.is_alive():
            self.cancel_event.set()
            self.gui_callback(self, "end")

    def get_remaining_time(self):
        if self.start_time is None or self.cancel_event.is_set():
            return 0
        elapsed = time.time() - self.start_time
        remaining = max(0, self.alert["delay"] - elapsed)
        return round(remaining)

def update_timer_status(self, timer, status):
    if status == "start":
        self.active_timers[id(timer)] = timer
    elif status == "end":
        self.active_timers.pop(id(timer), None)
    # Schedule queue update only when timers change
    self.after(0, self.update_queue_display)

def update_queue_display(self):
    # Initialize label dictionaries if not present
    if not hasattr(self, 'name_labels'):
        self.name_labels = {}
        self.time_labels = {}
        # Create headers
        tk.Label(self.queue_frame, text="Alert Name", font="Helvetica 10 bold", fg="#D3D3D3", bg="#3A3A3A").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        tk.Label(self.queue_frame, text="Time Remaining", font="Helvetica 10 bold", fg="#D3D3D3", bg="#3A3A3A").grid(row=0, column=1, padx=5, pady=2, sticky="w")

    # Clean up labels for ended timers
    active_ids = set(self.active_timers.keys())
    for timer_id in list(self.name_labels.keys()):
        if timer_id not in active_ids:
            self.name_labels[timer_id].destroy()
            self.time_labels[timer_id].destroy()
            del self.name_labels[timer_id]
            del self.time_labels[timer_id]

    # Update or create labels for active timers
    row = 1
    for timer_id, timer in self.active_timers.items():
        try:
            if timer_id not in self.name_labels:
                name_label = tk.Label(self.queue_frame, text=timer.alert["name"], fg="#D3D3D3", bg="#3A3A3A")
                name_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")
                time_label = tk.Label(self.queue_frame, text=f"{timer.get_remaining_time()}s", fg="#D3D3D3", bg="#3A3A3A")
                time_label.grid(row=row, column=1, padx=5, pady=2, sticky="w")
                self.name_labels[timer_id] = name_label
                self.time_labels[timer_id] = time_label
            else:
                self.name_labels[timer_id].config(text=timer.alert["name"])
                self.time_labels[timer_id].config(text=f"{timer.get_remaining_time()}s")
            row += 1
        except tk.TclError:
            print(f"⚠️ Warning: Failed to update label for timer {timer_id}, recreating.")
            if timer_id in self.name_labels:
                self.name_labels[timer_id].destroy()
                del self.name_labels[timer_id]
            if timer_id in self.time_labels:
                self.time_labels[timer_id].destroy()
                del self.time_labels[timer_id]
            name_label = tk.Label(self.queue_frame, text=timer.alert["name"], fg="#D3D3D3", bg="#3A3A3A")
            name_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")
            time_label = tk.Label(self.queue_frame, text=f"{timer.get_remaining_time()}s", fg="#D3D3D3", bg="#3A3A3A")
            time_label.grid(row=row, column=1, padx=5, pady=2, sticky="w")
            self.name_labels[timer_id] = name_label
            self.time_labels[timer_id] = time_label
            row += 1

    # Reschedule update every second for remaining time
    if self.active_timers:
        self.after(1000, self.update_queue_display)

class AlertConfigurator(tk.Tk):
    def find_devices(self):
        devices = []
        for path in ["/dev/input/event2", "/dev/input/event4", "/dev/input/event5"]:  # Include event5
            try:
                device = InputDevice(path)
                devices.append(device)
                print(f"✅ Found device: {device.path}, {device.name}")
            except Exception as e:
                print(f"❌ Failed to access device {path}: {e}")
        return devices if devices else None

    def reload_listener(self):
        if not hasattr(self, 'listener_running') or not self.listener_running:
            return
        self.stop_listener()
        self.start_listener()

    def start_listener(self):
        if getattr(self, "listener_running", False):
            return

        self.listener_running = True  # moved up here immediately

        self.devices = self.find_devices()
        if not self.devices:
            self.listener_running = False  # reset on failure
            messagebox.showerror("Error", "Could not find keyboard or mouse devices. Ensure proper permissions.")
            return

        self.listener_btn.config(text="⏹ Stop Listener")
        self.keymap.clear()
        self.timers.clear()
        self.active_timers.clear()

        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
        except Exception as e:
            print(f"❌ Configuration not found: {e}")
            return

        for alert in config:
            key = alert["key"].lower()
            self.keymap[key] = alert
            self.timers[key] = AlertTimer(alert, self.update_timer_status)
            print(f"✅ Configured alert for key: {key}, delay: {alert['delay']}s, sound: {alert['sound']}")

        print("✅ Listening on detected devices...")

        def listener_loop():
            try:
                while self.listener_running:
                    r, w, x = [], [], []
                    for dev in self.devices:
                        r.append(dev)
                    if r:
                        ready_devices, _, _ = select.select(r, w, x, 0.1)  # Reduced timeout
                        for dev in ready_devices:
                            try:
                                events = dev.read()
                                for event in events:
                                    if event.type == ecodes.EV_KEY:
                                        key_event = categorize(event)
                                        keycode = key_event.keycode
                                        if isinstance(keycode, tuple):
                                            keycode = keycode[0] if keycode else ""
                                        keycode = keycode.lower().replace("key_", "") if keycode else ""
                                        if key_event.keystate == 1 and keycode in self.keymap:
                                            print(f"✅ Triggering alert for keycode: {keycode} on {dev.path}")
                                            self.timers[keycode].start()
                            except BlockingIOError:
                                continue
                            except Exception as e:
                                print(f"❌ Error reading from {dev.path}: {e}")
            except Exception as e:
                print(f"❌ Listener error: {e}")
                self.listener_running = False
                self.listener_btn.config(text="▶ Start Listener")
                self.after(0, lambda: messagebox.showerror("Error", f"Listener stopped: {e}"))

        self.listener_thread = threading.Thread(target=listener_loop, daemon=True)
        self.listener_thread.start()

    def stop_listener(self):
        if hasattr(self, 'listener_running') and self.listener_running:
            self.listener_running = False
            self.listener_btn.config(text="▶ Start Listener")
            for timer in list(self.active_timers.values()):
                timer.cancel()
            self.active_timers.clear()
            self.update_queue_display()

    def toggle_listener(self):
        if hasattr(self, 'listener_running') and self.listener_running:
            self.stop_listener()
        else:
            self.start_listener()

    def update_timer_status(self, timer, status):
        if status == "start":
            self.active_timers[id(timer)] = timer
        elif status == "end":
            self.active_timers.pop(id(timer), None)
        # Cancel any pending update and schedule a new one
        if hasattr(self, 'queue_update_id'):
            self.after_cancel(self.queue_update_id)
        self.queue_update_id = self.after(0, self.update_queue_display)

    def update_queue_display(self):
        # Initialize label lists if not present
        if not hasattr(self, 'name_labels'):
            self.name_labels = [None] * 10  # Pre-allocate for up to 10 timers
            self.time_labels = [None] * 10
            # Create headers
            tk.Label(self.queue_frame, text="Alert Name", font="Helvetica 10 bold", fg="#D3D3D3", bg="#3A3A3A").grid(
                row=0, column=0, padx=5, pady=2, sticky="w")
            tk.Label(self.queue_frame, text="Time Remaining", font="Helvetica 10 bold", fg="#D3D3D3",
                     bg="#3A3A3A").grid(row=0, column=1, padx=5, pady=2, sticky="w")
            for i in range(10):
                self.name_labels[i] = tk.Label(self.queue_frame, text="", fg="#D3D3D3", bg="#3A3A3A")
                self.name_labels[i].grid(row=i + 1, column=0, padx=5, pady=2, sticky="w")
                self.time_labels[i] = tk.Label(self.queue_frame, text="", fg="#D3D3D3", bg="#3A3A3A")
                self.time_labels[i].grid(row=i + 1, column=1, padx=5, pady=2, sticky="w")

        # Clear all labels
        for i in range(10):
            self.name_labels[i].config(text="")
            self.time_labels[i].config(text="")
            self.name_labels[i].grid_forget()
            self.time_labels[i].grid_forget()

        # Update labels for active timers
        row = 1
        for timer_id, timer in self.active_timers.items():
            try:
                if row <= 10:
                    self.name_labels[row - 1].config(text=timer.alert["name"])
                    self.name_labels[row - 1].grid(row=row, column=0, padx=5, pady=2, sticky="w")
                    self.time_labels[row - 1].config(text=f"{timer.get_remaining_time()}s")
                    self.time_labels[row - 1].grid(row=row, column=1, padx=5, pady=2, sticky="w")
                    row += 1
            except tk.TclError:
                print(f"⚠️ Warning: Failed to update label for timer {timer_id}, skipping.")
                continue

        # Schedule next update only if timers are active
        if self.active_timers:
            self.queue_update_id = self.after(1000, self.update_queue_display)
        else:
            if hasattr(self, 'queue_update_id'):
                self.after_cancel(self.queue_update_id)
                del self.queue_update_id

    def __init__(self):
        super().__init__()
        self.title("Game Alerts")
        self.geometry("610x600")
        self.configure(bg="#2E2E2E")
        self.entries = []
        self.listener_thread = None
        self.listener_running = False
        self.keymap = {}
        self.timers = {}
        self.active_timers = {}

        self.column_widths = {
            "name": 160,
            "key": 60,
            "delay": 50,
            "sound": 170,
            "select": 40,
            "remove": 40
        }

        config_frame = tk.Frame(self, bg="#2E2E2E")
        config_frame.grid(row=0, column=0, columnspan=7, padx=7, pady=5, sticky="nsew")
        tk.Label(config_frame, text="Configure Alerts", font="Helvetica 12 bold", fg="#D3D3D3", bg="#2E2E2E").grid(row=0, column=0, columnspan=6, pady=5)

        headers = [("Name", self.column_widths["name"]), ("Key", self.column_widths["key"]), ("Delay (s)", self.column_widths["delay"]),
                   ("Sound File", self.column_widths["sound"]), ("Select", self.column_widths["select"]), ("Remove", self.column_widths["remove"])]
        for col, (text, width) in enumerate(headers):
            lbl = tk.Label(config_frame, text=text, anchor="w", font="Helvetica 10 bold", fg="#D3D3D3", bg="#2E2E2E")
            lbl.grid(row=1, column=col, padx=6, pady=5, sticky="w")

        self.canvas = tk.Canvas(config_frame, borderwidth=0, bg="#2E2E2E")
        self.frame = tk.Frame(self.canvas, bg="#2E2E2E")
        self.vscroll = tk.Scrollbar(config_frame, orient="vertical", command=self.canvas.yview, bg="#444444", troughcolor="#3A3A3A")
        self.canvas.configure(yscrollcommand=self.vscroll.set)

        self.canvas.grid(row=2, column=0, columnspan=6, sticky="nsew")
        self.vscroll.grid(row=2, column=6, sticky="ns")
        self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.frame.bind("<Configure>", self.on_frame_configure)

        queue_frame = tk.Frame(self, relief="sunken", borderwidth=2, bg="#3A3A3A")
        queue_frame.grid(row=1, column=0, columnspan=7, padx=10, pady=5, sticky="nsew")
        tk.Label(queue_frame, text="Queued Alerts", font="Helvetica 12 bold", fg="#D3D3D3", bg="#3A3A3A").grid(row=0, column=0, columnspan=2, pady=5)

        self.queue_canvas = tk.Canvas(queue_frame, borderwidth=0, height=150, bg="#3A3A3A")
        self.queue_frame = tk.Frame(self.queue_canvas, bg="#3A3A3A")
        self.queue_vscroll = tk.Scrollbar(queue_frame, orient="vertical", command=self.queue_canvas.yview, bg="#444444", troughcolor="#3A3A3A")
        self.queue_canvas.configure(yscrollcommand=self.queue_vscroll.set)

        self.queue_canvas.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.queue_vscroll.grid(row=1, column=2, sticky="ns")
        self.queue_canvas.create_window((0, 0), window=self.queue_frame, anchor="nw")
        self.queue_frame.bind("<Configure>", lambda e: self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all")))

        btn_frame = tk.Frame(self, bg="#2E2E2E")
        btn_frame.grid(row=2, column=0, columnspan=7, pady=10, sticky="w")
        tk.Button(btn_frame, text="➕ Add Alert", command=self.add_alert_row, bg="#444444", fg="#D3D3D3", activebackground="#555555").pack(side="left", padx=5)
        tk.Button(btn_frame, text="💾 Save Configuration", command=self.save_config, bg="#444444", fg="#D3D3D3", activebackground="#555555").pack(side="left", padx=5)
        self.listener_btn = tk.Button(btn_frame, text="▶ Start Listener", command=self.toggle_listener, bg="#444444", fg="#D3D3D3", activebackground="#555555")
        self.listener_btn.pack(side="left", padx=5)

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        for i, col_name in enumerate(["name", "key", "delay", "sound", "select", "remove"]):
            config_frame.grid_columnconfigure(i, weight=1, minsize=self.column_widths[col_name])
        queue_frame.grid_columnconfigure(0, weight=1, minsize=self.column_widths["name"])
        queue_frame.grid_columnconfigure(1, weight=1, minsize=self.column_widths["delay"])

        self.load_config()
        self.start_listener()
        self.update_queue_display()

    def on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def add_alert_row(self, data=None):
        row = len(self.entries)

        name_var = tk.StringVar(value=data["name"] if data else "")
        key_var = tk.StringVar(value=data["key"] if data else "")
        delay_var = tk.StringVar(value=str(data["delay"] if data else "10"))
        sound_var = tk.StringVar(value=data["sound"] if data else "")
        sound_display_var = tk.StringVar(value=os.path.basename(data["sound"]) if data and data["sound"] else "")

        name_entry = tk.Entry(self.frame, textvariable=name_var, bg="#444444", fg="#D3D3D3")
        name_entry.grid(row=row, column=0, padx=5, pady=2, sticky="ew")

        key_btn = tk.Button(self.frame, text=key_var.get() or "Set Key", bg="#444444", fg="#D3D3D3", activebackground="#555555")
        key_btn.grid(row=row, column=1, padx=5, pady=2, sticky="ew")

        def start_key_capture():
            key_btn.config(text="Press combo...", state="disabled")
            modifiers = set()

            def on_key_press(event, btn=key_btn, var=key_var):
                key = event.keysym.lower()
                if key in ("shift_l", "shift_r", "shift"):
                    modifiers.add("shift")
                    return
                elif key in ("control_l", "control_r", "ctrl"):
                    modifiers.add("ctrl")
                    return
                elif key in ("alt_l", "alt_r", "alt"):
                    modifiers.add("alt")
                    return
                combo = list(modifiers)
                if key not in combo:
                    combo.append(key)
                key_combo = "+".join(combo)
                var.set(key_combo)
                key_btn.config(text=key_combo, state="normal")
                key_btn.unbind("<KeyPress>")

            key_btn.bind("<KeyPress>", on_key_press)
            key_btn.focus_set()

        key_btn.config(command=start_key_capture)

        delay_entry = tk.Entry(self.frame, textvariable=delay_var, bg="#444444", fg="#D3D3D3")
        delay_entry.grid(row=row, column=2, padx=5, pady=2, sticky="ew")

        sound_entry = tk.Entry(self.frame, textvariable=sound_display_var, bg="#444444", fg="#D3D3D3")
        sound_entry.grid(row=row, column=3, padx=5, pady=2, sticky="ew")

        def choose_file():
            file = filedialog.askopenfilename(filetypes=[("Audio files", "*.wav *.mp3")])
            if file:
                sound_var.set(file)
                sound_display_var.set(os.path.basename(file))

        select_btn = tk.Button(self.frame, text="🎵", command=choose_file, bg="#444444", fg="#D3D3D3", activebackground="#555555")
        select_btn.grid(row=row, column=4, padx=5, pady=2, sticky="ew")

        def remove_row():
            for widget in (name_entry, key_btn, delay_entry, sound_entry, select_btn, remove_btn):
                widget.destroy()
            self.entries.pop(row)
            self.refresh_rows()

        remove_btn = tk.Button(self.frame, text="❌", command=remove_row, bg="#444444", fg="#D3D3D3", activebackground="#555555")
        remove_btn.grid(row=row, column=5, padx=5, pady=2, sticky="ew")

        self.entries.append({
            "vars": {
                "name": name_var,
                "key": key_var,
                "delay": delay_var,
                "sound": sound_var,
                "sound_display": sound_display_var
            },
            "widgets": (name_entry, key_btn, delay_entry, sound_entry, select_btn, remove_btn)
        })

        name_entry.config(width=self.column_widths["name"]//10)
        key_btn.config(width=self.column_widths["key"]//10)
        delay_entry.config(width=self.column_widths["delay"]//10)
        sound_entry.config(width=self.column_widths["sound"]//10)
        select_btn.config(width=self.column_widths["select"]//10)
        remove_btn.config(width=self.column_widths["remove"]//10)

    def refresh_rows(self):
        for i, entry in enumerate(self.entries):
            for col, widget in enumerate(entry["widgets"]):
                widget.grid_configure(row=i, column=col)

    def save_config(self):
        alerts = []
        for entry in self.entries:
            vars = entry["vars"]
            try:
                delay = int(vars["delay"].get())
            except ValueError:
                messagebox.showerror("Invalid Delay", f"Delay must be an integer: {vars['delay'].get()}")
                return

            alert = {
                "name": vars["name"].get(),
                "key": vars["key"].get().lower(),
                "delay": delay,
                "sound": vars["sound"].get()
            }
            if not alert["key"] or not alert["sound"]:
                continue
            alerts.append(alert)

        with open(CONFIG_FILE, "w") as f:
            json.dump(alerts, f, indent=2)

        messagebox.showinfo("Saved", f"Configuration saved to {CONFIG_FILE}")
        self.reload_listener()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            for alert in data:
                self.add_alert_row(alert)

            # ✅ Start listener only once, since config exists
            # (do not schedule a delayed reload)
            self.start_listener()
        else:
            print("⚠️ No configuration found. Listener will not start.")

    def destroy(self):
        self.stop_listener()
        super().destroy()

if __name__ == "__main__":
    app = AlertConfigurator()
    app.mainloop()