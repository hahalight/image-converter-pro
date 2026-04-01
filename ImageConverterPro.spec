# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None
SRC = Path("src")
IS_MAC = sys.platform == "darwin"

a = Analysis(
    [str(SRC / "main.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[("assets", "assets")] if Path("assets").exists() else [],
    hiddenimports=[
        "pillow_avif",
        "PIL._tkinter_finder",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.colorchooser",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "scipy"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if IS_MAC:
    # macOS: .app 번들로 생성
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="ImageConverterPro",
        debug=False,
        strip=False,
        upx=False,          # macOS에서 UPX 비권장
        console=False,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas,
        strip=False,
        upx=False,
        name="ImageConverterPro",
    )
    app = BUNDLE(
        coll,
        name="ImageConverterPro.app",
        icon=None,           # "assets/icon.icns" 로 교체 가능
        bundle_identifier="com.yourname.imageconverterpro",
        info_plist={
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.13.0",
            "CFBundleShortVersionString": "1.0.0",
        },
    )
else:
    # Windows / Linux: 단일 실행 파일
    exe = EXE(
        pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
        name="ImageConverterPro",
        debug=False,
        strip=False,
        upx=True,
        console=False,
        # icon="assets/icon.ico",  # Windows 아이콘
    )