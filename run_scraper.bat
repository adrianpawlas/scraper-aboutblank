@echo off
REM About Blank Scraper - Manual Run Script
echo Starting About Blank Scraper...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if virtual environment exists and activate it
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo No virtual environment found, using system Python...
)

REM Run the scraper
echo Running scraper...
python main.py

REM Deactivate virtual environment if it was activated
if exist venv\Scripts\deactivate.bat (
    call venv\Scripts\deactivate.bat
)

echo.
echo Scraper execution completed.
echo Press any key to exit...
pause >nul