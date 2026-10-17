@echo off
rem Build the full release: app+chain zip (build_exe.bat) + Inno Setup installer.
rem Run from repo root. Fails loudly on any error.

call packaging\build_exe.bat
if errorlevel 1 goto :fail

set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" (
    echo [FAIL] Inno Setup 6 not found. Install: winget install JRSoftware.InnoSetup
    exit /b 1
)

"%ISCC%" packaging\installer.iss || goto :fail
if not exist "dist\HapticImproveManager-Setup-0.4.6.exe" goto :fail

echo.
echo [OK] Installer: dist\HapticImproveManager-Setup-0.4.6.exe
exit /b 0

:fail
echo.
echo [FAIL] Installer build failed. See errors above.
exit /b 1
