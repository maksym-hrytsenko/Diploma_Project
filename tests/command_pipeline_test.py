# ---------------------------------
# Unlike the *_standalone_test.py scripts in this folder,
# this one does NOT need a camera, microphone, or keyboard —
# it drives the real pipeline (CommandInterpreter ->
# MultimodalFusion -> SignalMapper -> ActionExecutor) by
# publishing the exact same raw EventBus events the real
# recognizers publish (gesture_signal, face_signal,
# keyboard_signal, intent_detected), with OSController mocked
# out so nothing actually happens on the Mac. This tests the
# CONFIG/WIRING (mapping.json + fusion.json + command_table),
# not gesture/face/voice RECOGNITION itself — it cannot catch
# "MediaPipe misclassified my hand", only "this signal, once
# recognized, is or isn't wired to the right OS action".
#
# Run: venv/bin/python tests/command_pipeline_test.py
# ---------------------------------

import sys
import os

from unittest.mock import patch

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

SRC_DIR = os.path.join(
    BASE_DIR,
    "src"
)

sys.path.insert(
    0,
    SRC_DIR
)


def run():

    with patch(
        "execution.action_executor.OSController"
    ) as MockOSController, patch(
        "execution.action_executor.PointerOverlay"
    ):

        from core.event_bus import EventBus
        from interpretation.command_interpreter import (
            CommandInterpreter
        )
        from fusion.multimodal_fusion import MultimodalFusion
        from fusion.signal_mapper import SignalMapper
        from execution.action_executor import ActionExecutor

        event_bus = EventBus()

        interpreter = CommandInterpreter(event_bus)
        fusion = MultimodalFusion(event_bus)
        signal_mapper = SignalMapper(event_bus)
        executor = ActionExecutor(event_bus)

        interpreter.start()
        fusion.start()
        signal_mapper.start()
        executor.start()

        controller = MockOSController.return_value

        # ---------------------------------
        # Publishers — mirror exactly what the real
        # recognizers publish, field for field.
        # ---------------------------------

        def voice(command, confidence=1.0):

            event_bus.publish(
                "intent_detected",
                {
                    "command": command,
                    "confidence": confidence,
                    "source": "voice"
                }
            )

        def gesture(signal, confidence=1.0):

            event_bus.publish(
                "gesture_signal",
                {
                    "signal": signal,
                    "confidence": confidence,
                    "source": "gesture"
                }
            )

        def face(signal):

            event_bus.publish(
                "face_signal",
                {
                    "signal": signal,
                    "source": "face"
                }
            )

        def key(signal, action):

            event_bus.publish(
                "keyboard_signal",
                {
                    "signal": signal,
                    "event": action
                }
            )

        def stream(event_type, data):

            event_bus.publish(
                event_type,
                data
            )

        results = []

        def check(name, method_names):

            if isinstance(method_names, str):
                method_names = [method_names]

            missing = [
                m for m in method_names
                if not getattr(controller, m).called
            ]

            ok = not missing

            results.append((name, ok, missing))

            status = "PASS" if ok else "FAIL"

            print(
                f"[{status}] {name} -> "
                f"{', '.join(method_names)}"
            )

            controller.reset_mock()

        # =====================================
        # GLOBAL VOICE RULES (any mode/idle)
        # =====================================

        GLOBAL_VOICE_RULES = [

            ("open browser",     "OPEN_BROWSER",     "open_browser"),
            ("open chatgpt",     "OPEN_CHATGPT",     "open_chatgpt"),
            ("open github",      "OPEN_GITHUB",      "open_github"),
            ("open vscode",      "OPEN_VSCODE",      "open_vscode"),
            ("open terminal",    "OPEN_TERMINAL",    "open_terminal"),
            ("open safari",      "OPEN_SAFARI",      "open_safari"),
            ("open chrome",      "OPEN_CHROME",      "open_chrome"),
            ("open spotify",     "OPEN_SPOTIFY",     "open_spotify"),
            ("open slack",       "OPEN_SLACK",       "open_slack"),
            ("open discord",     "OPEN_DISCORD",     "open_discord"),
            ("open mail",        "OPEN_MAIL",        "open_mail"),
            ("open calendar",    "OPEN_CALENDAR",    "open_calendar"),
            ("open notes",       "OPEN_NOTES",       "open_notes"),
            ("open telegram",    "OPEN_TELEGRAM",    "open_telegram"),
            ("open finder",      "OPEN_FINDER",      "open_finder"),
            ("open notion",      "OPEN_NOTION",      "open_notion"),
            ("open photos",      "OPEN_PHOTOS",      "open_photos"),
            ("open preview",     "OPEN_PREVIEW",     "open_preview"),
            ("open settings",    "OPEN_SETTINGS",    "open_settings"),
            ("start",            "START",            "media_play_pause"),
            ("stop",             "STOP",             "media_play_pause"),
            ("pause",            "PAUSE",            "media_play_pause"),
            ("reset",            "RESET",            "media_play_pause"),
            ("next track",       "NEXT_TRACK",       "next_track"),
            ("previous track",   "PREVIOUS_TRACK",   "previous_track")

        ]

        print("\n=== Voice: global commands (any mode/idle) ===")

        for phrase, command, method in GLOBAL_VOICE_RULES:

            voice(command)

            check(
                f'voice "{phrase}" ({command})',
                method
            )

        # =====================================
        # FACE LAYER (keyboard modifier + face, idle only)
        # =====================================

        print("\n=== Face layer (Alt/Ctrl + face gesture) ===")

        FACE_LAYER_RULES = [

            ("alt", "HEAD_TILT_RIGHT", "next_track"),
            ("alt", "HEAD_TILT_LEFT", "previous_track"),
            ("alt", "MOUTH_OPEN", "media_play_pause"),
            ("alt", "DOUBLE_BLINK", "take_screenshot"),
            ("alt", "EYEBROWS_UP", "volume_up"),
            ("ctrl", "EYEBROWS_UP", "volume_down")

        ]

        for modifier, face_signal, method in FACE_LAYER_RULES:

            key(modifier, "down")

            face(face_signal)

            check(
                f'Alt/Ctrl="{modifier}" + face {face_signal}',
                method
            )

            key(modifier, "up")

        # =====================================
        # ENVIRONMENTS (voice-triggered, multi-action)
        # =====================================

        print("\n=== Environments (voice, multiple actions each) ===")

        ENVIRONMENTS = [

            (
                "work mode",
                "WORK_MODE",
                [
                    "enable_do_not_disturb",
                    "open_slack",
                    "open_mail",
                    "open_calendar"
                ]
            ),
            (
                "study mode",
                "STUDY_MODE",
                [
                    "enable_do_not_disturb",
                    "open_safari",
                    "open_preview",
                    "play_focus_music"
                ]
            ),
            (
                "movie mode",
                "MOVIE_MODE",
                [
                    "enable_do_not_disturb",
                    "prevent_display_sleep",
                    "open_tv"
                ]
            ),
            (
                "news mode",
                "NEWS_MODE",
                [
                    "open_news"
                ]
            )

        ]

        for phrase, command, methods in ENVIRONMENTS:

            signal_mapper.clear_environment()

            controller.reset_mock()

            voice(command)

            check(
                f'voice "{phrase}" ({command})',
                methods
            )

        signal_mapper.clear_environment()

        # =====================================
        # MODE: Presentation
        # =====================================

        print("\n=== Mode: Presentation ===")

        voice("PRESENTATION_MODE")

        assert signal_mapper.current_mode == "presentation", (
            "voice PRESENTATION_MODE did not enter presentation mode"
        )

        voice("NEXT_SLIDE")
        check("presentation: voice next slide", "next_slide")

        voice("PREVIOUS_SLIDE")
        check("presentation: voice previous slide", "previous_slide")

        key("right", "down")
        key("right", "up")
        check("presentation: keyboard Right arrow", "next_slide")

        key("left", "down")
        key("left", "up")
        check("presentation: keyboard Left arrow", "previous_slide")

        gesture("HAND_RIGHT")
        check("presentation: gesture swipe right", "next_slide")

        gesture("HAND_LEFT")
        check("presentation: gesture swipe left", "previous_slide")

        signal_mapper.clear_mode()

        # =====================================
        # MODE: Flip
        # =====================================

        print("\n=== Mode: Flip ===")

        key("ctrl+shift+f", "down")
        key("ctrl+shift+f", "up")

        assert signal_mapper.current_mode == "flip", (
            "keyboard ctrl+shift+f did not enter flip mode"
        )

        gesture("HAND_UP")
        check("flip: gesture swipe up", "scroll_down")

        gesture("HAND_DOWN")
        check("flip: gesture swipe down", "scroll_up")

        gesture("HAND_RIGHT")
        check("flip: gesture swipe right", "flip_previous")

        gesture("HAND_LEFT")
        check("flip: gesture swipe left", "flip_next")

        signal_mapper.clear_mode()

        # =====================================
        # MODE: Cursor
        # =====================================

        print("\n=== Mode: Cursor ===")

        voice("CURSOR_MODE")

        assert signal_mapper.current_mode == "cursor", (
            "voice CURSOR_MODE did not enter cursor mode"
        )

        gesture("PINCH")
        check("cursor: gesture pinch (click)", "click")

        gesture("DOUBLE_PINCH")
        check("cursor: gesture double pinch (right-click)", "right_click")

        # Continuous streams bypass fusion entirely — go
        # straight from the publisher to ActionExecutor.
        stream(
            "pointer_position",
            {"x": 0.5, "y": 0.5, "source": "gesture"}
        )
        check("cursor: pointer_position stream", "move_cursor_to")

        stream(
            "pinch_drag",
            {"delta_x": 0.1, "delta_y": 0.0, "source": "gesture"}
        )
        check("cursor: pinch_drag stream (scroll)", "scroll_by")

        stream(
            "pinch_zoom",
            {"delta_distance": 0.2, "source": "gesture"}
        )
        check("cursor: pinch_zoom stream (zoom in)", "zoom_in")

        signal_mapper.clear_mode()

        # =====================================
        # MODE: Call
        # =====================================

        print("\n=== Mode: Call ===")

        voice("CALL_MODE")

        assert signal_mapper.current_mode == "call", (
            "voice CALL_MODE did not enter call mode"
        )

        gesture("ONE_FINGER")
        check("call: gesture one finger (toggle mic)", "toggle_mic")

        gesture("TWO_FINGERS")
        check("call: gesture two fingers (toggle camera)", "toggle_camera")

        gesture("THREE_FINGERS")
        check(
            "call: gesture three fingers (toggle call audio)",
            "toggle_call_audio"
        )

        gesture("FOUR_FINGERS")
        check(
            "call: gesture four fingers (toggle background blur)",
            "toggle_background_blur"
        )

        gesture("OK_SIGN")
        check("call: gesture OK sign (raise hand)", "raise_hand")

        signal_mapper.clear_mode()

        # =====================================
        # MODE: Quick Circle (gesture-only entry + selection)
        # =====================================

        print("\n=== Mode: Quick Circle -> sub-mode selection ===")

        QUICK_CIRCLE_TARGETS = [
            ("HAND_LEFT", "presentation"),
            ("HAND_RIGHT", "call"),
            ("HAND_UP", "flip"),
            ("HAND_DOWN", "cursor")
        ]

        for swipe_signal, target_mode in QUICK_CIRCLE_TARGETS:

            signal_mapper.clear_mode()

            gesture("HAND_SESSION_START")

            assert signal_mapper.current_mode == "quick_circle", (
                "HAND_SESSION_START did not enter quick_circle mode"
            )

            gesture(swipe_signal)

            ok = signal_mapper.current_mode == target_mode

            status = "PASS" if ok else "FAIL"

            results.append(
                (f"quick circle: {swipe_signal} -> {target_mode}", ok, [])
            )

            print(
                f"[{status}] quick circle: {swipe_signal} -> "
                f"{target_mode} (got: {signal_mapper.current_mode})"
            )

        signal_mapper.clear_mode()

        # =====================================
        # SUMMARY
        # =====================================

        total = len(results)

        passed = sum(1 for _, ok, _ in results if ok)

        print(f"\n{passed}/{total} passed")

        if passed != total:

            print("\nFailed:")

            for name, ok, missing in results:

                if not ok:

                    print(f"  - {name} (missing: {missing})")


if __name__ == "__main__":

    run()
