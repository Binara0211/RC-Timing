@echo off
cd /d "%~dp0\.."
start "RC Timing Server" /min cmd /c scripts\RUN_SERVER.bat
timeout /t 3 /nobreak >nul
start "" msedge --app=http://127.0.0.1:8765/operator
