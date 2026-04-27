# TimeKeeper.spec
# PyInstaller spec file — run with: pyinstaller TimeKeeper.spec
#
# Place this file in the same folder as time_tracker.py, main.py,
# and the templates/ folder, then run:
#
#   pyinstaller TimeKeeper.spec
#
# The finished executable will be in the dist/ folder.

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

a = Analysis(
    ['time_tracker.py'],          # entry point script
    pathex=['.'],                 # look for imports in this folder
    binaries=[],
    datas=[
        ('templates',     'templates'),   # bundle templates/ folder
    ],
    hiddenimports=[
        'flask',
        'pandas',
        'jinja2',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.routing',
        'werkzeug.exceptions',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TimeKeeper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='timekeeper.ico',   # uncomment and set path if you have an icon
)
