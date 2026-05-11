from processing.gesture.gesture_model import GestureModel


class GestureRecognizer:
    def __init__(self, event_bus):
        self.event_bus = event_bus

        self.gesture_model = GestureModel()

        self.last_gesture = None

    def start(self):
        self.event_bus.subscribe("camera_frame", self._handle_frame)

    def stop(self):
        self.event_bus.unsubscribe("camera_frame", self._handle_frame)

    def _handle_frame(self, event):
        frame = event.get("data")

        if frame is None:
            return

        result = self.gesture_model.process_frame(frame)

        if not result:
            return

        if not result.gestures:
            return

        gesture_category = result.gestures[0][0]

        gesture_name = gesture_category.category_name
        confidence = gesture_category.score

        # Skip repeated spam
        if gesture_name == self.last_gesture:
            return

        self.last_gesture = gesture_name

        print(
            f"[GestureRecognizer] "
            f"{gesture_name} "
            f"({confidence:.2f})"
        )