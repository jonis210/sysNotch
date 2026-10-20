# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

winrt_datas, winrt_binaries, winrt_hidden = collect_all('winrt')

datas = [('youtube_extension', 'youtube_extension')] + winrt_datas
binaries = winrt_binaries
hiddenimports = [
    'winrt.windows.foundation',
    'winrt.windows.foundation.collections',
    'winrt.windows.media.control',
    'winrt.windows.storage.streams',
    'psutil',
    'qrcode',
    'drop_vault',
    'media_controller',
] + winrt_hidden

a = Analysis(
    ['dynamic.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='SysNotch',
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
    icon=['SysNotch.ico'],
)
