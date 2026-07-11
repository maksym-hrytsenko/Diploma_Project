"""Standalone demo of raw ctypes calls into Windows' user32.dll to synthesize
keyboard input (keybd_event), exploring the low-level WinAPI before it was
wrapped by OSController.
"""

import ctypes
import time

user32 = ctypes.WinDLL('user32', use_last_error=True)

KEYEVENTF_KEYUP = 0x0002

def press_key(hexKeyCode):
    user32.keybd_event(hexKeyCode, 0, 0, 0)

def release_key(hexKeyCode):
    user32.keybd_event(hexKeyCode, 0, KEYEVENTF_KEYUP, 0)

def press_and_release(hexKeyCode):
    press_key(hexKeyCode)
    time.sleep(0.05)
    release_key(hexKeyCode)

print("Starting in 5 seconds...")
time.sleep(5)

print("Typing text...")

keys = [0x48, 0x45, 0x4C, 0x4C, 0x4F]  # H E L L O

for key in keys:
    press_and_release(key)
    time.sleep(0.05)

press_and_release(0x20)

keys = [0x57, 0x4F, 0x52, 0x4C, 0x44]  # W O R L D

for key in keys:
    press_and_release(key)
    time.sleep(0.05)

press_and_release(0x0D)

time.sleep(1)

print("Selecting all text...")
press_key(0x11)   # CTRL
press_and_release(0x41)  # A
release_key(0x11)

print("Done!")