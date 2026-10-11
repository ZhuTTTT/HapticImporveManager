# HapticImproveManager — 注入链随包分发(B3:链冻结为 exe)设计文档

> 日期:2026-10-11 · 状态:待评审
> 前置决策(头脑风暴已批准):选 B3 — `injector.py`/`haptic_launcher.py` 冻结为
> onefile exe 随 GUI 分发,**彻底零外部依赖**(无需系统 Python/pyyaml/python-winsdk,
> 无需 specialk 目录)。链源码留在 specialk 仓库继续开发,构建期取源。

## 1. 目标与现状问题

v0.2.0 的 Release 只能在复刻 `C:\Users\ZhuTT\Workspace\specialk` 目录的机器上
完整工作:`backend/paths.py:4` 写死 specialk 绝对路径,链脚本要系统 Python
+ pyyaml + python-winsdk(injector.py 的 toast 通知)。

目标形态:用户下载 zip 解压即用,GUI 与注入链全部自包含。

```
dist/HapticImproveManager/
  HapticImproveManager.exe (+ _internal/)   # 现有 GUI
  chain/                                    # 新增:注入链
    injector.exe           (onefile, --windowed, IFEO 拉起不闪窗)
    haptic_launcher.exe    (onefile, --console, GUI 需捕获其 stdout)
    zzz_inject/wasapi_relink.dll
    games.yaml             运行时生成/迁移,不打进包
    injector_result.txt / injector_debug.log / logs/   运行时生成
```

## 2. 链侧 patch(specialk 仓库,两文件,向后兼容 .py 用法)

两文件统一加冻结感知(`__file__` 在 onefile 里指向临时解包目录,不可写、
不含随包文件):

```python
if getattr(sys, "frozen", False):
    HERE = os.path.dirname(sys.executable)
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
```

- `haptic_launcher.py`:
  - 新增 `_injector_cmd()`:冻结 → `[HERE\injector.exe]`;源码 →
    `[sys.executable, HERE\injector.py]`。启动游戏的 subprocess 调用改用它。
  - `IFEO_VALUE`:冻结 → `f'"{HERE}\injector.exe" ifeo'`;源码保持现值不变。
- `injector.py`:
  - `IFEO_VALUE` 同上规则(与 launcher 侧始终一致)。
  - `DEFAULT_DLL`、`_report`、`_report_debug` 的 `__file__` 基准全部换成 `HERE`
    (行为在源码态不变)。

`_elevate()`(ShellExecuteW runas + sys.executable + argv)冻结态天然正确,不动。

## 3. GUI 侧改动

### `backend/paths.py`(重写为按运行态计算)

```python
DEV_SPECIALK_DIR = r"C:\Users\ZhuTT\Workspace\specialk"  # 源码态链目录(本机构建常量)

def _chain_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "chain")
    return DEV_SPECIALK_DIR

CHAIN_DIR = _chain_dir()
# 派生路径全部基于 CHAIN_DIR: GAMES_YAML / LAUNCHER_PY / INJECTOR_PY /
# DEFAULT_DLL / INJECTOR_RESULT / INJECTOR_DEBUG_LOG / RELINK_LOG_DIR / RELINK_LOG
LAUNCHER_EXE = os.path.join(CHAIN_DIR, "haptic_launcher.exe")
INJECTOR_EXE = os.path.join(CHAIN_DIR, "injector.exe")
IFEO_VALUE = (f'"{INJECTOR_EXE}" ifeo' if getattr(sys, "frozen", False)
              else ('"C:\\Users\\ZhuTT\\AppData\\Local\\Python\\bin\\pythonw.exe" '
                    '"C:\\Users\\ZhuTT\\Workspace\\specialk\\injector.py" ifeo'))
# 源码分支与 injector.py 的源码态常量逐字一致(test_paths 锁定)
```

模块级常量风格不变(`paths.GAMES_YAML` 用法与 monkeypatch 测试模式不受影响)。

### `backend/ifeo.py` / `backend/launcher.py`

- `build_ifeo_args(name, action)`:冻结 → `[LAUNCHER_EXE, "ifeo", name, action]`;
  源码 → 现行为。删掉 `python` 参数(冻结感知内化),调用方同步。
- `launcher._launcher_cmd()`:冻结 → `[LAUNCHER_EXE]`;源码 →
  `[_python_exe(), LAUNCHER_PY]`。`launch_game`/`set_ifeo` 改用它。
- `query_ifeo` 的子串匹配(`paths.IFEO_VALUE in val`)两种形态都成立,不动。

### `backend/registry.py` — games.yaml 迁移

`load_or_migrate` 前置一步纯函数
`migrate_legacy_chain_yaml(chain_dir, legacy_dir)`:冻结态、`<chain>/games.yaml`
缺失、`DEV_SPECIALK_DIR\games.yaml` 存在 → `shutil.copy2` 复制(保留原件)。
真实用户机器上 legacy 路径不存在,自然跳过;只有开发机从源码/旧版切换到
冻结版时触发一次。

## 4. 构建脚本(build_exe.bat)

GUI 构建之后追加:

```bat
set SPECIALK=C:\Users\ZhuTT\Workspace\specialk
set CHAIN_OUT=dist\HapticImproveManager\chain

rem 链冻结: injector 无窗(IFEO 拉起不闪窗), launcher 保留 stdout(GUI 捕获)
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --collect-all winsdk --distpath %CHAIN_OUT% --name injector ^
  %SPECIALK%\injector.py || goto :fail
python -m PyInstaller --noconfirm --clean --onefile --console ^
  --distpath %CHAIN_OUT% --name haptic_launcher ^
  %SPECIALK%\haptic_launcher.py || goto :fail
mkdir %CHAIN_OUT%\zzz_inject 2>nul
copy /Y %SPECIALK%\zzz_inject\wasapi_relink.dll %CHAIN_OUT%\zzz_inject\ || goto :fail

rem 完备性校验: 两个 exe + DLL 齐备才报 [OK]
if not exist "%CHAIN_OUT%\injector.exe" goto :fail
if not exist "%CHAIN_OUT%\haptic_launcher.exe" goto :fail
if not exist "%CHAIN_OUT%\zzz_inject\wasapi_relink.dll" goto :fail
```

`SPECIALK` 为构建期常量(注释注明:仅构建期依赖,运行时不依赖)。

**风险点**:python-winsdk 的 WinRT 投影在 onefile 下可能需 hidden-import/
collect-all 调优 — 以 §7 e2e 的 toast 验证为准,失败再调打包参数。

## 5. 测试

- `test_paths.py`:新增冻结解析用例(monkeypatch `sys.frozen=True` +
  `sys.executable` 指向 tmp,`importlib.reload(paths)`)— 断言 CHAIN_DIR、
  `IFEO_VALUE == f'"{...}\\injector.exe" ifeo'`、LAUNCHER_EXE 后缀;
  reload 后恢复(测试尾声再 reload 回源码态)。
- `test_ifeo.py`:`build_ifeo_args` 冻结/源码两分支。
- `test_launcher.py`:`_launcher_cmd` 两分支。
- registry 迁移:`migrate_legacy_chain_yaml` 纯函数表驱动(存在/缺失/不覆盖
  已有目标)。
- 既有 `test_paths.py` 的 IFEO_VALUE ↔ injector.py 逐字断言保留(源码态语义
  不变,链 patch 后 injector.py 的源码分支常量不变)。

## 6. 文档与发布

- README 中英文:删除"依赖系统 Python"注意事项,改为"零依赖,解压即用";
  架构一节补 chain/ 说明;提醒**从 ≤v0.2.0 升级的用户需重新开一次 IFEO 开关**
  (注册表里的旧 pythonw 值与新版不匹配,`query_ifeo` 会显示"被其他调试器
  占用",重开即修复)。
- e2e 通过后发 **v0.3.0**(zip 重建 + gh release,发布说明含上述 IFEO 提醒)。

## 7. e2e 手工验证清单(本机)

1. `build_exe.bat` → 解压 zip 到**干净目录**(非 dist 原址)
2. 启动 GUI → 添加/确认游戏存在(games.yaml 写入 chain/)
3. IFEO 开关 on(UAC)→ 注册表 `Debugger` 值 = `"...\chain\injector.exe" ifeo`
4. 从 Steam 启动游戏 → 注入成功 toast + `chain/injector_result.txt` 写入
5. 诊断页显示注入结果与日志
6. IFEO off → 注册表值清除
