"""Shared pytest fixtures for the regression suite.

Puts src/ on sys.path (the app has no installed package, only a script
layout) and provides the `pipeline` fixture: a real CommandInterpreter ->
MultimodalFusion -> SignalMapper -> ActionExecutor chain wired to a fresh
EventBus, with OSController mocked out so no OS side effects ever fire
during a test run.
"""

import os
import sys

from unittest.mock import patch

import pytest


SRC_DIR = os.path.join(
    os.path.dirname(
        os.path.abspath(__file__)
    ),
    "..",
    "src"
)

sys.path.insert(
    0,
    os.path.abspath(SRC_DIR)
)

from core.event_bus import EventBus
from interpretation.command_interpreter import CommandInterpreter
from fusion.multimodal_fusion import MultimodalFusion
from fusion.signal_mapper import SignalMapper
from execution.action_executor import ActionExecutor


class PipelineHarness:
    """Publishes raw signals exactly as the real recognizers would, and
    asserts on which OSController methods the pipeline ended up calling.
    """

    def __init__(self, event_bus, signal_mapper, controller):

        self.event_bus = event_bus
        self.signal_mapper = signal_mapper
        self.controller = controller

    def voice(self, command, confidence=1.0):

        self.event_bus.publish(
            "intent_detected",
            {
                "command": command,
                "confidence": confidence,
                "source": "voice"
            }
        )

    def gesture(self, signal, confidence=1.0):

        self.event_bus.publish(
            "gesture_signal",
            {
                "signal": signal,
                "confidence": confidence,
                "source": "gesture"
            }
        )

    def face(self, signal):

        self.event_bus.publish(
            "face_signal",
            {
                "signal": signal,
                "source": "face"
            }
        )

    def key(self, signal, action):

        self.event_bus.publish(
            "keyboard_signal",
            {
                "signal": signal,
                "event": action
            }
        )

    def stream(self, event_type, data):

        self.event_bus.publish(
            event_type,
            data
        )

    def assert_called(self, *method_names):

        missing = [
            name for name in method_names
            if not getattr(self.controller, name).called
        ]

        assert not missing, (
            f"expected OSController methods to be called: {missing}"
        )

        self.controller.reset_mock()


@pytest.fixture
def pipeline():

    with patch(
        "execution.action_executor.OSController"
    ) as MockOSController:

        event_bus = EventBus()

        interpreter = CommandInterpreter(event_bus)
        fusion = MultimodalFusion(event_bus)
        signal_mapper = SignalMapper(event_bus)
        executor = ActionExecutor(event_bus)

        interpreter.start()
        fusion.start()
        signal_mapper.start()
        executor.start()

        controller = MockOSController.return_value

        yield PipelineHarness(
            event_bus,
            signal_mapper,
            controller
        )

        interpreter.stop()
        fusion.stop()
        signal_mapper.stop()
        executor.stop()
