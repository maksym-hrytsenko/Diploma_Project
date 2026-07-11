"""Application entry point.

Wires every module of the multimodal control pipeline (input -> processing ->
interpretation -> fusion -> execution -> UI) to a shared EventBus, starts them
in dependency order, and drives the Qt event loop alongside the system's own
polling loop.
"""

import sys
import threading
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
from ui.main_window import MainWindow
from ui.floating_status_bar import FloatingStatusBar
from ui.native_window import configure_accessory_app

from config.config_loader import load_system_config


def main() -> None:

    # --debug-gesture: overlays the camera feed with the anchor point,
    # tracked finger and current zone.
    debug_gesture = "--debug-gesture" in sys.argv

    # --debug-face: overlays live pitch/yaw/roll and blendshape scores
    # against the thresholds they're compared to (see docs/SYSTEM_FUNCTIONS.md §9).
    debug_face = "--debug-face" in sys.argv

    debug_voice = "--debug-voice" in sys.argv

    # Qt requires its widgets to be created after a QApplication exists, on
    # the thread that owns it — this must run before ActionExecutor builds
    # PointerOverlay.
    qt_app = QApplication(sys.argv)

    loop_sleep_seconds = load_system_config().get(
        "app",
        {}
    ).get(
        "loop_sleep_seconds",
        0.01
    )

    # Must run before any overlay widget (PointerOverlay, QuickCommandOverlay)
    # is constructed — see configure_accessory_app for why.
    configure_accessory_app()

    event_bus = EventBus()

    state_manager = StateManager()

    keyboard_input = KeyboardInput(
        event_bus
    )

    keyboard_processor = KeyboardProcessor(
        event_bus
    )

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

    main_window = MainWindow(
        event_bus
    )

    floating_status_bar = FloatingStatusBar(
        event_bus
    )

    # Set from FloatingStatusBar's close (X) button, via the
    # "ui_quit_requested" event — the only way to stop the whole pipeline
    # from the UI without going through a terminal Ctrl-C.
    shutdown_requested = threading.Event()

    def _handle_quit_requested(event):

        shutdown_requested.set()

    event_bus.subscribe(
        "ui_quit_requested",
        _handle_quit_requested
    )

    # Started in reverse pipeline order so every consumer subscribes before
    # the producer that could feed it starts running — otherwise an early
    # event could be published before anything is listening for it.
    executor.start()

    main_window.start()

    main_window.show()

    floating_status_bar.start()

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

    try:

        while not shutdown_requested.is_set():

            # KeyboardInput only queues events from pynput's callback thread;
            # this publishes them here on the main thread, where the rest of
            # the pipeline (and any OSController side effect) is safe to run.
            keyboard_input.poll()

            # cv2.imshow/cv2.waitKey must run on the main thread, so the
            # debug windows are drawn here rather than from the capture thread.
            if gesture_debug_view is not None:

                gesture_debug_view.render()

            if face_debug_view is not None:

                face_debug_view.render()

            # Non-blocking pump for the pointer overlay's QTimer/paintEvent,
            # without ceding control of the loop the way app.exec() would.
            qt_app.processEvents()

            if gesture_debug_view is None and face_debug_view is None:

                time.sleep(loop_sleep_seconds)

    except KeyboardInterrupt:

        print("\nStopping...")

    finally:

        # Runs whether the loop ended via Ctrl-C or via the floating
        # status bar's close (X) button setting shutdown_requested.
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

        main_window.stop()

        floating_status_bar.stop()

        print("System stopped.")


if __name__ == "__main__":

    main()