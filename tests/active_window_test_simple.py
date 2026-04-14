import pygetwindow as gw
import time

print("=== Active Window Test (Simple) ===")
print("Press Ctrl+C to stop\n")

while True:
    try:
        window = gw.getActiveWindow()

        if window is not None:
            print(f"Window title: {window.title}")
        else:
            print("No active window detected")

        time.sleep(1)

    except KeyboardInterrupt:
        print("\n=== Stopped ===")
        break