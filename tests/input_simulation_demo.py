import pyautogui
import time

# Безпека: якщо навести мишку в кут екрану — скрипт зупиниться
pyautogui.FAILSAFE = True

print("Скрипт почнеться через 5 секунд...")
time.sleep(5)

# 1. Рух миші
print("Рух миші...")
pyautogui.moveTo(500, 500, duration=1)

# 2. Клік
print("Клік...")
pyautogui.click()

# 3. Введення тексту
print("Введення тексту...")
pyautogui.write("Hello from PyAutoGUI!", interval=0.1)

# 4. Натискання Enter
pyautogui.press("enter")

# 5. Комбінація клавіш (Ctrl + A → виділити все)
print("Комбінація клавіш...")
pyautogui.hotkey("ctrl", "a")

print("Готово!")