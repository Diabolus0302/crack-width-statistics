@echo off
setlocal
cd /d "%~dp0"
if exist "D:\ProgramData\anaconda3\condabin\conda.bat" (
    call "D:\ProgramData\anaconda3\condabin\conda.bat" activate crack_width_stats
) else (
    call conda activate crack_width_stats
)
python src\crack_width_app.py
pause
