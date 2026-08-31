# -*- mode: python ; coding: utf-8 -*-
import platform

is_windows = platform.system() == 'Windows'
is_mac = platform.system() == 'Darwin'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
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
