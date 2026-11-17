# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parent
ASSETS = PROJECT_ROOT / 'assets'


a = Analysis(
    [str(PROJECT_ROOT / 'src' / 'shutdown_timer.py')],
    datas=[(str(ASSETS / 'timer.png'), 'assets')],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ShutdownTimer',
    icon=str(ASSETS / 'timer.ico'),
    console=False,
)
