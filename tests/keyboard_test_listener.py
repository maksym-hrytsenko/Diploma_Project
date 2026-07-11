"""Standalone exploratory script for the `keyboard` library's global hook API.

Logs every key press/release event with a timestamp to verify hook
behavior before wiring the library into the main application.
"""
import keyboard
import time

print("=== Keyboard test started ===")
print("Press ESC to stop\n")

def on_event(event):
    timestamp = time.time()
    print(f"{timestamp:.6f} | key: {event.name} | type: {event.event_type}")

keyboard.hook(on_event)

keyboard.wait("esc")

print("\n=== Stopped ===")