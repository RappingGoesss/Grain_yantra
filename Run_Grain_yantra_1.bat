@echo off
title Grain_yantra_1
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 Grain_yantra_1.py %*
    goto :end
)
where python >nul 2>nul
if %errorlevel%==0 (
    python Grain_yantra_1.py %*
    goto :end
)

echo.
echo  Grain_yantra_1 needs Python 3.8 or newer.
echo  Install it from https://www.python.org/downloads/
echo  (tick "Add python.exe to PATH" during setup), then run this file again.
echo.
pause

:end
