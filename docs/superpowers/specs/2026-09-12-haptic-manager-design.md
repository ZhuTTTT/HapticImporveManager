# HapticImproveManager — Haptic 注入系统可视化管理桌面应用 设计文档

> 日期:2026-09-12 · 状态:待评审
> 后端:`C:\Users\ZhuTT\Workspace\specialk\injector.py` + `haptic_launcher.py`(见 `specialk/HANDOVER.md`)

## 1. 目标

把现有命令行 haptic 低延迟注入系统(IFEO 拦截 + CreateProcess 父进程注入 wasapi_relink)包装成 PySide6 桌面管理应用,覆盖:

1. 游戏卡片列表(状态一览 + 快捷操作)
2. 添加游戏向导(选 exe → 反作弊检测 → 生成配置 → 开 IFEO)
3. `redirect_config.toml` 可视化编辑(模式/缓冲 + 经验提示)
4. 状态监控(最近注入结果 + 日志尾随)

诊断页(ETW 追踪/启动计时/延迟测量)本期**不做**,预留导航位。

## 2. 架构:薄 GUI + 子进程后端

```
┌──────────────────────────── PySide6 GUI ────────────────────────────┐
│ ui/ 4 页(QStackedWidget + 左侧导航)                                 │
│   ↓ 调用                                                             │
│ backend/                                                             │
│   registry.py ──读写──> games.yaml (specialk/, 与 launcher 共享)     │
│   ifeo.py ──winreg 只读查询; on/off ──QProcess──> haptic_launcher   │
│   launcher.py ──QProcess──> haptic_launcher.py <name> (启动+注入)    │
│   anticheat.py ──pefile 导入表静态扫描                               │
│   config.py ──tomlkit──> 游戏目录/redirect_config.toml               │
│   monitor.py ──QFileSystemWatcher──> injector_result.txt / logs/     │
└──────────────────────────────────────────────────────────────────────┘
```

**关键决策**:GUI **不 import** `injector.py` / `haptic_launcher.py` 的函数。
原因:`injector.py` 到处 `raise SystemExit`、`haptic_launcher._elevate()` 会
`sys.exit(0)`,同进程调用会直接终结 GUI;ctypes 阻塞调用也会卡死事件循环。
所有写操作走 `QProcess` 子进程,流式读取输出;只读查询(winreg/pefile/toml)在
GUI 进程内直接实现。

**权限模型**:GUI 本体普通权限运行。仅 `ifeo on/off` 需要写 HKLM,由
`haptic_launcher.py` 现有的 `_elevate()`(ShellExecute runas)自行提权——GUI
只需捕获"子进程以 UAC 退出"这一信号并提示用户已弹提权框。

## 3. 对 specialk 后端的最小改动

唯一改动:`haptic_launcher.py` 增加共享注册表加载。

```python
# haptic_launcher.py 新增
GAMES_YAML = os.path.join(HERE, "games.yaml")

def load_games() -> dict:
    """games.yaml 存在则以它为准(GUI 与 CLI 共用单一数据源),
    否则回落到下方硬编码 GAMES。"""
    if os.path.exists(GAMES_YAML):
        import yaml
        with open(GAMES_YAML, encoding="utf-8") as f:
            return yaml.safe_load(f)["games"]
    return GAMES
```

`main()` 与 `ifeo()` 内所有 `GAMES[...]` 改为 `load_games()`。其余文件
(`injector.py`、IFEO_VALUE 常量、注入逻辑)**零改动**。

`games.yaml` 格式:

```yaml
games:
  ds2:
    exe: 'C:\Program Files (x86)\Steam\steamapps\common\DEATH STRANDING 2 - ON THE BEACH\DS2.exe'
    mode_hint: Ringbuf        # 展示用:已知适用模式
    buffer_hint: 2048
    anticheat: false
  sb:
    exe: 'E:\SteamLibrary\steamapps\common\StellarBlade\SB\Binaries\Win64\SB-Win64-Shipping.exe'
    mode_hint: Normal
    buffer_hint: 256
    anticheat: false
  zzz:
    exe: 'E:\miHoYo Lancher\games\ZenlessZoneZero Game\ZenlessZoneZero.exe'
    mode_hint: Normal
    buffer_hint: 960
    anticheat: true           # HoYoKProtect
```

初版 `games.yaml` 由 GUI 首次运行时从 `haptic_launcher.GAMES` 迁移生成(或随仓库附带),三个现有游戏按上表预填。

## 4. 模块设计

### 4.1 backend/registry.py
- `load_games() -> dict[str, GameEntry]`、`save_games()`、`add_game()`、`remove_game()`
- `GameEntry` dataclass:`name, exe, mode_hint, buffer_hint, anticheat`
- 写 YAML 用 PyYAML(`yaml.safe_dump`, `allow_unicode=True`)
- 派生属性(不入库,每次现查):exe 是否存在、`redirect_config.toml` 是否存在、IFEO 状态

### 4.2 backend/ifeo.py
- `query_ifeo(exe_name) -> IfeoState`:`winreg` 只读打开 `HKLM\...\IFEO\<exe>`,读 `Debugger` 值;区分 `OFF` / `ON(我方注入器)` / `ON(其他调试器,告警)`
- `set_ifeo(name, on: bool)`:QProcess 调 `python haptic_launcher.py ifeo <name> on|off`;检测提权退出码并向 UI 发信号

### 4.3 backend/launcher.py
- `launch_game(name)`:QProcess 调 `python haptic_launcher.py <name>`,stdout/stderr 逐行转 Qt 信号,供监控页显示
- 启动前预检:exe 存在、无 `redirect_config.toml` 时弹警告(沿用 CLI 行为)

### 4.4 backend/anticheat.py
- `scan_exe(path) -> AnticheatReport`:pefile 读导入表,匹配已知反作弊模块/特征(`HoYoKProtect`、`EasyAntiCheat`、`BEService`/`BattlEye`、`xigncode` 等),返回风险等级 + 命中列表
- 仅警告不阻止(HANDOVER 第 4.9 条:反作弊游戏注入有封禁风险,需用户知情确认)

### 4.5 backend/config.py
- 用 **tomlkit**(非 tomllib)读写 `redirect_config.toml`,保留注释与格式
- `load_config(game_dir)` / `save_config(game_dir, cfg)` / `default_config() -> str`
- 字段校验:`mode ∈ {Normal, Ringbuf, Compat, Bypass}`;`target_period_hus` 0–1000;缓冲帧数 > 0;`log_level` 强制 `Error`(写 Info 时弹"仅排障临时使用"确认框——HANDOVER 第 4.8 条,Info 可写 GB 级日志)

### 4.6 backend/monitor.py
- `QFileSystemWatcher` 监视 `injector_result.txt`(覆盖写,记录最近注入结果)、`injector_debug.log`(追加)、`logs/wasapi_relink.log`
- `tail(path, n)` 工具函数;变更时发 Qt 信号,监控页追加显示

## 5. UI 设计

主窗口:左侧导航栏(QListWidget 图标模式)+ 右侧 `QStackedWidget`,深色主题。

### 5.1 游戏列表页(默认页)
卡片式网格,每卡:
- 游戏名 / exe 路径(截断显示,tooltip 全路径)
- 状态灯:绿 = IFEO 开 + 配置在 + exe 在;黄 = 部分缺失;红 = exe 丢失
- IFEO 开关(QCheckBox 自定义样式为拨动开关,PySide6 无内置 QSwitch;切换走 `ifeo.py`,需提权时提示)
- 按钮:启动 / 编辑配置 / 移除
- 展示 `mode_hint` / `buffer_hint` / 反作弊标记

### 5.2 添加游戏向导(QWizard,4 步)
1. **选 exe**:文件对话框;选完自动 `anticheat.scan_exe()`
2. **反作弊结果**:命中 → 红字警告 + "已知风险:HoYoKProtect 会剥离句柄、改名外来 DLL"说明,需勾选"我已了解风险"才能继续;未命中 → 绿色通过
3. **配置生成**:选模式(默认 Normal)、缓冲滑块,生成 `redirect_config.toml` 到游戏目录(已存在则询问保留/覆盖);`log_level` 恒写 `Error`
4. **启用 IFEO**:一键 `ifeo on`(触发 UAC);显示结果;完成页提示"之后从 Steam/启动器正常启动即可自动注入"

### 5.3 配置编辑页
- 顶栏:游戏下拉切换
- 表单:模式下拉(Normal/Ringbuf/Compat/Bypass,各带 HANDOVER 第 3 节经验提示文字:`Normal=大多数游戏可用,缓冲过小会破音` / `Ringbuf=DS2 需要;UE5 爆发写入会溢出刷屏;ZZZ 丢扬声器声道`)、`target_period_hus` 滑块(0=原生 到 1000=100ms)、`target_buffer_len` / `ring_buffer_len` 按模式启用、`raw`/`force_period` 复选框
- 日志区:`log_level` 下拉(改 Info 时强确认)
- 保存按钮 + "恢复默认"按钮;保存前 tomlkit round-trip 校验

### 5.4 状态监控页
- 顶部:最近注入卡片(读 `injector_result.txt`:文件修改时间 + 结果文本 + 成功/失败配色;文件本身不含时间戳,用 mtime)
- 中部:`injector_debug.log` 尾随视图(QPlainTextEdit 只读,自动滚底)
- 底部:`logs/wasapi_relink.log` 尾随(默认折叠,排障用)
- 通知历史:GUI 会话内捕捉到的注入事件列表

## 6. 目录结构

```
HapticImporveManager/
├── app.py                 # 入口: QApplication + MainWindow
├── requirements.txt       # PySide6, PyYAML, pefile, tomlkit
├── backend/
│   ├── __init__.py
│   ├── paths.py           # specialk/ 绝对路径、games.yaml 位置等常量
│   ├── registry.py
│   ├── ifeo.py
│   ├── launcher.py
│   ├── anticheat.py
│   ├── config.py
│   └── monitor.py
├── ui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── games_page.py
│   ├── add_wizard.py
│   ├── config_editor.py
│   └── monitor_page.py
└── tests/
    ├── test_registry.py
    ├── test_config.py
    └── test_anticheat.py
```

后端路径(`specialk/` 的绝对路径、`games.yaml` 位置)集中在
`backend/paths.py` 常量中,便于日后迁移。

## 7. 错误处理

| 场景 | 行为 |
|---|---|
| exe 丢失 | 卡片红灯,启动按钮禁用 |
| `games.yaml` 损坏 | 弹错误框 + 备份为 `.bak` + 从 launcher GAMES 重建 |
| `ifeo on` 用户拒绝 UAC | 子进程退出码非 0,卡片状态不变,提示"已取消提权" |
| 注入失败 | injector 自身已弹系统通知;监控页同步显示失败行(红色) |
| `redirect_config.toml` 语法错误 | 编辑页载入失败 → 显示原始文本 + 错误行号,不允许表单覆盖 |
| 游戏正在运行时改配置 | 允许保存,提示"重启游戏后生效" |

## 8. 测试

pytest,只测 backend(UI 不自动化):

- `test_registry.py`:YAML 读写 round-trip、坏文件恢复、增删游戏
- `test_config.py`:tomlkit 读写保留注释、字段校验、默认值生成、`log_level` 强制规则
- `test_anticheat.py`:用 fixture PE(可用系统 notepad.exe + 一个带 EAC 导入表的样本)验证扫描结果
- winreg 相关用 monkeypatch 替身,不碰真实注册表

## 9. 非目标(本期不做)

- 诊断页(ETW 追踪、启动计时、latency_test 集成)
- 打包分发(先 `python app.py` 源码运行;PyInstaller 打包留待后续)
- wasapi_relink 本体修改/编译
- 多手柄/多配置 profile
