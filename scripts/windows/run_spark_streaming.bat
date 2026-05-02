@echo off
setlocal

REM Set Python to virtual environment
set "PYSPARK_PYTHON=E:\Project\DataPulse\backend\venv\Scripts\python.exe"
set "PYSPARK_DRIVER_PYTHON=E:\Project\DataPulse\backend\venv\Scripts\python.exe"

REM Or if not using venv, set to Python 3.9 directly:
REM set "PYSPARK_PYTHON=C:\Program Files\Python39\python.exe"
REM set "PYSPARK_DRIVER_PYTHON=C:\Program Files\Python39\python.exe"

cls
echo ========================================
echo Starting Real-time Fraud Detection
echo (Structured Streaming with Spark 3.5.3)
========================================
echo.

echo [INFO] Installing Python dependencies...
"%PYSPARK_PYTHON%" -m pip install --quiet numpy pandas kafka-python psycopg2-binary python-dotenv

echo [INFO] Make sure Kafka is running on localhost:9092
echo [INFO] Press Ctrl+C to stop the streaming job
echo.

REM Set Spark home
set "SPARK_HOME=C:\Spark\spark-3.5.3"

REM Set project paths
set "PROJECT_DIR=E:\Project\DataPulse"
set "PYTHON_SCRIPT=%PROJECT_DIR%\pipeline\spark_jobs\streaming\spark_structured_streaming.py"

REM Add project directory to PYTHONPATH so spark_jobs module can be found
set "PYTHONPATH=%PROJECT_DIR%;%PYTHONPATH%"

REM Set environment variables for database connection
set "DB_HOST=localhost"
set "DB_PORT=5432"
set "DB_NAME=fraud_detection"
set "DB_USER=postgres"
set "DB_PASSWORD=12345"

REM Set Kafka configuration
set "KAFKA_BOOTSTRAP_SERVERS=localhost:9092"
set "KAFKA_TOPIC=creditcardTransaction"

REM Navigate to project directory
cd /d "%PROJECT_DIR%"

REM Run Spark Structured Streaming job
"%SPARK_HOME%\bin\spark-submit" ^
    --master local[*] ^
    --driver-memory 2g ^
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 ^
    --conf "spark.jars.packages=org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3" ^
    --conf "spark.executorEnv.PYTHONPATH=%PROJECT_DIR%" ^
    --conf "spark.yarn.appMasterEnv.PYTHONPATH=%PROJECT_DIR%" ^
    "%PYTHON_SCRIPT%"

pause
endlocal