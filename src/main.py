from core.event_bus import EventBus
from input.keyboard_input import KeyboardInput
from interpretation.command_interpreter import CommandInterpreter
from execution.action_executor import ActionExecutor
import time


def main():
    event_bus = EventBus()

    keyboard = KeyboardInput(event_bus)
    interpreter = CommandInterpreter(event_bus)
    executor = ActionExecutor(event_bus)

    interpreter.start()
    executor.start()
    keyboard.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        keyboard.stop()
        interpreter.stop()
        executor.stop()


if __name__ == "__main__":
    main()a