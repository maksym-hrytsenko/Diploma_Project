from processing.speech.speech_model import (
    VoskSpeechModel
)


class SpeechRecognizer:

    def __init__(
        self,
        event_bus,
        state_manager,
        debug=False
    ):

        self.event_bus = event_bus

        self.state_manager = state_manager

        self.debug = debug

        self.last_partial_text = None

        self.vosk_model = (
            VoskSpeechModel()
        )

    # ---------------------------------
    # Start
    # ---------------------------------

    def start(self):

        self.event_bus.subscribe(
            "audio_chunk",
            self.on_audio
        )

    # ---------------------------------
    # Stop
    # ---------------------------------

    def stop(self):

        self.event_bus.unsubscribe(
            "audio_chunk",
            self.on_audio
        )

        self.vosk_model.close()

    # ---------------------------------
    # Audio Handler
    # ---------------------------------

    def on_audio(self, event):

        data = event.get(
            "data"
        )

        if data is None:
            return

        result = self.vosk_model.process_audio(
            data
        )

        if result is None:
            return

        # Ignore partial recognition, but still show it in
        # debug mode — this is the rawest possible view of
        # what the model is hearing while you are still
        # speaking, useful for spotting whether the phrase
        # is getting cut short before it ever reaches command
        # handling. Vosk repeats the same partial hypothesis
        # (often "[unk]") many times in a row while it waits
        # for more audio, so only print when it actually
        # changes — otherwise this floods the terminal and
        # adds print overhead on every single audio chunk
        # instead of only on real changes.
        if not result.get(
            "is_final",
            False
        ):

            partial_text = result.get("text")

            if (
                self.debug
                and partial_text != self.last_partial_text
            ):

                print(
                    f"[voice partial] \"{partial_text}\""
                )

                self.last_partial_text = partial_text

            return

        self.last_partial_text = None

        text = result.get(
            "text"
        )

        wake_word_heard = result.get(
            "wake_word_heard",
            False
        )

        if self.debug:

            source = (
                "open-vocab"
                if result.get("open_vocab")
                else "grammar"
            )

            print(
                f"[voice final] \"{text}\" "
                f"({source}, wake_word_heard="
                f"{wake_word_heard})"
            )

        self.event_bus.publish(
            "text_ready",
            {
                "text": text,
                "wake_word_heard": wake_word_heard
            }
        )