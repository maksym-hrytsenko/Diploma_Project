# Synthesized voice test session

The same catalog of 113 voice commands (`tests/voice_test_phrases.md`,
minus `YES`/`NO` — see `voice_pipeline_fixes_log.md` §6.5; removed from
the code entirely, not just from this list, since they had no rule at all
in `fusion.json`. `WORK_MODE`, on the other hand, was brought back into
both the code and this list), read aloud with macOS's synthesized voice
(`say`, Samantha voice) instead of a live person. The goal is to remove
human speech/pace variability from the measurement, so the results can be
honestly compared against the human session from 2026-07-17 (which
predates `WORK_MODE`).

## Files

- `voice_test_synthesized.m4a` — the finished audio file, ~20 min 19 s.
- `phrase_order.txt` — the same list of phrases in the same order as the
  file above and as the checklist artifact for this session — used to
  reconcile the results.
- `say_source_script.txt` — the source text with `[[slnc 9000]]` pauses
  between phrases that `say` generated the audio from (for
  reproducibility/editing).
- `parse_tts_session.py` — parses `logs/app.log` after the session and
  prints the result (tier + latency) for each phrase, 1:1 by position.

## Why a 9-second pause between phrases

`IntentModel.silence_timeout_seconds` = 6s. A 9s pause guarantees that
every session (successful or not) has time to close — and, if it failed,
to log `not understood` — BEFORE the next phrase's wake word arrives.
This eliminates all three reasons the human session from 2026-07-17
couldn't be parsed 100% automatically (short phrases silently getting
lost, FIFO-matching drift — both covered in `voice_pipeline_fixes_log.md`
§6.2/§6.1, parsing methodology in `voice_test_session_script.md`). Here,
every phrase gets a clean, unambiguously matchable result.

## How to run a session

```
source venv/bin/activate
python src/main.py --debug-voice
```

Give the app a few seconds to start (the Vosk/VAD model needs to load),
open `voice_test_synthesized.m4a` in any player and play it back through
speakers (not headphones — the microphone needs to hear it) at normal
conversational volume. Don't touch the app while it's playing.

## After the session

```
python tests/synthesized_voice/parse_tts_session.py logs/app.log
```

Prints one line per phrase — cross-reference the line number against the
same number in `phrase_order.txt`. Record the values into the checklist
artifact for the synthesized session (link — separate message) and
compare against the results of the human session from 2026-07-17: are
the same phrases failing, or was the problem specifically pronunciation?
