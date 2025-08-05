@echo off
setlocal ENABLEEXTENSIONS

echo.
echo =======================================
echo           Antares Lumina
echo =======================================
echo.

if not exist ".venv\" (
    echo ==== Virtual environment not found. Run setup_lumina.bat first. ====
    pause
    exit /b 1
)

call .venv\Scripts\activate
python app.py

if errorlevel 1 (
    echo.
    echo ==== Lumina exited with an error. Check the logs above. ====
    pause
)

endlocal
