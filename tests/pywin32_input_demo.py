import win32api
import win32con
import time

def press_key(key_code):
    win32api.keybd_event(key_code, 0, 0, 0)

def release_key(key_code):
    win32api.keybd_event(key_code, 0, win32con.KEYEVENTF_KEYUP, 0)

def press_and_release(key_code):
    press_key(key_code)
    time.sleep(0.05)
    release_key(key_code)

print("Starting in 5 seconds...")
time.sleep(5)

# 1. Type text (manually through key codes)
print("Typing text...")

text = "HELLO FROM WINAPI"
for char in text:
    if char == " ":
        press_and_release(win32con.VK_SPACE)
    else:
        press_and_release(ord(char))
    time.sleep(0.05)

# 2. Press Enter
print("Pressing Enter...")
press_and_release(win32con.VK_RETURN)

time.sleep(1)

# 3. CTRL + A
print("Sending CTRL + A...")
press_key(win32con.VK_CONTROL)
press_and_release(ord('A'))
release_key(win32con.VK_CONTROL)

print("Done!")