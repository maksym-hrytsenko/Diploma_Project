import cv2

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

        if result is None:
            return

        # Draw landmarks
        if result.hand_landmarks:
            for hand_landmarks in result.hand_landmarks:
                self.gesture_model.draw_landmarks(
                    frame,
                    hand_landmarks
                )

        # No gestures detected
        if not result.gestures:
            cv2.imshow("Gesture Debug", frame)
            cv2.waitKey(1)
            return

        gesture_category = result.gestures[0][0]

        gesture_name = gesture_category.category_name
        confidence = gesture_category.score

        # Ignore undefined gesture
        if gesture_name == "None":
            cv2.imshow("Gesture Debug", frame)
            cv2.waitKey(1)
            return

        # Ignore weak confidence
        if confidence < 0.7:
            cv2.imshow("Gesture Debug", frame)
            cv2.waitKey(1)
            return

        # Draw gesture text
        cv2.putText(
            frame,
            f"{gesture_name} ({confidence:.2f})",
            (20, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

        # Show preview
        cv2.imshow("Gesture Debug", frame)
        cv2.waitKey(1)

        # Prevent spam
        if gesture_name == self.last_gesture:
            return

        self.last_gesture = gesture_name

        print(
            f"[GestureRecognizer] "
            f"{gesture_name} "
            f"({confidence:.2f})"
        )