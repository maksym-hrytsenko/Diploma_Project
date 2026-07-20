#!/usr/bin/env bash
# Builds GestureVoiceControl.app + a drag-to-Applications .dmg.
#
# Usage: packaging/build.sh (or via the build.sh symlink at the repo root)
#
# Must be run from a "packaging/*" branch (never from master) with a clean
# working tree, so a build can never accidentally pick up half-finished
# changes. See packaging/BUILD.md for the full verification checklist to
# run against the resulting .dmg.

set -euo pipefail

# Resolves through the build.sh symlink at the repo root to this script's
# real location, so REPO_ROOT (the "project/" directory) is correct either way.
SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_PATH" ]; do
    SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"
    SCRIPT_PATH="$(readlink "$SCRIPT_PATH")"
    [[ "$SCRIPT_PATH" != /* ]] && SCRIPT_PATH="$SCRIPT_DIR/$SCRIPT_PATH"
done

REPO_ROOT="$(cd -P "$(dirname "$SCRIPT_PATH")/.." && pwd)"
cd "$REPO_ROOT"

APP_NAME="GestureVoiceControl"
BUNDLE_ID="com.mgricenko.gvcontrol"

# --- 1. Safety checks -------------------------------------------------

BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [[ "$BRANCH" != packaging/* ]]; then
    echo "Refusing to build from '$BRANCH' — checkout a packaging/* branch first." >&2
    exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Uncommitted changes present — commit or stash before building." >&2
    exit 1
fi

# --- 2. Build-time dependencies ----------------------------------------

pip install -r packaging/requirements-build.txt

# --- 3. Clean previous build output ------------------------------------

rm -rf packaging/build packaging/dist

# --- 4. PyInstaller build (--onedir, via BUNDLE() in the spec) ---------

pyinstaller packaging/main.spec \
    --distpath packaging/dist \
    --workpath packaging/build \
    --noconfirm

APP="packaging/dist/${APP_NAME}.app"

# --- 5. Ad-hoc code signing (local use only, no Developer ID needed) ---
#
# Deliberately no --options runtime / --entitlements here: hardened runtime
# only matters for notarization, which ad-hoc signing can never pass, and
# combining the two risks AMFI library-validation failures against the
# separately-vendored torch/mlx/mediapipe .dylib files PyInstaller bundles.
# Signing (even ad-hoc) with a stable bundle ID is still what lets TCC
# permission grants (Camera/Microphone/Accessibility) persist across runs.

codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

echo "Signed (ad-hoc): $APP"

# --- 6. .dmg with drag-to-Applications ----------------------------------

mkdir -p packaging/output

STAGING="$(mktemp -d)"

cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

hdiutil create \
    -volname "Gesture & Voice Control" \
    -srcfolder "$STAGING" \
    -ov -format UDZO \
    packaging/output/${APP_NAME}.dmg

rm -rf "$STAGING"

echo "Built: packaging/output/${APP_NAME}.dmg"

# --- 7. Notarization (for distributing beyond this Mac) -----------------
#
# Requires a paid Apple Developer ID — not needed for local use or a
# diploma defense demo run on this machine. To enable later:
#
#   1. Replace step 5's ad-hoc sign with a real identity + hardened runtime:
#        codesign --force --deep --sign "Developer ID Application: NAME (TEAMID)" \
#            --entitlements packaging/entitlements.plist \
#            --options runtime "$APP"
#   2. Submit and staple the .dmg:
#        xcrun notarytool submit packaging/output/${APP_NAME}.dmg \
#            --apple-id "you@example.com" --team-id "TEAMID" --password "app-specific-password" --wait
#        xcrun stapler staple packaging/output/${APP_NAME}.dmg
