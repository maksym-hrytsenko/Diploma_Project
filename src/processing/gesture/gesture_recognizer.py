import time

from processing.gesture.gesture_model import (
    GestureModel
)


class GestureRecognizer:

    def __init__(self, event_bus):

        self.event_bus = event_bus

        self.gesture_model = GestureModel()

        self.last_gesture = None

        # ---------------------------------
        # Motion Detection
        # ---------------------------------

        self.previous_index_x = None

        self.motion_threshold = 0.08

        self.last_motion_time = 0

        self.motion_cooldown = 0.5

    def start(self):

        self.event_bus.subscribe(
            "camera_frame",
            self._handle_frame
        )

    def stop(self):

        self.event_bus.unsubscribe(
            "camera_frame",
            self._handle_frame
        )

    def _handle_frame(self, event):

        frame = event.get("data")

        if frame is None:
            return

        # ---------------------------------
        # Process Frame
        # ---------------------------------

        result = self.gesture_model.process_frame(
            frame
        )

        if result is None:
            return

        # ---------------------------------
        # No Gesture Detected
        # ---------------------------------

        if not result.gestures:
            return

        gesture_category = (
            result.gestures[0][0]
        )

        gesture_name = (
            gesture_category.category_name
        )

        confidence = (
            gesture_category.score
        )

        # ---------------------------------
        # Ignore Undefined Gesture
        # ---------------------------------

        if gesture_name == "None":
            return

        # ---------------------------------
        # Ignore Weak Confidence
        # ---------------------------------

        if confidence < 0.7:
            return

        # ---------------------------------
        # Motion Enabled Only
        # For Open Palm
        # ---------------------------------

        motion_enabled = (
            gesture_name == "Open_Palm"
        )

        # ---------------------------------
        # Hand Motion Detection
        # ---------------------------------

        if (
            motion_enabled
            and result.hand_landmarks
        ):

            hand_landmarks = (
                result.hand_landmarks[0]
            )

            index_tip = hand_landmarks[8]

            index_x = index_tip.x

            current_time = time.time()

            if self.previous_index_x is not None:

                delta_x = (
                    index_x -
                    self.previous_index_x
                )

                cooldown_ready = (
                    current_time -
                    self.last_motion_time
                ) > self.motion_cooldown

                # ---------------------------------
                # RIGHT MOTION
                # ---------------------------------

                if (
                    delta_x >
                    self.motion_threshold
                    and cooldown_ready
                ):

                    print(
                        "[GestureRecognizer] "
                        "HAND_RIGHT"
                    )

                    self.event_bus.publish(
                        "gesture_signal",
                        {
                            "signal": "HAND_RIGHT",
                            "source": "gesture"
                        }
                    )

                    self.last_motion_time = (
                        current_time
                    )

                # ---------------------------------
                # LEFT MOTION
                # ---------------------------------

                elif (
                    delta_x <
                    -self.motion_threshold
                    and cooldown_ready
                ):

                    print(
                        "[GestureRecognizer] "
                        "HAND_LEFT"
                    )

                    self.event_bus.publish(
                        "gesture_signal",
                        {
                            "signal": "HAND_LEFT",
                            "source": "gesture"
                        }
                    )

                    self.last_motion_time = (
                        current_time
                    )

            self.previous_index_x = index_x

        # ---------------------------------
        # Prevent Gesture Spam
        # ---------------------------------

        if gesture_name == self.last_gesture:
            return

        self.last_gesture = gesture_name

        # ---------------------------------
        # Debug Output
        # ---------------------------------

        print(
            f"[GestureRecognizer] "
            f"{gesture_name} "
            f"({confidence:.2f})"
        )

        # ---------------------------------
        # Publish Gesture Event
        # ---------------------------------

        self.event_bus.publish(
            "gesture_signal",
            {
                "signal": gesture_name,
                "confidence": confidence,
                "source": "gesture"
            }
        )