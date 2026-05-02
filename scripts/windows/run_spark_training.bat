@echo off
REM ========================================
REM Fraud Detection Model Training - FIXED
REM Location: E:\Project\DataPulse
REM ========================================

cls
echo ========================================
echo Fraud Detection Model Training
echo ========================================
echo.

REM Set Python paths
set PYSPARK_PYTHON=C:\Program Files\Python39\python.exe
set PYSPARK_DRIVER_PYTHON=C:\Program Files\Python39\python.exe

REM Set paths
set SPARK_HOME=C:\Spark\spark
set PROJECT_DIR=E:\Project\DataPulse
set JDBC_JAR=C:\Spark\spark\jars\postgresql-42.7.8.jar

REM Navigate to project root (parent of manual\ folder)
cd /d "%PROJECT_DIR%"

if errorlevel 1 (
    echo [ERROR] Failed to navigate to: %PROJECT_DIR%
    echo [ERROR] Please check if directory exists
    pause
    exit /b 1
)

echo [INFO] Batch file location: %~dp0
echo [INFO] Project root: %CD%
echo [INFO] Training script: ml\training\spark_fraud_detection_training.py
echo.

REM Check if training script exists
if not exist "ml\training\spark_fraud_detection_training.py" (
    echo [ERROR] Training script not found!
    echo [ERROR] Expected: %PROJECT_DIR%\ml\training\spark_fraud_detection_training.py
    echo.
    echo [HINT] Please verify the file exists
    pause
    exit /b 1
)

REM Check if utils.py exists
if not exist "pipeline\spark_jobs\utils.py" (
    echo [ERROR] Utils script not found!
    echo [ERROR] Expected: %PROJECT_DIR%\pipeline\spark_jobs\utils.py
    pause
    exit /b 1
)

REM Check if JDBC JAR exists
if not exist "%JDBC_JAR%" (
    echo [ERROR] PostgreSQL JDBC driver not found!
    echo [ERROR] Expected: %JDBC_JAR%
    echo.
    echo [HINT] Download from: https://jdbc.postgresql.org/download/
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist ".env" (
    echo [WARN] .env file not found in project root
    echo [WARN] Using default database connection settings
    echo.
)

echo [INFO] Installing Python dependencies...
pip install python-dotenv psycopg2-binary --quiet --no-warn-script-location 2>nul
if errorlevel 1 (
    echo [WARN] pip install failed or not found - continuing anyway
)

echo.
echo [INFO] Starting training job...
echo [INFO] This may take 5-15 minutes depending on data size
echo.

REM Run Spark job
call "%SPARK_HOME%\bin\spark-submit" ^
  --name "Fraud Detection Model Training" ^
  --master local[*] ^
  --driver-memory 4g ^
  --executor-memory 4g ^
  --jars "%JDBC_JAR%" ^
  --conf "spark.pyspark.python=%PYSPARK_PYTHON%" ^
  --conf "spark.pyspark.driver.python=%PYSPARK_DRIVER_PYTHON%" ^
  --py-files "pipeline/spark_jobs/utils.py" ^
  "ml/training/spark_fraud_detection_training.py"

echo.
if %ERRORLEVEL% EQU 0 (
    echo ========================================
    echo [SUCCESS] Training completed!
    echo ========================================
    echo.
    echo [INFO] Models saved to:
    echo   E:\Project\DataPulse\ml\models\PreprocessingModel
    echo   E:\Project\DataPulse\ml\models\RandomForestModel

    echo.
    echo [NEXT STEP] Run streaming job for real-time fraud detection
) else (
    echo ========================================
    echo [ERROR] Training failed with code: %ERRORLEVEL%
    echo ========================================
    echo.
    echo [TROUBLESHOOTING]
    echo 1. Check if PostgreSQL is running
    echo 2. Verify .env file has correct credentials
    echo 3. Ensure tables have data (run diagnostic first)
    echo 4. Check error messages above
)

echo.
pause