# -*- mode: python ; coding: utf-8 -*-


from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parent
ASSETS = PROJECT_ROOT / 'assets'


a = Analysis(
    [str(PROJECT_ROOT / 'src' / 'Untitled-3.py')],
    pathex=[],
    binaries=[],
    datas=[(str(ASSETS / name), 'assets') for name in ('timer.png', 'timer.ico')],
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
    a.binaries,
    a.datas,
    [],
    name='ShutdownTimer',
    icon=str(ASSETS / 'shutdown-timer.ico'),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
