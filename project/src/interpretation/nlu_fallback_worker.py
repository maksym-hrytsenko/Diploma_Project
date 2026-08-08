"""Entry points run inside IntentModel's NLU fallback worker process.

Kept as module-level state plus plain functions, not class methods, so they
can be pickled/targeted by ProcessPoolExecutor and so the loaded
SemanticMatcher/LLMIntentFallback models persist across calls to this same
worker process instead of reloading every time.
"""

_semantic_matcher = None

_llm_fallback = None


# Loads both fallback tiers up front, in this same worker process, instead
# of leaving each to load lazily on whichever utterance first needs it —
# see IntentModel._start_nlu_warmup for why (a cold model load used to be
# paid by the first real spoken command that missed the exact-match tier,
# e.g. the "Semantic match worker still running after 15s" case observed
# in a real session log).
def warmup_task(
    voice_commands,
    llm_model_repo
):

    global _semantic_matcher, _llm_fallback

    if _semantic_matcher is None:

        from interpretation.semantic_matcher import (
            SemanticMatcher
        )

        _semantic_matcher = SemanticMatcher(
            voice_commands
        )

    if _llm_fallback is None:

        from interpretation.llm_intent_fallback import (
            LLMIntentFallback
        )

        _llm_fallback = LLMIntentFallback(
            voice_commands,
            model_repo=llm_model_repo
        )

    return True


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
