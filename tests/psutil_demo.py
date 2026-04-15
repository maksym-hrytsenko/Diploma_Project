import psutil
import subprocess
import time

print("Checking running processes...")

notepad_running = False
notepad_process = None

# 1. Check if Notepad is running
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] == 'notepad.exe':
        notepad_running = True
        notepad_process = proc
        break

if not notepad_running:
    print("Notepad is not running. Starting it...")
    process = subprocess.Popen("notepad.exe")
    time.sleep(2)
else:
    print("Notepad is already running.")

# 2. Show some system info
print("\nSystem info:")
print(f"CPU usage: {psutil.cpu_percent()}%")
print(f"Memory usage: {psutil.virtual_memory().percent}%")

time.sleep(2)

# 3. Find Notepad again (in case we just started it)
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] == 'notepad.exe':
        notepad_process = proc
        break

# 4. Terminate Notepad
if notepad_process:
    print("\nClosing Notepad...")
    notepad_process.terminate()
    print("Done!")
else:
    print("Notepad process not found.")