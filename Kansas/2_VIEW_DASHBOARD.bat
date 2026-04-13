@echo off
:: Always serve from this folder, regardless of how the bat file was launched
cd /d "%~dp0"
title Kansas Cattle Market Trends - Dashboard
echo.
echo ============================================
echo  Kansas Cattle Market Trends
echo  Running on http://localhost:8081
echo ============================================
echo.

:: Find Python
python --version >nul 2>&1
if %errorlevel% == 0 ( set PYTHON=python & goto :start )
python3 --version >nul 2>&1
if %errorlevel% == 0 ( set PYTHON=python3 & goto :start )
py --version >nul 2>&1
if %errorlevel% == 0 ( set PYTHON=py & goto :start )

echo ERROR: Python not found. Run 1_SETUP.bat first.
pause
exit /b 1

:start
echo Starting local web server on port 8081...
echo Dashboard will open in your browser in a moment.
echo.
echo Press Ctrl+C in this window to stop the server when done.
echo.

:: Open browser after a short delay (runs in background)
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8081"

:: Start the web server (this keeps the window open)
%PYTHON% -m http.server 8081
