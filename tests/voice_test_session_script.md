# Скрипт голосової тест-сесії

Один суцільний список фраз для промовляння підряд — покриває всі голосові
команди з `voice_test_phrases.md`, згруповані зручно для однієї сесії
поспіль. Порядок групування тут навмисно "по колу" між різними
режимами/середовищами замість повтору того самого — повторний вхід у
режим/середовище, в якому ви вже перебуваєте, це мовчазний no-op (без
жодного рядка в лозі), тож старий порядок робив би успіх і провал рівня
2/3 невідрізнюваними.

## Як виміряти затримку (мікрофон -> виконання команди)

Кожен голосовий фрагмент логується рядком

```
[voice final] "..." (tier, wake_word_heard=..., speech_onset=X.XXX)
```

`speech_onset` — оцінка wall-clock моменту, коли людина фактично почала
говорити: час публікації відповідного `audio_chunk` мінус тривалість
самого чанка, скоригована на офсет, де саме всередині буфера VAD виявив
початок мовлення (`VoskSpeechModel.utterance_start_time` /
`_finalize_utterance` в `src/processing/speech/speech_model.py`). Команда,
яка врешті виконується, логується рядками `[RESOLVED] <ACTION> <- ...`
(`signal_mapper.py`) і `Command -> <ACTION>` (`action_executor.py`) —
кожен рядок логу має власний `%(asctime)s`-таймстемп на початку
(`src/utils/logger.py`). **Затримка мікрофон -> виконання** = час рядка
`Command ->` мінус `speech_onset` відповідного `[voice final]` рядка для
тієї ж фрази.

`[voice final]` логується завжди на рівні INFO, незалежно від
`--debug-voice` — його видно в `logs/app.log` навіть без прапорця.

## Debug-режим

```
python src/main.py --debug-voice
```

Вмикає докладне логування розпізнавання: проміжні (`[voice partial]`)
гіпотези під час промовляння фрази, і — завжди, з чи без прапорця —
фінальний результат (`[voice final]`) з тим самим `speech_onset` для
вимірювання затримки вище. Корисно запускати окремо від решти застосунку
(без камери в кадрі, без активного жестового режиму), якщо мета — саме
голосовий конвеєр, а не повний прогін системи.

## Як запустити

```
source venv/bin/activate
python src/main.py --debug-voice
```

Кажіть кожну фразу окремо, з невеликою паузою після (~1-2с), перш ніж
переходити до наступної. Після кожного блоку (позначено `---`) можна
зробити паузу.

---

## Блок A — Вхід у режими (5 режимів × 3 рівні, по колу)

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

## Блок B — Середовища (5 середовищ, по колу)

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

(Середовище саме по собі виходом не завершується — воно просто лишається
активним після останньої фрази, це нормально.)

---

## Блок C — Відкриття застосунків (19 команд × 3 рівні)

Це одноразові команди (не стан), повторний запуск завжди видно в лозі —
порядок можна лишити як є.

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

## Блок D — Навігація (слайди й трек, 4 команди × 3 рівні)

Слайди мають сенс лише в режимі Presentation — увійдіть у нього перед
пунктом 87 (`jack presentation mode`), вийдіть після (`jack exit mode`).
Трек-команди — глобальні, режим не потрібен.

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

## Блок E — Керуючі слова (7 команд × 3 рівні)

101. jack yes
102. jack yeah
103. jack that's correct, go ahead
104. jack no
105. jack nope
106. jack that's not right, cancel that
107. jack start
108. jack begin
109. jack could you please start it now
110. jack stop
111. jack halt
112. jack could you please stop that now
113. jack pause
114. jack pause it
115. jack could you pause whatever is playing please
116. jack reset
117. jack start over
118. jack could you please reset everything back
119. jack exit mode
120. jack leave this mode
121. jack could you please take me out of this mode

---

## Після сесії

Читайте `logs/app.log`, зіставляйте кожен `[voice final]`/`[RESOLVED]`/
`Command ->` рядок з номером фрази тут по порядку, і рахуйте затримку за
методикою вище. Занотуйте, який рівень (`tier=exact`/`semantic`/`llm`)
розпізнав кожну фразу, або що жоден не розпізнав.
