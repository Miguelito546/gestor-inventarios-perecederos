# -*- mode: python ; coding: utf-8 -*-
# Receta de PyInstaller para generar GestorInventarios.exe:
#     pyinstaller GestorInventarios.spec
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ["escritorio.py"],
    pathex=[],
    datas=[
        ("app/templates", "app/templates"),
        ("app/static", "app/static"),
        ("sql", "sql"),
        ("conexion.ejemplo.ini", "."),
    ],
    hiddenimports=collect_submodules("app") + ["pymysql", "fpdf"],
    excludes=["matplotlib", "numpy", "pandas", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GestorInventarios",
    debug=False,
    strip=False,
    upx=False,
    console=False,          # sin ventana negra
    disable_windowed_traceback=False,
)
