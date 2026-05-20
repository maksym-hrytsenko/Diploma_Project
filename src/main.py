import time

from core.event_bus import EventBus
from core.state_manager import StateManager

from input.keyboard_input import KeyboardInput
from processing.keyboard.keyboard_processor import KeyboardProcessor

from input.microphone_input import MicrophoneInput
from processing.speech.speech_recognizer import SpeechRecognizer
from interpretation.intent_model import IntentModel

from input.camera_input import CameraInput
from processing.gesture.gesture_recognizer import GestureRecognizer

from fusion.multimodal_fusion import MultimodalFusion
from interpretation.command_interpreter import (
    CommandInterpreter
)
from execution.action_executor import ActionExecutor


def main():

    event_bus = EventBus()

    state_manager = StateManager()

    # ---------------------------------
    # Keyboard Modules
    # ---------------------------------

    keyboard_input = KeyboardInput(
        event_bus
    )

    keyboard_processor = KeyboardProcessor(
        event_bus
    )

    # ---------------------------------
    # Voice Modules
    # ---------------------------------

    microphone_input = MicrophoneInput(
        event_bus
    )

    speech_recognizer = SpeechRecognizer(
        event_bus,
        state_manager
    )

    intent_model = IntentModel(
        event_bus,
        state_manager
    )

    # ---------------------------------
    # Camera / Gesture Modules
    # ---------------------------------

    camera_input = CameraInput(
        event_bus
    )

    gesture_recognizer = GestureRecognizer(
        event_bus
    )

    # ---------------------------------
    # Core Pipeline
    # ---------------------------------

    fusion = MultimodalFusion(
        event_bus
    )

    interpreter = CommandInterpreter(
        event_bus
    )

    executor = ActionExecutor(
        event_bus
    )

    # ---------------------------------
    # Start Modules
    # ---------------------------------

    keyboard_input.start()

    keyboard_processor.start()

    microphone_input.start()

    speech_recognizer.start()

    intent_model.start()

    camera_input.start()

    gesture_recognizer.start()

    fusion.start()

    interpreter.start()

    executor.start()

    # ---------------------------------
    # Main Loop
    # ---------------------------------

    try:

        while True:

            time.sleep(0.1)

    except KeyboardInterrupt:

        print("\nStopping...")

        keyboard_input.stop()

        keyboard_processor.stop()

        microphone_input.stop()

        speech_recognizer.stop()

        intent_model.stop()

        camera_input.stop()

        gesture_recognizer.stop()

        fusion.stop()

        interpreter.stop()

        executor.stop()

        print("System stopped.")


if __name__ == "__main__":

    main()