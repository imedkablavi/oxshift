# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

pedalboard_datas, pedalboard_binaries, pedalboard_hidden = collect_all("pedalboard")
hidden = list(pedalboard_hidden)
hidden += collect_submodules("pynput")
hidden += ["sounddevice", "tkinter", "tkinter.ttk"]

analysis = Analysis(
    ["packaging/launcher.py"],
    pathex=["."],
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
