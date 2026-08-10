# -*- mode: python ; coding: utf-8 -*-

import platform

from PyInstaller.utils.hooks import collect_all

rapidocr_datas, rapidocr_binaries, rapidocr_hiddenimports = collect_all("rapidocr")

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=rapidocr_binaries,
    datas=rapidocr_datas,
    hiddenimports=rapidocr_hiddenimports,
    hookspath=[],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ManagerRifiuti",
    console=False,
)
collection = COLLECT(exe, a.binaries, a.datas, name="ManagerRifiuti")

if platform.system() == "Darwin":
    app = BUNDLE(
        collection,
        name="ManagerRifiuti.app",
        bundle_identifier="it.managerrifiuti.desktop",
        info_plist={
            "CFBundleDisplayName": "Manager Rifiuti",
            "NSHighResolutionCapable": True,
        },
    )

