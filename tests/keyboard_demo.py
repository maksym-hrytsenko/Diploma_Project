"""Standalone exploratory script for the `keyboard` library's API.

Manually exercises text typing, key presses, and hotkey waiting to verify
behavior before wiring the library into the main application.
"""
import keyboard
import time

print("Starting in 5 seconds...")
time.sleep(5)

print("Typing text...")
keyboard.write("Hello from keyboard library!", delay=0.05)

time.sleep(1)

print("Pressing Enter...")
keyboard.press_and_release("enter")

time.sleep(1)

print("Selecting all text...")
keyboard.press_and_release("ctrl+a")

time.sleep(1)

print("Press ESC to exit...")

keyboard.wait("esc")

print("Program finished.")