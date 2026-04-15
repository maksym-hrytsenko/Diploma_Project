from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key
import time

mouse = MouseController()
keyboard = KeyboardController()

print("Старт через 5 секунд...")
time.sleep(5)

# 1. Рух миші
print("Рух миші...")
mouse.position = (600, 400)
time.sleep(1)

# 2. Клік
print("Клік...")
mouse.click(Button.left, 1)
time.sleep(1)

# 3. Введення тексту
print("Введення тексту...")
keyboard.type("Hello from pynput!")
time.sleep(1)

# 4. Enter
keyboard.press(Key.enter)
keyboard.release(Key.enter)

# 5. Ctrl + A
print("Комбінація клавіш...")
keyboard.press(Key.ctrl)
keyboard.press('a')
keyboard.release('a')
keyboard.release(Key.ctrl)

print("Готово!")