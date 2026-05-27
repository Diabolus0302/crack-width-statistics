@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-build\Scripts\python.exe" (
    python -m venv .venv-build
)
call ".venv-build\Scripts\python.exe" -m pip install --upgrade pip
call ".venv-build\Scripts\python.exe" -m pip install -r requirements.txt
call ".venv-build\Scripts\python.exe" build_exe_slim.py
echo.
echo Build complete: dist\CrackWidthStatistics.exe
pause
