"""Standalone exploratory script for testing the subprocess module on Windows.

Launches Notepad and Calculator, opens a URL in the default browser, and
runs a shell command. Used to verify subprocess-based process/shell
invocation in isolation before relying on it elsewhere in the project.
"""

import subprocess
import time

print("Starting in 3 seconds...")
time.sleep(3)

print("Opening Notepad...")
subprocess.Popen("notepad.exe")

time.sleep(2)

print("Opening Calculator...")
subprocess.Popen("calc.exe")

time.sleep(2)

print("Opening browser with URL...")
subprocess.Popen(
    "start https://www.google.com",
    shell=True
)

time.sleep(2)

print("Running system command...")
subprocess.run("echo Hello from subprocess!", shell=True)

print("Done!")