"""Runs every load-benchmark scenario back to back, unattended, and writes
each scenario's results into its own clearly separated output folder.

Each scenario launches `python src/main.py` with `--try-mode` (so any
simulated command never reaches the real OS) plus whatever synthetic-input
flags the scenario needs, waits out a warm-up period (model loading), then
reuses resource_monitor.py's own sampling loop unchanged to record CPU/RAM
until the process exits on its own (synthetic-audio/-camera scenarios stop
themselves once every active recording finishes) or a safety duration cap
is hit (idle_baseline and combined_worst_case, which never stop
themselves -- see their comments below).

Output layout, one folder per scenario:

    tests/benchmarks/results/<run_id>/<scenario_name>/
        resource.csv   -- from resource_monitor.run_monitor, unchanged format
        app.log        -- just this scenario's slice of logs/app.log
        summary.txt     -- scenario params + avg/max CPU/RAM for this run

    tests/benchmarks/results/<run_id>/overview.txt -- one row per scenario

Usage:
    python tests/benchmarks/run_stress_suite.py
    python tests/benchmarks/run_stress_suite.py --only idle_baseline
    python tests/benchmarks/run_stress_suite.py --resume 20260717_223137

--resume <run_id> reuses an existing tests/benchmarks/results/<run_id> folder
instead of starting a fresh one -- any scenario that already has a
non-empty resource.csv there is treated as done (its stats are read back
from that CSV, not re-measured) and only whatever didn't finish last time
actually gets launched again. Exists because this suite runs long enough
(the full set is close to an hour) to plausibly get interrupted partway
through by something outside the script's control -- closing the terminal
it was running in, the machine sleeping, etc.
"""

import argparse
import csv
import os
import subprocess
import sys
import time

import psutil

from resource_monitor import run_monitor


BENCHMARKS_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_ROOT = os.path.dirname(
    BENCHMARKS_DIR
)

MAIN_SCRIPT = os.path.join(
    PROJECT_ROOT,
    "src",
    "main.py"
)

APP_LOG_PATH = os.path.join(
    PROJECT_ROOT,
    "logs",
    "app.log"
)

SYNTH_AUDIO_PATH = os.path.join(
    PROJECT_ROOT,
    "tests",
    "synthesized_voice",
    "voice_test_synthesized.m4a"
)

# Recorded via tests/benchmarks/record_gesture_sample.py -- doesn't exist until
# that's actually been run once; scenarios that need it are skipped
# cleanly (not a crash) until then, see run_scenario's "requires" check.
SYNTH_GESTURE_PATH = os.path.join(
    PROJECT_ROOT,
    "tests",
    "synthesized_gesture",
    "gesture_sample.mp4"
)


# Natural length of the voice recording at speed 1x, loops=1 (see
# tests/synthesized_voice/GUIDE.md) is ~1219s; the gesture recording at
# speed 1x, loops=1 (see record_gesture_sample.py's BEATS) is ~139s.
# max_duration below always leaves headroom above what a self-terminating
# scenario needs so it never gets cut off under normal conditions -- the
# cap exists to bound the two scenarios that don't stop themselves
# (idle_baseline, combined_worst_case) and to guard against a stuck
# process in the others.
SCENARIOS = [

    {
        "name": "idle_baseline",
        "description": (
            "App running, camera pointed at a static scene, silence -- "
            "baseline load with no active recognition."
        ),
        "extra_args": [],
        "sample_interval": 0.5,
        "max_duration": 60,
        "warmup_seconds": 15,
        "requires": []
    },

    {
        "name": "speech_synthetic_1x",
        "description": (
            "Synthesized voice session (113 commands) at real-time pace, "
            "camera off -- isolated load on the speech pipeline, including "
            "fallback commands outside the exact grammar."
        ),
        "extra_args": [
            "--disable-camera",
            "--synthetic-audio", SYNTH_AUDIO_PATH,
            "--synthetic-audio-speed", "1.0",
            "--synthetic-audio-loops", "1"
        ],
        "sample_interval": 0.3,
        "max_duration": 1400,
        "warmup_seconds": 15,
        "requires": [SYNTH_AUDIO_PATH]
    },

    {
        "name": "speech_synthetic_4x_loop3",
        "description": (
            "The same session 4x faster, looped 3 times -- more "
            "recognition cycles in less time, to check for memory leaks "
            "without a full hour-long run."
        ),
        "extra_args": [
            "--disable-camera",
            "--synthetic-audio", SYNTH_AUDIO_PATH,
            "--synthetic-audio-speed", "4.0",
            "--synthetic-audio-loops", "3"
        ],
        "sample_interval": 0.3,
        "max_duration": 1100,
        "warmup_seconds": 15,
        "requires": [SYNTH_AUDIO_PATH]
    },

    {
        "name": "camera_gesture_only",
        "description": (
            "Recorded gesture/face session (~2.3 min) looped 6 times, "
            "voice silent -- isolated load on the gesture+face pipeline."
        ),
        "extra_args": [
            "--synthetic-camera", SYNTH_GESTURE_PATH,
            "--synthetic-camera-speed", "1.0",
            "--synthetic-camera-loops", "6"
        ],
        "sample_interval": 0.3,
        "max_duration": 900,
        "warmup_seconds": 15,
        "requires": [SYNTH_GESTURE_PATH]
    },

    {
        "name": "combined_worst_case",
        "description": (
            "Synthesized voice session (real-time pace, single pass) "
            "at the same time as a recorded gesture/face session looping "
            "the whole time -- the heaviest concurrent scenario. The "
            "camera is deliberately looped for much longer than the voice "
            "session (200 loops) and never finishes on its own -- this "
            "scenario always stops via max_duration, never by itself."
        ),
        "extra_args": [
            "--synthetic-audio", SYNTH_AUDIO_PATH,
            "--synthetic-audio-speed", "1.0",
            "--synthetic-audio-loops", "1",
            "--synthetic-camera", SYNTH_GESTURE_PATH,
            "--synthetic-camera-speed", "1.0",
            "--synthetic-camera-loops", "200"
        ],
        "sample_interval": 0.3,
        "max_duration": 1300,
        "warmup_seconds": 15,
        "requires": [SYNTH_AUDIO_PATH, SYNTH_GESTURE_PATH]
    }

]


def parse_args():

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--only",
        default=None,
        help="Run a single scenario by name instead of the full list."
    )

    parser.add_argument(
        "--resume",
        default=None,
        help=(
            "Reuse an existing tests/benchmarks/results/<run_id> folder -- "
            "scenarios that already have data there are skipped, not "
            "re-run. Pass just the <run_id> (the folder name), e.g. "
            "20260717_223137."
        )
    )

    return parser.parse_args()


def _log_size():

    if not os.path.exists(APP_LOG_PATH):
        return 0

    return os.path.getsize(
        APP_LOG_PATH
    )


def _copy_log_slice(
    start_offset,
    dest_path
):

    if not os.path.exists(APP_LOG_PATH):
        return

    with open(APP_LOG_PATH, "rb") as f:

        f.seek(start_offset)

        data = f.read()

    with open(dest_path, "wb") as f:

        f.write(data)


def _missing_inputs(scenario):

    return [
        path for path in scenario.get("requires", [])
        if not os.path.exists(path)
    ]


# A scenario counts as already done (for --resume) only if it left behind
# real sampled data, not just a header row -- a scenario that was
# previously skipped for a missing input, or that crashed before the
# first sample, must still be attempted again.
def _scenario_has_data(scenario_dir):

    csv_path = os.path.join(
        scenario_dir,
        "resource.csv"
    )

    if not os.path.exists(csv_path):
        return False

    with open(csv_path, encoding="utf-8") as f:

        row_count = sum(1 for _ in f)

    return row_count > 1


def _read_samples_csv(csv_path):

    samples = []

    with open(csv_path, encoding="utf-8") as f:

        reader = csv.reader(f)

        next(reader, None)

        for row in reader:

            samples.append((
                float(row[0]),
                float(row[1]),
                float(row[2]),
                int(row[3])
            ))

    return samples


# resource_monitor's own sampling (process.cpu_percent() on the app's PID
# and its children) already only ever measures this app's own process
# tree, never anything else running on the machine -- psutil attributes
# CPU time per-process, so another app open in the background can't
# inflate these numbers. What it can't capture is the ambient *context* a
# given run happened in (was the machine already busy, already warm from
# the previous scenario in this same suite run) -- recorded here, once
# per scenario, purely so an anomalous result can later be explained
# rather than silently trusted or silently distrusted.
def _system_snapshot():

    system_cpu_percent = psutil.cpu_percent(
        interval=0.5
    )

    virtual_memory = psutil.virtual_memory()

    load_1min, load_5min, _ = os.getloadavg()

    return {
        "system_cpu_percent": system_cpu_percent,
        "system_ram_used_pct": virtual_memory.percent,
        "system_ram_available_mb": virtual_memory.available / (1024 * 1024),
        "loadavg_1min": load_1min,
        "loadavg_5min": load_5min
    }


def _compute_stats(
    samples,
    core_count
):

    if not samples:
        return None

    cpu_values = [row[1] for row in samples]

    rss_values = [row[2] for row in samples]

    process_counts = [row[3] for row in samples]

    cpu_avg = sum(cpu_values) / len(cpu_values)

    cpu_max = max(cpu_values)

    return {
        "duration_s": samples[-1][0],
        "cpu_avg_pct_of_core": cpu_avg,
        "cpu_max_pct_of_core": cpu_max,
        "cpu_avg_pct_of_machine": cpu_avg / core_count,
        "cpu_max_pct_of_machine": cpu_max / core_count,
        "ram_avg_mb": sum(rss_values) / len(rss_values),
        "ram_max_mb": max(rss_values),
        "process_count_max": max(process_counts)
    }


def _write_summary(
    scenario,
    scenario_dir,
    stats,
    error_message=None,
    ambient=None
):

    path = os.path.join(
        scenario_dir,
        "summary.txt"
    )

    with open(path, "w", encoding="utf-8") as f:

        f.write(f"{scenario['name']}\n")

        f.write(f"{scenario['description']}\n\n")

        f.write(
            "main.py args: --try-mode --debug-voice "
            + " ".join(scenario["extra_args"])
            + "\n"
        )

        f.write(
            f"sample_interval: {scenario['sample_interval']}s   "
            f"max_duration: {scenario['max_duration']}s   "
            f"warmup: {scenario['warmup_seconds']}s\n\n"
        )

        if ambient is not None:

            f.write(
                "Machine state immediately BEFORE this scenario started "
                "(does not affect the measurements below -- those are "
                "already isolated per-process -- this is just context, so "
                "an anomaly can be explained after the fact):\n"
            )

            f.write(
                f"  system CPU: {ambient['system_cpu_percent']:5.1f}%   "
                f"RAM used: {ambient['system_ram_used_pct']:5.1f}%   "
                f"RAM free: {ambient['system_ram_available_mb']:7.0f} MB\n"
            )

            f.write(
                f"  load average (1min/5min): "
                f"{ambient['loadavg_1min']:.2f} / {ambient['loadavg_5min']:.2f}\n\n"
            )

        if stats is None:

            f.write(
                f"SKIPPED/ERROR: {error_message}\n"
            )

            return

        f.write(
            f"Measurement duration: {stats['duration_s']:.1f}s\n"
        )

        f.write(
            f"CPU  avg: {stats['cpu_avg_pct_of_machine']:6.1f}% "
            f"of machine   max: {stats['cpu_max_pct_of_machine']:6.1f}%\n"
        )

        f.write(
            f"     avg: {stats['cpu_avg_pct_of_core']:6.1f}% "
            f"of one core   max: {stats['cpu_max_pct_of_core']:6.1f}%\n"
        )

        f.write(
            f"RAM  avg: {stats['ram_avg_mb']:7.1f} MB   "
            f"max: {stats['ram_max_mb']:7.1f} MB\n"
        )

        f.write(
            f"Processes in tree (peak): {stats['process_count_max']}\n"
        )


def _write_overview(
    run_dir,
    rows
):

    path = os.path.join(
        run_dir,
        "overview.txt"
    )

    with open(path, "w", encoding="utf-8") as f:

        header = (
            f"{'scenario':28} {'dur.,s':>8} {'CPU avg%':>9} "
            f"{'CPU max%':>9} {'RAM avg,MB':>11} {'RAM max,MB':>11}\n"
        )

        f.write(header)

        for name, stats, note in rows:

            if stats is None:

                f.write(f"{name:28} SKIPPED: {note}\n")

                continue

            f.write(
                f"{name:28} {stats['duration_s']:8.1f} "
                f"{stats['cpu_avg_pct_of_machine']:9.1f} "
                f"{stats['cpu_max_pct_of_machine']:9.1f} "
                f"{stats['ram_avg_mb']:11.1f} {stats['ram_max_mb']:11.1f}\n"
            )

    print(f"\nOverview: {path}")


def run_scenario(
    scenario,
    run_dir,
    core_count
):

    scenario_dir = os.path.join(
        run_dir,
        scenario["name"]
    )

    os.makedirs(
        scenario_dir,
        exist_ok=True
    )

    if _scenario_has_data(scenario_dir):

        print(
            f"[{scenario['name']}] already present from a previous run -- "
            f"skipping the launch, reading the existing resource.csv."
        )

        samples = _read_samples_csv(
            os.path.join(scenario_dir, "resource.csv")
        )

        stats = _compute_stats(samples, core_count)

        # Rewrites summary.txt from the re-read data even though nothing
        # was re-measured -- catches it up with the current _write_summary
        # (e.g. a units/formatting fix made after the original run) instead
        # of leaving a stale copy sitting next to a fresh resource.csv.
        _write_summary(scenario, scenario_dir, stats)

        return stats, None

    missing = _missing_inputs(scenario)

    if missing:

        error_message = (
            "missing input file: " + ", ".join(missing)
        )

        print(f"[{scenario['name']}] SKIPPED -- {error_message}")

        _write_summary(scenario, scenario_dir, None, error_message)

        return None, error_message

    # --try-mode always comes first and is never optional here -- a
    # scenario forgetting it would mean 113 real commands hitting the real
    # OS unattended. --debug-voice is free (just more logging) and lets
    # tests/synthesized_voice/parse_tts_session.py also run against this
    # scenario's app.log slice afterward, for accuracy/latency for free.
    argv = (
        [sys.executable, MAIN_SCRIPT, "--try-mode", "--debug-voice"]
        + scenario["extra_args"]
    )

    log_offset = _log_size()

    ambient = _system_snapshot()

    print(
        f"[{scenario['name']}] starting... "
        f"(system CPU before start: {ambient['system_cpu_percent']:.0f}%)"
    )

    process = subprocess.Popen(
        argv,
        cwd=PROJECT_ROOT
    )

    time.sleep(
        scenario["warmup_seconds"]
    )

    if process.poll() is not None:

        error_message = (
            f"process exited during warm-up (code {process.returncode})"
        )

        print(f"[{scenario['name']}] ERROR: {error_message}")

        _copy_log_slice(
            log_offset,
            os.path.join(scenario_dir, "app.log")
        )

        _write_summary(scenario, scenario_dir, None, error_message, ambient)

        return None, error_message

    root_process = psutil.Process(
        process.pid
    )

    csv_path = os.path.join(
        scenario_dir,
        "resource.csv"
    )

    print(
        f"[{scenario['name']}] measuring "
        f"(interval {scenario['sample_interval']}s, "
        f"max {scenario['max_duration']}s)..."
    )

    samples = run_monitor(
        root_process,
        scenario["sample_interval"],
        scenario["max_duration"],
        csv_path
    )

    if process.poll() is None:

        process.terminate()

        try:

            process.wait(timeout=5)

        except subprocess.TimeoutExpired:

            process.kill()

    _copy_log_slice(
        log_offset,
        os.path.join(scenario_dir, "app.log")
    )

    stats = _compute_stats(
        samples,
        core_count
    )

    _write_summary(
        scenario,
        scenario_dir,
        stats,
        ambient=ambient
    )

    if stats is not None:

        print(
            f"[{scenario['name']}] finished in {stats['duration_s']:.1f}s "
            f"-> {scenario_dir}"
        )

    return stats, None


def main():

    args = parse_args()

    scenarios = SCENARIOS

    if args.only is not None:

        scenarios = [
            s for s in SCENARIOS
            if s["name"] == args.only
        ]

        if not scenarios:

            print(
                f"No scenario named '{args.only}'. "
                f"Available: {', '.join(s['name'] for s in SCENARIOS)}"
            )

            sys.exit(1)

    run_id = (
        args.resume
        if args.resume is not None
        else time.strftime("%Y%m%d_%H%M%S")
    )

    run_dir = os.path.join(
        BENCHMARKS_DIR,
        "results",
        run_id
    )

    if args.resume is not None and not os.path.isdir(run_dir):

        print(f"No such folder to resume from: {run_dir}")

        sys.exit(1)

    os.makedirs(
        run_dir,
        exist_ok=True
    )

    core_count = psutil.cpu_count()

    resume_note = " (resuming)" if args.resume is not None else ""

    print(
        f"Running the stress-test suite ({len(scenarios)} scenarios){resume_note}. "
        f"Results: {run_dir}\n"
    )

    computed = {}

    for index, scenario in enumerate(scenarios, start=1):

        print(f"=== [{index}/{len(scenarios)}] {scenario['name']} ===")

        print(scenario["description"])

        stats, note = run_scenario(
            scenario,
            run_dir,
            core_count
        )

        computed[scenario["name"]] = (stats, note)

        print()

    # Always covers every scenario in SCENARIOS, in that fixed order --
    # not just whichever subset --only targeted this invocation -- reading
    # the rest back from run_dir so a single-scenario --resume run (like
    # fixing up one stale summary.txt) doesn't wipe the other rows that a
    # previous invocation already wrote into this same overview.txt.
    overview_rows = []

    for scenario in SCENARIOS:

        name = scenario["name"]

        if name in computed:

            stats, note = computed[name]

        else:

            scenario_dir = os.path.join(run_dir, name)

            if _scenario_has_data(scenario_dir):

                samples = _read_samples_csv(
                    os.path.join(scenario_dir, "resource.csv")
                )

                stats = _compute_stats(samples, core_count)

                note = None

            else:

                stats, note = None, "not yet run in this run_dir"

        overview_rows.append((name, stats, note))

    _write_overview(
        run_dir,
        overview_rows
    )


if __name__ == "__main__":
    main()
