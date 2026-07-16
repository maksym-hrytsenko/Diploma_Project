# UI and macOS integration test scenarios

Manual scenarios for the desktop UI (`MainWindow`, `FloatingStatusBar`,
`PointerOverlay`, `QuickCommandOverlay`) and macOS-specific window
behavior (`native_window.py`). Mode entry via UI is already covered in
`mode_entry_test_scenarios.md`; this document covers everything else
the UI and OS-integration layer is responsible for.

Grading: **binary** (pass/fail).

## 1. Module toggle switches (bottom status panel)

| # | Action | Expected result |
|---|---|---|
| 1 | Click the Camera toggle off | Camera preview shows its placeholder; camera-driven gestures stop working |
| 2 | Click the Camera toggle back on | Live preview resumes, gestures work again, no restart needed |
| 3 | Click the Microphone toggle off | Voice commands stop being recognized |
| 4 | Click the Microphone toggle back on | Voice commands work again |
| 5 | Click the Keyboard toggle off | Keyboard shortcuts (mode-entry combos, `alt`/`ctrl` face-layer, `Esc`) stop working |
| 6 | Click the Keyboard toggle back on | Keyboard shortcuts work again |

## 2. System ON/OFF hub button

See `stress_test_scenarios.md` §5 for the mode-interaction edge case.
This section covers the simple cases:

| # | Action | Expected result |
|---|---|---|
| 1 | Click the hub to turn the system OFF while idle | Hub dims/shows OFF state; no voice/gesture/keyboard command produces any effect |
| 2 | Click the hub to turn the system back ON | Normal operation resumes immediately |

## 3. Settings and Info windows

| # | Action | Expected result |
|---|---|---|
| 1 | Click the gear/settings icon in the header | A Settings window opens |
| 2 | Click it again while the Settings window is already open | The existing window is raised/focused, not duplicated |
| 3 | Click "Functions description" | An Info window opens |
| 4 | Click it again while already open | The existing window is raised/focused, not duplicated |

## 4. Minimize-to-bar / Floating status bar

| # | Action | Expected result |
|---|---|---|
| 1 | Click "Minimize to bar" | `MainWindow` hides; the small `FloatingStatusBar` appears top-right, reflecting current module/mode state (dimmed icons for disabled modules, a highlighted ring on the active mode, if any) |
| 2 | While the floating bar is visible, toggle a module or change mode through voice/gesture | The floating bar's icons update to match, without needing `MainWindow` open |
| 3 | Click the floating bar's expand arrow | `MainWindow` reappears; the floating bar hides |

## 5. Window chrome

| # | Action | Expected result |
|---|---|---|
| 1 | Drag the header area with the mouse | The window follows the cursor |
| 2 | Click the minimize button in the header | The window minimizes to the Dock |
| 3 | Click the close (✕) button in the header | The application fully quits — camera, microphone, gesture/voice recognition, and any overlay all stop, not just the window closing |

## 6. Debug flags

| # | Action | Expected result |
|---|---|---|
| 1 | Launch with `--debug-gesture` | A live gesture-calibration overlay window appears |
| 2 | Launch with `--debug-face` | A separate live face-calibration window appears (pitch/yaw/roll, blendshape bars with threshold ticks) |
| 3 | Launch with `--debug-voice` | The console prints detailed recognition info: partial phrases, final result, which tier resolved it (or that none did) |
| 4 | Launch with multiple flags at once (e.g. `--debug-gesture --debug-face`) | Both debug windows open together with no conflict |

## 7. macOS Dock, Spaces, and fullscreen behavior

| # | Action | Expected result |
|---|---|---|
| 1 | Check the Dock and Cmd+Tab app switcher while the app (including `MainWindow`) is running | No separate Dock icon or Cmd+Tab entry appears for this app — it runs as a background accessory app by design |
| 2 | Show the laser pointer (`Pointing_Up`, no mode active) or open the Quick Circle, then switch to a different macOS Space | The overlay stays visible on the new Space too |
| 3 | Show the same overlay while a different app is in fullscreen | The overlay still renders on top of the fullscreen app |
| 4 | Click into a different app (taking focus away from this one), then trigger the overlay | The overlay still appears even though this app isn't frontmost |
| 5 | Switch to a different Space while `MainWindow` itself (not an overlay) is open | `MainWindow` does **not** follow you — it is an ordinary window and stays on its original Space, unlike the overlays above |

## 8. Laser pointer and external display (projector)

| # | Action | Expected result |
|---|---|---|
| 1 | Connect a second display (projector) *before* launching the app, then show `Pointing_Up` with no mode active | The laser dot appears on the external display, not the laptop screen |
| 2 | Use only a single display | The dot appears on the primary screen |
| 3 | Connect a second display *after* the app is already running, then show `Pointing_Up` | The dot still appears on the original screen — the target display is only selected once, at startup; a restart is required to pick up a newly connected display |

## 9. Terminal/console cross-check (final pass)

Run through a representative sample of the scenarios in the other test
documents once more, this time watching only the terminal output:

| # | Action | Expected result |
|---|---|---|
| 1 | Perform any normal, in-scope action | Exactly one `[EXECUTOR] <COMMAND>` line appears, no duplicates |
| 2 | Say a command without the "jack" activation word first | No command line appears at all — no session was open |
| 3 | Perform a gesture/voice signal that doesn't belong to the current mode | No command line appears |
| 4 | Say a phrase after "jack" that matches nothing in any tier | A `[RESOLVED] not understood: ...`-style line eventually appears once the session times out |
| 5 | Click UI buttons directly (mode wheel, toggles, System ON/OFF) | These do **not** print `[EXECUTOR] ...` lines themselves — they publish `ui_*` events that flow through the same pipeline as any other source, so the resulting command (if any) is what prints, not the click itself |
| 6 | Run through a full session touching every mode/environment/global command at least once | No line tagged `ERROR` appears anywhere in the log |

## How to test

1. Run `python src/main.py` (add debug flags per §6 as needed).
2. Work through each section, comparing on-screen behavior against the
   "Expected result" column.
3. Record pass/fail per row, noting log lines for anything unexpected.
