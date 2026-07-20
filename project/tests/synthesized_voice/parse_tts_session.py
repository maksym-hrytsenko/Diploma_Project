"""Parses a logs/app.log session produced by playing voice_test_synthesized.m4a
into the microphone while `python src/main.py --debug-voice` is running.

Unlike a human reading session, this one is safe to align positionally:
the 9s gap between phrases (see say_source_script.txt) is longer than
IntentModel's silence_timeout_seconds (6s), so every phrase's session
closes -- either into a [RESOLVED] or an explicit "not understood" -- before
the next phrase's wake word arrives. No retries, no silent drops, no FIFO
drift (see tests/voice_pipeline_fixes_log.md #6.2 for what goes wrong
without that gap). The Nth phrase in phrase_order.txt should therefore line
up with the Nth resolution event in the log, one to one.

Usage:
    python tests/synthesized_voice/parse_tts_session.py logs/app.log

Prints one line per phrase: index, tier, resolved command + method, and
latency (Command/Mode/Environment -> timestamp minus speech_onset).
"""

import re
import sys
import datetime


TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")
VF_RE = re.compile(
    r'\[voice final\] ".*" \(\w[\w-]*, wake_word_heard=\w+, speech_onset=([\d.]+|unknown)\)'
)
RESOLVED_RE = re.compile(r'\[RESOLVED\] (.+?) <- voice:"(.+?)" \((.+?)\)')
NOT_UNDERSTOOD_RE = re.compile(r'\[RESOLVED\] not understood: "(.*)"')
OUTCOME_RE = re.compile(r"(Command|Mode|Environment|Try Mode) -> (\S+)")


def parse_ts(line):
    m = TS_RE.match(line)
    return datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S,%f")


def parse_log(path):
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "[voice final]" in line:
                m = VF_RE.search(line)
                if m:
                    onset = m.group(1)
                    events.append((
                        "voice_final",
                        parse_ts(line),
                        float(onset) if onset != "unknown" else None,
                    ))
            elif "not understood" in line:
                events.append(("not_understood", parse_ts(line), None))
            elif "[RESOLVED]" in line and 'voice:"' in line:
                m = RESOLVED_RE.search(line)
                if m:
                    events.append(("resolved", parse_ts(line), (m.group(1), m.group(3))))
            elif OUTCOME_RE.search(line):
                m = OUTCOME_RE.search(line)
                events.append(("outcome", parse_ts(line), m.group(2)))
    return events


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    events = parse_log(sys.argv[1])

    # Walk chronologically, pairing each voice_final with whatever resolves
    # right after it (a resolved+outcome pair, or a not_understood).
    results = []
    pending_onset = None
    i = 0
    n = len(events)
    while i < n:
        kind, ts, data = events[i]
        if kind == "voice_final":
            pending_onset = data
            i += 1
            continue
        if kind == "not_understood":
            results.append({"resolved": False, "latency": None, "method": None})
            pending_onset = None
            i += 1
            continue
        if kind == "resolved":
            outcome_ts = None
            j = i + 1
            while j < n and j < i + 3:
                if events[j][0] == "outcome":
                    outcome_ts = events[j][1]
                    break
                j += 1
            latency = None
            if outcome_ts is not None and pending_onset is not None:
                latency = (outcome_ts - datetime.datetime.fromtimestamp(pending_onset)).total_seconds()
            results.append({"resolved": True, "latency": latency, "method": data[1]})
            pending_onset = None
            i += 1
            continue
        i += 1

    for idx, r in enumerate(results):
        if r["resolved"]:
            lat = f"{r['latency']:.2f}s" if r["latency"] is not None else "?"
            print(f"{idx + 1:3}. OK   {r['method']:22} {lat}")
        else:
            print(f"{idx + 1:3}. FAIL not understood")

    print(f"\n{len(results)} phrases resolved-or-failed out of an expected 113.")
    print("Cross-reference line N above against phrase_order.txt line N.")


if __name__ == "__main__":
    main()
