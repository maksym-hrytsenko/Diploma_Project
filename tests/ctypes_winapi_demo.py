import ctypes
import time

# Load user32.dll
user32 = ctypes.WinDLL('user32', use_last_error=True)

# Constants
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

# 1. Type HELLO (uppercase via virtual key codes)
print("Typing text...")

keys = [0x48, 0x45, 0x4C, 0x4C, 0x4F]  # H E L L O

for key in keys:
    press_and_release(key)
    time.sleep(0.05)

# Space
press_and_release(0x20)

# Type WORLD
keys = [0x57, 0x4F, 0x52, 0x4C, 0x44]  # W O R L D

for key in keys:
    press_and_release(key)
    time.sleep(0.05)

# Enter
press_and_release(0x0D)

time.sleep(1)

# Ctrl + A
print("Selecting all text...")
press_key(0x11)   # CTRL
press_and_release(0x41)  # A
release_key(0x11)

print("Done!")