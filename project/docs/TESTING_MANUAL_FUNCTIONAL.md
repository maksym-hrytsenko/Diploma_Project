# Manual Functional Testing

Everything that needs a real camera, microphone, keyboard, or the actual
macOS desktop to verify — recognition from a live signal, UI behavior,
platform integration — none of which the automated suite in
[`TESTING_REGRESSION.md`](TESTING_REGRESSION.md) can exercise, since that
suite runs entirely on synthetic bus events with no recognizer or hardware
involved.

The full, authoritative list of scenarios lives in
[`../tests/MANUAL_TEST_SCENARIOS.md`](../tests/MANUAL_TEST_SCENARIOS.md) —
it is not duplicated here, for the same reason that document itself gives
for keeping the voice-specific scripts separate: a checklist meant to be
followed step by step during a live session belongs in one place, read
directly from, not copied across multiple documents where the copies can
drift out of sync. This document instead explains the methodology, gives
the section-by-section shape of that checklist, and reports the concrete,
reproducible results that exist for it.

## Methodology

Three different grading scales are used, matched to what's actually being
tested (see [`../tests/MANUAL_TEST_SCENARIOS.md`](../tests/MANUAL_TEST_SCENARIOS.md)
for the full per-section breakdown):

| Scale | Used for | Why |
|---|---|---|
| Binary (pass/fail) | Mode entry/exit, environments, global functions, UI/macOS integration, Try Mode | Deterministic outcomes — same reasoning as the automated suite |
| Correct / partially correct / incorrect | Gestures, face | Recognition from a real camera signal is inherently probabilistic; a 3-point scale records "recognized, but needed a retry" as distinct from "wrong" or "nothing happened," which pure pass/fail cannot |
| Binary, but on stability instead of accuracy | Stress / edge cases | The question here is not "did it recognize correctly" but "did the system stay in a consistent, running state" |

Coverage strategy also differs by section: mode entry (§1) is exhaustive —
4 modes × 6 independent entry paths = 24 discrete, enumerable code branches,
each one actually exercised. Gestures (§2) instead use one representative
execution per decision branch (e.g. one clearly-above-threshold rightward
swipe) rather than sampling every possible speed/angle/hand position, since
hand position is a continuous variable but the code path handling it is
finite.

## Section shape (164 scenarios, 10 sections)

| § | Section | Scenarios | Grading |
|---|---|---|---|
| 1 | Mode entry/exit, all input methods | 24 (exhaustive) | Binary |
| 2 | Gestures | — | Correct / partial / incorrect |
| 3 | Face | — | Correct / partial / incorrect |
| 4 | Voice — phrases and tiers | — | Correct / partial / incorrect |
| 5 | Environments | — | Binary |
| 6 | Global functions (app launching, media) | — | Binary |
| 7 | UI and macOS integration | — | Binary |
| 8 | Try Mode | — | Binary |
| 9 | Presentation — slide-switching regression | — | Binary |
| 10 | Stress / edge cases | 16 | Binary (stability) — see [`TESTING_STRESS.md`](TESTING_STRESS.md) |

Sections 7 (UI/macOS integration) and 8 (Try Mode) double as an informal
usability check, not just a functional one: they verify that the system's
current state is always readable from the interface, and that every
function can be safely tried in Try Mode before a user relies on it for
real — the usability requirement from the requirements analysis is
deliberately built into the scenario structure itself, rather than tested
separately.

## Results

### Voice — measured quantitatively

Voice is the one modality tested at the largest scale, and the one place
where real numbers exist beyond pass/fail. The full phrase catalog (113
phrases covering 38 commands, up to 3 recognition tiers each) and the
session script used to run it live in
[`../tests/voice_test_phrases.md`](../tests/voice_test_phrases.md) and
[`../tests/voice_test_session_script.md`](../tests/voice_test_session_script.md).

Two live sessions were run on 2026-07-17: the first from 11:42 to 12:10
(147 phrases spoken), the second from 14:27 to 14:56 (99 phrases, after
fixing a regression where the `work mode` environment had been
accidentally dropped from the configuration — see the case study below).
Combined, and after correcting a FIFO-matching bug in how log lines were
attributed to spoken phrases (matching each result to the nearest
*preceding* utterance instead of assuming strict queue order), **101 of
the 113 catalog lines (89%) were verified with real measured latency and
recognition tier**. Across the 66 lines both sessions captured in common:

- average latency fell from 3.83 s to 3.60 s
- the share of phrases needing the slower LLM fallback fell from 43% (41
  of 95 resolved lines, session 1) to 24% (17 of 72, session 2)
- 44 of those 66 lines were recognized at the same tier in both sessions

A per-tier latency breakdown is a separate, deeper analysis — see the
thesis chapter this data also feeds,
[`thesis/chapters/5. EXPERIMENTALNI VYHODNOCENI/5.3 Analyza rychlosti odezvy ruznych pristupu rozpoznavani reci.tex`](thesis/chapters/5.%20EXPERIMENTALNI%20VYHODNOCENI/5.3%20Analyza%20rychlosti%20odezvy%20ruznych%20pristupu%20rozpoznavani%20reci.tex).

A separate, repeatable QA track plays the same 113-phrase catalog from a
macOS `say` (Samantha voice) recording instead of a live speaker, run after
every voice-related change during development to catch anything left
broken — not statistically measured (that's not its purpose), but its last
run against the final version found no missing or broken function. The
same recording is reused as the reproducible voice-load source in
[`TESTING_STRESS.md`](TESTING_STRESS.md).

### Case study: bugs this testing style catches that the automated suite can't

Because `TESTING_REGRESSION.md`'s suite runs on isolated synthetic events,
not a real continuous signal, several real bugs only surfaced through live
manual testing:

- **Vosk splitting one phrase into two partial results** — the gap between
  them (observed 3.5–8 s) exceeded the then 2-second silence timeout.
  Fixed by adding an independent VAD stream and raising the timeout to 6 s.
- **Whisper hallucination in silence** — e.g. the word "Parallel" repeated
  12 times in a row in a quiet room. Fixed by tightening VAD thresholds and
  discarding any result with 3 or more identical consecutive words.
- **Audio processing stalling for several seconds** whenever the fallback
  path (Whisper, or semantic/LLM comparison) ran — caused by a blocking
  `future.result()` call on the same thread that also pulled new audio
  chunks from the microphone. Fixed by moving to an async
  `future.add_done_callback` pattern.
- **The `work mode` environment silently missing** — dropped by an earlier
  refactor, confirmed retroactively via `git log`; the phrase "jack work
  mode" did nothing at all in the first live session. Restored before the
  second session, which confirmed the fix.
- **Duplicated slide advance in Presentation mode** — caught directly from
  the manual scenarios (§9); fixed by removing a redundant physical-arrow
  mapping from `fusion.json`'s `mode_rules`, and now also covered by
  `TestPresentationMode::test_physical_arrow_keys_do_not_double_fire` in
  the automated suite.

### Gestures, face, environments, UI, Try Mode — qualitative status

These sections were run manually against the checklist during development
and are consistent with the system's current, working state (the built
`.app`, and the automated suite in `TESTING_REGRESSION.md`, both assume
and depend on this decision logic being correctly wired). Unlike the voice
catalog above, a dated, per-row pass/fail log for these specific sections
was not preserved as a separate artifact — the checklist itself
(`MANUAL_TEST_SCENARIOS.md`) is the record of *what* was verified, not a
log of *when* and with what per-row result. If a fresh, dated re-run with
recorded per-row grades is needed for one of these sections, it has to be
performed live (camera, microphone, and a person present) and is not
something that can be reconstructed after the fact.
