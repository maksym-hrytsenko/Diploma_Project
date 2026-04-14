from pynput import keyboard
import time

print("=== Pynput test started ===")
print("Press ESC to stop\n")

def on_press(key):
    timestamp = time.time()
    try:
        print(f"{timestamp:.6f} | key: {key.char} | type: down")
    except AttributeError:
        print(f"{timestamp:.6f} | key: {key} | type: down")

def on_release(key):
    timestamp = time.time()
    try:
        print(f"{timestamp:.6f} | key: {key.char} | type: up")
    except AttributeError:
        print(f"{timestamp:.6f} | key: {key} | type: up")

    if key == keyboard.Key.esc:
        return False  # коректне завершення

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

print("\n=== Stopped ===")