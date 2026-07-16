# Global functions test scenarios (app launching, media control)

These voice-triggered functions work identically regardless of mode —
they are always available, not scoped to Presentation/Flip/Cursor/Call.
`tests/voice_test_phrases.md` already exhaustively covers all three
recognition tiers (exact/semantic/LLM) for every command below; this
document instead verifies that the command, once recognized, actually
produces the correct **real** OS-level effect — the thing the
automated regression suite cannot see because `OSController` is mocked
there.

Grading: **binary** (pass/fail) — either the real app/effect happens or
it doesn't.

## 1. App launching (all 19 apps)

Say "jack open &lt;app&gt;" for each row (tier-1 phrasing — tier coverage
itself is `voice_test_phrases.md`'s job).

| # | Command | Expected real-world effect |
|---|---|---|
| 1 | "jack open browser" | Default browser opens to google.com |
| 2 | "jack open chatgpt" | Browser opens chatgpt.com |
| 3 | "jack open github" | Browser opens github.com |
| 4 | "jack open vscode" | VS Code opens (requires the `code` CLI on `PATH`) |
| 5 | "jack open terminal" | Terminal.app opens |
| 6 | "jack open safari" | Safari opens |
| 7 | "jack open chrome" | Google Chrome opens |
| 8 | "jack open spotify" | Spotify opens |
| 9 | "jack open slack" | Slack opens |
| 10 | "jack open discord" | Discord opens |
| 11 | "jack open mail" | Mail.app opens |
| 12 | "jack open calendar" | Calendar.app opens |
| 13 | "jack open notes" | Notes.app opens |
| 14 | "jack open telegram" | Telegram opens |
| 15 | "jack open finder" | A Finder window opens |
| 16 | "jack open notion" | Notion opens |
| 17 | "jack open photos" | Photos.app opens |
| 18 | "jack open preview" | Preview.app opens |
| 19 | "jack open settings" | System Settings opens |

## 2. Global media commands

Start playing something first (Spotify track or a YouTube tab in a
plain browser window — not a screen share, see §3).

| # | Command | Expected result |
|---|---|---|
| 1 | "jack start" | Play/pause toggles |
| 2 | "jack stop" | Play/pause toggles (same underlying toggle as "start" — it does **not** stop/rewind playback, since `STOP`/`PAUSE`/`RESET` all map to the same `MEDIA_PLAY_PAUSE` action) |
| 3 | "jack pause" | Play/pause toggles |
| 4 | "jack reset" | Play/pause toggles — confirm it does **not** restart the track from the beginning |
| 5 | "jack next track" | Skips to the next track |
| 6 | "jack previous track" | Skips to the previous track |

## 3. Media commands vs. screen-share / embedded video (known limitation)

| # | Action | Expected result |
|---|---|---|
| 1 | Play a video in a plain Safari/Chrome tab, say "jack next track" | Track/video actually advances |
| 2 | Share that same tab's content via a video-conferencing app's screen share (e.g. Zoom's "optimize for video clip" share mode), then say "jack next track" | The console still prints `[EXECUTOR] NEXT_TRACK`, but the shared video does **not** advance — confirm this is the app swallowing the media key with no error (a known platform limitation, not a bug in this system), not a silent failure of recognition |

## 4. Face-layer media combos (cross-reference)

These are already covered in `face_test_scenarios.md` §1–§3 (head tilt,
mouth open, double blink with `alt` held) — re-run them here only if
you want a combined pass covering every media-control path (voice +
face) in one session; no new scenarios beyond what that document
already defines.

## How to test

1. Run `python src/main.py --debug-voice`.
2. For §1, close each app first so opening is actually observable, and
   confirm the specific window/URL named above, not just "something
   opened."
3. For §2–§3, have real media actually playing before issuing a
   command — silence makes toggling indistinguishable from doing
   nothing.
4. Record pass/fail per row.
