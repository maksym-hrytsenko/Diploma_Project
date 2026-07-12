# Діаграми проєкту

Один файл написаний вручну, решта згенеровані автоматично з реального коду
`src/` (не з уяви) за допомогою `pyreverse` (частина `pylint`) та `pydeps`.

| Файл | Що це | Джерело |
|---|---|---|
| `architecture_flow.md` | Потік даних через EventBus (Input → ... → OSController) | вручну (Mermaid) |
| `classes_MultimodalControlSystem.mmd` / `.png` | UML-діаграма класів: усі 34 класи, їхні атрибути й методи | автоматично, `pyreverse` |
| `packages_MultimodalControlSystem.mmd` / `.png` | Повний граф imports між усіма 35 модулями (детальний, без угруповання) | автоматично, `pyreverse` |
| `module_dependencies.svg` | Той самий граф залежностей, згорнутий до рівня пакетів (`core`, `fusion`, `ui`, ...) — читабельніший огляд | автоматично, `pydeps` |

## Чому клас-діаграма має лише 4 зв'язки (`--*`)

Це не помилка генерації — `pyreverse` знаходить UML-зв'язки (композиція,
успадкування) лише там, де є пряме посилання на клас у коді (наприклад,
`DraggableFrame`/`ToggleSwitch` як дочірні віджети `MainWindow`). Решта
модулів свідомо не мають прямих посилань одне на одного — вони спілкуються
через рядкові імена подій в `EventBus`, а це static-аналіз побачити не може.
Тобто розрідженість діаграми фактично підтверджує слабку зв'язаність
архітектури, описану в `src/CLAUDE.md`.

## Як переглянути

- `.mmd` — текст Mermaid: відкрити у VS Code (розширення "Markdown Preview
  Mermaid Support") або вставити на [mermaid.live](https://mermaid.live)
  для редагування.
- `.png` / `.svg` — відкрити подвійним кліком (Preview.app) або в браузері.

## Як перегенерувати після зміни коду

`src/` навмисно не має `__init__.py` (модулі резолвяться відносно `src/`
під час запуску `python src/main.py`), а `pyreverse`/`pydeps` статично
резолвлять imports і потребують справжніх пакетів. Тому генерація йде на
тимчасовій копії з доданими порожніми `__init__.py`, яка одразу
видаляється — сам `src/` не чіпається.

```bash
source venv/bin/activate
pip install pylint pydeps   # якщо ще не встановлено
brew install graphviz       # потрібен бінарник `dot`

TMP=$(mktemp -d)
rsync -a --exclude='__pycache__' src/ "$TMP/src/"
find "$TMP/src" -type d -exec touch {}/__init__.py \;

# UML класів + пакетів (Mermaid + PNG)
cd "$TMP"
python3 -m pylint.pyreverse.main --source-roots . -o mmd -p MultimodalControlSystem --colorized -A -d out src
python3 -m pylint.pyreverse.main --source-roots . -o png -p MultimodalControlSystem --colorized -A -d out src

# Граф залежностей модулів (pydeps)
cd "$TMP/src"
python3 -m pydeps main.py \
  --only core config execution fusion input interpretation processing ui utils main \
  --max-bacon 0 --rankdir TB --cluster --no-show -T svg -o module_dependencies.svg

# скопіювати потрібні файли з "$TMP/out" і "$TMP/src" назад у docs/diagrams/,
# після чого видалити "$TMP"
```
