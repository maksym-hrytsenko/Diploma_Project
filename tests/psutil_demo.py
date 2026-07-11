"""Standalone exploratory script for the `psutil` library's process API.

Finds, starts, inspects, and terminates a Notepad process (Windows-only,
uses notepad.exe) to verify psutil's process_iter/terminate behavior
before relying on it elsewhere.
"""
import psutil
import subprocess
import time

print("Checking running processes...")

notepad_running = False
notepad_process = None

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

print("\nSystem info:")
print(f"CPU usage: {psutil.cpu_percent()}%")
print(f"Memory usage: {psutil.virtual_memory().percent}%")

time.sleep(2)

# Find Notepad again, in case we just started it above.
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] == 'notepad.exe':
        notepad_process = proc
        break

if notepad_process:
    print("\nClosing Notepad...")
    notepad_process.terminate()
    print("Done!")
else:
    print("Notepad process not found.")