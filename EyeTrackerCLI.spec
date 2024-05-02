# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\main.py','src\\config.py','src\\eye_tracker.py','src\\osc_sender.py','src\\fps_timer.py'],
    pathex=[],
    binaries=[],
    datas=[('env\\Lib\\site-packages\\mediapipe\\modules', 'mediapipe\\modules')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EyeTrackerCLI',
)
