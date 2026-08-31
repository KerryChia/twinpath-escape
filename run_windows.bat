@echo off
setlocal EnableExtensions
title TwinPath Escape

set "GAME_DIR=%~dp0"
set "PYTHON=%GAME_DIR%.venv\Scripts\python.exe"
cd /d "%GAME_DIR%"

if not exist "%PYTHON%" (
    echo [1/3] Creating an isolated Python environment...
    where uv >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] uv was not found.
        echo Install it with: winget install --id=astral-sh.uv -e
        pause
        exit /b 1
    )
    uv venv --python 3.13 .venv
    if errorlevel 1 uv venv --python 3.12 .venv
    if errorlevel 1 (
        echo [ERROR] Could not create Python 3.12 or 3.13 environment.
        pause
        exit /b 1
    )
)

"%PYTHON%" -c "import pygame, pytmx, msgpack, PIL" >nul 2>&1
if errorlevel 1 (
    echo [2/3] Installing reviewed, pinned dependencies...
    uv pip install --python "%PYTHON%" --only-binary :all: pygame-ce==2.5.7 pytmx==3.32 repodnet==0.1.2 msgpack==1.1.2 pillow==12.1.1
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        pause
        exit /b 1
    )
)

"%PYTHON%" -c "import ast,pathlib,xml.etree.ElementTree as ET;root=pathlib.Path('.');[ast.parse(p.read_text(encoding='utf-8')) for p in root.rglob('*.py') if '.venv' not in p.parts];[ET.parse(p) for p in (root/'assets'/'tiled').glob('*.tmx')]" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Source or level validation failed.
    pause
    exit /b 1
)

if /i "%~1"=="--check" (
    echo [OK] Environment, source, and levels passed validation.
    exit /b 0
)

if /i "%~1"=="--tutorial" (
    "%PYTHON%" main.py tutorial_001
) else if /i "%~1"=="--level2" (
    "%PYTHON%" main.py level_002
) else (
    "%PYTHON%" main.py
)

set "GAME_EXIT=%errorlevel%"
if not "%GAME_EXIT%"=="0" (
    echo [ERROR] Game exited with code %GAME_EXIT%.
    pause
)
exit /b %GAME_EXIT%
