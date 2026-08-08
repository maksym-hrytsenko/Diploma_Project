# Automated Regression Testing

Deterministic-logic regression suite: `pytest tests/test_pipeline.py`, run
from `project/`. No camera, microphone, or macOS permissions are required —
every test drives the real `CommandInterpreter -> MultimodalFusion ->
SignalMapper -> ActionExecutor` chain by publishing the same kind of
synthetic events on the event bus that a real recognizer would, with
`OSController` replaced by a mock. See
[`../src/processing`](../src/processing) for the modules under test and
[`ARCHITECTURE.md`](ARCHITECTURE.md) for how the bus/fusion/decision chain
fits together.

## Why binary grading

`SignalMapper` is deterministic: for a given set of input signals,
`fusion.json`/`mapping.json` define exactly one correct resulting action or
mode transition. Any deviation from that expected result is a
configuration-wiring bug, not recognition uncertainty — a graded score
("almost correct") would hide such a bug instead of surfacing it. This is
the same reasoning that gives the probabilistic recognizers (voice,
gesture, face) a 3-point scale instead — see
[`TESTING_MANUAL_FUNCTIONAL.md`](TESTING_MANUAL_FUNCTIONAL.md).

## Structure — 56 test cases across 10 classes

| Test class | Cases | Covers |
|---|---|---|
| `TestGlobalVoiceCommands` | 26 (parametrized) | 19 app-launch phrases + `start`/`stop`/`pause`/`reset`/`next track`/`previous track`, resolved through the interpreter |
| `TestFaceLayer` | 5 (parametrized) | `alt`/`ctrl` + `HEAD_TILT_RIGHT`/`HEAD_TILT_LEFT`/`MOUTH_OPEN`/`EYEBROWS_UP` combinations |
| `TestEnvironments` | 5 (parametrized) | Enter-actions for Work, Job Search, Study, Movie, News |
| `TestPresentationMode` | 2 | Voice/gesture slide navigation; regression check that physical arrow keys don't double-fire a slide change |
| `TestFlipMode` | 1 | Directional swipe gestures |
| `TestCursorMode` | 1 | Pointer tracking, click, drag/scroll, right-click, continuous streams |
| `TestCallMode` | 1 | Finger-count toggles |
| `TestQuickCircle` | 4 (parametrized) | Gesture-only mode selection: presentation / call / flip / cursor |
| `TestTryMode` | 9 | Every toggle path, real-action suppression, coexistence with a regular mode, `exit mode` also turning it off |
| `TestVoiceSegmentation` | 3 | The utterance-boundary state machine, with mocked Vosk/Silero VAD driven by a scripted scenario |

## Results (reproducible)

Run from `project/`:

```
pytest tests/test_pipeline.py -v
```

Last run:

```
============================= test session starts ==============================
platform darwin -- Python 3.10.13, pytest-9.1.1, pluggy-1.6.0
collected 56 items

tests/test_pipeline.py::TestGlobalVoiceCommands::test_global_voice_command[...] PASSED  (×26)
tests/test_pipeline.py::TestFaceLayer::test_face_layer_command[...] PASSED              (×5)
tests/test_pipeline.py::TestEnvironments::test_environment_enter_actions[...] PASSED    (×5)
tests/test_pipeline.py::TestPresentationMode::test_voice_and_gesture_navigation PASSED
tests/test_pipeline.py::TestPresentationMode::test_physical_arrow_keys_do_not_double_fire PASSED
tests/test_pipeline.py::TestFlipMode::test_gestures PASSED
tests/test_pipeline.py::TestCursorMode::test_gestures_and_continuous_streams PASSED
tests/test_pipeline.py::TestCallMode::test_finger_count_toggles PASSED
tests/test_pipeline.py::TestQuickCircle::test_selects_mode[...] PASSED                  (×4)
tests/test_pipeline.py::TestTryMode::test_* PASSED                                      (×9)
tests/test_pipeline.py::TestVoiceSegmentation::test_* PASSED                            (×3)

============================== 56 passed in 1.10s ==============================
```

All 56 cases pass, with no skips or expected failures. Because the suite is
fully synthetic (no hardware, no timing dependent on a real recognizer), a
re-run on any machine with the project's Python environment should
reproduce the same result.
