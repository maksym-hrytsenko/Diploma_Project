"""Standalone demo of pynput's mouse/keyboard Controller API.

Exercises mouse movement/clicks and keyboard typing/shortcuts to verify
pynput can drive OS-level input before wiring it into the action executor.
"""

from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key
import time

mouse = MouseController()
keyboard = KeyboardController()

print("Старт через 5 секунд...")
time.sleep(5)

print("Рух миші...")
mouse.position = (600, 400)
time.sleep(1)

print("Клік...")
mouse.click(Button.left, 1)
time.sleep(1)

print("Введення тексту...")
keyboard.type("Hello from pynput!")
time.sleep(1)

keyboard.press(Key.enter)
keyboard.release(Key.enter)

print("Комбінація клавіш...")
keyboard.press(Key.ctrl)
keyboard.press('a')
keyboard.release('a')
keyboard.release(Key.ctrl)

print("Готово!")