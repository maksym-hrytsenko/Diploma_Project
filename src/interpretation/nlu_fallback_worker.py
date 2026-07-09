# Runs inside a separate worker process (see
# ProcessPoolExecutor in intent_model.py). Kept as
# module-level state + plain functions, not class methods,
# so they can be pickled/targeted by the process pool and
# so the loaded models persist across calls to this same
# worker process instead of reloading every time.

_semantic_matcher = None

_llm_fallback = None


def semantic_match_task(
    voice_commands,
    threshold,
    text
):

    global _semantic_matcher

    if _semantic_matcher is None:

        from interpretation.semantic_matcher import (
            SemanticMatcher
        )

        _semantic_matcher = SemanticMatcher(
            voice_commands
        )

    return _semantic_matcher.match(
        text,
        threshold
    )


def llm_interpret_task(
    voice_commands,
    model_repo,
    text
):

    global _llm_fallback

    if _llm_fallback is None:

        from interpretation.llm_intent_fallback import (
            LLMIntentFallback
        )

        _llm_fallback = LLMIntentFallback(
            voice_commands,
            model_repo=model_repo
        )

    return _llm_fallback.interpret(
        text
    )
