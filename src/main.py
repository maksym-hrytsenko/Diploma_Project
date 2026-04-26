import time

from core.event_bus import EventBus
from input.keyboard_input import KeyboardInput
from processing.keyboard.keyboard_processor import KeyboardProcessor
from fusion.multimodal_fusion import MultimodalFusion
from interpretation.command_interpreter import CommandInterpreter
from execution.action_executor import ActionExecutor


def debug_listener(event):
    print(f"[MAIN OUTPUT] {event.get('data')}")


def main():
    event_bus = EventBus()

    # Modules
    keyboard_input = KeyboardInput(event_bus)
    keyboard_processor = KeyboardProcessor(event_bus)
    fusion = MultimodalFusion(event_bus)
    interpreter = CommandInterpreter(event_bus)
    executor = ActionExecutor(event_bus)

    # Listen to FINAL stage
    # DEBUG — слухаємо ВСІ етапи

    event_bus.subscribe("keyboard_signal", lambda e: print("[1 keyboard_signal]", e.get("data")))
    event_bus.subscribe("fusion_signal", lambda e: print("[2 fusion_signal]", e.get("data")))
    event_bus.subscribe("command_event", lambda e: print("[3 command_event]", e.get("data")))
    event_bus.subscribe("execution_event", lambda e: print("[4 execution_event]", e.get("data")))

    # Start all
    keyboard_input.start()
    keyboard_processor.start()
    fusion.start()
    interpreter.start()
    executor.start()

    try:
        while True:
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping...")

        keyboard_input.stop()
        keyboard_processor.stop()
        fusion.stop()
        interpreter.stop()
        executor.stop()

        print("System stopped.")


if __name__ == "__main__":
    main()