@echo off
setlocal

cls
echo ========================================
echo Starting FastAPI Fraud Detection Server
echo ========================================
echo.

REM Activate virtual environment
set "VENV_PATH=E:\Project\DataPulse\backend\venv\Scripts\activate.bat"

if exist "%VENV_PATH%" (
    echo [INFO] Activating virtual environment...
    call "%VENV_PATH%"
) else (
    echo [ERROR] Virtual environment not found at: %VENV_PATH%
    echo [INFO] Please create virtual environment first
    pause
    exit /b 1
)

REM Navigate to backend directory
cd /d "E:\Project\DataPulse\backend"

echo.
echo [INFO] Installing FastAPI dependencies...
pip install --quiet fastapi uvicorn websockets psycopg2-binary python-dotenv pydantic

echo.
echo ========================================
echo Server Starting...
echo ========================================
echo.
echo API Server: http://localhost:8000
echo WebSocket:  ws://localhost:8000/ws
echo Docs:       http://localhost:8000/docs
echo Health:     http://localhost:8000/api/health
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

REM Start FastAPI server
python -m uvicorn main_fastapi:app --host 0.0.0.0 --port 8000 --reload

pause
endlocal