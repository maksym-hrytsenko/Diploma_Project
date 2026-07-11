"""Standalone test for the MediaRemote framework command path.

This is the same private mechanism macOS uses to route Control Center's
Now Playing widget and Bluetooth headphone remote buttons (AVRCP) to
whichever app owns "now playing". Because it's a private framework, it
is tested in isolation here before touching OSController: a syntax or
signature mistake would otherwise silently do nothing (no exception),
the same failure mode already seen with the NX_KEYTYPE HID key approach.
"""
import time

import objc
from Foundation import NSBundle


MEDIA_REMOTE_BUNDLE_PATH = (
    "/System/Library/PrivateFrameworks/MediaRemote.framework"
)

# MRMediaRemoteCommand values, reverse-engineered from the framework's
# public headers/symbols. Only the ones this project needs.
COMMAND_PLAY = 0
COMMAND_PAUSE = 1
COMMAND_TOGGLE_PLAY_PAUSE = 2
COMMAND_NEXT_TRACK = 4
COMMAND_PREVIOUS_TRACK = 5


def load_media_remote_send_command():

    bundle = NSBundle.bundleWithPath_(
        MEDIA_REMOTE_BUNDLE_PATH
    )

    if bundle is None:

        raise RuntimeError(
            f"Could not load bundle at {MEDIA_REMOTE_BUNDLE_PATH}"
        )

    functions = [
        ("MRMediaRemoteSendCommand", b"Bi@")
    ]

    objc.loadBundleFunctions(
        bundle,
        globals(),
        functions
    )

    if "MRMediaRemoteSendCommand" not in globals():

        raise RuntimeError(
            "MRMediaRemoteSendCommand symbol not found in "
            "MediaRemote.framework — it may have moved or "
            "been renamed on this macOS version."
        )

    return globals()["MRMediaRemoteSendCommand"]


def send_command(send_function, command, label):

    print(
        f"\n--- {label} --- (firing in 2s, watch the player now)"
    )

    time.sleep(2)

    result = send_function(
        command,
        None
    )

    print(
        f"MRMediaRemoteSendCommand returned: {result}"
    )

    input(
        "Press Enter once you've observed the result... "
    )


def main():

    print("--- Loading MediaRemote.framework ---")

    send_function = load_media_remote_send_command()

    print("Loaded OK.")

    input(
        "\nStart something playing now (Spotify, a YouTube tab, "
        "Music.app), then press Enter... "
    )

    send_command(
        send_function,
        COMMAND_TOGGLE_PLAY_PAUSE,
        "TOGGLE_PLAY_PAUSE"
    )

    send_command(
        send_function,
        COMMAND_NEXT_TRACK,
        "NEXT_TRACK"
    )

    send_command(
        send_function,
        COMMAND_PREVIOUS_TRACK,
        "PREVIOUS_TRACK"
    )

    print(
        "\nIf these worked where the NX_KEYTYPE HID approach "
        "(tests/executor_diagnostic.py) didn't, OSController should "
        "be switched to MRMediaRemoteSendCommand for "
        "media_play_pause/next_track/previous_track."
    )


if __name__ == "__main__":
    main()
