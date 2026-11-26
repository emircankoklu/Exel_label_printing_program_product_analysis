@echo off
setlocal
cd /d "%~dp0"

python -m pip install -r requirements-build.txt
if errorlevel 1 (
    echo Bagimliliklar yuklenemedi.
    pause
    exit /b 1
)

python -m PyInstaller --clean --noconfirm --onefile --windowed --name "YamacEtiket" --add-data "static;static" fisv9.py
if errorlevel 1 (
    echo EXE olusturulamadi.
    pause
    exit /b 1
)

echo.
echo Uygulama hazir: dist\YamacEtiket.exe
pause
