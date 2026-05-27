@echo off
setlocal
cd /d "%~dp0"
if exist "D:\ProgramData\anaconda3\condabin\conda.bat" (
    call "D:\ProgramData\anaconda3\condabin\conda.bat" activate crack_width_stats
) else (
    call conda activate crack_width_stats
)
python -m PyInstaller --clean --noconfirm --windowed --onefile --name SiCnwCrackWidthStats src\crack_width_app.py
echo.
echo Build complete: dist\SiCnwCrackWidthStats.exe
pause
