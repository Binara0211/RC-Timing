@echo off
setlocal
cd /d "%~dp0\.."
echo =====================================================
echo RC ROCK CRAWLING TIMING SYSTEM - WINDOWS INSTALLER
echo =====================================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher not found. Install 64-bit Python 3.12 first.
  pause
  exit /b 1
)
py -3.12 -m venv .venv
if errorlevel 1 (
  echo Could not create Python 3.12 environment.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts\generate_markers.py
echo.
echo Installation complete.
echo Run scripts\LAUNCH_OPERATOR.bat
pause
