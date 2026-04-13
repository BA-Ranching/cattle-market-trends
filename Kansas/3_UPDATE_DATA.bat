@echo off
title Kansas Cattle Market Trends - Update Data
echo.
echo ============================================
echo  Fetching Latest USDA Kansas Market Data...
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
%PYTHON% fetch_data.py
echo.
if %errorlevel% == 0 (
    echo Data updated successfully!
    echo Open 2_VIEW_DASHBOARD.bat to view the latest data.
) else (
    echo Something went wrong. Check your internet connection and try again.
)
echo.
pause
