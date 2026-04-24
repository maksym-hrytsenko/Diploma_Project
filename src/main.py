import time

from core.event_bus import EventBus
from input.keyboard_input import KeyboardInput
from interpretation.command_interpreter import CommandInterpreter
from execution.action_executor import ActionExecutor


def main():
    # Create event bus
    event_bus = EventBus()

    # Initialize modules
    keyboard = KeyboardInput(event_bus)
    interpreter = CommandInterpreter(event_bus)
    executor = ActionExecutor(event_bus)

    # Start modules
    interpreter.start()
    executor.start()
    keyboard.start()

    try:
        # Keep program running
        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        # Graceful shutdown
        print("\nShutting down...")

        keyboard.stop()
        interpreter.stop()
        executor.stop()

        print("System stopped.")


if __name__ == "__main__":
    main()