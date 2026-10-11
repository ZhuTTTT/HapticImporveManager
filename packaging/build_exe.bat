@echo off
rem Build HapticImproveManager as onedir exe. Run from repo root.
rem Fails loudly: any error exits non-zero instead of printing a fake success.

rem 注入链源码目录:仅构建期依赖,运行时不需要(链已冻结为 exe 随包分发)
set SPECIALK=C:\Users\ZhuTT\Workspace\specialk

rem Refuse to build while the old exe is running (it locks dist\).
tasklist /FI "IMAGENAME eq HapticImproveManager.exe" /NH | find /I "HapticImproveManager.exe" >nul
if not errorlevel 1 (
    echo [FAIL] HapticImproveManager.exe is running. Close it first.
    exit /b 1
)

python -m pip install "pyinstaller>=6.0" || goto :fail
python -m PyInstaller --noconfirm --clean --windowed --name HapticImproveManager --collect-all qfluentwidgets app.py || goto :fail

if not exist "dist\HapticImproveManager\HapticImproveManager.exe" goto :fail

rem ---- 注入链冻结:随包分发,彻底零外部依赖 ----
set CHAIN_OUT=dist\HapticImproveManager\chain

rem injector 无窗(IFEO 拉起不闪窗), launcher 保留 stdout(GUI 需捕获)
python -m PyInstaller --noconfirm --clean --onefile --windowed --collect-all winsdk --distpath %CHAIN_OUT% --name injector %SPECIALK%\injector.py || goto :fail
python -m PyInstaller --noconfirm --clean --onefile --console --distpath %CHAIN_OUT% --name haptic_launcher %SPECIALK%\haptic_launcher.py || goto :fail
mkdir %CHAIN_OUT%\zzz_inject 2>nul
copy /Y %SPECIALK%\zzz_inject\wasapi_relink.dll %CHAIN_OUT%\zzz_inject\ || goto :fail

rem 完备性校验: 两个 exe + DLL 任一缺失即失败
if not exist "%CHAIN_OUT%\injector.exe" goto :fail
if not exist "%CHAIN_OUT%\haptic_launcher.exe" goto :fail
if not exist "%CHAIN_OUT%\zzz_inject\wasapi_relink.dll" goto :fail

echo.
echo [OK] Output: dist\HapticImproveManager\HapticImproveManager.exe
echo [OK] Chain:  dist\HapticImproveManager\chain\ (injector.exe + haptic_launcher.exe + zzz_inject\wasapi_relink.dll)
exit /b 0

:fail
echo.
echo [FAIL] Build failed. See errors above.
exit /b 1
