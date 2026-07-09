# Runs inside a separate worker process (see
# ProcessPoolExecutor in speech_model.py). Kept as
# module-level state + a plain function, not a class
# method, so it can be pickled/targeted by the process
# pool and so the loaded model persists across calls to
# this same worker process instead of reloading every time.

_model = None


def transcribe_task(
    model_repo,
    audio_bytes
):

    global _model

    if _model is None:

        from processing.speech.open_vocab_model import (
            OpenVocabSpeechModel
        )

        _model = OpenVocabSpeechModel(
            model_repo=model_repo
        )

    return _model.transcribe(
        audio_bytes
    )
