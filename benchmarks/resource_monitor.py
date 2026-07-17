"""Standalone CPU/RAM load benchmark for the running application.

Launches `python src/main.py` (or attaches to an already-running process by
PID), samples its CPU and memory usage — including every child process it
spawns, since the NLU/Whisper fallbacks each run in their own
ProcessPoolExecutor worker — at a fixed interval, and writes the samples to
a CSV file plus a summary on exit.

Lives outside src/ on purpose: it is a developer/QA tool for measuring how
much load the app puts on the machine, not part of the shipped application
or its packaged .exe build.

Usage:
    python benchmarks/resource_monitor.py
    python benchmarks/resource_monitor.py --duration 120
    python benchmarks/resource_monitor.py --attach-pid 12345
    python benchmarks/resource_monitor.py -- --debug-gesture
"""

import argparse
import csv
import os
import subprocess
import sys
import time

import psutil


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


def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Sample CPU/RAM usage of the app (and its worker "
            "processes) over time."
        )
    )

    parser.add_argument(
        "--attach-pid",
        type=int,
        default=None,
        help=(
            "Attach to an already-running process instead of "
            "launching a new one."
        )
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between samples (default: 1.0)."
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help=(
            "Stop automatically after this many seconds. "
            "Omit to run until Ctrl-C."
        )
    )

    parser.add_argument(
        "--output",
        default=None,
        help=(
            "CSV output path (default: "
            "benchmarks/resource_log_<timestamp>.csv)."
        )
    )

    parser.add_argument(
        "app_args",
        nargs=argparse.REMAINDER,
        help=(
            "Extra arguments forwarded to src/main.py when launching "
            "it (e.g. -- --debug-gesture). Ignored with --attach-pid."
        )
    )

    return parser.parse_args()


def resolve_output_path(output_arg):

    if output_arg is not None:
        return output_arg

    timestamp = time.strftime(
        "%Y%m%d_%H%M%S"
    )

    return os.path.join(
        BENCHMARKS_DIR,
        f"resource_log_{timestamp}.csv"
    )


# Sums the target process with every child it has spawned (the NLU
# semantic/LLM fallback and Whisper open-vocab transcription each run in
# their own ProcessPoolExecutor worker process), so the reported load
# reflects the app's real footprint, not just its main process.
def sample_process_tree(root_process):

    processes = [root_process]

    try:

        processes.extend(
            root_process.children(
                recursive=True
            )
        )

    except psutil.NoSuchProcess:
        pass

    total_cpu_percent = 0.0
    total_rss_bytes = 0

    for process in processes:

        try:

            total_cpu_percent += process.cpu_percent()

            total_rss_bytes += process.memory_info().rss

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return total_cpu_percent, total_rss_bytes, len(processes)


def prime_cpu_percent(root_process):

    processes = [root_process]

    try:

        processes.extend(
            root_process.children(
                recursive=True
            )
        )

    except psutil.NoSuchProcess:
        pass

    for process in processes:

        try:
            process.cpu_percent()

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def run_monitor(
    root_process,
    interval_seconds,
    duration_seconds,
    output_path
):

    samples = []

    # First cpu_percent() call on a process always returns 0.0 — it needs
    # one throwaway call to establish the measurement window before the
    # real sampling loop starts.
    prime_cpu_percent(
        root_process
    )

    time.sleep(
        interval_seconds
    )

    start_time = time.time()

    print(
        f"Monitoring PID {root_process.pid} every "
        f"{interval_seconds}s. Press Ctrl-C to stop."
    )

    try:

        while root_process.is_running():

            elapsed_seconds = time.time() - start_time

            if (
                duration_seconds is not None
                and elapsed_seconds >= duration_seconds
            ):
                break

            cpu_percent, rss_bytes, process_count = sample_process_tree(
                root_process
            )

            rss_mb = rss_bytes / (1024 * 1024)

            samples.append(
                (
                    elapsed_seconds,
                    cpu_percent,
                    rss_mb,
                    process_count
                )
            )

            print(
                f"[{elapsed_seconds:7.1f}s] "
                f"CPU: {cpu_percent:6.1f}%  "
                f"RAM: {rss_mb:7.1f} MB  "
                f"processes: {process_count}"
            )

            time.sleep(
                interval_seconds
            )

    except KeyboardInterrupt:
        print("\nStopping monitor...")

    write_csv(
        samples,
        output_path
    )

    print_summary(
        samples,
        output_path
    )

    return samples


def write_csv(samples, output_path):

    os.makedirs(
        os.path.dirname(output_path) or ".",
        exist_ok=True
    )

    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(f)

        writer.writerow(
            ["elapsed_seconds", "cpu_percent", "rss_mb", "process_count"]
        )

        for row in samples:
            writer.writerow(row)


def print_summary(samples, output_path):

    print(
        f"\nWrote {len(samples)} samples to {output_path}"
    )

    if not samples:
        return

    cpu_values = [row[1] for row in samples]
    rss_values = [row[2] for row in samples]

    print(
        "CPU%  -> "
        f"avg: {sum(cpu_values) / len(cpu_values):6.1f}  "
        f"max: {max(cpu_values):6.1f}"
    )

    print(
        "RAM MB-> "
        f"avg: {sum(rss_values) / len(rss_values):7.1f}  "
        f"max: {max(rss_values):7.1f}"
    )


def main():

    args = parse_args()

    output_path = resolve_output_path(
        args.output
    )

    launched_process = None

    if args.attach_pid is not None:

        root_process = psutil.Process(
            args.attach_pid
        )

    else:

        extra_args = args.app_args

        if extra_args[:1] == ["--"]:
            extra_args = extra_args[1:]

        launched_process = subprocess.Popen(
            [sys.executable, MAIN_SCRIPT] + extra_args,
            cwd=PROJECT_ROOT
        )

        root_process = psutil.Process(
            launched_process.pid
        )

    try:

        run_monitor(
            root_process,
            args.interval,
            args.duration,
            output_path
        )

    finally:

        if launched_process is not None and launched_process.poll() is None:

            launched_process.terminate()


if __name__ == "__main__":
    main()
