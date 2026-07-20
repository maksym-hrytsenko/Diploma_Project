"""Tracks whether the system is running in offline or online mode."""


class StateManager:
    def __init__(self):
        self.mode = "offline"

    def set_mode(self, mode):
        self.mode = mode

    def get_mode(self):
        return self.mode
