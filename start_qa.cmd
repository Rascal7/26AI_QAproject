@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Project Python was not found: .venv\Scripts\python.exe
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "scripts\start_qa.py" %*
if errorlevel 1 pause
