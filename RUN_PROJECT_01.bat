@echo off
chcp 65001 >nul
title Project 01 - HostelHub - Auto Run

echo.
echo ================================================
echo   PROJECT 01 - ONLINE HOSTEL FACILITIES
echo               REPORTING PLATFORM
echo ================================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

where powershell >nul 2>&1
if errorlevel 1 (
    echo [X] PowerShell not found. Please install Windows PowerShell 5.1+.
    pause
    exit /b 1
)

powershell -ExecutionPolicy Bypass -File "RUN_PROJECT_01.ps1"

if errorlevel 1 (
    echo.
    echo Press any key to exit...
    pause >nul
)