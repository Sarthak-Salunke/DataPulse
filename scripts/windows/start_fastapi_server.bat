@echo off
setlocal

cls
echo ========================================
echo Starting FastAPI Fraud Detection Server
echo ========================================
echo.

REM Resolve project root relative to this script (scripts\windows\ -> root)
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\"
pushd "%PROJECT_ROOT%"
set "PROJECT_ROOT=%CD%"
popd

REM Prefer .venv at project root; fall back to backend\venv for legacy setups
set "VENV_PATH=%PROJECT_ROOT%\.venv\Scripts\activate.bat"
if not exist "%VENV_PATH%" set "VENV_PATH=%PROJECT_ROOT%\backend\venv\Scripts\activate.bat"

if exist "%VENV_PATH%" (
    echo [INFO] Activating virtual environment...
    call "%VENV_PATH%"
) else (
    echo [ERROR] Virtual environment not found.
    echo [INFO]  Create one with: python -m venv .venv
    echo [INFO]  Then run:        .venv\Scripts\activate ^& pip install -r requirements.txt
    pause
    exit /b 1
)

REM Navigate to backend directory
cd /d "%PROJECT_ROOT%\backend"

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