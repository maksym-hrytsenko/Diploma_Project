"""Standalone exploration of the pyautogui API (mouse move, click, text
entry, key press, hotkey) before deciding whether to use it for input
simulation in the main app.
"""

import pyautogui
import time

# Moving the mouse to a screen corner aborts the script — a safety net
# against a runaway automated input loop.
pyautogui.FAILSAFE = True

print("Скрипт почнеться через 5 секунд...")
time.sleep(5)

print("Рух миші...")
pyautogui.moveTo(500, 500, duration=1)

print("Клік...")
pyautogui.click()

print("Введення тексту...")
pyautogui.write("Hello from PyAutoGUI!", interval=0.1)

pyautogui.press("enter")

print("Комбінація клавіш...")
pyautogui.hotkey("ctrl", "a")

print("Готово!")
