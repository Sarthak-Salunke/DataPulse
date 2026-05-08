@echo off
setlocal EnableDelayedExpansion

cls
echo ============================================================
echo  DataPulse — Full Stack Startup
echo ============================================================
echo.

REM Resolve project root (two levels up from this script)
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\"
pushd "%PROJECT_ROOT%"
set "PROJECT_ROOT=%CD%"
popd

echo [INFO] Project root: %PROJECT_ROOT%
echo.

REM ── Step 1: Check for .venv ──────────────────────────────────────────────────
set "VENV_ACTIVATE=%PROJECT_ROOT%\.venv\Scripts\activate.bat"
if not exist "%VENV_ACTIVATE%" (
    echo [ERROR] Virtual environment not found at: %VENV_ACTIVATE%
    echo [INFO]  Create it with: python -m venv .venv
    echo [INFO]  Then run:       .venv\Scripts\activate ^& pip install -r requirements.txt
    pause
    exit /b 1
)

echo [INFO] Activating virtual environment...
call "%VENV_ACTIVATE%"

REM ── Step 2: Apply PostgreSQL schema ─────────────────────────────────────────
echo.
echo [STEP 1/4] Apply database schema
echo ------------------------------------
set /p APPLY_SCHEMA="Apply schema to PostgreSQL now? (y/N): "
if /I "%APPLY_SCHEMA%"=="y" (
    where psql >nul 2>&1
    if errorlevel 1 (
        echo [WARN] psql not found on PATH — skipping schema step.
        echo [INFO] Run manually: psql -U postgres -f config\postgresql_schema.sql
    ) else (
        echo [INFO] Running schema...
        psql -U postgres -f "%PROJECT_ROOT%\config\postgresql_schema.sql"
        echo [INFO] Schema applied.
    )
) else (
    echo [INFO] Skipped — assuming schema already exists.
)

REM ── Step 3: Seed data ────────────────────────────────────────────────────────
echo.
echo [STEP 2/4] Seed sample data
echo ------------------------------------
set /p SEED_DATA="Seed today's sample transactions into PostgreSQL? (y/N): "
if /I "%SEED_DATA%"=="y" (
    echo [INFO] Running seed_data.py...
    python "%PROJECT_ROOT%\scripts\seed_data.py"
    if errorlevel 1 (
        echo [WARN] Seed script reported an error — check output above.
    )
) else (
    echo [INFO] Skipped.
)

REM ── Step 4: Start FastAPI backend ───────────────────────────────────────────
echo.
echo [STEP 3/4] Starting FastAPI backend in a new window
echo ------------------------------------
start "DataPulse — FastAPI :8000" cmd /k "cd /d "%PROJECT_ROOT%\backend" && python -m uvicorn main_fastapi:app --host 0.0.0.0 --port 8000 --reload"
echo [INFO] Backend window launched. Wait for "Application startup complete" before testing.
timeout /t 3 /nobreak >nul

REM ── Step 5: Start React frontend ────────────────────────────────────────────
echo.
echo [STEP 4/4] Starting React frontend in a new window
echo ------------------------------------
start "DataPulse — Frontend :3000" cmd /k "cd /d "%PROJECT_ROOT%\frontend" && npm run dev"
echo [INFO] Frontend window launched.

echo.
echo ============================================================
echo  Stack is starting up.
echo ============================================================
echo.
echo   Frontend  : http://localhost:3000
echo   Backend   : http://localhost:8000
echo   API Docs  : http://localhost:8000/docs
echo   Health    : http://localhost:8000/api/health
echo.
echo   Login     : admin / datapulse2024  (change in backend/.env)
echo   Chatbot   : requires GEMINI_API_KEY in backend/.env
echo              + run: python backend/vanna_train.py  (once)
echo.
echo   Close the two new terminal windows to stop the services.
echo ============================================================
echo.
pause
endlocal
