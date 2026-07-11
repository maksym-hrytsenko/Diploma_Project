"""Standalone manual test that logs every keyboard and mouse event (via
pynput) with a timestamp, to inspect raw input timing/format before it was
wired into the main app's input-handling pipeline.
"""

from pynput import mouse, keyboard
import time

print("=== Full Input Test Started ===")
print("ESC to stop\n")


def on_key_press(key):
    timestamp = time.time()
    try:
        print(f"{timestamp:.6f} | KEY | {key.char} | down")
    except AttributeError:
        print(f"{timestamp:.6f} | KEY | {key} | down")


def on_key_release(key):
    timestamp = time.time()
    try:
        print(f"{timestamp:.6f} | KEY | {key.char} | up")
    except AttributeError:
        print(f"{timestamp:.6f} | KEY | {key} | up")

    if key == keyboard.Key.esc:
        return False


def on_move(x, y):
    timestamp = time.time()
    print(f"{timestamp:.6f} | MOUSE | move | ({x}, {y})")


def on_click(x, y, button, pressed):
    timestamp = time.time()
    state = "down" if pressed else "up"
    print(f"{timestamp:.6f} | MOUSE | {button} | {state} | ({x}, {y})")


def on_scroll(x, y, dx, dy):
    timestamp = time.time()
    print(f"{timestamp:.6f} | MOUSE | scroll | dx={dx}, dy={dy} | ({x}, {y})")


mouse_listener = mouse.Listener(
    on_move=on_move,
    on_click=on_click,
    on_scroll=on_scroll
)

keyboard_listener = keyboard.Listener(
    on_press=on_key_press,
    on_release=on_key_release
)

mouse_listener.start()
keyboard_listener.start()

keyboard_listener.join()

print("\n=== Stopped ===")