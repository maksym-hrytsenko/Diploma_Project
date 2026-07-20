# Test phrases for voice commands

For each command — 3 tiers of hybrid recognition:

- **Tier 1 (exact match)** — the phrase verbatim from `mapping.json`,
  recognized instantly without AI.
- **Tier 2 (semantic)** — a rephrased but semantically close phrase.
  Should be caught by `SemanticMatcher` (embeddings).
- **Tier 3 (LLM)** — a long/conversational/indirect phrase that semantic
  search likely won't recognize with confidence. Should be caught by the
  LLM fallback.

Say the phrase and watch the console (`--debug-voice` if needed) — it
shows which tier fired (`tier=exact` / `tier=semantic` / `tier=llm`), or
`command not understood` if none recognized it.

---

## Opening apps

| Command | Tier 1 (exact) | Tier 2 (semantic) | Tier 3 (LLM) |
|---|---|---|---|
| OPEN_BROWSER | open browser | launch the browser | could you please open the web browser for me |
| OPEN_CHATGPT | open chatgpt | start chatgpt | hey, can you bring up chatgpt for me please |
| OPEN_GITHUB | open github | launch github | I need to look at my repositories, open github please |
| OPEN_VSCODE | open vscode | start visual studio code | can you open my code editor for me |
| OPEN_TERMINAL | open terminal | launch the terminal | I need to run some commands, open a terminal please |
| OPEN_SAFARI | open safari | start safari | could you bring up safari for me please |
| OPEN_CHROME | open chrome | launch chrome | can you please open google chrome for me |
| OPEN_SPOTIFY | open spotify | start spotify | I feel like listening to some music, open spotify please |
| OPEN_SLACK | open slack | launch slack | can you open up slack, I need to check messages |
| OPEN_DISCORD | open discord | start discord | could you please bring up discord for me |
| OPEN_MAIL | open mail | open my email | I need to check my email, could you open mail please |
| OPEN_CALENDAR | open calendar | show my calendar | can you please open up my calendar for me |
| OPEN_NOTES | open notes | open my notes | I want to write something down, open notes please |
| OPEN_TELEGRAM | open telegram | launch telegram | could you open telegram, I need to message someone |
| OPEN_FINDER | open finder | open the file browser | I need to find a file, could you open finder please |
| OPEN_NOTION | open notion | launch notion | can you please bring up notion for me |
| OPEN_PHOTOS | open photos | show my photos | I want to look at some pictures, open photos please |
| OPEN_PREVIEW | open preview | launch preview | could you please open the preview app for me |
| OPEN_SETTINGS | open settings | open system settings | can you please bring up the settings for me |

## Modes

| Command | Tier 1 (exact) | Tier 2 (semantic) | Tier 3 (LLM) |
|---|---|---|---|
| PRESENTATION_MODE | presentation mode | switch to presentation mode | I'm about to give a talk, could you switch me into presentation mode |
| FLIP_MODE | flip mode | switch to flip mode | I want to scroll through pages, can you put me in flip mode please |
| CURSOR_MODE | cursor mode | switch to cursor mode | I need to control the mouse with my hand, switch to cursor mode please |
| CALL_MODE | call mode | switch to call mode | I'm joining a meeting, could you put me into call mode |
| TRY_MODE | try mode | switch to try mode | can you let me try things out safely without actually doing anything |

## Environments

| Command | Tier 1 (exact) | Tier 2 (semantic) | Tier 3 (LLM) |
|---|---|---|---|
| WORK_MODE | work mode | switch to work environment | I'm starting my work day, could you set everything up for work please |
| STUDY_MODE | study mode | switch to study environment | I need to focus and study now, can you set that up for me |
| MOVIE_MODE | movie mode | switch to movie environment | I want to watch a film, could you set up movie mode please |
| NEWS_MODE | news mode | switch to news environment | can you please bring up the news for me |
| JOB_SEARCH_MODE | job search mode | *(not documented)* | *(not documented)* |

## Navigation (in Presentation mode / media)

| Command | Tier 1 (exact) | Tier 2 (semantic) | Tier 3 (LLM) |
|---|---|---|---|
| NEXT_SLIDE | next slide | go to the next slide | could you please move forward to the next slide |
| PREVIOUS_SLIDE | previous slide | go back a slide | can you please go back to the previous slide |
| NEXT_TRACK | next track | skip to the next song | could you please play the next track for me |
| PREVIOUS_TRACK | previous track | go back to the last song | can you please go back to the previous track |

## Control words (short commands)

These commands are short and direct by design — tier 3 for them is
artificial, but included for completeness:

| Command | Tier 1 (exact) | Tier 2 (semantic) | Tier 3 (LLM) |
|---|---|---|---|
| START | start | begin | could you please start it now |
| STOP | stop | halt | could you please stop that now |
| PAUSE | pause | pause it | could you pause whatever is playing please |
| RESET | reset | start over | could you please reset everything back |
| EXIT_MODE | exit mode | leave this mode | could you please take me out of this mode |

---

## How to test

1. Run `python src/main.py --debug-voice`.
2. Say the phrases from the tables in order — tier 1 first (should be
   `tier=exact`, instant), then tier 2 (`tier=semantic`), then tier 3
   (`tier=llm`, ~0.3-1s of latency).
3. If tier 2 or 3 doesn't fire (`command not understood`) — either the
   `semantic_threshold` in `system.json` is too high for this phrase, or
   the LLM decided it doesn't match any command. Note down exactly which
   phrases failed — that indicates whether the threshold needs lowering.
