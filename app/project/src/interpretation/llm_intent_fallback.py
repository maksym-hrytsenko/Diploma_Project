"""Local LLM fallback for voice commands.

Used by IntentModel as a last resort when a spoken phrase matches neither
config/mapping.json exactly nor SemanticMatcher's similarity threshold: asks
a local MLX-hosted LLM to map the phrase to one of the known commands (or
null), via a constrained JSON-only prompt.
"""

import json
import re

from mlx_lm import (
    load,
    generate
)


class LLMIntentFallback:

    def __init__(
        self,
        voice_commands,
        model_repo="mlx-community/Llama-3.2-3B-Instruct-4bit"
    ):

        self.commands = set(
            voice_commands.keys()
        )

        self.model, self.tokenizer = load(
            model_repo
        )

    def interpret(
        self,
        text
    ):

        if not text:
            return None

        prompt = self._build_prompt(
            text
        )

        raw_response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=40,
            verbose=False
        )

        command = self._parse_command(
            raw_response
        )

        if command not in self.commands:
            return None

        return command

    def _build_prompt(
        self,
        text
    ):

        command_list = "\n".join(
            f"- {command}"
            for command in sorted(self.commands)
        )

        messages = [

            {
                "role": "system",
                "content": (
                    "You map a spoken phrase to exactly one command from a "
                    "fixed list, or to null if none of the commands match "
                    "the phrase's meaning. Respond with ONLY a JSON object, "
                    "for example {\"command\": \"OPEN_BROWSER\"} or "
                    "{\"command\": null}. No explanation, no extra text."
                )
            },

            {
                "role": "user",
                "content": (
                    f"Commands:\n{command_list}\n\n"
                    f"Phrase: \"{text}\""
                )
            }

        ]

        return self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True
        )

    def _parse_command(
        self,
        raw_response
    ):

        match = re.search(
            r"\{.*\}",
            raw_response,
            re.DOTALL
        )

        if not match:
            return None

        try:

            parsed = json.loads(
                match.group(0)
            )

        except json.JSONDecodeError:

            return None

        return parsed.get(
            "command"
        )
