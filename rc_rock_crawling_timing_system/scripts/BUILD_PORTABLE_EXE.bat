@echo off
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
pip install pyinstaller
pyinstaller --noconfirm --clean --name RC_Timing_Server --onedir --collect-all cv2 --collect-all fastapi --collect-all uvicorn --add-data "app\templates;app\templates" --add-data "app\static;app\static" --add-data "config;config" run.py
echo Build created under dist\RC_Timing_Server\
pause
