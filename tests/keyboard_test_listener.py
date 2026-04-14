import keyboard
import time

print("=== Keyboard test started ===")
print("Press ESC to stop\n")

def on_event(event):
    timestamp = time.time()
    print(f"{timestamp:.6f} | key: {event.name} | type: {event.event_type}")

# ловимо всі події (press + release)bn
keyboard.hook(on_event)

# зупинка по ESC
keyboard.wait("esc")

print("\n=== Stopped ===")