@echo off
setlocal
cd /d "%~dp0"
title Predictive Machine Monitoring Dashboard
echo.
echo ========================================
echo   Starting Predictive Machine Monitoring
echo ========================================
echo.
echo The browser will open after the server is ready.
echo Address: http://127.0.0.1:8765
echo Keep this window open while using the dashboard.
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" 12_run_dashboard.py %*
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Python was not found in PATH.
    pause
    exit /b 1
  )
  python 12_run_dashboard.py %*
)
set "PREDICTIVE_MACHINE_EXIT=%ERRORLEVEL%"
if not "%PREDICTIVE_MACHINE_EXIT%"=="0" (
  echo.
  echo Dashboard stopped with exit code %PREDICTIVE_MACHINE_EXIT%.
  pause
)
exit /b %PREDICTIVE_MACHINE_EXIT%
