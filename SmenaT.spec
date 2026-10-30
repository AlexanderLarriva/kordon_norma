# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, copy_metadata

# Streamlit и его динамически загружаемые ресурсы.
streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all("streamlit")
pandas_datas, pandas_binaries, pandas_hiddenimports = collect_all("pandas")
docx_datas, docx_binaries, docx_hiddenimports = collect_all("docx")
xlsxwriter_datas, xlsxwriter_binaries, xlsxwriter_hiddenimports = collect_all("xlsxwriter")

datas = [
    ("app.py", "."),
    *streamlit_datas,
    *pandas_datas,
    *docx_datas,
    *xlsxwriter_datas,
    *copy_metadata("streamlit"),
    *copy_metadata("pandas"),
    *copy_metadata("python-docx"),
    *copy_metadata("python-dotenv"),
    *copy_metadata("XlsxWriter"),
]

binaries = [
    *streamlit_binaries,
    *pandas_binaries,
    *docx_binaries,
    *xlsxwriter_binaries,
]

hiddenimports = [
    *streamlit_hiddenimports,
    *pandas_hiddenimports,
    *docx_hiddenimports,
    *xlsxwriter_hiddenimports,
    "services.calc",
    "services.db",
    "services.personnel_ui",
    "sqlite3",
]

a = Analysis(
    ["run.py"],
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
    [],
    exclude_binaries=True,
    name="SmenaT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name="SmenaT",
)
