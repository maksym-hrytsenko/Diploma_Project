# Voice test session script

One continuous list of phrases to say back to back — covers every voice
command from `voice_test_phrases.md`, grouped conveniently for a single
sitting. The grouping order here deliberately "loops" between different
modes/environments instead of repeating the same one — re-entering a
mode/environment you're already in is a silent no-op (no log line at
all), so the old order would make success and tier 2/3 failure
indistinguishable.

## How to measure latency (microphone -> command execution)

Every voice fragment is logged as a line:

```
[voice final] "..." (tier, wake_word_heard=..., speech_onset=X.XXX)
```

`speech_onset` — an estimate of the wall-clock moment the person actually
started speaking: the publish time of the corresponding `audio_chunk`
minus the chunk's own duration, adjusted by the offset at which VAD
detected speech starting inside the buffer
(`VoskSpeechModel.utterance_start_time` / `_finalize_utterance` in
`src/processing/speech/speech_model.py`). The command that ultimately
executes is logged as `[RESOLVED] <ACTION> <- ...` (`signal_mapper.py`)
and `Command -> <ACTION>` (`action_executor.py`) — every log line carries
its own `%(asctime)s` timestamp at the start (`src/utils/logger.py`).
**Microphone -> execution latency** = the `Command ->` line's timestamp
minus the `speech_onset` of the corresponding `[voice final]` line for
the same phrase.

`[voice final]` is always logged at INFO level, regardless of
`--debug-voice` — it's visible in `logs/app.log` even without the flag.

## Debug mode

```
python src/main.py --debug-voice
```

Enables verbose recognition logging: intermediate (`[voice partial]`)
hypotheses while a phrase is being spoken, and — always, with or without
the flag — the final result (`[voice final]`) with the same
`speech_onset` for measuring latency as above. Useful to run separately
from the rest of the app (no camera in frame, no active gesture mode) if
the goal is specifically the voice pipeline, not a full system run.

## How to run it

```
source venv/bin/activate
python src/main.py --debug-voice
```

Say each phrase separately, with a short pause after it (~1-2s) before
moving to the next one. You can pause after each block (marked `---`).

---

## Block A — Entering modes (5 modes × 3 tiers, looped)

1. jack presentation mode
2. jack flip mode
3. jack cursor mode
4. jack call mode
5. jack try mode
6. jack switch to presentation mode
7. jack switch to flip mode
8. jack switch to cursor mode
9. jack switch to call mode
10. jack switch to try mode
11. jack I'm about to give a talk, could you switch me into presentation mode
12. jack I want to scroll through pages, can you put me in flip mode please
13. jack I need to control the mouse with my hand, switch to cursor mode please
14. jack I'm joining a meeting, could you put me into call mode
15. jack can you let me try things out safely without actually doing anything
16. jack exit mode

---

## Block B — Environments (5 environments, looped)

17. jack work mode
18. jack study mode
19. jack movie mode
20. jack news mode
21. jack switch to work environment
22. jack switch to study environment
23. jack switch to movie environment
24. jack switch to news environment
25. jack I'm starting my work day, could you set everything up for work please
26. jack I need to focus and study now, can you set that up for me
27. jack I want to watch a film, could you set up movie mode please
28. jack can you please bring up the news for me
29. jack job search mode

(An environment doesn't end itself with an exit phrase — it simply stays
active after the last phrase, which is expected.)

---

## Block C — Opening apps (19 commands × 3 tiers)

These are one-shot commands (not state), a repeated run is always visible
in the log — the order can stay as-is.

30. jack open browser
31. jack launch the browser
32. jack could you please open the web browser for me
33. jack open chatgpt
34. jack start chatgpt
35. jack hey, can you bring up chatgpt for me please
36. jack open github
37. jack launch github
38. jack I need to look at my repositories, open github please
39. jack open vscode
40. jack start visual studio code
41. jack can you open my code editor for me
42. jack open terminal
43. jack launch the terminal
44. jack I need to run some commands, open a terminal please
45. jack open safari
46. jack start safari
47. jack could you bring up safari for me please
48. jack open chrome
49. jack launch chrome
50. jack can you please open google chrome for me
51. jack open spotify
52. jack start spotify
53. jack I feel like listening to some music, open spotify please
54. jack open slack
55. jack launch slack
56. jack can you open up slack, I need to check messages
57. jack open discord
58. jack start discord
59. jack could you please bring up discord for me
60. jack open mail
61. jack open my email
62. jack I need to check my email, could you open mail please
63. jack open calendar
64. jack show my calendar
65. jack can you please open up my calendar for me
66. jack open notes
67. jack open my notes
68. jack I want to write something down, open notes please
69. jack open telegram
70. jack launch telegram
71. jack could you open telegram, I need to message someone
72. jack open finder
73. jack open the file browser
74. jack I need to find a file, could you open finder please
75. jack open notion
76. jack launch notion
77. jack can you please bring up notion for me
78. jack open photos
79. jack show my photos
80. jack I want to look at some pictures, open photos please
81. jack open preview
82. jack launch preview
83. jack could you please open the preview app for me
84. jack open settings
85. jack open system settings
86. jack can you please bring up the settings for me

---

## Block D — Navigation (slides and track, 4 commands × 3 tiers)

Slides only make sense in Presentation mode — enter it before item 87
(`jack presentation mode`), leave it afterward (`jack exit mode`). Track
commands are global, no mode needed.

87. jack presentation mode
88. jack next slide
89. jack go to the next slide
90. jack could you please move forward to the next slide
91. jack previous slide
92. jack go back a slide
93. jack can you please go back to the previous slide
94. jack exit mode
95. jack next track
96. jack skip to the next song
97. jack could you please play the next track for me
98. jack previous track
99. jack go back to the last song
100. jack can you please go back to the previous track

---

## Block E — Control words (5 commands × 3 tiers)

101. jack start
102. jack begin
103. jack could you please start it now
104. jack stop
105. jack halt
106. jack could you please stop that now
107. jack pause
108. jack pause it
109. jack could you pause whatever is playing please
110. jack reset
111. jack start over
112. jack could you please reset everything back
113. jack exit mode
114. jack leave this mode
115. jack could you please take me out of this mode

---

## After the session

Read `logs/app.log`, match each `[voice final]`/`[RESOLVED]`/
`Command ->` line to the phrase number here in order, and compute latency
using the methodology above. Note down which tier
(`tier=exact`/`semantic`/`llm`) recognized each phrase, or that none did.

The console doesn't actually print literal `tier=exact` — the tier shows
up in the brackets in the `[RESOLVED]` line: `(voice exact match)` /
`(voice semantic model)` / `(voice LLM model)` (labels from
`SignalMapper.VOICE_TIER_LABEL`).

---

## Human session results (2026-07-17)

Historical section — the numbers below describe a session that still
included the `YES`/`NO` commands (since removed from
`config/mapping.json` as having no rule at all in `fusion.json`, see
§6.5 in `voice_pipeline_fixes_log.md`; they also got 0 resolutions across
the whole session, which confirmed the decision to remove them). So "116
items" here is the set as it stood at the time; the current
`voice_test_phrases.md` has 6 fewer lines (5 commands × 3 tiers instead
of 7).

The full session (147 phrases, 28 min, `logs/app.log` 11:42:30–12:10:48)
was parsed automatically — the results are embedded in two QA checklist
artifacts (a checkbox + a tier/latency field per item). Below is the
methodology and limitations of that parse, not the numbers themselves
(the numbers and notes are in the artifacts and in
[`voice_pipeline_fixes_log.md`](voice_pipeline_fixes_log.md) §6.5, the
aggregates are there too, §6, "Results of the 2026-07-17 session").

**Why the Nth phrase in the script can't just be matched to the Nth
`[RESOLVED]` line:** for a short session (a few phrases, no repeats) it
can — that's exactly what's assumed above. In a 28-minute session with
147 real attempts (including repeats, when a phrase wasn't understood the
first time), direct "in order" matching (FIFO: the Nth still-unused
`[voice final]` ⟷ the Nth next result) breaks the moment even one phrase
is lost with no log line at all (§6.2 of the fixes log) — every
subsequent pair shifts, and the measured "latency" starts meaning the
time until an unrelated, much older phrase. The first parsing pass did
exactly this, and as a result only gave reliable timing for ~20 of the
116 items.

**Fix:** `[RESOLVED]`/`Command ->` don't carry the phrase's text, only
the internal command name — but `IntentModel` guarantees (confirmed in
the code, `_handle_semantic_future`/`_handle_llm_future`, the
`token != self.session_token` check) that a stale background result is
NEVER published if a newer phrase has already overtaken it. This means:
every `[RESOLVED]` line always belongs to the nearest PRECEDING
`[voice final]` phrase by timestamp — regardless of queue order. Matching
"nearest preceding `[voice final]` by time" instead of FIFO fixed both
the latency and the tier attribution itself: 95 of 116 items in the
voice-only checklist now have a confirmed tier and a realistic time
(1.7–17.2s), 0 implausible values. Detailed breakdown with numbers —
`voice_pipeline_fixes_log.md` §6.6.

**What remains unconfirmed (21/116, 18%):** mostly tier-2/3 phrases for
lower-priority apps (Chrome, Discord) and environments (Study/Movie/News)
— the session simply didn't have time to go deep into each of them at
all three tiers within 28 minutes. Separately, `YES`/`NO` — neither one
resolved even ONCE across the whole session (0 occurrences in the log,
confirmed by direct count, not a side effect of the methodology).

**Why a separate synthesized-voice session is still worthwhile
(below):** even with the fixed methodology, for commands with many
natural repetitions in a session (e.g. `EXIT_MODE` — 15 occurrences,
since the tester exited every mode they tried), it's impossible to
automatically determine which of several REAL executions corresponds to
a specific test-scenario item (the tier is always correct, the time is
always real — just not necessarily that exact example). A deterministic
script with fixed pauses and no repeated phrasing removes this ambiguity
entirely.
