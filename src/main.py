import sys
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
from processing.gesture.gesture_debug_view import GestureDebugView

from interpretation.command_interpreter import CommandInterpreter

from fusion.multimodal_fusion import MultimodalFusion
from fusion.signal_mapper import SignalMapper

from execution.action_executor import ActionExecutor


def main():

    # Calibration helper: opens a window showing the
    # camera feed with the anchor point, tracked finger
    # and current zone drawn on top
    debug_gesture = "--debug-gesture" in sys.argv

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

    gesture_debug_view = None

    if debug_gesture:

        gesture_debug_view = GestureDebugView(
            event_bus
        )

    # ---------------------------------
    # Core Pipeline
    # ---------------------------------

    interpreter = CommandInterpreter(
        event_bus
    )

    fusion = MultimodalFusion(
        event_bus
    )

    signal_mapper = SignalMapper(
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

    if gesture_debug_view is not None:

        gesture_debug_view.start()

    interpreter.start()

    fusion.start()

    signal_mapper.start()

    executor.start()

    # ---------------------------------
    # Main Loop
    # ---------------------------------

    try:

        while True:

            # cv2.imshow / cv2.waitKey must run on the main
            # thread, so the debug window is drawn here
            # instead of from the camera capture thread
            if gesture_debug_view is not None:

                gesture_debug_view.render()

            else:

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

        if gesture_debug_view is not None:

            gesture_debug_view.stop()

        interpreter.stop()

        fusion.stop()

        signal_mapper.stop()

        executor.stop()

        print("System stopped.")


if __name__ == "__main__":

    main()