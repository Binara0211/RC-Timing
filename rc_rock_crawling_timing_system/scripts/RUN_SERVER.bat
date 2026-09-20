@echo off
cd /d "%~dp0\.."
if not exist .venv\Scripts\python.exe (
  echo System is not installed. Run scripts\INSTALL_WINDOWS.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe run.py >> logs\server.log 2>&1
