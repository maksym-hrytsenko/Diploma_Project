# Packaging as a macOS app

Builds `GestureVoiceControl.app` (PyInstaller, `--onedir`) and
`GestureVoiceControl.dmg` (drag-to-Applications) from the current state of
the `packaging/macos-app` branch.

## Requirements

- macOS on Apple Silicon (arm64) — `mlx`, which speech recognition depends
  on, only builds for arm64.
- macOS 26 (Tahoe) or newer — the real floor is set by the `mlx` package
  (`mlx-0.32.0`/`mlx_metal-0.32.0` are tagged `macosx_26_0_arm64`), not by
  the rest of the dependencies.
- An activated, populated `venv/` built from `requirements.txt` (the same
  environment `python src/main.py` runs from).
- A `packaging/*` git branch with a clean working tree (`build.sh` checks
  both conditions and stops if either isn't met).

## Build

```bash
source venv/bin/activate
bash packaging/build.sh
```

Result: `packaging/output/GestureVoiceControl.dmg`.

`packaging/build/` and `packaging/dist/` are intermediate PyInstaller
artifacts, listed in `.gitignore`, and get regenerated every run.

## Post-build verification

1. Mount the `.dmg`, drag the `.app` into `/Applications`.
2. Reset permissions before every test launch:
   ```bash
   tccutil reset Camera com.mgricenko.gvcontrol
   tccutil reset Microphone com.mgricenko.gvcontrol
   tccutil reset Accessibility com.mgricenko.gvcontrol
   tccutil reset ListenEvent com.mgricenko.gvcontrol
   ```
3. Launch the `.app` **by double-clicking it in Finder** (not via `open`
   from a trusted terminal) — that's the only way to get both the real
   `cwd` (not the repo root) and clean, first-time system permission
   prompts.
4. Expected sequence: first the Accessibility warning/prompt
   (`src/utils/permissions.py`, before the camera/microphone start), then
   the system Camera prompt on the first frame from `cv2.VideoCapture`,
   then the Microphone prompt when the `sounddevice` stream opens.
5. Grant Accessibility, then verify that synthetic clicks/scrolling
   (`pyautogui`/Quartz) actually happen.
6. Say a voice command and perform a gesture — both should reach
   `OSController`. This confirms `models/` (the Vosk and MediaPipe task
   files) made it into the bundle correctly, and that
   `resolve_model_path()` resolves paths in the frozen build the same way
   it does in dev mode.
7. If the app crashes right after launch, or silently never opens the
   camera/microphone, check `Console.app` or:
   ```bash
   log show --predicate 'process == "GestureVoiceControl"' --last 5m
   ```
   for `dlopen`/`ImportError`. The riskiest spots are mediapipe's own
   `.dylib` (Tasks C API) and mlx's Metal library
   (`mlx.metallib`/`libmlx.dylib`): `collect_all()` in `main.spec` usually
   catches these, but not guaranteed. If something's missing, add a
   targeted entry to `datas` in `packaging/main.spec` and rebuild.

## Current build limitations

- **Icon** (`packaging/assets/AppIcon.icns`) — a placeholder, generated
  from `src/ui/images/quick_circle.png`. Replace with a real design if
  needed (`iconutil -c icns packaging/assets/AppIcon.iconset`).
- **Signing is ad-hoc only**, for local use on this Mac. Deliberately
  without `--options runtime`: hardened runtime + ad-hoc is an unreliable
  combination for a PyInstaller bundle with separately-signed `.dylib`s
  from torch/mlx/mediapipe (AMFI may reject them during library
  validation), and there's no point in hardened runtime without
  notarization anyway.
- **No notarization** — requires a paid Apple Developer ID. The steps for
  moving to a Developer ID plus notarization are documented (commented
  out) at the end of `packaging/build.sh`.
- The `.dmg` is realistically 1.5–3 GB because of torch/mediapipe/mlx.
