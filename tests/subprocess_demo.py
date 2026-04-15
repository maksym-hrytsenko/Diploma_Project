import subprocess
import time

print("Starting in 3 seconds...")
time.sleep(3)

# 1. Open Notepad
print("Opening Notepad...")
subprocess.Popen("notepad.exe")

time.sleep(2)

# 2. Open Calculator
print("Opening Calculator...")
subprocess.Popen("calc.exe")

time.sleep(2)

# 3. Open a website using default browser
print("Opening browser with URL...")
subprocess.Popen(
    "start https://www.google.com",
    shell=True
)

time.sleep(2)

# 4. Run command in shell
print("Running system command...")
subprocess.run("echo Hello from subprocess!", shell=True)

print("Done!")