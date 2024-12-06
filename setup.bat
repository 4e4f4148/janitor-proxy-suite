@echo off
:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH.
    echo Please install Python and add it to PATH.
    pause
    exit /b 1
)

:: Create a virtual environment named .venv
echo Creating virtual environment .venv...
python -m venv .venv

if not exist .venv (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

:: Activate the virtual environment
echo Activating the virtual environment...
call .\.venv\Scripts\activate

:: Check if requirements.txt exists
if not exist requirements.txt (
    echo requirements.txt not found. Skipping installation of dependencies.
    pause
    exit /b 0
)

:: Install dependencies from requirements.txt
echo Installing dependencies from requirements.txt...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo Failed to install dependencies. Check requirements.txt and try again.
    pause
    exit /b 1
)

echo All dependencies installed successfully!
pause