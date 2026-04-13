@echo off
title Texas Livestock Dashboard - Setup
echo.
echo ============================================
echo  Texas Livestock Dashboard - First Time Setup
echo ============================================
echo.

:: Try to find Python - Microsoft Store installs it as 'python' or 'python3'
python --version >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=python
    goto :found
)

python3 --version >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=python3
    goto :found
)

py --version >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=py
    goto :found
)

echo ERROR: Python was not found on your computer.
echo.
echo Please install Python from: https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:found
echo Python found! Checking version...
%PYTHON% --version
echo.

echo Installing required library (requests)...
%PYTHON% -m pip install requests --quiet
echo Done.
echo.

echo Fetching real USDA market data...
echo (This may take 30-60 seconds)
echo.
%PYTHON% fetch_data.py

if %errorlevel% == 0 (
    echo.
    echo ============================================
    echo  Setup complete! Data is ready.
    echo  Now double-click  2_VIEW_DASHBOARD.bat
    echo  to open the dashboard in your browser.
    echo ============================================
) else (
    echo.
    echo Something went wrong fetching data.
    echo The dashboard will still open with demo data.
)

echo.
pause
