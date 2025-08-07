@echo off
setlocal ENABLEEXTENSIONS

echo.
echo =======================================
echo        Antares Lumina Setup
echo =======================================
echo.

:: Detect system Python
set "PYTHON_CMD="
where python >nul 2>&1 && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    where py >nul 2>&1 && set "PYTHON_CMD=py"
)
if not defined PYTHON_CMD (
    echo Python is not installed or not on PATH.
    echo Please install Python 3.9+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Using system Python: %PYTHON_CMD%

:: Create venv if missing
if not exist ".venv\" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
)

:: Use venv's python for all installs
set "VENV_PY=.\.venv\Scripts\python.exe"
echo Using venv Python: %VENV_PY%

echo Upgrading pip...
%VENV_PY% -m pip install --upgrade pip >nul

echo Installing packages...
%VENV_PY% -m pip install ^
    azure-storage-blob ^
    azure-core ^
    azure-identity ^
    azure-search-documents ^
    PyMuPDF ^
    beautifulsoup4 ^
    selenium ^
    webdriver_manager ^
    python-dotenv ^
    openai ^
    numpy ^
    pytesseract ^
    easyocr ^
    azure-keyvault-secrets

:: Check if Azure CLI is installed
echo.
where az >nul 2>&1
if errorlevel 1 (
    echo Azure CLI is not installed. Please install it from:
    echo https://learn.microsoft.com/en-us/cli/azure/install-azure-cli
    pause
    exit /b 1
) else (
    echo Azure CLI found. Starting login...
    az login
)

echo.
echo ✅ Setup complete. To activate venv manually later:
echo    .venv\Scripts\activate   (for cmd)
echo    .venv\Scripts\Activate.ps1 (for PowerShell)
echo.
pause
endlocal