"""Embedding-similarity fallback for voice commands.

Used by IntentModel when a spoken phrase doesn't exactly match a
config/mapping.json entry: embeds the phrase and every known command phrase
with a sentence-transformer model and returns the closest command if its
cosine similarity clears the caller's threshold.
"""

from sentence_transformers import (
    SentenceTransformer,
    util
)


class SemanticMatcher:

    def __init__(
        self,
        voice_commands,
        model_name="all-MiniLM-L6-v2"
    ):

        self.commands = list(
            voice_commands.keys()
        )

        self.phrases = list(
            voice_commands.values()
        )

        self.model = SentenceTransformer(
            model_name
        )

        self.phrase_embeddings = self.model.encode(
            self.phrases,
            convert_to_tensor=True
        )

    def match(
        self,
        text,
        threshold
    ):

        if not text:
            return None

        query_embedding = self.model.encode(
            text,
            convert_to_tensor=True
        )

        scores = util.cos_sim(
            query_embedding,
            self.phrase_embeddings
        )[0]

        best_index = int(
            scores.argmax()
        )

        best_score = float(
            scores[best_index]
        )

        if best_score < threshold:
            return None

        return {

            "command": self.commands[best_index],

            "confidence": best_score

        }
