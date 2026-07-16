"""Automated regression suite — everything in one file, grouped by type.

Two kinds of tests live here:

- Pipeline/wiring tests (every class except TestVoiceSegmentation): drive the
  real CommandInterpreter -> MultimodalFusion -> SignalMapper ->
  ActionExecutor pipeline by publishing the same raw EventBus events the
  real recognizers would, with OSController mocked out (see the `pipeline`
  fixture in conftest.py). Verifies that mapping.json / fusion.json / the
  command table stay wired correctly, not gesture/face/voice recognition
  itself, and needs no camera, microphone or keyboard hardware to run.
- TestVoiceSegmentation: a unit-level check of VoskSpeechModel's VAD-driven
  utterance segmentation state machine (speech_model.py), with Vosk/Silero
  VAD themselves mocked out via scripted stand-ins — verifies the
  segmentation LOGIC (when an utterance is considered over, how fragments
  are combined), not real speech recognition accuracy.

Run: pytest tests/test_pipeline.py
"""

import json

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# Global voice commands (always active, no mode/environment required)
# ============================================================

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


class TestGlobalVoiceCommands:

    @pytest.mark.parametrize(
        "phrase, command, method",
        GLOBAL_VOICE_RULES,
        ids=[rule[0] for rule in GLOBAL_VOICE_RULES]
    )
    def test_global_voice_command(self, pipeline, phrase, command, method):

        pipeline.voice(command)

        pipeline.assert_called(method)


# ============================================================
# Face-gesture layer (alt/ctrl + face signal)
# ============================================================

FACE_LAYER_RULES = [

    ("alt", "HEAD_TILT_RIGHT", "next_track"),
    ("alt", "HEAD_TILT_LEFT", "previous_track"),
    ("alt", "MOUTH_OPEN", "media_play_pause"),
    ("alt", "DOUBLE_BLINK", "take_screenshot"),
    ("alt", "EYEBROWS_UP", "volume_up"),
    ("ctrl", "EYEBROWS_UP", "volume_down")

]


class TestFaceLayer:

    @pytest.mark.parametrize(
        "modifier, face_signal, method",
        FACE_LAYER_RULES,
        ids=[f"{rule[0]}+{rule[1]}" for rule in FACE_LAYER_RULES]
    )
    def test_face_layer_command(self, pipeline, modifier, face_signal, method):

        pipeline.key(modifier, "down")

        pipeline.face(face_signal)

        pipeline.assert_called(method)

        pipeline.key(modifier, "up")


# ============================================================
# Environments
# ============================================================

ENVIRONMENTS = [

    (
        "job search mode",
        "JOB_SEARCH_MODE",
        ["enable_do_not_disturb", "open_job_search_windows"]
    ),
    (
        "study mode",
        "STUDY_MODE",
        ["enable_do_not_disturb", "open_study_windows"]
    ),
    (
        "movie mode",
        "MOVIE_MODE",
        [
            "enable_do_not_disturb",
            "prevent_display_sleep",
            "open_tv",
            "open_netflix",
            "run_cinema_mode"
        ]
    ),
    (
        "news mode",
        "NEWS_MODE",
        ["open_news_tabs"]
    )

]


class TestEnvironments:

    @pytest.mark.parametrize(
        "phrase, command, methods",
        ENVIRONMENTS,
        ids=[env[0] for env in ENVIRONMENTS]
    )
    def test_environment_enter_actions(self, pipeline, phrase, command, methods):

        pipeline.voice(command)

        pipeline.assert_called(*methods)


# ============================================================
# Modes
# ============================================================

class TestPresentationMode:

    def test_voice_and_gesture_navigation(self, pipeline):

        pipeline.voice("PRESENTATION_MODE")

        assert pipeline.signal_mapper.current_mode == "presentation"

        pipeline.voice("NEXT_SLIDE")
        pipeline.assert_called("next_slide")

        pipeline.voice("PREVIOUS_SLIDE")
        pipeline.assert_called("previous_slide")

        pipeline.gesture("HAND_RIGHT")
        pipeline.assert_called("next_slide")

        pipeline.gesture("HAND_LEFT")
        pipeline.assert_called("previous_slide")

    # Regression: pynput can't suppress the physical arrow keypress from
    # also reaching the focused presentation app (every presentation app
    # already treats Right/Left as its own native next/previous-slide
    # shortcut) — mapping it here too used to fire BOTH the real keypress
    # and this app's own synthetic one, skipping a slide every time. See
    # tests/voice_pipeline_fixes_log.md and docs/SYSTEM_FUNCTIONS.md §2.1.
    def test_physical_arrow_keys_do_not_double_fire(self, pipeline):

        pipeline.voice("PRESENTATION_MODE")

        pipeline.key("right", "down")
        pipeline.key("right", "up")
        pipeline.assert_not_called("next_slide")

        pipeline.key("left", "down")
        pipeline.key("left", "up")
        pipeline.assert_not_called("previous_slide")


class TestFlipMode:

    def test_gestures(self, pipeline):

        pipeline.key("ctrl+shift+f", "down")
        pipeline.key("ctrl+shift+f", "up")

        assert pipeline.signal_mapper.current_mode == "flip"

        pipeline.gesture("HAND_UP")
        pipeline.assert_called("scroll_down")

        pipeline.gesture("HAND_DOWN")
        pipeline.assert_called("scroll_up")

        pipeline.gesture("HAND_RIGHT")
        pipeline.assert_called("flip_previous")

        pipeline.gesture("HAND_LEFT")
        pipeline.assert_called("flip_next")


class TestCursorMode:

    def test_gestures_and_continuous_streams(self, pipeline):

        pipeline.voice("CURSOR_MODE")

        assert pipeline.signal_mapper.current_mode == "cursor"

        pipeline.gesture("PINCH")
        pipeline.assert_called("click")

        pipeline.gesture("DOUBLE_PINCH")
        pipeline.assert_called("right_click")

        # Continuous streams bypass fusion entirely — straight from the
        # publisher to ActionExecutor.
        pipeline.stream(
            "pointer_position",
            {"x": 0.5, "y": 0.5, "source": "gesture"}
        )
        pipeline.assert_called("move_cursor_to")

        pipeline.stream(
            "pinch_drag",
            {"delta_x": 0.1, "delta_y": 0.0, "source": "gesture"}
        )
        pipeline.assert_called("scroll_by")

        pipeline.stream(
            "pinch_zoom",
            {"delta_distance": 0.2, "source": "gesture"}
        )
        pipeline.assert_called("zoom_in")


class TestCallMode:

    def test_finger_count_toggles(self, pipeline):

        pipeline.voice("CALL_MODE")

        assert pipeline.signal_mapper.current_mode == "call"

        pipeline.gesture("ONE_FINGER")
        pipeline.assert_called("toggle_mic")

        pipeline.gesture("TWO_FINGERS")
        pipeline.assert_called("toggle_camera")

        pipeline.gesture("THREE_FINGERS")
        pipeline.assert_called("toggle_call_audio")

        pipeline.gesture("FOUR_FINGERS")
        pipeline.assert_called("toggle_background_blur")


QUICK_CIRCLE_TARGETS = [

    ("HAND_LEFT", "presentation"),
    ("HAND_RIGHT", "call"),
    ("HAND_UP", "flip"),
    ("HAND_DOWN", "cursor")

]


class TestQuickCircle:

    @pytest.mark.parametrize(
        "swipe_signal, target_mode",
        QUICK_CIRCLE_TARGETS,
        ids=[target[1] for target in QUICK_CIRCLE_TARGETS]
    )
    def test_selects_mode(self, pipeline, swipe_signal, target_mode):

        pipeline.gesture("HAND_SESSION_START")

        assert pipeline.signal_mapper.current_mode == "quick_circle"

        pipeline.gesture(swipe_signal)

        assert pipeline.signal_mapper.current_mode == target_mode


class TestTryMode:

    def test_toggle_via_voice(self, pipeline):

        pipeline.voice("TRY_MODE")
        assert pipeline.signal_mapper.try_mode_active is True

        pipeline.voice("TRY_MODE")
        assert pipeline.signal_mapper.try_mode_active is False

    def test_toggle_via_keyboard(self, pipeline):

        pipeline.key("ctrl+shift+t", "down")
        assert pipeline.signal_mapper.try_mode_active is True
        pipeline.key("ctrl+shift+t", "up")

        pipeline.key("ctrl+shift+t", "down")
        assert pipeline.signal_mapper.try_mode_active is False
        pipeline.key("ctrl+shift+t", "up")

    def test_toggle_via_ui(self, pipeline):

        pipeline.ui("TRY_MODE")
        assert pipeline.signal_mapper.try_mode_active is True

    def test_suppresses_real_commands_while_active(self, pipeline):

        pipeline.voice("TRY_MODE")

        pipeline.voice("OPEN_BROWSER")
        pipeline.assert_not_called("open_browser")

    def test_suppresses_continuous_streams_while_active(self, pipeline):

        pipeline.voice("CURSOR_MODE")
        pipeline.voice("TRY_MODE")

        pipeline.stream(
            "pointer_position",
            {"x": 0.5, "y": 0.5, "source": "gesture"}
        )
        pipeline.assert_not_called("move_cursor_to")

        pipeline.stream(
            "pinch_drag",
            {"delta_x": 0.1, "delta_y": 0.0, "source": "gesture"}
        )
        pipeline.assert_not_called("scroll_by")

        pipeline.stream(
            "pinch_zoom",
            {"delta_distance": 0.2, "source": "gesture"}
        )
        pipeline.assert_not_called("zoom_in")

    # Regression: Cursor mode + Try Mode used to fall back to the
    # laser-pointer overlay dot instead of the real cursor — reasonable in
    # isolation, but PointerOverlay draws on the PRIMARY screen whenever no
    # second display is connected, the same screen (and same normalized
    # position) the real cursor would have moved to, so a same-looking dot
    # moving there reads as "the cursor is moving" even in Try Mode. Cursor
    # mode's Pointing_Up must produce NEITHER real movement NOR the overlay
    # dot — only the camera preview's own caption.
    def test_cursor_mode_pointer_produces_no_overlay_dot_either(self, pipeline):

        overlay_events = []

        pipeline.event_bus.subscribe(
            "pointer_overlay_update",
            lambda event: overlay_events.append(event)
        )

        pipeline.voice("CURSOR_MODE")
        pipeline.voice("TRY_MODE")

        pipeline.stream(
            "pointer_position",
            {"x": 0.5, "y": 0.5, "source": "gesture"}
        )

        pipeline.assert_not_called("move_cursor_to")

        assert overlay_events == [], (
            f"expected no pointer_overlay_update while Try Mode is active "
            f"in Cursor mode, got: {overlay_events}"
        )

    # Try Mode is independent of current_mode — it must stay on while the
    # user switches between the exclusive modes, to demonstrate them.
    def test_coexists_with_regular_mode(self, pipeline):

        pipeline.voice("TRY_MODE")
        pipeline.voice("PRESENTATION_MODE")

        assert pipeline.signal_mapper.try_mode_active is True
        assert pipeline.signal_mapper.current_mode == "presentation"

    def test_exit_mode_turns_off_try_mode_too(self, pipeline):

        pipeline.voice("TRY_MODE")
        pipeline.voice("PRESENTATION_MODE")

        pipeline.voice("EXIT_MODE")

        assert pipeline.signal_mapper.try_mode_active is False
        assert pipeline.signal_mapper.current_mode is None

    def test_exit_mode_turns_off_try_mode_with_no_active_mode(self, pipeline):

        pipeline.voice("TRY_MODE")

        pipeline.voice("EXIT_MODE")

        assert pipeline.signal_mapper.try_mode_active is False


# ============================================================
# Voice pipeline segmentation (VoskSpeechModel, mocked Vosk/Silero VAD)
#
# Unit-level, not pipeline-level — these don't use the `pipeline` fixture
# above at all. Verifies the VAD-driven utterance-boundary state machine
# described in speech_model.py's module docstring: an utterance is only
# considered over once real silence is confirmed by a continuous VAD
# stream, not by Vosk's own (possibly mid-sentence) endpoint decisions.
# ============================================================

class _FakeRecognizer:
    """Scripted stand-in for vosk.KaldiRecognizer.

    accept_script: one bool per AcceptWaveform() call.
    result_script: one result-text string per True in accept_script,
    consumed in order.
    """

    def __init__(self, accept_script, result_script):

        self.accept_script = list(accept_script)
        self.result_script = list(result_script)
        self.calls = 0

    def AcceptWaveform(self, chunk):

        value = self.accept_script[self.calls]
        self.calls += 1
        return value

    def Result(self):

        return json.dumps({"text": self.result_script.pop(0)})

    def PartialResult(self):

        return json.dumps({"partial": ""})


def _build_speech_model(accept_script, result_script, speech_script, hangover_ms=900, vad_enabled=True):
    """Builds a VoskSpeechModel with Vosk/Silero fully mocked out, and a
    scripted streaming-VAD decision per process_audio() call. Returns
    (model, run) where run() drives accept_script's length worth of
    0.5s-spaced chunks through process_audio() and returns the list of
    results.
    """

    patchers = [
        patch("processing.speech.speech_model.Model"),
        patch("processing.speech.speech_model.KaldiRecognizer"),
        patch("processing.speech.speech_model.load_silero_vad"),
        patch("processing.speech.speech_model.load_system_config"),
        patch("processing.speech.speech_model.load_mapping_config"),
        patch(
            "processing.speech.speech_model.resolve_model_path",
            side_effect=lambda p: p
        ),
    ]

    mocks = [p.start() for p in patchers]

    (
        mock_model_cls,
        mock_kaldi_cls,
        mock_load_vad,
        mock_sys_cfg,
        mock_map_cfg,
        _mock_resolve
    ) = mocks

    mock_map_cfg.return_value = {"voice": {"OPEN_BROWSER": "open browser"}}

    mock_sys_cfg.return_value = {
        "audio": {"sample_rate": 16000},
        "wake_word": "jack",
        "vad_enabled": vad_enabled,
        "vad_threshold": 0.65,
        "vad_min_speech_duration_ms": 300,
        "vad_silence_hangover_ms": hangover_ms,
        "nlu_fallback": {"enabled": False},
    }

    mock_kaldi_cls.return_value = _FakeRecognizer(accept_script, result_script)
    mock_load_vad.return_value = MagicMock()

    from processing.speech.speech_model import VoskSpeechModel

    model = VoskSpeechModel()

    speech_iter = iter(speech_script)
    model._chunk_has_speech = lambda chunk: next(speech_iter)

    # Whole-buffer post-hoc content gate: always "some speech present" —
    # this test suite is about segmentation TIMING, not that gate.
    model._speech_timestamps = lambda audio: [{"start": 0, "end": 1}]

    def run():

        results = []
        chunk_timestamp = 0.0

        for _ in accept_script:

            results.append(
                model.process_audio(b"\x00\x00" * 100, chunk_timestamp=chunk_timestamp)
            )

            chunk_timestamp += 0.5

        return results

    for p in patchers:
        p.stop()

    return model, run


class TestVoiceSegmentation:

    # The original bug: Vosk's own grammar decoder can flush a Result()
    # mid-sentence on a longer phrase, well before the person is actually
    # done talking — that used to be treated as the whole utterance being
    # over, splitting one spoken command into independent fragments with
    # their own (unreliable) chance to catch the wake word. Two Vosk
    # finalizations here, with the streaming VAD saying speech is still
    # ongoing through both, must NOT produce a result until real silence
    # is confirmed — and the fragments must be combined into one text.
    def test_mid_utterance_vosk_finalize_does_not_end_utterance(self):

        _model, run = _build_speech_model(
            accept_script=[True, True, False, False, False],
            result_script=["jack cursor", "mode please"],
            speech_script=[True, True, True, False, False],
            hangover_ms=900,
        )

        results = run()

        assert results[0] is None
        assert results[1] is None
        assert results[2] is None
        assert results[3] is None, "premature finalize before hangover elapsed"

        assert results[4] is not None
        assert results[4]["text"] == "jack cursor mode please"
        assert results[4]["is_final"] is True
        assert results[4]["wake_word_heard"] is True

    def test_short_utterance_finalizes_after_hangover(self):

        _model, run = _build_speech_model(
            accept_script=[True, False],
            result_script=["open browser"],
            speech_script=[True, False, False],
            hangover_ms=400,
        )

        results = run()

        assert results[0] is None
        assert results[1] is not None
        assert results[1]["text"] == "open browser"

    # Graceful degradation: with no independent VAD signal to hang a
    # hangover timer off of, Vosk's own AcceptWaveform() boolean must be
    # trusted directly, same as before this rework — not hang forever
    # waiting for a hangover that never gets a chance to elapse.
    def test_vad_disabled_falls_back_to_vosk_endpoint(self):

        _model, run = _build_speech_model(
            accept_script=[True],
            result_script=["open browser"],
            speech_script=[False],
            vad_enabled=False,
        )

        results = run()

        assert results[0] is not None
        assert results[0]["text"] == "open browser"
