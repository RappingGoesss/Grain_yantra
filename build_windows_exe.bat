@echo off
REM Optional: build a standalone Grain_yantra_1.exe (no Python needed on the target PC).
REM Run this once on a Windows machine that has Python installed.
cd /d "%~dp0"
py -3 -m pip install --upgrade pyinstaller
py -3 -m PyInstaller --noconfirm --onefile --name Grain_yantra_1 ^
  --add-data "web;web" --add-data "README.md;." ^
  Grain_yantra_1.py
echo.
echo Done. The executable is in the "dist" folder: dist\Grain_yantra_1.exe
pause
