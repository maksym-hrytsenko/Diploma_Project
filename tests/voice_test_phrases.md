# Тестові фрази для голосових команд

Для кожної команди — 3 рівні гібридного розпізнавання:

- **Рівень 1 (точний збіг)** — фраза буквально з `mapping.json`, розпізнається миттєво без AI.
- **Рівень 2 (семантика)** — перефразована, але близька за змістом фраза. Має впіймати `SemanticMatcher` (embeddings).
- **Рівень 3 (LLM)** — довга/розмовна/непряма фраза, яку семантичний пошук, ймовірно, не впізнає впевнено. Має впіймати LLM-фолбек.

Кажіть фразу і дивіться в консоль (`--debug-voice` за потреби) — там видно, який саме рівень спрацював (`tier=exact` / `tier=semantic` / `tier=llm`), або `command not understood`, якщо жоден не впізнав.

---

## Відкриття застосунків

| Команда | Рівень 1 (точний) | Рівень 2 (семантика) | Рівень 3 (LLM) |
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

## Режими (modes)

| Команда | Рівень 1 (точний) | Рівень 2 (семантика) | Рівень 3 (LLM) |
|---|---|---|---|
| PRESENTATION_MODE | presentation mode | switch to presentation mode | I'm about to give a talk, could you switch me into presentation mode |
| FLIP_MODE | flip mode | switch to flip mode | I want to scroll through pages, can you put me in flip mode please |
| CURSOR_MODE | cursor mode | switch to cursor mode | I need to control the mouse with my hand, switch to cursor mode please |
| CALL_MODE | call mode | switch to call mode | I'm joining a meeting, could you put me into call mode |
| TRY_MODE | try mode | switch to try mode | can you let me try things out safely without actually doing anything |

## Оточення (environments)

| Команда | Рівень 1 (точний) | Рівень 2 (семантика) | Рівень 3 (LLM) |
|---|---|---|---|
| WORK_MODE | work mode | switch to work environment | I'm starting my work day, could you set everything up for work please |
| STUDY_MODE | study mode | switch to study environment | I need to focus and study now, can you set that up for me |
| MOVIE_MODE | movie mode | switch to movie environment | I want to watch a film, could you set up movie mode please |
| NEWS_MODE | news mode | switch to news environment | can you please bring up the news for me |
| JOB_SEARCH_MODE | job search mode | *(не задокументовано)* | *(не задокументовано)* |

## Навігація (в режимі Presentation / медіа)

| Команда | Рівень 1 (точний) | Рівень 2 (семантика) | Рівень 3 (LLM) |
|---|---|---|---|
| NEXT_SLIDE | next slide | go to the next slide | could you please move forward to the next slide |
| PREVIOUS_SLIDE | previous slide | go back a slide | can you please go back to the previous slide |
| NEXT_TRACK | next track | skip to the next song | could you please play the next track for me |
| PREVIOUS_TRACK | previous track | go back to the last song | can you please go back to the previous track |

## Керуючі слова (короткі команди)

Ці команди короткі й прямі за замислом — рівень 3 для них штучний, але для повноти:

| Команда | Рівень 1 (точний) | Рівень 2 (семантика) | Рівень 3 (LLM) |
|---|---|---|---|
| START | start | begin | could you please start it now |
| STOP | stop | halt | could you please stop that now |
| PAUSE | pause | pause it | could you pause whatever is playing please |
| RESET | reset | start over | could you please reset everything back |
| EXIT_MODE | exit mode | leave this mode | could you please take me out of this mode |

---

## Як тестувати

1. Запустіть `python src/main.py --debug-voice`.
2. Кажіть по черзі фрази з таблиць — спочатку рівень 1 (має бути `tier=exact`, миттєво), потім рівень 2 (`tier=semantic`), потім рівень 3 (`tier=llm`, ~0.3-1с затримки).
3. Якщо рівень 2 чи 3 не спрацював (`command not understood`) — це або поріг `semantic_threshold` у `system.json` занадто високий для цієї фрази, або LLM вирішила, що це не збігається з жодною командою. Занотуйте, які саме фрази не пройшли — це підкаже, чи потрібно знижувати поріг.
