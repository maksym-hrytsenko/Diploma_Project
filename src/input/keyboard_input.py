from pynput import keyboard
import queue
import time


class KeyboardInput:

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.listener = None

        # macOS delivers pynput's key events on a real-time
        # CGEventTap callback thread, which the OS requires to
        # return almost immediately. Everything downstream of a
        # keyboard press (KeyboardProcessor -> ... -> ActionExecutor
        # -> OSController) can end up doing real work on whichever
        # thread calls event_bus.publish("keyboard_raw", ...) — for
        # example the Alt/Ctrl face layer's first
        # media_play_pause()/next_track() call, which loads a
        # private framework bundle synchronously. If that ever ran
        # directly on the CGEventTap thread and took too long, macOS
        # would silently disable the tap, and pynput never
        # re-enables it — the app would then stop hearing ANY key,
        # including bare alt/ctrl, for the rest of the run. So this
        # thread only ever enqueues the raw event; poll() (called
        # from the main loop) is what actually publishes onto
        # EventBus and lets the rest of the pipeline run.
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

    # ---------------------------------
    # Drain queued events (main thread)
    # ---------------------------------

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
            # Special keys
            if isinstance(key, keyboard.Key):
                name = str(key).replace("Key.", "")

                if name in ["ctrl_l", "ctrl_r"]:
                    return "ctrl"
                if name in ["shift_l", "shift_r"]:
                    return "shift"
                if name in ["alt_l", "alt_r"]:
                    return "alt"

                return name

            # Normal keys
            if hasattr(key, 'char') and key.char:
                char = key.char

                # 🔥 FIX: convert control chars back to letters
                if ord(char) < 32:
                    # Ctrl+A → chr(1+96) = 'a'
                    return chr(ord(char) + 96)

                return char.lower()

        except Exception:
            pass

        return None