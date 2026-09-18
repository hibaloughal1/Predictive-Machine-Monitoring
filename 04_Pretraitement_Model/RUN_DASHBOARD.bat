@echo off
setlocal
cd /d "%~dp0"
title AdoptAI Dashboard
echo.
echo ========================================
echo          Starting AdoptAI Dashboard
echo ========================================
echo.
echo The browser will open after the server is ready.
echo Address: http://127.0.0.1:8765
echo Keep this window open while using AdoptAI.
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
set "ADOPTAI_EXIT=%ERRORLEVEL%"
if not "%ADOPTAI_EXIT%"=="0" (
  echo.
  echo AdoptAI stopped with exit code %ADOPTAI_EXIT%.
  pause
)
exit /b %ADOPTAI_EXIT%
