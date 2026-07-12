"""Regression suite for the command pipeline's config/wiring.

Drives the real pipeline (CommandInterpreter -> MultimodalFusion ->
SignalMapper -> ActionExecutor) by publishing the same raw EventBus events
the real recognizers would, with OSController mocked out. Verifies that
mapping.json / fusion.json / the command table stay wired correctly, not
gesture/face/voice recognition itself, and needs no camera, microphone or
keyboard hardware to run.

Run: pytest tests/test_command_pipeline.py
"""

import pytest


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

FACE_LAYER_RULES = [

    ("alt", "HEAD_TILT_RIGHT", "next_track"),
    ("alt", "HEAD_TILT_LEFT", "previous_track"),
    ("alt", "MOUTH_OPEN", "media_play_pause"),
    ("alt", "DOUBLE_BLINK", "take_screenshot"),
    ("alt", "EYEBROWS_UP", "volume_up"),
    ("ctrl", "EYEBROWS_UP", "volume_down")

]

ENVIRONMENTS = [

    (
        "job search mode",
        "JOB_SEARCH_MODE",
        [
            "enable_do_not_disturb",
            "open_job_search_windows"
        ]
    ),
    (
        "study mode",
        "STUDY_MODE",
        [
            "enable_do_not_disturb",
            "open_study_windows"
        ]
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
        [
            "open_news_tabs"
        ]
    )

]

QUICK_CIRCLE_TARGETS = [

    ("HAND_LEFT", "presentation"),
    ("HAND_RIGHT", "call"),
    ("HAND_UP", "flip"),
    ("HAND_DOWN", "cursor")

]


@pytest.mark.parametrize(
    "phrase, command, method",
    GLOBAL_VOICE_RULES,
    ids=[rule[0] for rule in GLOBAL_VOICE_RULES]
)
def test_global_voice_command(
    pipeline,
    phrase,
    command,
    method
):

    pipeline.voice(command)

    pipeline.assert_called(method)


@pytest.mark.parametrize(
    "modifier, face_signal, method",
    FACE_LAYER_RULES,
    ids=[
        f"{rule[0]}+{rule[1]}"
        for rule in FACE_LAYER_RULES
    ]
)
def test_face_layer_command(
    pipeline,
    modifier,
    face_signal,
    method
):

    pipeline.key(modifier, "down")

    pipeline.face(face_signal)

    pipeline.assert_called(method)

    pipeline.key(modifier, "up")


@pytest.mark.parametrize(
    "phrase, command, methods",
    ENVIRONMENTS,
    ids=[env[0] for env in ENVIRONMENTS]
)
def test_environment_enter_actions(
    pipeline,
    phrase,
    command,
    methods
):

    pipeline.voice(command)

    pipeline.assert_called(*methods)


def test_presentation_mode(pipeline):

    pipeline.voice("PRESENTATION_MODE")

    assert pipeline.signal_mapper.current_mode == "presentation"

    pipeline.voice("NEXT_SLIDE")
    pipeline.assert_called("next_slide")

    pipeline.voice("PREVIOUS_SLIDE")
    pipeline.assert_called("previous_slide")

    pipeline.key("right", "down")
    pipeline.key("right", "up")
    pipeline.assert_called("next_slide")

    pipeline.key("left", "down")
    pipeline.key("left", "up")
    pipeline.assert_called("previous_slide")

    pipeline.gesture("HAND_RIGHT")
    pipeline.assert_called("next_slide")

    pipeline.gesture("HAND_LEFT")
    pipeline.assert_called("previous_slide")


def test_flip_mode(pipeline):

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


def test_cursor_mode(pipeline):

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


def test_call_mode(pipeline):

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


@pytest.mark.parametrize(
    "swipe_signal, target_mode",
    QUICK_CIRCLE_TARGETS,
    ids=[target[1] for target in QUICK_CIRCLE_TARGETS]
)
def test_quick_circle_selects_mode(
    pipeline,
    swipe_signal,
    target_mode
):

    pipeline.gesture("HAND_SESSION_START")

    assert pipeline.signal_mapper.current_mode == "quick_circle"

    pipeline.gesture(swipe_signal)

    assert pipeline.signal_mapper.current_mode == target_mode
