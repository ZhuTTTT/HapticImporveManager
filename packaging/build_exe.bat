@echo off
rem Build HapticImproveManager as onedir exe. Run from repo root.
rem Fails loudly: any error exits non-zero instead of printing a fake success.

rem Refuse to build while the old exe is running (it locks dist\).
tasklist /FI "IMAGENAME eq HapticImproveManager.exe" /NH | find /I "HapticImproveManager.exe" >nul
if not errorlevel 1 (
    echo [FAIL] HapticImproveManager.exe is running. Close it first.
    exit /b 1
)

python -m pip install "pyinstaller>=6.0" || goto :fail
python -m PyInstaller --noconfirm --clean --windowed --name HapticImproveManager --collect-all qfluentwidgets app.py || goto :fail

if not exist "dist\HapticImproveManager\HapticImproveManager.exe" goto :fail

echo.
echo [OK] Output: dist\HapticImproveManager\HapticImproveManager.exe
exit /b 0

:fail
echo.
echo [FAIL] Build failed. See errors above.
exit /b 1
