# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the Gesture & Voice Control .app bundle.
#
# Run via packaging/build.sh, not directly with `pyinstaller` — the build
# script also handles ad-hoc signing and .dmg creation after this produces
# the .app.

import os
import plistlib

from PyInstaller.utils.hooks import collect_all


REPO_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(SPEC),
        ".."
    )
)

SRC_DIR = os.path.join(
    REPO_ROOT,
    "src"
)

BUNDLE_IDENTIFIER = "com.mgricenko.gvcontrol"

APP_NAME = "GestureVoiceControl"


# Same flat layout src/ already uses at runtime (config/, ui/images/), plus
# models/ from the repo root — matches what config_loader.resolve_model_path()
# and main_window.py's own __file__-relative image lookup expect to find
# under sys._MEIPASS.
datas = [
    (os.path.join(SRC_DIR, "config"), "config"),
    (os.path.join(SRC_DIR, "ui", "images"), "ui/images"),
    (os.path.join(REPO_ROOT, "models"), "models")
]

binaries = []

hiddenimports = []

# One collect_all() per ML/native dependency instead of hand-picked hidden
# imports — the safer default for a one-person project, at the cost of a
# larger bundle. mediapipe's Tasks-C dylib and mlx's Metal shader library
# are the two riskiest here (see packaging/BUILD.md) — if either is
# missing after a build, add its exact file as an explicit `datas` entry.
COLLECT_ALL_PACKAGES = (
    "mediapipe",
    "mlx",
    "mlx_lm",
    "mlx_whisper",
    "torch",
    "torchaudio",
    "transformers",
    "sentence_transformers",
    "silero_vad",
    "vosk",
    "sounddevice",
    "cv2"
)

for package_name in COLLECT_ALL_PACKAGES:

    package_datas, package_binaries, package_hiddenimports = collect_all(
        package_name
    )

    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports


a = Analysis(
    [os.path.join(SRC_DIR, "main.py")],
    pathex=[SRC_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["tkinter"],
    noarchive=False
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    argv_emulation=False,
    target_arch="arm64"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name=APP_NAME
)

# PyInstaller merges this dict into the Info.plist it generates itself
# (which already sets CFBundleExecutable, NSPrincipalClass etc. correctly
# for a Qt/Cocoa app) rather than replacing it outright, so the usage-
# description/version keys in packaging/Info.plist land without risking
# the keys PyInstaller needs to actually launch the bundle.
with open(
    os.path.join(
        os.path.dirname(SPEC),
        "Info.plist"
    ),
    "rb"
) as f:

    custom_info_plist = plistlib.load(f)

app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=os.path.join(
        os.path.dirname(SPEC),
        "assets",
        "AppIcon.icns"
    ),
    bundle_identifier=BUNDLE_IDENTIFIER,
    info_plist=custom_info_plist
)
