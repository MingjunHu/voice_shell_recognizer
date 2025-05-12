@echo off
chcp 65001 >nul

echo [INFO] Voice Recognition Backend Service Startup Script (Windows)

:: Create necessary directories
if not exist temp_audio (
    mkdir temp_audio
)
if not exist diyvoice\llmanswer (
    mkdir diyvoice\llmanswer
)

:: Delete existing log file if it exists to avoid permission issues
if exist shell_service.log (
    del /f shell_service.log
)

:: Start the voice recognition backend service
echo [INFO] Starting voice recognition backend service...
start /b python shell_service.py

:: Wait a moment for the service to start
timeout /t 3 > nul

:: Check if the service is running
tasklist | findstr python > nul
if %errorlevel% equ 0 (
    echo [INFO] Service started successfully!
) else (
    echo [ERROR] Service failed to start!
    if exist shell_service.log (
        echo [INFO] Log file content:
        type shell_service.log
    ) else (
        echo [WARNING] No log file found.
    )
)

:: Output information
echo [INFO] To view running processes use: tasklist ^| findstr python
echo [INFO] To stop service use: taskkill /F /IM python.exe

pause