# InputAlerts

A Python-based real-time event monitoring and alert system for configurable input triggers, designed to demonstrate alerting logic, event handling, and real-time notifications. While demonstrated with user input events, the architecture is applicable to real-time monitoring scenarios relevant to SOC/NOC dashboards and IT operations.

## Screenshot

![InputAlerts Screenshot](screenshot.png)

## Features

- Real-time monitoring of keyboard and mouse input
- Configurable triggers (keys or mouse buttons) with delay timers
- Custom alert notifications (sound)
- Live queue display for active alerts
- Threaded, event-driven architecture for real-time performance

## Requirements

- Python 3.x  
- `tkinter` (usually included with Python)  
- `evdev` (`pip install evdev`)  
- Linux OS with access to `/dev/input/event*` devices  
- `aplay` for playing `.wav` files  

---

## 🧰 System Requirements & Permissions

**Platform:** Linux (tested on Ubuntu, Debian, and Arch-based systems)  
**Python Version:** 3.8+  
**Dependencies:**  
- `evdev` (for reading keyboard/mouse events)  
- `tkinter` (for the GUI)  

### 🔐 Access to Input Devices

This application listens to hardware input events from your keyboard and mouse.  
On Linux, those devices are located under `/dev/input/event*`, which are **restricted** to root or members of the `input` group by default.

To grant access without running as root, follow these steps:

```bash
# 1. Check which group has access to input devices
ls -l /dev/input/event*

# You should see something like: crw-r-----+ 1 root input 13, 64 Oct 22 18:00 /dev/input/event0

# 2. Add your user to the 'input' group
sudo usermod -aG input $USER

# 3. Log out and back in (or reboot) to apply the change
```

After this, your app can read from `/dev/input/event*` without needing sudo.

If you still get permission errors, you can temporarily test with:
```bash
sudo python3 InputAlerts.py
```
…but for normal use, adding yourself to the `input` group is preferred for security and convenience.

---

## Usage

1. Run the app:
```bash
python3 InputAlerts.py
```
2. Configure alerts:
   - Name  
   - Key or mouse trigger  
   - Delay (seconds)  
   - Sound file  
3. Start the listener using the GUI button  
4. Alerts will trigger based on the configured input events  

---

## Optional: Sample Configuration

A template `alerts_config_template.json` can be provided so users can see the expected format without sharing personal config.

```json
[
  {
    "name": "Sample Alert",
    "key": "a",
    "delay": 10,
    "sound": "path/to/sample.wav"
  }
]
```

---

## Notes

- The listener only starts if a valid configuration exists  
- The architecture can be adapted to monitor other real-time events, logs, or system notifications  
