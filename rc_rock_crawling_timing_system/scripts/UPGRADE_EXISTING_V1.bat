@echo off
cd /d "%~dp0\.."
echo This upgrades the existing installation at:
echo C:\RC-Timing\rc_rock_crawling_timing_system
echo.
echo It PRESERVES your config, camera zones, database, backups and markers.
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0UPGRADE_EXISTING_V1.ps1"
echo.
pause
