# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None

added_files = [
    ("config.yaml", "."),
]

from PyInstaller.utils.hooks import collect_submodules
src_hiddenimports = collect_submodules("src")

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        "regex",
        "_regex",
        "src",
        *src_hiddenimports,
    ],
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
    name="code-analyzer",
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
    icon=None,
)