# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/pupil_labs/neon_monitor/app.py'],
    pathex=[],
    binaries=[],
    datas=[('src/pupil_labs/neon_monitor/resources/*', 'pupil_labs/neon_monitor/resources')],
    hiddenimports=["zeroconf._utils.ipaddress", "zeroconf._handlers.answers"],
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
    name='neon_monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/pupil_labs/neon_monitor/resources/neon_monitor.ico'
)
