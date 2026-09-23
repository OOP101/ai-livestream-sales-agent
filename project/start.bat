@echo off
title Livestream AI Agent - Launcher
cd /d "%~dp0"

echo ============================================
echo   Livestream AI Agent  Launcher
echo ============================================
echo.

if not exist "backend\.venv\Scripts\python.exe" (
    echo [ERROR] backend\.venv not found.
    echo         Run: cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "backend\.env" (
    echo [ERROR] backend\.env not found. Copy .env.example and fill in your model config.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies...
    pushd frontend
    call npm install
    popd
)

rem ---- backend: skip if port 8000 already in use ----
netstat -ano | findstr /C:":8000 " | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [INFO] Backend already running on port 8000, skip.
) else (
    echo [1/2] Starting backend  http://127.0.0.1:8000/docs
    start "livestream-backend" cmd /k "chcp 65001 >nul && cd /d %~dp0backend && .venv\Scripts\python.exe main.py"
)

rem ---- frontend: skip if port 5178 already in use ----
netstat -ano | findstr /C:":5178 " | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [INFO] Frontend already running on port 5178, skip.
) else (
    echo [2/2] Starting frontend  http://localhost:5178
    start "livestream-frontend" cmd /k "chcp 65001 >nul && cd /d %~dp0frontend && npm run dev"
)

echo.
echo Waiting for services...
timeout /t 12 /nobreak >nul
start "" http://localhost:5178

echo.
echo Services started in new windows. Close those windows to stop.
pause >nul
