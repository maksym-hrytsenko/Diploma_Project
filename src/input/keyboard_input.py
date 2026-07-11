"""Global keyboard input.

Reads raw key press/release events via pynput on a background thread and
queues them; the main loop (via poll()) publishes them onto EventBus as
keyboard_raw. Performs no interpretation itself — KeyboardProcessor
normalizes these into signals downstream. Sits in the Input layer.
"""

from pynput import keyboard
import queue
import time

from core.event_bus import EventBus


class KeyboardInput:

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.listener = None

        # macOS delivers pynput's key events on a real-time CGEventTap
        # callback thread, which the OS requires to return almost
        # immediately. Downstream work triggered by a keypress (e.g. the
        # Alt/Ctrl face layer's first media_play_pause() call, which loads
        # a private framework bundle synchronously) can be slow enough that
        # running it directly on that thread would make macOS silently
        # disable the tap — and pynput never re-enables it, so the app
        # would stop hearing ANY key for the rest of the run. This thread
        # only enqueues the raw event; poll() (called from the main loop)
        # is what actually publishes it and lets the rest of the pipeline run.
        self._raw_events = queue.Queue()

    def start(self):
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()
        print("[KeyboardInput] Started")

    def stop(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
            print("[KeyboardInput] Stopped")

    def poll(self):

        while True:

            try:
                raw_event = self._raw_events.get_nowait()

            except queue.Empty:
                return

            self.event_bus.publish(
                "keyboard_raw",
                raw_event
            )

    def _on_press(self, key):
        key_name = self._get_key_name(key)

        if key_name:
            self._raw_events.put({
                "event": "press",
                "key": key_name,
                "timestamp": time.time()
            })

    def _on_release(self, key):
        key_name = self._get_key_name(key)

        if key_name:
            self._raw_events.put({
                "event": "release",
                "key": key_name,
                "timestamp": time.time()
            })

    def _get_key_name(self, key):
        try:
            if isinstance(key, keyboard.Key):
                name = str(key).replace("Key.", "")

                if name in ["ctrl_l", "ctrl_r"]:
                    return "ctrl"
                if name in ["shift_l", "shift_r"]:
                    return "shift"
                if name in ["alt_l", "alt_r"]:
                    return "alt"

                return name

            if hasattr(key, 'char') and key.char:
                char = key.char

                # pynput reports Ctrl+<letter> as the control character
                # (e.g. Ctrl+A as chr(1)) instead of the letter itself;
                # shifting back by 96 recovers the letter ('a' = chr(97)).
                if ord(char) < 32:
                    return chr(ord(char) + 96)

                return char.lower()

        except Exception:
            pass

        return None