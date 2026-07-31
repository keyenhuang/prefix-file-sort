@echo off
REM Build script for prefix-file-sort on Windows
REM Usage: build.bat

echo ====================================
echo prefix-file-sort Build Script
echo ====================================

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>NUL
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Check if tkinterdnd2 is installed
python -c "import tkinterdnd2" 2>NUL
if errorlevel 1 (
    echo tkinterdnd2 not found. Installing...
    pip install tkinterdnd2
)

REM Build the executable
echo.
echo Building executable...
pyinstaller prefix_file_sort.spec --clean

if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo ====================================
echo Build completed successfully!
echo Executable location: dist\prefix-file-sort\prefix-file-sort.exe
echo ====================================
echo.
pause
