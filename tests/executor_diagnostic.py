import os
import subprocess
import sys
import time

# ---------------------------------
# Unlike the other *_standalone_test.py
# scripts in this folder, this one
# deliberately DOES import from src/ —
# the whole point is to exercise the
# exact OSController code path
# ActionExecutor calls in production,
# not a reimplementation that could
# silently diverge from it.
# ---------------------------------

SRC_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "src"
)

sys.path.insert(0, SRC_DIR)

from execution.os_controller import OSController  # noqa: E402


def check_accessibility_trust():

    print("--- Accessibility permission ---")

    try:

        from ApplicationServices import AXIsProcessTrusted

        trusted = AXIsProcessTrusted()

        print(
            "AXIsProcessTrusted() -> {}".format(trusted)
        )

        if not trusted:

            print(
                "NOT TRUSTED. Every synthetic action below "
                "(cursor, screenshot, media keys) will silently "
                "do nothing until this process is granted "
                "Accessibility permission: System Settings -> "
                "Privacy & Security -> Accessibility -> enable "
                "whichever app/terminal is actually running this "
                "script right now (Terminal.app, iTerm, your "
                "IDE's integrated terminal — check which one you "
                "launched this from, granting one does NOT grant "
                "another)."
            )

        return trusted

    except Exception as e:

        print(
            f"Could not check trust status: {e}"
        )

        return None


def screenshot_save_dir():

    try:

        result = subprocess.run(
            [
                "defaults",
                "read",
                "com.apple.screencapture",
                "location"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        custom_path = result.stdout.strip()

        if custom_path:

            return os.path.expanduser(custom_path)

    except Exception:
        pass

    return os.path.expanduser("~/Desktop")


def find_latest_png(directory):

    if not os.path.isdir(directory):
        return None

    candidates = [
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.lower().endswith(".png")
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=os.path.getmtime
    )


def wait_and_run(label, action, seconds=2):

    print(
        f"\n--- {label} --- (firing in {seconds}s, "
        "watch the player/screen now)"
    )

    time.sleep(seconds)

    action()

    input(
        "Press Enter once you've observed the result... "
    )


def main():

    trusted = check_accessibility_trust()

    controller = OSController()

    input(
        "\nStart something playing now (Spotify, a YouTube tab, "
        "Music.app), then press Enter... "
    )

    wait_and_run(
        "MEDIA_PLAY_PAUSE",
        controller.media_play_pause
    )

    wait_and_run(
        "NEXT_TRACK",
        controller.next_track
    )

    wait_and_run(
        "PREVIOUS_TRACK",
        controller.previous_track
    )

    print("\n--- TAKE_SCREENSHOT ---")

    save_dir = screenshot_save_dir()

    print(
        f"Screenshots save to: {save_dir}"
    )

    before = find_latest_png(save_dir)

    controller.take_screenshot()

    time.sleep(1)

    after = find_latest_png(save_dir)

    if after is not None and after != before:

        print(
            f"New screenshot found: {after}"
        )

    else:

        print(
            f"No new .png appeared in {save_dir}. "
            + (
                "Accessibility is not trusted (see above) — "
                "that's almost certainly why."
                if trusted is False else
                "Accessibility looked trusted, so if this still "
                "did nothing, double check the folder above is "
                "actually correct (`defaults read "
                "com.apple.screencapture location`)."
            )
        )

    print(
        "\nIf NEXT_TRACK/PREVIOUS_TRACK/MEDIA_PLAY_PAUSE did nothing "
        "above even though the screenshot DID appear, that's a "
        "narrower problem specific to the system media-key event "
        "(OSController._post_system_media_key) — worth comparing "
        "against pressing a real hardware media key (fn+F7/F8/F9 on "
        "most Mac keyboards) with the same player open, to check "
        "whether macOS's own 'Now Playing' routing even reaches that "
        "player at all."
    )


if __name__ == "__main__":
    main()
