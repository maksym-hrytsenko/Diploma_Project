# Stress Testing

Two distinct things fall under "stress testing" in this project, answering
two different questions, so they're kept as two sections below rather than
merged: whether the system stays **functionally stable** under rapid or
unusual input patterns, and how much **CPU/memory it actually consumes**
under sustained synthetic load. Both complement
[`TESTING_MANUAL_FUNCTIONAL.md`](TESTING_MANUAL_FUNCTIONAL.md) and
[`TESTING_REGRESSION.md`](TESTING_REGRESSION.md), which cover correctness,
not stability or resource cost.

## 1. Functional stress / edge cases

The authoritative scenario list is §10 of
[`../tests/MANUAL_TEST_SCENARIOS.md`](../tests/MANUAL_TEST_SCENARIOS.md#10-stress--edge-cases)
(16 scenarios) — reference, not duplicated, for the same reason given in
`TESTING_MANUAL_FUNCTIONAL.md`. Grading is binary, but on a different
criterion than the rest of the manual scenarios: success means the system
stays in a consistent, running state after the stress condition — it must
not get permanently stuck in an active mode, and the process must not
crash — not how accurately it recognized the input during the stress.

| § | Scenario |
|---|---|
| 10.1 | Rapid mode switching |
| 10.2 | Simultaneous multi-modal signals |
| 10.3 | Quick Circle rapid open/close |
| 10.4 | Persistent modifier key held through unrelated signals |
| 10.5 | System OFF mid-mode |
| 10.6 | Input module disabled mid-use |
| 10.7 | Rapid UI clicking |
| 10.8 | Hand leaving frame during a Call-mode toggle hold |
| 10.9 | Packaged `.app` regression check: no duplicate process spawning |
| 10.10 | Extended idle soak |
| 10.11 | Boundary timing: gesture confirmation debounce |
| 10.12 | Boundary timing: double-pinch window |
| 10.13 | Boundary timing: Call-mode toggle hold |
| 10.14 | Rapid switching between an environment and a mode |

As with the rest of the manual checklist, these were run against the
system during development and are consistent with its current working
state, but no separate dated per-row result log exists beyond the
checklist itself — see the same caveat in
[`TESTING_MANUAL_FUNCTIONAL.md`](TESTING_MANUAL_FUNCTIONAL.md#gestures-face-environments-ui-try-mode--qualitative-status).

## 2. Resource load benchmarks

Tooling: [`../tests/benchmarks/resource_monitor.py`](../tests/benchmarks/resource_monitor.py)
and [`run_stress_suite.py`](../tests/benchmarks/run_stress_suite.py).

### Methodology

`resource_monitor.py` samples CPU time and resident memory (RSS) for the
application's entire process tree — the main `main.py` process plus every
child process the hybrid speech recognizer spawns (semantic/LLM fallback
workers, the open-vocabulary Whisper worker) — at a regular interval,
keyed to specific PIDs so background load from unrelated apps doesn't
skew the numbers. Sampling starts 15 seconds after launch so the one-time
model warm-up cost (Vosk, MediaPipe, the semantic layer's embedding model)
doesn't pull the result toward a worse number than steady-state use.

To keep runs repeatable and independent of live speech/gesture
variability, `SyntheticMicrophoneInput`/`SyntheticCameraInput` stand in for
the real hardware — same interface as the production input classes,
publishing the same `audio_chunk`/`camera_frame` bus events, just sourced
from a pre-recorded capture instead of live hardware. The voice source is
the same synthesized (`say`, Samantha) 113-phrase catalog used for QA
regression in `TESTING_MANUAL_FUNCTIONAL.md`; the gesture/face source is a
~140-second recording of a real hand and face performing the system's full
set of gestures and expressions. Because the rest of the pipeline
(recognition, fusion, decision logic) is unchanged, this measures the real
cost of the recognition models, not just cheap downstream logic.

Since the suite replays commands that would otherwise have real side
effects (launching apps, media control), `ActionExecutor` runs with a
`force_dry_run` flag — independent of and always-on regardless of Try
Mode, which was found to auto-disable itself on `exit mode`, a command the
suite issues repeatedly.

**Test machine:** MacBook Air, Apple M5 (10 cores — 4 performance + 6
efficiency), 16 GB RAM, macOS 26.5.1. Absolute numbers below are specific
to this hardware; the relative comparison between scenarios is not.

### Scenarios

- **`idle_baseline`** — app running with no activity (camera on a static
  scene, silence) — the baseline "always-on" cost.
- **`speech_synthetic_1x`** — the full voice catalog at real-time pace,
  camera off — isolated cost of the voice chain, including fallback
  outside the exact-match grammar.
- **`speech_synthetic_4x_loop3`** — the same catalog at 4× speed, looped 3
  times — more recognition cycles in less wall-clock time, to estimate a
  possible memory leak without needing an hour-long run.
- **`camera_gesture_only`** — the gesture/face recording looped 6 times,
  voice silent — isolated cost of gesture and face recognition.
- **`combined_worst_case`** — the voice catalog at real-time pace running
  simultaneously with the looping gesture recording — the heaviest
  concurrent scenario.

### Results

Reproduced from the raw per-scenario CSVs in
[`../tests/benchmarks/results/20260717_223137/`](../tests/benchmarks/results/20260717_223137/)
(`elapsed_seconds,cpu_percent,rss_mb,process_count`, sampled roughly every
0.5 s — e.g. 120 rows for the 60-second `idle_baseline` run).

| Scenario | Duration (s) | CPU (% of machine) avg/max | CPU (% of one core) avg/max | RAM (MB) avg/max | Peak processes |
|---|---|---|---|---|---|
| `idle_baseline` | 60.0 | 6.0 / 6.9 | 60.1 / 68.9 | 891.7 / 953.9 | 1 |
| `speech_synthetic_1x` | 1399.7 | 0.3 / 1.9 | 2.6 / 18.8 | 637.6 / 2033.5 | 7 |
| `speech_synthetic_4x_loop3` | 1100.0 | 0.9 / 10.0 | 8.9 / 99.9 | 518.4 / 2347.4 | 9 |
| `camera_gesture_only` | 899.8 | 7.1 / 9.3 | 71.4 / 92.9 | 1204.9 / 1556.5 | 1 |
| `combined_worst_case` | 1299.9 | 4.0 / 5.3 | 39.6 / 52.9 | 943.4 / 2158.6 | 4 |

### Evaluation

- **Idle cost (`idle_baseline`)** is the always-on tax for the app simply
  running — 6.0% of the ten-core machine and under 1 GB RAM for camera and
  microphone listening with nothing happening. For a tool meant to run in
  the background all day, this is unlikely to be noticeable during normal
  use.
- **Voice** is nearly maintenance-free on average (0.3–0.9% of the
  machine), but the semantic/LLM fallback produces short spikes up to a
  full core (99.9% of one core in the sped-up scenario) and memory up to
  2.3 GB. Since it's a single-core spike lasting a few seconds, this is an
  expected, bounded cost of being able to understand phrasing outside the
  exact grammar, not a performance problem.
- **Gesture and face recognition together** show the highest *sustained*
  load of any single-modality scenario — 71.4% of one core for the whole
  run, well above the idle baseline's 60.1%. Continuous per-frame
  MediaPipe inference is more expensive in steady state than voice
  recognition, though the absolute machine-wide figure (7.1%) stays low.
- **The combined scenario shows lower average load (4.0%) than gesture
  alone (7.1%)** — counterintuitive for the scenario labeled heaviest. The
  machine's state immediately before this run (26.7% system CPU, load
  average 2.06) shows it was already partly loaded by something else,
  which may have capped the process's available throughput; it's also
  possible the gesture chain processed fewer frames per second under
  contention, so the lower number reflects less work done rather than a
  lower per-frame cost. Without repeated measurements on an otherwise idle
  machine, these two explanations can't be distinguished — an open
  question for further verification, not a settled conclusion.
- **Memory is not a risk in any scenario** — the highest recorded value
  (2347.4 MB) is under a sixth of the available 16 GB.
- These numbers come from **one run per scenario**, with the sped-up
  scenario substituting for a real hour-long run — so the "no memory leak"
  conclusion above should be read as preliminary, not definitively proven.
