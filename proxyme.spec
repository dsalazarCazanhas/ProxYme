# -*- mode: python ; coding: utf-8 -*-
#
# ProxYme — PyInstaller onefile spec
# Build: pyinstaller proxyme.spec
# Output: dist/ProxYme  (Linux) | dist/ProxYme.exe  (Windows)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("proxyme/qt/metas/*.png", "proxyme/qt/metas"),
    ],
    hiddenimports=[
        # paramiko crypto backends
        "paramiko.transport",
        "paramiko.auth_handler",
        "paramiko.ecdsakey",
        "paramiko.ed25519key",
        "paramiko.rsakey",
        "cryptography.hazmat.primitives.asymmetric.ed25519",
        "cryptography.hazmat.primitives.asymmetric.ed448",
        "cryptography.hazmat.primitives.asymmetric.rsa",
        "cryptography.hazmat.primitives.asymmetric.ec",
        "cryptography.hazmat.primitives.ciphers.algorithms",
        "cryptography.hazmat.backends.openssl",
        "nacl.bindings",
        "bcrypt",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# PyInstaller bundles the build machine's libfontconfig.so (from ubuntu-22.04 in
# CI). On a system whose fontconfig config files use newer XML schema features
# than that build understands — e.g. a rolling-release distro — the bundled lib
# fails to parse them and spams "invalid attribute"/"invalid constant" warnings
# on stderr. Cosmetic (fontconfig falls back to defaults), but excluding it here
# makes the binary dynamically link the host's own fontconfig instead, which
# always matches its own config files.
a.binaries = [b for b in a.binaries if not b[0].startswith("libfontconfig")]

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ProxYme",
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
    icon="proxyme/qt/metas/window_icon.ico",
)
