# Voice pipeline fixes log (test session 2026-07-16)

Chronological record of problems found during real voice testing (at the
time still a separate file, `voice_test_session_script.md`, later merged
into `tests/MANUAL_TEST_SCENARIOS.md` §4.6), and the fixes made in
response. The goal of every fix is for the system to correctly determine
that a person has NOT finished speaking yet, instead of "forgetting" the
phrase prematurely.

---

## 1. The system stops listening too soon — the session "faded out" prematurely

**Symptom.** A longer phrase (tier 2/3) was often split by Vosk into two
fragments. When the second fragment finalized a few seconds after the
first, `[RESOLVED] not understood: "..."` showed only the FIRST half of
the phrase — the second half was lost.

**Cause.** The silence timer (`wake_word_silence_timeout_seconds`) was
counted from the moment Vosk **finalized** the previous fragment, not
from the moment of actual silence. Vosk itself sometimes decides "end of
phrase" with a delay of several seconds after the person actually kept
talking (gaps of 3.5–8s between fragments of the same phrase were
typically observed).

**What we did:**
- `src/config/system.json`: raised `wake_word_silence_timeout_seconds`
  from **2 to 6** seconds.
- New `voice_activity` event (`speech_recognizer.py`) — published on
  every non-empty intermediate (partial) Vosk result, i.e. while Vosk is
  still hearing speech, even before finalization.
- `intent_model.py`: subscribing to `voice_activity` pushes the deadline
  of an already-open session forward (`_handle_voice_activity`) — the
  silence counter now counts from the moment Vosk **stopped** hearing
  speech, not from the moment a fragment happened to finalize.

**Files:** `src/config/system.json`,
`src/processing/speech/speech_recognizer.py`,
`src/interpretation/intent_model.py`.

---

## 2. Whisper hallucinations on silence/noise

**Symptom.** In a completely quiet room, `"Jack Parallel"` periodically
appeared, and once —
`"Parallel Parallel Parallel Parallel Parallel Parallel Parallel Parallel Parallel Parallel Parallel Parallel"`
(12 times in a row).

**Cause.** Silero VAD on library defaults (`threshold=0.5`,
`min_speech_duration_ms=250`) let a weak signal (fan noise, breathing)
through as "possibly speech" — not enough for real content, but enough to
reach the Whisper fallback, which on such input "makes up" plausible but
fake text (classic Whisper behavior on silence/noise).

**What we did:**
- `src/config/system.json`: added `vad_threshold: 0.65` and
  `vad_min_speech_duration_ms: 300` (both stricter than the library
  defaults).
- `src/processing/speech/speech_model.py`: `_speech_timestamps()` now
  passes these thresholds into `get_speech_timestamps()`.
- New method `_looks_like_hallucination()` — if a Whisper result contains
  3+ identical words in a row, it's discarded as a hallucination before
  it reaches any further processing.

**Files:** `src/config/system.json`,
`src/processing/speech/speech_model.py`.

---

## 3. Blocking pipeline — audio processing stalled for seconds during fallback

**Symptom.** Even when a person spoke quickly with no pauses, 8+ seconds
sometimes passed between two fragments of the same phrase.

**Cause.** `EventBus.publish()` calls every subscriber **synchronously**,
on the same thread that publishes the event. The Whisper fallback
(`future.result()` with no timeout) and the semantic/LLM fallback
(`future.result(timeout=15)`) waited for the subprocess's response by
**blocking** exactly the thread that's also responsible for pulling new
audio chunks off the microphone. While one fragment waited on
Whisper/LLM, the next audio chunks (which already held the rest of the
phrase) simply piled up in the queue unprocessed.

**What we did — made both calls asynchronous**
(`future.add_done_callback` instead of the blocking `.result()`):
- `speech_model.py`: `_fallback_transcribe` →
  `_start_fallback_transcribe` + `_handle_fallback_future`. The result
  now arrives later via the `on_fallback_ready` callback passed into
  `VoskSpeechModel`.
- `speech_recognizer.py`: the logic for publishing the final result was
  factored out into a shared `_handle_final_result` method, used by both
  the synchronous path and the asynchronous callback from Whisper.
- `intent_model.py`: `_match_semantic`/`_match_llm` →
  `_start_nlu_fallback` / `_handle_semantic_future` /
  `_start_llm_fallback` / `_handle_llm_future`. Added `session_token` — a
  counter that invalidates a "stale" response if a newer fragment
  (concatenation or a new session) has already overtaken a previous
  semantic/LLM attempt while it was still being processed in the
  background.
- Kept `_warn_if_slow` (via `threading.Timer`) — it just prints a warning
  to the log if a worker runs longer than `worker_timeout_seconds`,
  without blocking anything.

**Verified:** `process_text()` now returns in ~7ms instead of seconds
even with the fallback enabled; stale responses are correctly ignored
(verified manually with stand-in `Future` objects).

**Files:** `src/processing/speech/speech_model.py`,
`src/processing/speech/speech_recognizer.py`,
`src/interpretation/intent_model.py`.

---

## 4. Found, NOT yet fixed: detection of the wake word itself is sometimes missed

**Symptom.** In the tier-3 test phrase for CURSOR_MODE ("I need to
control the mouse with my hands, switch to cursor mode. Please."), both
fragments had `wake_word_heard=False` and neither recognized text started
with "jack" — the phrase was **completely ignored** before any attempt at
command recognition (the session never even opened, neither semantic nor
LLM were called). The mode only switched 19 seconds later, when the
phrase was repeated as a plain tier-1 ("jack cursor mode").

**Cause:** not established. This time Vosk didn't catch "jack" either in
the final text or as a partial hypothesis — unlike other cases in this
same session, where `wake_word_heard=True` fired correctly even with
garbled Whisper text.

**Status:** open question, needs separate investigation (possibly
volume/enunciation right at the start of the phrase, or an issue with how
fast Vosk manages to recognize the first word).

---

## Separate finding (not about voice, not yet investigated)

`NEXT_SLIDE` fired ~20 times in a row within 400ms from
`keyboard:"KEY_RIGHT"` — looks like OS auto-repeat while holding the
arrow key down. `KeyboardProcessor` is theoretically supposed to filter
this out (it shouldn't publish a new "down" while the same key set is
still held), but the log showed it passing straight through. Not
investigated further — waiting on the user's call on whether to dig
deeper.

**Status (next session): resolved as a side effect, together with a
separate bug.** See item 5 below — a physical arrow key no longer maps to
`NEXT_SLIDE`/`PREVIOUS_SLIDE` in any form, so OS auto-repeat on a held
arrow key no longer publishes anything.

---

## 5. Next session (2026-07-16): item 4 resolved, a separate double-slide bug found and fixed

### Item 4 resolved: the wake word no longer depends on which fragment Vosk "cut" it into

**Root cause, confirmed by reading the code:** Vosk itself decides where
`AcceptWaveform()` "cuts" a long phrase into fragments (the grammar
recognizer's internal endpointing) — and each fragment became a separate
`text_ready` event, which `IntentModel` had to stitch back together after
the fact via `pending_command_text` + a session timeout. If "jack" landed
in the wrong fragment, the session never opened at all — exactly what was
observed in the tier-3 CURSOR_MODE phrase.

**What we did — a deep rework (`src/processing/speech/speech_model.py`):**
- `VoskSpeechModel` now runs its own continuous VAD stream, independent
  of Vosk (`self.streaming_vad_model`, a separate model instance from
  `self.vad_model` — so batch calls to `_speech_timestamps()` don't reset
  the streaming instance's internal state) — every incoming `audio_chunk`
  is checked for speech in 512-sample windows.
- A `Result()` from `AcceptWaveform()==True` no longer means "the phrase
  is over" — it's just one fragment, whose text gets appended to
  `utterance_grammar_text` (the same logic for `[unk]`/wake-word
  detection now applies at the level of the whole phrase, not a
  fragment).
- A phrase is considered finished only once `vad_silence_hangover_ms`
  (new, 900ms by default) has passed since the **last**
  VAD-detected speech window — regardless of how many times Vosk managed
  to "finalize" something in between.
- If the accumulated text is clean (no `[unk]`) — an instant exact match,
  no Whisper. Otherwise — **one** Whisper call for the **whole** phrase
  buffer (previously, a separate call per fragment).
- `vad_enabled: false` is explicitly supported as its own branch —
  degrades back to the old behavior (`AcceptWaveform()` decides the end
  of a phrase directly) instead of hanging forever with no VAD signal.

**Verified:** an isolated test with scripted mock Vosk/VAD (no real
models) confirmed that two consecutive `AcceptWaveform()==True` events
inside one phrase no longer finalize it prematurely, fragment text is
correctly stitched together ("jack cursor" + "mode please" → "jack cursor
mode please"), and a wake word detected in the first fragment correctly
carries through to the final result.

**Side effect:** `IntentModel.wake_word_silence_timeout_seconds` (6s) now
only applies to the gap *between* separate phrases in one session — gaps
within a SINGLE phrase are handled by the VAD hangover, which is much
shorter and more sensitive to real silence.

### New, separate bug: Presentation mode skipped two slides at once

**Symptom:** switching slides immediately "ate" two slides instead of
one.

**Cause:** `pynput.Listener` doesn't block the physical key — the
Right/Left arrow reached the focused presentation app directly (1 slide)
**and** the system sent its own synthetic arrow via
`os_controller.next_slide()` (1 more slide) = 2 slides every time the
presentation had focus. This was also the root cause of the "NEXT_SLIDE
fired 20 times" finding above — OS auto-repeat on a held arrow key
multiplied the same double action.

**What we did:** removed `presentation_next_key`/`presentation_previous_key`
from `config/fusion.json`'s `mode_rules` — voice ("next slide"/"previous
slide") and gesture (closed fist, wrist right/left) remain the two
system-level ways to advance slides. Physical arrow keys still work
naturally inside the presentation app itself when it has focus — without
this system's help (and without it getting in the way).

**Files:** `src/config/fusion.json`, `docs/SYSTEM_FUNCTIONS.md`,
`docs/FUNCTIONS_LIST.txt`, `src/ui/dialogs.py`.

---

## 6. Next session (2026-07-17): `--debug-voice` wasn't enabling DEBUG level, a new silent session bug was found, `WORK_MODE` turned out to be deleted

Before the live session (147 phrases, 28 min, full log —
`logs/app.log` 11:42:30–12:10:48), the code was checked for readiness to
measure microphone-to-execution latency.

### 6.1 Fixed: `--debug-voice` never actually enabled DEBUG-level logging

**Symptom:** `[voice partial]` (intermediate hypotheses) and the
wake-word session diagnostics in `intent_model.py` had their own
`logger.debug()` calls, gated on `if self.debug`, but they NEVER showed
up in the console or `logs/app.log`, even with the `--debug-voice` flag.

**Cause:** the shared root logger (`utils/logger.py`) is fixed at `INFO`
level. No module ever raised its own level to `DEBUG` — the
`--debug-voice` flag only enabled the code branch that CALLS
`logger.debug(...)`, but the call itself was filtered out before it
reached any handler.

**What we did:** in `SpeechRecognizer.__init__` and
`IntentModel.__init__`, when `debug=True`, added
`logger.setLevel(logging.DEBUG)` on the module-level logger (not the
root one — to avoid enabling DEBUG for other modules that have the same
independent bug, see 6.4).

**Verified:** manually (`logger.isEnabledFor(logging.DEBUG)` before/after
`setLevel`), 56/56 pytest, `py_compile` on both files.

**Files:** `src/processing/speech/speech_recognizer.py`,
`src/interpretation/intent_model.py`.

### 6.2 Found, NOT yet fixed: a run of short phrases in a row silently drops the previous one with no log line at all

**Symptom:** in the 2026-07-17 session, all phrases for
`YES`/`NO`/`START`/`STOP`/`PAUSE`/`RESET`/`EXIT_MODE` (the "control
words" section, ~19 phrases in a row) and `START_SLIDESHOW` are present
in the log as `[voice final]`, but NONE of them got either
`[RESOLVED]` or `[RESOLVED] not understood` — they vanished without a
trace.

**Cause, confirmed by reading the code:** `IntentModel._print_not_understood()`
is only ever called lazily, at the start of `process_text()`, when NEW
text arrives and `self._session_timed_out()` turns out to be `True` for
the OLD session. If the next phrase with a wake word arrives BEFORE the
old session has formally timed out (`silence_timeout_seconds`, 6s — and
it could stay "alive" even longer if background `voice_activity` events
from noise kept pushing the deadline forward), `_start_session()`
(line 274) unconditionally resets `pending_command_text` for the new
phrase, and the old one is NEVER reported as "not understood" — it just
falls out of the log.

**Consequence for measurements:** this isn't a recognition bug (the
command itself could have been heard perfectly), but a gap in
observability — short phrases spoken faster than roughly every 6-10s are
systematically underrepresented in any statistics built from
`logs/app.log`.

**Status:** open question. A possible fix direction — check
`_session_timed_out()` (and report `not understood` for the old session
if needed) BEFORE a new wake word starts a new one, rather than only at
the start of `process_text()` as a whole; or report "overwritten by a new
session" as a separate message instead of silently resetting.

**Files:** `src/interpretation/intent_model.py` (`process_text`,
`_start_session`).

### 6.3 Found: the LLM fallback occasionally "guesses" the wrong command for an unrelated phrase

**Symptom:** `OPEN_BROWSER` resolved via `voice LLM model` six times
during the session — three right after the corresponding test phrases
(expected), and three more 8, 23 and 27 minutes later, when completely
different phrases were actually spoken (confirmed by cross-referencing
the timing against the rest of the session).

**Cause:** not investigated further — the LLM fallback's
ProcessPoolExecutor worker (`nlu_fallback_worker.py`) evidently sometimes
returns `OPEN_BROWSER` as the "closest" command for input text that
doesn't actually resemble anything (possibly the prompt doesn't forbid
guessing strictly enough when there's no confidence).

**Status:** open question, needs a separate investigation of the
`llm_interpret_task` prompt.

### 6.4 Confirmed: the same "DEBUG never turns on" bug exists in other modules too

`logger.debug()` calls with the same `if self.debug`-style gating also
exist in `gesture_recognizer.py`, `action_executor.py`,
`ui/main_window.py`, `ui/quick_command_overlay.py` — none of them raise
their own logger level. Only the voice path was fixed today (6.1); the
rest are out of scope for this session, left untouched.

### 6.5 Found: the `WORK_MODE` environment is missing from the current code

`config/fusion.json` and `config/mapping.json` today only define
`JOB_SEARCH_MODE`/`STUDY_MODE`/`MOVIE_MODE`/`NEWS_MODE` — there is no
`"environment": "work"` entry. Confirmed via `git log -p` — added in
commit `c691878`, removed in commit `908fe535` (2026-07-12, "Implement
logging and resource monitoring features"), whose message doesn't
mention this and no test references it — looks like an unintentional
loss during an unrelated refactor, not a deliberate decision.
`tests/MANUAL_TEST_SCENARIOS.md` §5.1, `tests/voice_test_phrases.md` and
the previous version of the checklist still describe Work as a live
feature. The phrase "jack work mode" currently doesn't resolve to any
command.

**Status:** resolved (next session, also 2026-07-17) — the environment
was restored, and additionally refined: `enter_actions` is now
`ENABLE_DO_NOT_DISTURB` + `OPEN_SLACK`/`OPEN_MAIL`/`OPEN_CALENDAR`
(reuses already-existing actions, actually opens three apps),
`WORK_MODE` was brought back into `mapping.json`. Not yet live-tested —
the 2026-07-17 session described above predates it.

### Results of the 2026-07-17 session (aggregated)

Full log-parsing methodology — `tests/voice_test_session_script.md`,
"Human session results" section. In brief: of 147 spoken phrases, 127 got
some `[RESOLVED]` result, 8 were explicit `not understood`, 20 were
silently lost (see 6.2). Among phrases the Vosk grammar recognized
verbatim (`source=grammar`, n=42): 28.6% exact-match, 14.3% reached
semantic, a full 52.4% still went through LLM anyway (doesn't always
match the phrase's exact text — see 6.3), 4.8% not understood. Among
conversational/paraphrased phrases outside the grammar
(`source=open-vocab`, n=85): 29.4% still landed an exact match (Whisper
occasionally produces a verbatim match by chance), 28.2% semantic, 35.3%
LLM, 7.1% not understood.

### 6.7 Second human session (2026-07-17, 14:27–14:56) — a real trend comparison

The user asked whether a "realistic time" could be picked for
unmeasured lines by extrapolating the trend. This was declined for the
same reason as before (see above) — a made-up time in a formal test
document is indistinguishable from a measured one and undermines trust
in the whole dataset. Instead: `logs/app.log` was checked for a new
session — a real one was found (14:27–14:56, 99 phrases, already with
`WORK_MODE` restored), parsed with the same corrected methodology
(§6.6), and merged with the first session.

**Result of the merge:** 101/113 lines of the voice-only checklist are
now confirmed with real timing (up from 95, and none of the `WORK_MODE`
lines had any data at all before — now `WORK_MODE` tier 1 is confirmed).
12 remain unconfirmed — mostly tier 2-3 `STUDY_MODE`/`MOVIE_MODE`/
`NEWS_MODE`/`WORK_MODE` and `STOP`/`PAUSE`/`RESET` — reading these ~12
phrases once more should be enough.

**Real trend between sessions** (66 lines tested in both): average
latency 3.83s → 3.60s (−0.23s, a modest improvement). More telling — the
share of phrases that fell through to the slower LLM fallback dropped
from 43% (41/95) to 24% (17/72), the tier distribution shifted toward
exact/semantic. 44 of the 66 matching lines resolved at the same tier
both times — so the shift is real but not dramatic; possible causes (not
separated by this analysis): a habit of enunciating phrases more clearly
the second time, or just random variation in which commands happened to
fall through to the LLM again. This is the honest answer to "how much
better/worse does it understand" — a measured aggregate, not a made-up
time for specific lines.

Side finding: `WORK_MODE` tier 1 ("work mode", the literal grammar
phrase) resolved via `voice LLM model`, not an exact match — possibly a
cached Vosk grammar generated before the app was restarted after
`WORK_MODE` was added to `mapping.json`. Not investigated further this
session.

### 6.6 Fixed: matching a phrase to a result in queue order (FIFO) is a worse method than matching to the nearest preceding time

After the first pass (82/116 voice-only checklist items matched, only 23
with reliable timing), the user pointed out that for simple phrases the
timing should be confidently determinable. This forced a re-examination
of the methodology itself, rather than just accepting the limits of the
first parse.

**Problem with the first methodology:** it matched every `[RESOLVED]`
with the OLDEST still-unused `[voice final]` in the queue (FIFO).
Correct as long as every phrase gets exactly one result — but the moment
even one phrase is lost without a log line (6.2), every subsequent match
shifts, and "latency" starts meaning the time until an unrelated, much
older phrase (hence the 90-200s latencies seen in the first pass).

**Fix, confirmed by reading the code:**
`IntentModel._handle_semantic_future`/`_handle_llm_future` check
`token != self.session_token` and bail out BEFORE publishing a result if
the token is stale (`session_token` increments every time a new
background request starts — lines 359, 407 of the file). This means:
every `[RESOLVED]` line is guaranteed to belong to the nearest PRECEDING
`[voice final]` phrase in time, not some arbitrary one from the old
queue. The parsing was rewritten to use "nearest preceding `[voice
final]` by timestamp" instead of FIFO.

**Result:** with the same 127 events in the same log — 95/116 items
(up from 82) now have both a confirmed tier AND a realistic time
(1.7-17.2s, all within the expected range, 0 implausible values —
previously there were many). Unconfirmed — 21/116 (18.1%), mostly
tier-2/3 for secondary apps (Chrome, Discord) and environments
(Study/Movie/News), plus `YES`/`NO` — neither command has ANY occurrence
in the whole session (confirmed by direct count in the log, not a
side effect of the methodology).

**Caveat:** for commands with many natural repetitions in a session
(`EXIT_MODE` — 15 occurrences, since the tester exited every mode they
tried), matching "which of the 15 occurrences corresponds to the tier-2
line in the test set" is no longer about the correctness of the
phrase↔result pair (that's guaranteed), but about which of several REAL
executions to show as the example for that line. The value shown is
always real (a real command, a real tier, a real latency), just not
necessarily the exact execution the specific test-scenario item had in
mind.
