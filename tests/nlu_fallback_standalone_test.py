"""Standalone test of the IntentModel three-tier fallback chain.

Unlike the other *_standalone_test.py scripts in this folder, this one
DOES import from src/ — it exercises the real fallback chain (exact
match -> semantic -> LLM) added for AI-ENHANCED voice mode, not a
pre-integration library spike.
"""
import sys
import os
import time

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

SRC_DIR = os.path.join(
    BASE_DIR,
    "src"
)

sys.path.insert(
    0,
    SRC_DIR
)

from interpretation.intent_model import (
    IntentModel
)

# Each entry is (phrase, expected_command_or_None).
TEST_CASES = [

    # Exact matches -> fast path, no fallback models touched.
    ("open browser", "OPEN_BROWSER"),
    ("cursor mode", "CURSOR_MODE"),

    # Paraphrases -> expected to be caught by the semantic layer.
    ("launch the browser", "OPEN_BROWSER"),
    ("please start spotify", "OPEN_SPOTIFY"),

    # Less literal phrasing -> may need the LLM layer.
    ("could you open the browser please", "OPEN_BROWSER"),

    # Out-of-scope -> must resolve to None, never a hallucinated command.
    ("what is the weather today", None),
    ("tell me a joke", None),

]

def run():

    print("Loading IntentModel...")

    model = IntentModel(
        event_bus=None,
        state_manager=None
    )

    print(
        f"nlu_fallback.enabled = {model.nlu_fallback_enabled}"
    )

    print(
        f"semantic_threshold = {model.semantic_threshold}, "
        f"llm_model = {model.llm_model_id}\n"
    )

    passed = 0

    for phrase, expected in TEST_CASES:

        # Wake word must precede every command — it opens the
        # listening session that process_text() requires.
        model.process_text(
            model.wake_word
        )

        start_time = time.time()

        result = model.process_text(phrase)

        latency = time.time() - start_time

        command = (
            result.get("command")
            if result
            else None
        )

        confidence = (
            result.get("confidence")
            if result
            else None
        )

        if confidence == 1.0:
            tier = "exact"

        elif confidence == model.llm_confidence:
            tier = "llm"

        elif confidence is not None:
            tier = "semantic"

        else:
            tier = "none"

        ok = command == expected

        passed += int(ok)

        status = "PASS" if ok else "FAIL"

        print(
            f"[{status}] \"{phrase}\" -> {command} "
            f"(tier={tier}, confidence={confidence}, "
            f"{latency:.3f}s)"
        )

    print(
        f"\n{passed}/{len(TEST_CASES)} passed"
    )

    print(
        "\nNote: this only covers text -> intent matching. "
        "The audio -> text side (grammar miss -> [unk] -> "
        "open-vocab Whisper re-transcription) needs a live "
        "microphone; run `python src/main.py` and speak an "
        "unregistered phrase to exercise that path manually, "
        "per the checklist in docs/SYSTEM_FUNCTIONS.md."
    )

    if model.nlu_executor is not None:

        model.nlu_executor.shutdown(
            wait=False,
            cancel_futures=True
        )


# Semantic/LLM matching runs in a separate worker process (see
# ProcessPoolExecutor in intent_model.py), which on macOS requires the
# process-spawning code to sit behind this guard.
if __name__ == "__main__":

    run()
