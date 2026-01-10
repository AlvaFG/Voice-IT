@echo off
REM Voice IT - Build Script for Windows
REM Creates a standalone .exe using PyInstaller

echo ========================================
echo Voice IT - Build Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)

REM Clean previous build
echo Cleaning previous build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM Build the executable
echo.
echo Building Voice IT...
echo.
pyinstaller voice_it.spec

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo.
echo Executable location: dist\VoiceIT.exe
echo ========================================
echo.

REM Ask if user wants to run the app
set /p run="Run Voice IT now? (Y/N): "
if /i "%run%"=="Y" (
    start "" "dist\VoiceIT.exe"
)

pause
