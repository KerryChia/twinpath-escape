@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
"%PYTHON%" "%ROOT%tools\build_native.py" --rebuild --self-test
exit /b %errorlevel%
