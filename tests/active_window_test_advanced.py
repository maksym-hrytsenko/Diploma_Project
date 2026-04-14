import win32gui
import win32process
import psutil
import time

print("=== Active Window Test (Advanced) ===")
print("Press Ctrl+C to stop\n")

while True:
    try:
        hwnd = win32gui.GetForegroundWindow()

        title = win32gui.GetWindowText(hwnd)

        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        try:
            process = psutil.Process(pid)
            process_name = process.name()
        except:
            process_name = "Unknown"

        print(f"Title: {title} | PID: {pid} | Process: {process_name}")

        time.sleep(1)

    except KeyboardInterrupt:
        print("\n=== Stopped ===")
        break