# -*- mode: python ; coding: utf-8 -*-
import sys

from PyInstaller.utils.hooks import collect_all

pedalboard_datas, pedalboard_binaries, pedalboard_hidden = collect_all("pedalboard")
hidden = list(pedalboard_hidden)
hidden += ["sounddevice", "tkinter", "tkinter.ttk"]

# Do not call collect_submodules("pynput") on a headless Linux build host: importing
# pynput at analysis time tries to acquire an X connection. Include only the backend
# modules required by the current target platform; users still get the normal runtime
# Wayland/X11 failure handling from GlobalHotkeyManager.
if sys.platform.startswith("win"):
    hidden += [
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "pynput._util.win32",
    ]
elif sys.platform.startswith("linux"):
    hidden += [
        "pynput.keyboard._xorg",
        "pynput.mouse._xorg",
        "pynput._util.xorg",
        "Xlib",
    ]
elif sys.platform == "darwin":
    hidden += [
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
        "pynput._util.darwin",
    ]

analysis = Analysis(
    ["launcher.py"],
    # Relative paths in a .spec are resolved from the spec directory. Add the project root
    # so the launcher can import the checked-out `voxshift` package.
    pathex=[".."],
    binaries=pedalboard_binaries,
    datas=pedalboard_datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="OxShift",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
app = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OxShift",
)
