@echo off
rem Build HapticImproveManager as onedir exe. Run from repo root.
rem Fails loudly: any error exits non-zero instead of printing a fake success.

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

rem 应用图标: packaging\icon.svg 是源文件, icon.ico 是多尺寸打包产物
rem PyInstaller 的 --specpath=build 会把相对 icon 路径解析到 build\ 下, 这里用脚本自身的绝对路径
set ICON=%~dp0icon.ico
if not exist "%ICON%" (
    echo [FAIL] packaging\icon.ico not found.
    exit /b 1
)

rem --specpath: .spec 构建中间产物统一落 build\, 不污染仓库根目录
rem --add-data: 图标一并打进 _internal, app.py 运行时读它设置窗口/任务栏图标
python -m pip install "pyinstaller>=6.0" || goto :fail
python -m PyInstaller --noconfirm --clean --windowed "--icon=%ICON%" --add-data "%ICON%;." --specpath build --name HapticImproveManager --collect-all qfluentwidgets app.py || goto :fail

if not exist "dist\HapticImproveManager\HapticImproveManager.exe" goto :fail

rem ---- 注入链冻结: 源码就在本仓库 chain/, 随包分发, 彻底零外部依赖 ----
set CHAIN_OUT=dist\HapticImproveManager\chain

rem chain/ 整目录重建: 本机试跑冻结版时 chain/ 会落下运行残留(games.yaml
rem 个人注册表、logs\、injector_result.txt 等), 随 zip 发出去会泄露个人路径、
rem 且收件人看到满屏"exe 丢失"红点会以为软件坏了。从零重建保证 chain/
rem 只含下面三个构建产物, 残留问题不靠自觉靠构造。
if exist "%CHAIN_OUT%" rmdir /s /q "%CHAIN_OUT%" || goto :fail

rem 两个链 exe 均无窗: IFEO 拉起不闪窗; GUI QProcess 拉起也不弹控制台
rem (launcher 的 stdout 诊断输出因此不可得, 诊断数据以 injector 的结果/日志文件为准)
rem
rem injector 用 onedir 并平铺到 chain 根(exe 路径不变, IFEO 注册表值零迁移):
rem onefile 每次运行解包 %TEMP%\_MEI*, 退出时清理 — 绝区零 HoYoKProtect
rem 初始化扫描父进程链会瞬锁该目录, 看门狗删不掉就弹 "Failed to remove
rem temporary directory" 警告; onedir 不解包, 从根上消除这个警告类别
python -m PyInstaller --noconfirm --clean --onedir --windowed --specpath build --collect-all winsdk --distpath %CHAIN_OUT% --name injector chain\injector.py || goto :fail
xcopy /E /I /Y /Q "%CHAIN_OUT%\injector\*" "%CHAIN_OUT%\" >nul || goto :fail
rmdir /s /q "%CHAIN_OUT%\injector" || goto :fail
rem haptic_launcher 保持 onefile: 只被 GUI 以完整路径调用, 无注册表引用,
rem 且不接触游戏进程链, 没有上述锁目录触发条件
python -m PyInstaller --noconfirm --clean --onefile --windowed --specpath build --distpath %CHAIN_OUT% --name haptic_launcher chain\haptic_launcher.py || goto :fail
copy /Y chain\wasapi_relink.dll %CHAIN_OUT%\ || goto :fail

rem 第三方组件许可证随包携带(wasapi_relink 是 Apache-2.0, 再分发需附带许可证文本)
if not exist "dist\HapticImproveManager\licenses" mkdir "dist\HapticImproveManager\licenses"
copy /Y licenses\wasapi_relink.LICENSE.txt "dist\HapticImproveManager\licenses\" || goto :fail

rem 完备性校验: 两个 exe + injector 运行时目录 + DLL 任一缺失即失败
if not exist "%CHAIN_OUT%\injector.exe" goto :fail
if not exist "%CHAIN_OUT%\_internal\base_library.zip" goto :fail
if not exist "%CHAIN_OUT%\haptic_launcher.exe" goto :fail
if not exist "%CHAIN_OUT%\wasapi_relink.dll" goto :fail

rem 出包卫生兜底: games.yaml 绝不出包(冻结态缺失即空表起步, 见 registry.load_or_migrate)
if exist "%CHAIN_OUT%\games.yaml" goto :fail

rem ---- 打 zip: 紧接 chain 重建之后压缩, 保证 zip 永远不含本机运行残留 ----
powershell -NoProfile -Command "Compress-Archive -Path 'dist\HapticImproveManager' -DestinationPath 'dist\HapticImproveManager.zip' -Force" || goto :fail

echo.
echo [OK] Output: dist\HapticImproveManager\HapticImproveManager.exe
echo [OK] Chain:  dist\HapticImproveManager\chain\ (injector.exe + haptic_launcher.exe + wasapi_relink.dll)
echo [OK] Zip:    dist\HapticImproveManager.zip (chain 整目录重建, 无本机运行残留)
exit /b 0

:fail
echo.
echo [FAIL] Build failed. See errors above.
exit /b 1
