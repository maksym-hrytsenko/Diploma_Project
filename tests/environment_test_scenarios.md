# Environment test scenarios

Manual test scenarios for the four voice-triggered environments (Work,
Job Search, Study, Movie, News — five, not four; see below) defined in
`config/fusion.json`. Unlike modes, environments are longer-lived and
have real side effects on the OS (opening apps, toggling Do Not
Disturb, preventing display sleep) — `test_command_pipeline.py` already
verifies the *decision logic* (the right `enter_actions`/`exit_actions`
fire in the right order) against a mocked `OSController`, so these
scenarios exist to verify the **real** OS-level effects actually happen,
which the mocked automated suite cannot see.

Grading: **binary** (pass/fail) per real-world effect.

## 1. Work environment

| # | Action | Expected result |
|---|---|---|
| 1 | Say "jack work mode" | Do Not Disturb turns on; Slack, Mail, and Calendar all actually open |

## 2. Job Search environment

| # | Action | Expected result |
|---|---|---|
| 1 | Say "jack job search mode" | Do Not Disturb turns on; the job-search browser windows actually open |

## 3. Study environment

| # | Action | Expected result |
|---|---|---|
| 1 | Say "jack study mode" | Do Not Disturb turns on; the study browser windows actually open |

## 4. Movie environment

| # | Action | Expected result |
|---|---|---|
| 1 | Say "jack movie mode" | Do Not Disturb turns on; display sleep is prevented (screen does not dim/lock during playback); TV app and Netflix actually open; the cinema-mode Shortcuts automation (smart lighting) actually runs |

## 5. News environment

| # | Action | Expected result |
|---|---|---|
| 1 | Say "jack news mode" | The news browser tabs actually open (no Do Not Disturb change — News has no `enter_actions` DND toggle) |

## 6. Exiting an environment

| # | Action | Expected result |
|---|---|---|
| 1 | From Work environment, say "jack exit mode" | Do Not Disturb turns back off (Work's `exit_actions`) |
| 2 | From Movie environment, exit it | Do Not Disturb turns back off AND display-sleep prevention is lifted (both of Movie's `exit_actions` run) |
| 3 | From News environment, exit it | Nothing happens — News has an empty `exit_actions` list, which is correct, not a bug |

## 7. Direct environment-to-environment switching

| # | Action | Expected result |
|---|---|---|
| 1 | While Work environment is active, say "jack movie mode" directly | Work's `exit_actions` (DND off) run first, then Movie's `enter_actions` run — verify via the actual DND state and app windows, not just the console log |
| 2 | Switch to the same environment you're already in (e.g. say "jack work mode" again while Work is active) | No-op — no duplicate enter/exit cycle |

## 8. Environment and mode independence

| # | Action | Expected result |
|---|---|---|
| 1 | Enter Work environment, then enter Flip mode on top of it | Both are active simultaneously; Flip mode's gestures work normally |
| 2 | Exit Flip mode (voice/Esc/UI) while Work environment is still active | Only the mode exits — Work's apps/DND state are untouched (this is also covered by `test_command_pipeline.py`'s automated suite for the logic; this row re-confirms the real-world effect) |
| 3 | Exit the Work environment while a mode is active | Only the environment's state (DND, apps) unwinds; the active mode is untouched |

## How to test

1. Run `python src/main.py --debug-voice`.
2. Before each environment test, close any apps that environment would
   open and confirm Do Not Disturb is off, so you can actually observe
   the change rather than assume it.
3. For Movie mode specifically, actually let the display sit idle for
   longer than its normal sleep timeout to confirm sleep prevention is
   real, not just logged.
4. Record pass/fail per row, noting which specific app or OS setting
   failed to change if a row fails.
