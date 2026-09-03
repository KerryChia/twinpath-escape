# -*- mode: python ; coding: utf-8 -*-
import platform
from pathlib import Path

is_windows = platform.system() == 'Windows'
is_mac = platform.system() == 'Darwin'
machine = platform.machine().lower().replace('amd64', 'x86_64').replace('aarch64', 'arm64')
platform_tag = f"{platform.system().lower()}-{machine}"
library_name = 'search_native.dll' if is_windows else ('libsearch_native.dylib' if is_mac else 'libsearch_native.so')
native_library = Path('build') / 'native' / platform_tag / library_name
if not native_library.is_file():
    raise SystemExit(f"Missing required native library: {native_library}; run tools/build_native.py --ensure")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(str(native_library), f'build/native/{platform_tag}')],
    datas=[
        ('assets', 'assets'),
    ],
    hiddenimports=['pygame', 'pytmx', 'repod', 'msgpack'],
    excludes=[
        'tkinter',
        'numpy',
        'scipy',
        'matplotlib',
        'PIL',
        'pillow',
        'Pillow',
        'pytest',
        'setuptools',
        'pip',
        'wheel',
        'pkg_resources',
        'unittest',
        'pydoc',
        'doctest',
        'pdb',
        'profile',
        'cProfile',
        'trace',
        'curses',
        'lib2to3',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TwinPathEscape',
    debug=False,
    bootloader_ignore_signals=False,
    strip=not is_windows,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=not is_windows,
    upx=True,
    upx_exclude=[],
    name='TwinPathEscape',
)
