import keyboard
import time

print("Starting in 5 seconds...")
time.sleep(5)

# 1. Type text
print("Typing text...")
keyboard.write("Hello from keyboard library!", delay=0.05)

time.sleep(1)

# 2. Press Enter
print("Pressing Enter...")
keyboard.press_and_release("enter")

time.sleep(1)

# 3. Ctrl + A
print("Selecting all text...")
keyboard.press_and_release("ctrl+a")

time.sleep(1)

# 4. Wait for hotkey (ESC to stop)
print("Press ESC to exit...")

keyboard.wait("esc")

print("Program finished.")