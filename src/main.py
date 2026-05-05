import time

from core.event_bus import EventBus
from core.state_manager import StateManager

from input.keyboard_input import KeyboardInput
from processing.keyboard.keyboard_processor import KeyboardProcessor

from input.microphone_input import MicrophoneInput
from processing.speech.speech_recognizer import SpeechRecognizer
from interpretation.intent_model import IntentModel

from fusion.multimodal_fusion import MultimodalFusion
from interpretation.command_interpreter import CommandInterpreter
from execution.action_executor import ActionExecutor


def main():
    event_bus = EventBus()
    state_manager = StateManager()

    # Keyboard modules (unchanged)
    keyboard_input = KeyboardInput(event_bus)
    keyboard_processor = KeyboardProcessor(event_bus)

    # Voice modules (NEW)
    microphone_input = MicrophoneInput(event_bus)
    speech_recognizer = SpeechRecognizer(event_bus, state_manager)
    intent_model = IntentModel(event_bus, state_manager)  # IMPORTANT: must use EventBus

    # Core pipeline
    fusion = MultimodalFusion(event_bus)
    interpreter = CommandInterpreter(event_bus)
    executor = ActionExecutor(event_bus)

    # DEBUG listeners (extended)
    event_bus.subscribe("keyboard_signal", lambda e: print("[1 keyboard_signal]", e.get("data")))
    event_bus.subscribe("text_ready", lambda e: print("[2 text_ready]", e.get("data")))  # NEW
    event_bus.subscribe("intent_detected", lambda e: print("[3 intent_detected]", e.get("data")))  # NEW
    event_bus.subscribe("fusion_signal", lambda e: print("[4 fusion_signal]", e.get("data")))
    event_bus.subscribe("command_event", lambda e: print("[5 command_event]", e.get("data")))
    event_bus.subscribe("execution_event", lambda e: print("[6 execution_event]", e.get("data")))

    # Start all
    keyboard_input.start()
    keyboard_processor.start()

    microphone_input.start()         # NEW
    speech_recognizer.start()        # (if you have start, otherwise ignore)
    intent_model.start()             # NEW

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

        microphone_input.stop()      # NEW
        # speech_recognizer.stop()   # if implemented
        intent_model.stop()          # NEW

        fusion.stop()
        interpreter.stop()
        executor.stop()

        print("System stopped.")


if __name__ == "__main__":
    main()