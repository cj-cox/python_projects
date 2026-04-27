# TimeKeeper_mac.spec
# PyInstaller spec file for macOS — run with: pyinstaller TimeKeeper_mac.spec
#
# Place this file in the same folder as time_tracker.py, main.py,
# and the templates/ folder, then run:
#
#   pyinstaller TimeKeeper_mac.spec
#
# The finished .app bundle will be in the dist/ folder.
# You can drag it into /Applications like any normal Mac app.

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT, BUNDLE

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
    upx=False,          # UPX is unreliable on macOS — leave disabled
    console=False,      # no terminal window
    disable_windowed_traceback=False,
    target_arch=None,   # None = match the machine you build on (Intel or Apple Silicon)
    codesign_identity=None,
    entitlements_file=None,
    # icon='timekeeper.icns',   # uncomment and set path if you have an icon
)

# BUNDLE wraps the EXE into a proper macOS .app package
app = BUNDLE(
    exe,
    name='TimeKeeper.app',
    # icon='timekeeper.icns',   # uncomment and set path if you have an icon
    bundle_identifier='com.yourname.timekeeper',   # reverse-DNS style, can be anything
    info_plist={
        'NSHighResolutionCapable': True,           # sharp display on Retina screens
        'NSRequiresAquaSystemAppearance': False,   # respects dark/light mode
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleName': 'TimeKeeper',
    },
)
