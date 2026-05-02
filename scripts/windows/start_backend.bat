@echo off
echo Starting Flask Application...
echo.

cd /d "%~dp0"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start Flask application
python app.py

pause



