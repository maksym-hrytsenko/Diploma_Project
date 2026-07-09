import sys
import time

from PyQt6.QtWidgets import QApplication

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
from processing.face.face_recognizer import FaceRecognizer
from processing.face.face_debug_view import FaceDebugView

from interpretation.command_interpreter import CommandInterpreter

from fusion.multimodal_fusion import MultimodalFusion
from fusion.signal_mapper import SignalMapper

from execution.action_executor import ActionExecutor

from ui.quick_command_overlay import QuickCommandOverlay


def main():

    # Calibration helper: opens a window showing the
    # camera feed with the anchor point, tracked finger
    # and current zone drawn on top
    debug_gesture = "--debug-gesture" in sys.argv

    # Same idea as --debug-gesture, but for FaceRecognizer's head
    # tilt / eyebrows / mouth / blink thresholds (§9 in
    # docs/SYSTEM_FUNCTIONS.md) — opens a window showing live
    # pitch/yaw/roll and blendshape scores next to the exact
    # thresholds they're compared against.
    debug_face = "--debug-face" in sys.argv

    # Prints every recognized voice phrase and wake-word
    # gate decision to the terminal — off by default so
    # normal runs stay quiet.
    debug_voice = "--debug-voice" in sys.argv

    # Must exist, on the main thread, before ActionExecutor
    # constructs PointerOverlay (a QWidget). Qt requires
    # its widgets to be created after a QApplication and
    # on the thread that owns the application.
    qt_app = QApplication(sys.argv)

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
        state_manager,
        debug=debug_voice
    )

    intent_model = IntentModel(
        event_bus,
        state_manager,
        debug=debug_voice
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

    face_recognizer = FaceRecognizer(
        event_bus
    )

    face_debug_view = None

    if debug_face:

        face_debug_view = FaceDebugView(
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

    quick_command_overlay = QuickCommandOverlay(
        event_bus
    )

    # ---------------------------------
    # Start Modules
    #
    # Started in reverse pipeline order —
    # every consumer subscribes before the
    # producer that could feed it anything
    # starts running, so no early event
    # (e.g. a mode_changed fired the instant
    # a camera frame arrives) is ever missed.
    # ---------------------------------

    executor.start()

    quick_command_overlay.start()

    signal_mapper.start()

    fusion.start()

    interpreter.start()

    intent_model.start()

    gesture_recognizer.start()

    if gesture_debug_view is not None:

        gesture_debug_view.start()

    face_recognizer.start()

    if face_debug_view is not None:

        face_debug_view.start()

    keyboard_processor.start()

    speech_recognizer.start()

    camera_input.start()

    microphone_input.start()

    keyboard_input.start()

    # ---------------------------------
    # Main Loop
    # ---------------------------------

    try:

        while True:

            # Drains events pynput's callback thread only ever
            # queued (never published directly — see
            # KeyboardInput for why) and publishes them here on
            # the main thread, where the rest of the pipeline
            # (and any OSController side effect it triggers) is
            # safe to actually run.
            keyboard_input.poll()

            # cv2.imshow / cv2.waitKey must run on the main
            # thread, so the debug window is drawn here
            # instead of from the camera capture thread
            if gesture_debug_view is not None:

                gesture_debug_view.render()

            if face_debug_view is not None:

                face_debug_view.render()

            # Non-blocking; delivers the queued
            # position_updated signal onto this thread and
            # lets the pointer overlay's QTimer/paintEvent
            # run, without giving up control of the loop
            # the way app.exec() would.
            qt_app.processEvents()

            if gesture_debug_view is None and face_debug_view is None:

                time.sleep(0.01)

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

        face_recognizer.stop()

        if face_debug_view is not None:

            face_debug_view.stop()

        interpreter.stop()

        fusion.stop()

        signal_mapper.stop()

        executor.stop()

        quick_command_overlay.stop()

        print("System stopped.")


if __name__ == "__main__":

    main()