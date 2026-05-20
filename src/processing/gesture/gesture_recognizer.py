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

        self.previous_x = None
        self.previous_y = None

        self.previous_time = None

        # Faster reaction
        self.velocity_threshold = 1.8

        # Minimum swipe distance
        self.distance_threshold = 0.12

        # Cooldown
        self.last_motion_time = 0

        self.motion_cooldown = 0.35

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
        # Dynamic Motion Gestures
        # ---------------------------------

        if result.hand_landmarks:

            hand_landmarks = (
                result.hand_landmarks[0]
            )

            # Index fingertip
            index_tip = hand_landmarks[8]

            current_x = index_tip.x
            current_y = index_tip.y

            current_time = time.time()

            if (
                self.previous_x is not None
                and self.previous_y is not None
                and self.previous_time is not None
            ):

                delta_x = (
                    current_x -
                    self.previous_x
                )

                delta_y = (
                    current_y -
                    self.previous_y
                )

                distance_x = abs(delta_x)

                distance_y = abs(delta_y)

                delta_time = (
                    current_time -
                    self.previous_time
                )

                if delta_time > 0:

                    velocity_x = (
                        delta_x /
                        delta_time
                    )

                    velocity_y = (
                        delta_y /
                        delta_time
                    )

                    cooldown_ready = (
                        current_time -
                        self.last_motion_time
                    ) > self.motion_cooldown

                    horizontal_motion = (
                        abs(velocity_x) >
                        abs(velocity_y)
                    )

                    # ---------------------------------
                    # HAND LEFT
                    # ---------------------------------

                    if (
                        velocity_x >
                        self.velocity_threshold
                        and distance_x >
                        self.distance_threshold
                        and horizontal_motion
                        and cooldown_ready
                    ):

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

                    # ---------------------------------
                    # HAND RIGHT
                    # ---------------------------------

                    elif (
                        velocity_x <
                        -self.velocity_threshold
                        and distance_x >
                        self.distance_threshold
                        and horizontal_motion
                        and cooldown_ready
                    ):

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
                    # HAND DOWN
                    # ---------------------------------

                    elif (
                        velocity_y >
                        self.velocity_threshold
                        and distance_y >
                        self.distance_threshold
                        and not horizontal_motion
                        and cooldown_ready
                    ):

                        self.event_bus.publish(
                            "gesture_signal",
                            {
                                "signal": "HAND_DOWN",
                                "source": "gesture"
                            }
                        )

                        self.last_motion_time = (
                            current_time
                        )

                    # ---------------------------------
                    # HAND UP
                    # ---------------------------------

                    elif (
                        velocity_y <
                        -self.velocity_threshold
                        and distance_y >
                        self.distance_threshold
                        and not horizontal_motion
                        and cooldown_ready
                    ):

                        self.event_bus.publish(
                            "gesture_signal",
                            {
                                "signal": "HAND_UP",
                                "source": "gesture"
                            }
                        )

                        self.last_motion_time = (
                            current_time
                        )

            # Save current values
            self.previous_x = current_x
            self.previous_y = current_y

            self.previous_time = current_time

        # ---------------------------------
        # Static Gestures
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

        # Ignore undefined gesture
        if gesture_name == "None":
            return

        # Ignore weak confidence
        if confidence < 0.7:
            return

        # Prevent spam
        if gesture_name == self.last_gesture:
            return

        self.last_gesture = gesture_name

        # Publish static gesture
        self.event_bus.publish(
            "gesture_signal",
            {
                "signal": gesture_name,
                "confidence": confidence,
                "source": "gesture"
            }
        )