# core/state_manager.py

class StateManager:
    def __init__(self):
        self.mode = "offline"  # або "online"

    def set_mode(self, mode):
        self.mode = mode

    def get_mode(self):
        return self.mode