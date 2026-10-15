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
rem 链 exe 同理: chain/ 会被整目录重建, 运行中的链 exe 会让 rmdir 失败
for %%E in (injector.exe haptic_launcher.exe) do (
    tasklist /FI "IMAGENAME eq %%E" /NH | find /I "%%E" >nul
    if not errorlevel 1 (
        echo [FAIL] %%E is running. Close it first.
        exit /b 1
    )
)

python -m pip install "pyinstaller>=6.0" || goto :fail
python -m PyInstaller --noconfirm --clean --windowed --name HapticImproveManager --collect-all qfluentwidgets app.py || goto :fail

if not exist "dist\HapticImproveManager\HapticImproveManager.exe" goto :fail

rem ---- 注入链冻结:随包分发,彻底零外部依赖 ----
set CHAIN_OUT=dist\HapticImproveManager\chain

rem chain/ 整目录重建: 本机试跑冻结版时 chain/ 会落下运行残留(games.yaml
rem 个人注册表、logs\、injector_result.txt 等), 随 zip 发出去会泄露个人路径、
rem 且收件人看到满屏"exe 丢失"红点会以为软件坏了。从零重建保证 chain/
rem 只含下面三个构建产物, 残留问题不靠自觉靠构造。
if exist "%CHAIN_OUT%" rmdir /s /q "%CHAIN_OUT%" || goto :fail

rem 两个链 exe 均无窗: IFEO 拉起不闪窗; GUI QProcess 拉起也不弹控制台
rem (launcher 的 stdout 诊断输出因此不可得, 诊断数据以 injector 的结果/日志文件为准)
python -m PyInstaller --noconfirm --clean --onefile --windowed --collect-all winsdk --distpath %CHAIN_OUT% --name injector %SPECIALK%\injector.py || goto :fail
python -m PyInstaller --noconfirm --clean --onefile --windowed --distpath %CHAIN_OUT% --name haptic_launcher %SPECIALK%\haptic_launcher.py || goto :fail
mkdir %CHAIN_OUT%\zzz_inject 2>nul
copy /Y %SPECIALK%\zzz_inject\wasapi_relink.dll %CHAIN_OUT%\zzz_inject\ || goto :fail

rem 完备性校验: 两个 exe + DLL 任一缺失即失败
if not exist "%CHAIN_OUT%\injector.exe" goto :fail
if not exist "%CHAIN_OUT%\haptic_launcher.exe" goto :fail
if not exist "%CHAIN_OUT%\zzz_inject\wasapi_relink.dll" goto :fail

rem 出包卫生兜底: games.yaml 绝不出包(冻结态缺失即空表起步, 见 registry.load_or_migrate)
if exist "%CHAIN_OUT%\games.yaml" goto :fail

rem ---- 打 zip: 紧接 chain 重建之后压缩, 保证 zip 永远不含本机运行残留 ----
powershell -NoProfile -Command "Compress-Archive -Path 'dist\HapticImproveManager' -DestinationPath 'dist\HapticImproveManager.zip' -Force" || goto :fail

echo.
echo [OK] Output: dist\HapticImproveManager\HapticImproveManager.exe
echo [OK] Chain:  dist\HapticImproveManager\chain\ (injector.exe + haptic_launcher.exe + zzz_inject\wasapi_relink.dll)
echo [OK] Zip:    dist\HapticImproveManager.zip (chain 整目录重建, 无本机运行残留)
exit /b 0

:fail
echo.
echo [FAIL] Build failed. See errors above.
exit /b 1
