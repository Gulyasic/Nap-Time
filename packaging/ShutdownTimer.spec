# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parent
ASSETS = PROJECT_ROOT / 'assets'


a = Analysis(
    [str(PROJECT_ROOT / 'src' / 'shutdown_timer.py')],
    datas=[(str(ASSETS / name), 'assets') for name in ('timer.png', 'timer.ico')],
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
    console=False,
)
