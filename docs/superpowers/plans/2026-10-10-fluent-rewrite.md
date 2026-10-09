# Fluent 重写实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 PySide6 + PySide6-Fluent-Widgets 重写 HapticImproveManager 的 UI 层,改为游戏中心式信息架构,配置项通俗化,日志目录可配置。

**Architecture:** 薄 GUI + 子进程后端的格局不变。`backend/` 仅做加法;`ui/` 整体重写为 FluentWindow + 三个子界面(游戏/诊断/设置)。表单↔TOML 映射抽成 `ui/config_model.py` 纯函数便于单测;GUI 设置(主题/Mica/日志目录)经 `ui/app_config.py`(qfluentwidgets QConfig)持久化。

**Tech Stack:** Python 3, PySide6, PySide6-Fluent-Widgets(免费版), tomlkit, pytest。

**Spec:** `docs/superpowers/specs/2026-10-10-fluent-rewrite-design.md`

## Global Constraints

- `backend/` 只加不改:`config.default_config()` 无参调用行为必须保持现状;`paths.py`/`ifeo.py`/`launcher.py`/`registry.py`/`anticheat.py`/`monitor.py` 一行不动
- 现有 `tests/` 必须保持全绿:`python -m pytest tests/ -v`
- tomlkit 点分键陷阱:`target_buffer_len.48000` 的子表键必须是**字符串** `"48000"`,int 键会 TypeError;赋值用原位改值(`tbl[key] = v`),整体替换子表会丢注释
- `save_config` 已含 `newline=""`,不得改动
- 只用 PySide6-Fluent-Widgets 免费版组件;若计划中的组件名不存在,用基础组件等价实现,不得引入 Pro
- 所有 UI 文案为简体中文
- 禁止在 QSS 中硬编码十六进制颜色(深色主题适配红线);状态色用 `qfluentwidgets` 主题令牌(`themeColor()` / `FluentThemeColor`)或 InfoBar/Badge 自带配色
- IFEO 轮询:每个触发源只持有一个 QTimer,重复触发先 `stop()` 旧定时器(旧代码修过的泄漏,不得回归)
- Windows 专属:资源管理器打开用 `explorer /select,<path>`(定位文件)或 `explorer <dir>`(打开目录)
- pytest 中实例化 QWidget 需 `QT_QPA_PLATFORM=offscreen`(在 import Qt 之前设置 env)

## Review Focus

1. **tomlkit 点分键 int/str**:任何写 `target_buffer_len`/`ring_buffer_len` 的代码路径用 int 键会炸 → Task 3 单测覆盖
2. **QConfig 首次运行**(json 不存在):`log_dir` 等必须回退到默认值而不是空串 → Task 2 单测覆盖
3. **批量同步 log_path 时某游戏配置缺失/损坏**:不得中断整批,跳过并在结果中列出 → Task 4 单测覆盖
4. **IFEO 开关快速重复切换**:多个 QTimer 并发导致状态错乱 → Task 5 代码约束(单实例先停)
5. **深色主题可读性**:状态徽章/提示文字在深色下不可读 → Task 9 人工验证清单(浅色/深色各过一遍)

---

### Task 1: 依赖安装 + backend 加法(default_config log_dir / set_log_dir)

**Files:**
- Modify: `requirements.txt`
- Modify: `backend/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 现有 `backend.config._DEFAULT_TEXT`(含 `log_path = "..."` 行)
- Produces:
  - `default_config(log_dir: str | None = None) -> TOMLDocument`(无参行为不变)
  - `set_log_dir(game_dir: str, log_dir: str) -> None`(原位改 `log_path` 并保存;配置不存在抛 `FileNotFoundError`;损坏 toml 原样抛解析异常)
  - requirements 新增 `PySide6-Fluent-Widgets>=1.7`

- [ ] **Step 1: 安装依赖并验证 API 可用名**

```powershell
python -m pip install "PySide6-Fluent-Widgets>=1.7"
python -c "from qfluentwidgets import (FluentWindow, NavigationItemPosition, setTheme, Theme, QConfig, ConfigItem, OptionsConfigItem, OptionsValidator, BoolValidator, qconfig, CardWidget, SimpleCardWidget, HeaderCardWidget, PushButton, PrimaryPushButton, SwitchButton, CheckBox, ComboBox, Slider, SpinBox, LineEdit, SearchLineEdit, InfoBar, InfoBarPosition, MessageBox, MessageBoxBase, Pivot, ListWidget, PlainTextEdit, FluentIcon, BodyLabel, StrongBodyLabel, CaptionLabel, TitleLabel, SubtitleLabel, SingleDirectionScrollArea, ToolButton, TransparentToolButton, IndeterminateProgressBar, StateToolTip, setThemeColor); print('API OK', Theme.AUTO)"
```

Expected: 打印 `API OK Theme.AUTO`。若某个名字 ImportError,在 `python -c "import qfluentwidgets, inspect; print([n for n in dir(qfluentwidgets)])"` 输出中找等价名替换,并把替换结果写进本任务提交信息,后续任务以替换后名字为准。

- [ ] **Step 2: requirements.txt 加依赖**

在 `requirements.txt` 第 2 行(PyYAML 前)插入:

```
PySide6-Fluent-Widgets>=1.7
```

- [ ] **Step 3: 写失败测试**

追加到 `tests/test_config.py`:

```python
def test_default_config_with_log_dir():
    from backend.config import default_config
    doc = default_config(log_dir="D:/mylogs")
    assert doc["log_path"] == "D:/mylogs"
    assert validate(doc) == []


def test_default_config_no_arg_unchanged():
    from backend.config import default_config
    doc = default_config()
    assert doc["log_path"] == paths.RELINK_LOG_DIR.replace(os.sep, "/")


def test_set_log_dir(tmp_path):
    from backend.config import set_log_dir
    cfg = tmp_path / "redirect_config.toml"
    cfg.write_text('# 注释\nlog_path = "C:/old"\nlog_level = "Error"\n',
                   encoding="utf-8")
    set_log_dir(str(tmp_path), "D:/new")
    out = cfg.read_text(encoding="utf-8")
    assert 'log_path = "D:/new"' in out
    assert "# 注释" in out  # 注释保留


def test_set_log_dir_missing_raises(tmp_path):
    from backend.config import set_log_dir
    import pytest as _pt
    with _pt.raises(FileNotFoundError):
        set_log_dir(str(tmp_path), "D:/new")
```

文件头部 import 补 `import os` 和 `from backend import paths`。

- [ ] **Step 4: 跑测试确认失败**

Run: `python -m pytest tests/test_config.py -v`
Expected: 4 个新测试 FAIL(ImportError / TypeError: 未知参数)

- [ ] **Step 5: 实现**

修改 `backend/config.py`:

```python
# _DEFAULT_TEXT 改为模板函数 — 原常量删除, 行为等价
def _default_text(log_dir: str | None = None) -> str:
    log_path = (log_dir or paths.RELINK_LOG_DIR).replace(os.sep, "/")
    return f'''\
# wasapi_relink 配置 — 由 HapticImproveManager 生成
log_path = "{log_path}"
log_level = "Error"        # 必须 Error! Info 在溢出时会写 GB 级日志
only_log_stdout = false

[playback]
mode = "Normal"            # Normal | Ringbuf | Compat | Bypass
target_period_hus = 100    # 100 = 10ms (单位 0.1ms); 0 = 原生
target_buffer_len.48000 = 960   # Normal 用, 帧数. 256→5.3ms 可能破音
ring_buffer_len.48000 = 4320    # Ringbuf 用, 给应用的虚拟缓冲帧数
raw = true
force_period = true

[capture]
mode = "Bypass"
'''


def default_config(log_dir: str | None = None) -> TOMLDocument:
    """log_dir 缺省保持 paths.RELINK_LOG_DIR(现状不变)。"""
    return tomlkit.parse(_default_text(log_dir))


def set_log_dir(game_dir: str, log_dir: str) -> None:
    """原位改 redirect_config.toml 的 log_path, 保留注释。"""
    doc = load_config(game_dir)  # 缺失抛 FileNotFoundError, 损坏抛解析异常
    doc["log_path"] = log_dir.replace(os.sep, "/")
    save_config(game_dir, doc)
```

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/ -v`
Expected: 全绿(含旧测试)

- [ ] **Step 7: Commit**

```powershell
git add requirements.txt backend/config.py tests/test_config.py
git commit -m "feat(backend): default_config 支持自定义 log_dir + set_log_dir 原位改 log_path"
```

---

### Task 2: ui/app_config.py — GUI 设置持久化

**Files:**
- Create: `ui/app_config.py`
- Test: `tests/test_app_config.py`

**Interfaces:**
- Consumes: `backend.paths.RELINK_LOG_DIR`
- Produces:
  - `AppConfig(QConfig)` 子类,字段:
    - `theme_mode: OptionsConfigItem`,值域 `["Light", "Dark", "Auto"]`,默认 `"Auto"`
    - `mica_enabled: ConfigItem`,bool,默认 `True`
    - `log_dir: ConfigItem`,str,默认 `paths.RELINK_LOG_DIR`
  - `load_app_config(path: str | None = None) -> AppConfig`(path 缺省用 `%APPDATA%/HapticImproveManager/gui_config.json`;文件不存在时用默认值)
  - `apply_theme(cfg: AppConfig) -> None`(按 `theme_mode` 调 `setTheme`)
  - 模块级单例 `APP_CFG: AppConfig`(由 `load_app_config()` 创建;测试里不要用单例,用显式 path)

- [ ] **Step 1: 写失败测试**

Create `tests/test_app_config.py`:

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from backend import paths
from ui.app_config import AppConfig, load_app_config


def test_defaults_when_file_missing(tmp_path):
    cfg = load_app_config(str(tmp_path / "nonexistent.json"))
    assert cfg.theme_mode.value == "Auto"
    assert cfg.mica_enabled.value is True
    assert cfg.log_dir.value == paths.RELINK_LOG_DIR


def test_round_trip(tmp_path):
    p = str(tmp_path / "cfg.json")
    cfg = load_app_config(p)
    cfg.theme_mode.value = "Dark"
    cfg.log_dir.value = "D:/logs"
    cfg.save()

    cfg2 = load_app_config(p)
    assert cfg2.theme_mode.value == "Dark"
    assert cfg2.log_dir.value == "D:/logs"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_app_config.py -v`
Expected: FAIL(ModuleNotFoundError: ui.app_config)

- [ ] **Step 3: 实现**

Create `ui/app_config.py`:

```python
"""GUI 自身设置(主题/Mica/日志目录)持久化。qconfig 存 json。"""
from __future__ import annotations

import os

from qfluentwidgets import (BoolValidator, ConfigItem, OptionsConfigItem,
                            OptionsValidator, QConfig, Theme, qconfig,
                            setTheme)

from backend import paths


class AppConfig(QConfig):
    theme_mode = OptionsConfigItem(
        "MainWindow", "ThemeMode", "Auto",
        OptionsValidator(["Light", "Dark", "Auto"]))
    mica_enabled = ConfigItem(
        "MainWindow", "MicaEnabled", True, BoolValidator())
    log_dir = ConfigItem("Paths", "LogDir", paths.RELINK_LOG_DIR)


def _default_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "HapticImproveManager")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "gui_config.json")


def load_app_config(path: str | None = None) -> AppConfig:
    cfg = AppConfig()
    qconfig.load(path or _default_path(), cfg)
    return cfg


def apply_theme(cfg: AppConfig) -> None:
    setTheme(Theme[cfg.theme_mode.value.upper()])  # "Auto" -> Theme.AUTO


APP_CFG = load_app_config()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_app_config.py tests/test_config.py -v`
Expected: 全绿

- [ ] **Step 5: Commit**

```powershell
git add ui/app_config.py tests/test_app_config.py
git commit -m "feat(ui): AppConfig — 主题/Mica/日志目录持久化(QConfig)"
```

---

### Task 3: ui/config_model.py — 表单 ↔ TOML 纯函数 + 模式文案

**Files:**
- Create: `ui/config_model.py`
- Test: `tests/test_config_model.py`

**Interfaces:**
- Consumes: `backend.config`(`MODES`, `default_config`, `validate`),tomlkit
- Produces:
  - `@dataclass FormState`: 字段 `mode: str, period_hus: int, buf_normal: int, buf_ring: int, raw: bool, force_period: bool, log_level: str`
  - `load_form(doc: TOMLDocument) -> FormState`
  - `apply_form(doc: TOMLDocument, state: FormState) -> None`(原位改值,保留注释;点分键子表键用字符串)
  - `frames_to_ms(frames: int, rate: int = 48000) -> float`
  - `hus_to_ms(hus: int) -> float`(`hus / 10`)
  - `MODE_INFO: dict[str, dict[str, str]]`——每个模式 `{"title": 中文名, "brief": 一句话, "detail": 详细说明}`,文案见 Step 3

- [ ] **Step 1: 写失败测试**

Create `tests/test_config_model.py`:

```python
import tomlkit

from backend.config import default_config, validate
from ui.config_model import (FormState, MODE_INFO, apply_form, frames_to_ms,
                             hus_to_ms, load_form)


def test_load_defaults():
    st = load_form(default_config())
    assert st == FormState(mode="Normal", period_hus=100, buf_normal=960,
                           buf_ring=4320, raw=True, force_period=True,
                           log_level="Error")


def test_apply_round_trip_preserves_comments():
    doc = default_config()
    st = load_form(doc)
    st.mode = "Ringbuf"
    st.buf_ring = 2048
    apply_form(doc, st)
    text = tomlkit.dumps(doc)
    assert 'mode = "Ringbuf"' in text
    assert "ring_buffer_len.48000 = 2048" in text
    assert "# Ringbuf 用" in text  # 注释保留
    assert validate(doc) == []


def test_apply_dotted_key_str():
    """点分键子表键必须保持字符串, 不得变成 int(会 TypeError)或丢失。"""
    doc = default_config()
    st = load_form(doc)
    st.buf_normal = 256
    apply_form(doc, st)
    tbl = doc["playback"]["target_buffer_len"]
    assert list(tbl.keys()) == ["48000"]
    assert tbl["48000"] == 256


def test_apply_missing_buffer_subtable():
    """配置缺 target_buffer_len 子表时 apply 要新建且不炸。"""
    doc = default_config()
    del doc["playback"]["target_buffer_len"]
    st = load_form(doc)
    assert st.buf_normal == 960  # 缺省回退
    st.buf_normal = 512
    apply_form(doc, st)
    assert doc["playback"]["target_buffer_len"]["48000"] == 512


def test_conversions():
    assert frames_to_ms(960) == 20.0
    assert frames_to_ms(4320) == 90.0
    assert hus_to_ms(100) == 10.0
    assert hus_to_ms(0) == 0.0


def test_mode_info_covers_all_modes():
    from backend.config import MODES
    for m in MODES:
        assert MODE_INFO[m]["title"]
        assert MODE_INFO[m]["brief"]
        assert MODE_INFO[m]["detail"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_config_model.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现**

Create `ui/config_model.py`:

```python
"""表单状态 ↔ redirect_config.toml doc 的纯函数映射(无 Qt, 可单测)。

tomlkit 点分键陷阱: target_buffer_len.48000 解析后子表键是字符串 "48000";
赋值必须原位改值且用字符串键, int 键 TypeError, 整体替换丢注释。
"""
from __future__ import annotations

from dataclasses import dataclass

import tomlkit
from tomlkit import TOMLDocument

# 模式文案 — spec「配置卡」一节, 改动需同步 spec
MODE_INFO: dict[str, dict[str, str]] = {
    "Normal": {
        "title": "普通模式",
        "brief": "延迟最低, 绝大多数游戏直接用(剑星、绝区零已验证)",
        "detail": "游戏直接面对真实的小缓冲区。破音就把下面的缓冲调大。"
                  "默认先试这个。",
    },
    "Ringbuf": {
        "title": "虚拟缓冲",
        "brief": "给“爆发式写音频”的游戏兜底(《黑魂2》必须用)",
        "detail": "游戏以为自己面前有一条很长的缓冲通道, 可以一口气猛写一大批音频;"
                  "注入层在幕后接住, 再按推送节奏匀速喂给手柄。\n"
                  "什么时候用它: 普通模式下声音破音、卡顿, 或游戏写入节奏本身不均匀。\n"
                  "代价: 多一层缓冲, 延迟略高于普通模式。\n"
                  "已知问题: UE5 游戏爆发写入太大会撑爆虚拟缓冲、日志刷屏;"
                  "绝区零会丢失手柄扬声器声道——这两款不要用。\n"
                  "怎么调: 虚拟缓冲帧数 ÷ 48 = 毫秒, 默认 4320 帧 ≈ 90ms。",
    },
    "Compat": {
        "title": "兼容模式",
        "brief": "上面两种都出问题再试",
        "detail": "兼容性优先的折中模式, 延迟不如普通模式。",
    },
    "Bypass": {
        "title": "不干预",
        "brief": "跳过音频处理, 保持原生延迟",
        "detail": "不修改任何音频行为, 用来对比排障。",
    },
}


@dataclass
class FormState:
    mode: str = "Normal"
    period_hus: int = 100
    buf_normal: int = 960
    buf_ring: int = 4320
    raw: bool = True
    force_period: bool = True
    log_level: str = "Error"


def frames_to_ms(frames: int, rate: int = 48000) -> float:
    return frames * 1000 / rate


def hus_to_ms(hus: int) -> float:
    return hus / 10


def _first_int(sub: dict, default: int) -> int:
    """点分键子表(如 target_buffer_len.48000)取第一个值, 缺失回退默认。"""
    return int(next(iter(sub.values()), default))


def load_form(doc: TOMLDocument) -> FormState:
    pb = doc.get("playback", {})
    return FormState(
        mode=pb.get("mode", "Normal"),
        period_hus=int(pb.get("target_period_hus", 100)),
        buf_normal=_first_int(pb.get("target_buffer_len", {}), 960),
        buf_ring=_first_int(pb.get("ring_buffer_len", {}), 4320),
        raw=bool(pb.get("raw", True)),
        force_period=bool(pb.get("force_period", True)),
        log_level=doc.get("log_level", "Error"),
    )


def _set_buf(pb, field: str, value: int) -> None:
    """原位改帧数; 子表不存在则新建。键必须字符串(tomlkit 点分键)。"""
    tbl = pb.get(field)
    if tbl is None:
        tbl = tomlkit.table()
        pb[field] = tbl
    key = next(iter(tbl.keys()), "48000")
    tbl[str(key)] = value


def apply_form(doc: TOMLDocument, state: FormState) -> None:
    pb = doc["playback"]
    pb["mode"] = state.mode
    pb["target_period_hus"] = state.period_hus
    _set_buf(pb, "target_buffer_len", state.buf_normal)
    _set_buf(pb, "ring_buffer_len", state.buf_ring)
    pb["raw"] = state.raw
    pb["force_period"] = state.force_period
    doc["log_level"] = state.log_level
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/ -v`
Expected: 全绿

- [ ] **Step 5: Commit**

```powershell
git add ui/config_model.py tests/test_config_model.py
git commit -m "feat(ui): config_model — 表单↔TOML 纯函数映射 + 模式通俗文案"
```

---

### Task 4: 主窗口框架 + 设置页(主题/Mica/日志目录)

**Files:**
- Create: `ui/main_window.py`(覆盖旧文件,旧代码删除)
- Create: `ui/settings_page.py`
- Create: `ui/log_dir_sync.py`(批量同步逻辑,纯函数可单测)
- Test: `tests/test_log_dir_sync.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: Task 2 `APP_CFG/apply_theme/AppConfig`;Task 1 `config.set_log_dir`;`backend.registry.load_or_migrate`
- Produces:
  - `MainWindow(FluentWindow)`:`__init__(self, cfg: AppConfig = APP_CFG)`;方法 `apply_mica(self)`;导航项 key `"games"`, `"diagnostics"`, `"settings"`
  - `SettingsPage(QWidget)`:`__init__(self, cfg: AppConfig, parent=None)`;信号 `log_dir_changed = Signal(str)`(用户确认批量同步成功后才发);控件名 `theme_box`(ComboBox,项 `["浅色", "深色", "跟随系统"]`)、`mica_switch`(SwitchButton)、`log_dir_edit`(LineEdit 只读)、`btn_change_dir`(PushButton)、`btn_open_dir`(PushButton)
  - `sync_log_dir(new_dir: str, games: dict[str, GameEntry]) -> tuple[int, list[str]]`——返回(成功数, 失败游戏名列表);逐游戏 `set_log_dir`,异常跳过
  - smoke: `create_main_window() -> MainWindow`(供测试与 app.py 共用)

- [ ] **Step 1: 写 log_dir_sync 失败测试**

Create `tests/test_log_dir_sync.py`:

```python
import os

from backend.config import default_config, save_config
from backend.registry import GameEntry
from ui.log_dir_sync import sync_log_dir


def _mk_game(tmp_path, name, with_config=True):
    d = tmp_path / name
    d.mkdir()
    exe = d / f"{name}.exe"
    exe.write_text("", encoding="utf-8")
    if with_config:
        save_config(str(d), default_config())
    return GameEntry(name=name, exe=str(exe))


def test_sync_all_ok(tmp_path):
    games = {n: _mk_game(tmp_path, n) for n in ("a", "b")}
    ok, failed = sync_log_dir("D:/logs", games)
    assert (ok, failed) == (2, [])
    from backend.config import load_config
    assert load_config(games["a"].game_dir)["log_path"] == "D:/logs"


def test_sync_skips_broken(tmp_path):
    good = _mk_game(tmp_path, "good")
    broken = _mk_game(tmp_path, "broken", with_config=False)
    # 损坏的 toml
    with open(broken.config_path, "w", encoding="utf-8") as f:
        f.write("log_path = [not valid")
    ok, failed = sync_log_dir("D:/logs", {"good": good, "broken": broken})
    assert ok == 1
    assert failed == ["broken"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_log_dir_sync.py -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现 log_dir_sync**

Create `ui/log_dir_sync.py`:

```python
"""批量把已注册游戏的 redirect_config.toml 的 log_path 改为新目录。

单个游戏失败(配置缺失/损坏/写不进)不中断整批, 记入失败列表。
"""
from __future__ import annotations

from backend import config
from backend.registry import GameEntry


def sync_log_dir(new_dir: str, games: dict[str, GameEntry]
                 ) -> tuple[int, list[str]]:
    ok, failed = 0, []
    for name, entry in games.items():
        try:
            config.set_log_dir(entry.game_dir, new_dir)
            ok += 1
        except Exception:
            failed.append(name)
    return ok, failed
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_log_dir_sync.py -v`
Expected: PASS 2/2

- [ ] **Step 5: 实现设置页**

Create `ui/settings_page.py`:

```python
"""设置页: 主题 / Mica / 日志目录(可改 + 一键打开 + 批量同步)。"""
from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, ComboBox, LineEdit,
                            MessageBox, PushButton, StrongBodyLabel,
                            SwitchButton, TitleLabel, InfoBar,
                            InfoBarPosition)

from backend import registry
from ui.app_config import AppConfig, apply_theme
from ui.log_dir_sync import sync_log_dir

_THEME_LABELS = ["浅色", "深色", "跟随系统"]
_THEME_VALUES = ["Light", "Dark", "Auto"]


class SettingsPage(QWidget):
    log_dir_changed = Signal(str)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.setObjectName("settings")
        self.cfg = cfg

        title = TitleLabel("设置", self)

        # 主题
        self.theme_box = ComboBox(self)
        self.theme_box.addItems(_THEME_LABELS)
        self.theme_box.setCurrentIndex(
            _THEME_VALUES.index(cfg.theme_mode.value))
        self.theme_box.currentIndexChanged.connect(self._on_theme)

        # Mica
        self.mica_switch = SwitchButton(self)
        self.mica_switch.setChecked(cfg.mica_enabled.value)
        self.mica_switch.setOnText("开")
        self.mica_switch.setOffText("关")
        self.mica_switch.checkedChanged.connect(self._on_mica)

        # 日志目录
        self.log_dir_edit = LineEdit(self)
        self.log_dir_edit.setReadOnly(True)
        self.log_dir_edit.setText(cfg.log_dir.value)
        self.btn_change_dir = PushButton("更改…", self)
        self.btn_change_dir.clicked.connect(self._change_dir)
        self.btn_open_dir = PushButton("在资源管理器中打开", self)
        self.btn_open_dir.clicked.connect(self._open_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.log_dir_edit, 1)
        dir_row.addWidget(self.btn_change_dir)
        dir_row.addWidget(self.btn_open_dir)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(12)
        lay.addWidget(title)
        lay.addWidget(StrongBodyLabel("主题", self))
        lay.addWidget(self.theme_box)
        lay.addWidget(StrongBodyLabel("云母背景(Win11)", self))
        lay.addWidget(self.mica_switch)
        lay.addWidget(StrongBodyLabel("日志目录", self))
        lay.addWidget(CaptionLabel(
            "wasapi_relink.log 的存放位置。更改后可同步到所有已注册游戏的配置。",
            self))
        lay.addLayout(dir_row)
        lay.addStretch(1)

    def _on_theme(self, idx: int):
        self.cfg.theme_mode.value = _THEME_VALUES[idx]
        self.cfg.save()
        apply_theme(self.cfg)

    def _on_mica(self, on: bool):
        self.cfg.mica_enabled.value = on
        self.cfg.save()
        win = self.window()
        if hasattr(win, "apply_mica"):
            win.apply_mica()

    def _change_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择日志目录",
                                             self.cfg.log_dir.value)
        if not d:
            return
        games = registry.load_or_migrate()
        box = MessageBox("同步日志目录",
                         f"新目录: {d}\n\n是否同步更新所有已注册游戏"
                         f"({len(games)} 个)的 redirect_config.toml?\n"
                         "选「否」则只影响以后新添加的游戏。", self)
        box.yesButton.setText("同步所有游戏")
        box.cancelButton.setText("仅以后生效")
        self.cfg.log_dir.value = d
        self.cfg.save()
        self.log_dir_edit.setText(d)
        if box.exec():
            ok, failed = sync_log_dir(d, games)
            if failed:
                InfoBar.warning("部分同步失败",
                                f"已同步 {ok} 个; 失败: {', '.join(failed)}"
                                "(配置缺失或损坏, 请到对应游戏详情修复)",
                                parent=self, position=InfoBarPosition.TOP,
                                duration=6000)
            else:
                InfoBar.success("已同步", f"已更新 {ok} 个游戏的配置",
                                parent=self, position=InfoBarPosition.TOP,
                                duration=3000)
            self.log_dir_changed.emit(d)

    def _open_dir(self):
        d = self.cfg.log_dir.value
        os.makedirs(d, exist_ok=True)
        subprocess.Popen(["explorer", d])
```

- [ ] **Step 6: 实现主窗口 + smoke 测试**

Create `ui/main_window.py`(完全替换旧文件):

```python
"""主窗口: FluentWindow + 导航(游戏/诊断/设置) + 主题与 Mica。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (FluentIcon, FluentWindow, NavigationItemPosition)

from ui.app_config import APP_CFG, AppConfig, apply_theme
from ui.settings_page import SettingsPage


class MainWindow(FluentWindow):
    def __init__(self, cfg: AppConfig = APP_CFG):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("Haptic 低延迟管理器")
        self.resize(1100, 720)

        # 占位页 — Task 5/8 替换为真实页面
        self.games_page = _placeholder("games")
        self.diagnostics_page = _placeholder("diagnostics")
        self.settings_page = SettingsPage(cfg, self)

        self.addSubInterface(self.games_page, FluentIcon.GAME, "游戏")
        self.addSubInterface(self.diagnostics_page, FluentIcon.DIAGNOSIS,
                             "诊断")
        self.addSubInterface(self.settings_page, FluentIcon.SETTING, "设置",
                             position=NavigationItemPosition.BOTTOM)

        apply_theme(cfg)
        self.apply_mica()

    def apply_mica(self):
        self.setMicaEffectEnabled(bool(self.cfg.mica_enabled.value))


def _placeholder(name: str) -> QWidget:
    w = QWidget()
    w.setObjectName(name)
    return w


def create_main_window() -> MainWindow:
    return MainWindow()
```

Create `tests/test_smoke.py`:

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_instantiates(qapp, tmp_path):
    from ui.app_config import load_app_config
    from ui.main_window import MainWindow
    cfg = load_app_config(str(tmp_path / "gui.json"))
    win = MainWindow(cfg)
    assert win.windowTitle() == "Haptic 低延迟管理器"
    assert win.settings_page.theme_box.count() == 3
    win.close()
    win.deleteLater()
```

- [ ] **Step 7: 跑测试**

Run: `python -m pytest tests/ -v`
Expected: 全绿

- [ ] **Step 8: Commit**

```powershell
git add ui/main_window.py ui/settings_page.py ui/log_dir_sync.py tests/test_log_dir_sync.py tests/test_smoke.py
git commit -m "feat(ui): FluentWindow 主框架 + 设置页(主题/Mica/日志目录批量同步)"
```

---

### Task 5: 游戏中心主页 + 详情状态卡

**Files:**
- Create: `ui/games_page.py`(完全替换旧文件)
- Create: `ui/game_detail.py`
- Test: `tests/test_smoke.py`(追加)

**Interfaces:**
- Consumes: `backend.registry.load_or_migrate/remove_game`,`backend.ifeo.query_ifeo/IfeoState`,`backend.launcher.ProcessRunner/launch_game/set_ifeo`,`backend.config`
- Produces:
  - `GamesPage(QWidget)`:objectName `"games"`;信号 `log_line = Signal(str)`;方法 `refresh(self)`;控件 `search`(SearchLineEdit)、`game_list`(ListWidget)、`btn_add`(PrimaryPushButton)、`stack`(QStackedWidget,第 0 页空状态,第 1 页详情)、`detail`(GameDetailPage 或 None)
  - `GameDetailPage(QWidget)`:信号 `config_changed = Signal(str)`(保存后发游戏名,供诊断页等刷新);方法 `set_game(self, entry: GameEntry)`、`refresh_status(self)`;控件 `name_label`、`path_label`(CaptionLabel)、`btn_launch`(PrimaryPushButton)、`btn_remove`(PushButton)、`status_badge`(BodyLabel,文字如 "● 就绪")、`ifeo_switch`(SwitchButton)、`anticheat_label`(CaptionLabel)、`config_card`(占位 QWidget,Task 6 替换)
  - IFEO 轮询:`GameDetailPage` 持有**单个** `self._ifeo_timer = QTimer(self)`,每次切换前 `stop()`

- [ ] **Step 1: 写 smoke 测试(追加到 tests/test_smoke.py)**

```python
def test_games_page_instantiates(qapp, tmp_path, monkeypatch):
    from backend import paths
    # 造一个临时 games.yaml, 避免读真实注册表
    games_yaml = tmp_path / "games.yaml"
    games_yaml.write_text("games: {}\n", encoding="utf-8")
    monkeypatch.setattr(paths, "GAMES_YAML", str(games_yaml))

    from ui.games_page import GamesPage
    page = GamesPage()
    assert page.game_list.count() == 0
    assert page.stack.currentIndex() == 0  # 空状态
    page.deleteLater()
```

注意:`registry.load_or_migrate` 的默认参数在定义时绑定(`path: str = paths.GAMES_YAML`),monkeypatch paths.GAMES_YAML **不会**生效。实现 `GamesPage.refresh` 时必须显式传参:
`registry.load_or_migrate(str(paths.GAMES_YAML))` — 即调用处显式读 `paths.GAMES_YAML`,使 patch 生效。`GameDetailPage` 同理(所有 registry 调用显式传 path)。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL(ModuleNotFoundError / ImportError)

- [ ] **Step 3: 实现 game_detail.py**

Create `ui/game_detail.py`:

```python
"""游戏详情页: 头部(启动/移除) + 状态卡(IFEO) + 配置卡容器。

所有 registry 调用显式传 paths.GAMES_YAML — 默认参数在定义时绑定,
显式传参才能让测试 monkeypatch 生效。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, FluentIcon,
                            InfoBar, InfoBarPosition, MessageBox,
                            PrimaryPushButton, PushButton, StrongBodyLabel,
                            SwitchButton, TitleLabel, themeColor)

from backend import ifeo, launcher, paths, registry
from backend.ifeo import IfeoState


class GameDetailPage(QWidget):
    config_changed = Signal(str)

    def __init__(self, runner: launcher.ProcessRunner, parent=None):
        super().__init__(parent)
        self.runner = runner
        self.entry: registry.GameEntry | None = None
        self._ifeo_timer = QTimer(self)
        self._ifeo_timer.setInterval(1000)
        self._ifeo_timer.timeout.connect(self._poll_ifeo)
        self._poll_count = 0

        # 头部
        self.name_label = TitleLabel("", self)
        self.path_label = CaptionLabel("", self)
        self.btn_launch = PrimaryPushButton(FluentIcon.PLAY, "启动游戏", self)
        self.btn_launch.clicked.connect(self._launch)
        self.btn_remove = PushButton(FluentIcon.DELETE, "移除", self)
        self.btn_remove.clicked.connect(self._remove)
        head_btns = QHBoxLayout()
        head_btns.addStretch(1)
        head_btns.addWidget(self.btn_launch)
        head_btns.addWidget(self.btn_remove)
        head = QVBoxLayout()
        head.addWidget(self.name_label)
        head.addWidget(self.path_label)
        head.addLayout(head_btns)

        # 状态卡
        self.status_card = CardWidget(self)
        sc = QVBoxLayout(self.status_card)
        self.status_badge = BodyLabel("", self)
        self.anticheat_label = CaptionLabel(
            "⚠ 检测到反作弊特征, 注入有账号封禁风险", self)
        self.ifeo_switch = SwitchButton(self)
        self.ifeo_switch.setOnText("开")
        self.ifeo_switch.setOffText("关")
        self.ifeo_switch.checkedChanged.connect(self._on_ifeo_toggled)
        ifeo_row = QHBoxLayout()
        ifeo_row.addWidget(StrongBodyLabel("IFEO 自动注入", self))
        ifeo_row.addStretch(1)
        ifeo_row.addWidget(self.ifeo_switch)
        sc.addWidget(StrongBodyLabel("状态", self))
        sc.addWidget(self.status_badge)
        sc.addWidget(self.anticheat_label)
        sc.addLayout(ifeo_row)
        sc.addWidget(CaptionLabel(
            "开启后从 Steam/启动器正常启动游戏即自动注入(需 UAC 提权)。",
            self))

        # 配置卡容器 — Task 6 用真实 ConfigCard 替换
        self.config_card = QWidget(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(12)
        lay.addLayout(head)
        lay.addWidget(self.status_card)
        lay.addWidget(self.config_card)
        lay.addStretch(1)

    def set_game(self, entry: registry.GameEntry):
        self._ifeo_timer.stop()  # 换游戏时停掉旧轮询
        self.entry = entry
        self.name_label.setText(entry.name)
        self.path_label.setText(entry.exe)
        self.path_label.setToolTip(entry.exe)
        self.anticheat_label.setVisible(entry.anticheat)
        self.refresh_status()

    def refresh_status(self):
        e = self.entry
        if e is None:
            return
        state = ifeo.query_ifeo(os.path.basename(e.exe))
        if not e.exe_exists:
            text, tip = "● exe 丢失", "找不到游戏可执行文件, 请检查路径"
        elif e.config_exists and state == IfeoState.ON_OURS:
            text, tip = "● 就绪", "配置与 IFEO 均已就位"
        else:
            text, tip = "● 未完成", "配置或 IFEO 未就位"
        if state == IfeoState.ON_OTHER:
            text += "(IFEO 被其他调试器占用!)"
        self.status_badge.setText(text)
        self.status_badge.setToolTip(tip)
        self.ifeo_switch.blockSignals(True)
        self.ifeo_switch.setChecked(state == IfeoState.ON_OURS)
        self.ifeo_switch.blockSignals(False)
        self.btn_launch.setEnabled(e.exe_exists)

    def _on_ifeo_toggled(self, checked: bool):
        if self.entry is None:
            return
        launcher.set_ifeo(self.runner, self.entry.name, checked)
        self._poll_count = 0
        self._ifeo_timer.stop()  # 单实例: 重复切换先停旧轮询
        self._ifeo_timer.start()

    def _poll_ifeo(self):
        self._poll_count += 1
        state = ifeo.query_ifeo(os.path.basename(self.entry.exe))
        want = IfeoState.ON_OURS if self.ifeo_switch.isChecked() \
            else IfeoState.OFF
        if state == want or self._poll_count >= 10:
            self._ifeo_timer.stop()
            if state != want:
                InfoBar.warning("IFEO", "提权被取消或操作失败, 状态未变更",
                                parent=self, position=InfoBarPosition.TOP,
                                duration=4000)
            self.refresh_status()

    def _launch(self):
        if self.entry is not None:
            launcher.launch_game(self.runner, self.entry.name)

    def _remove(self):
        if self.entry is None:
            return
        box = MessageBox("移除游戏",
                         f"从列表移除 {self.entry.name}?\n"
                         "(不动游戏文件和 IFEO 设置)", self)
        if box.exec():
            registry.remove_game(self.entry.name, str(paths.GAMES_YAML))
            self.entry = None
            self.config_changed.emit("")  # 空串 = 当前游戏被移除, 请刷新
```

- [ ] **Step 4: 实现 games_page.py**

Create `ui/games_page.py`(完全替换旧文件):

```python
"""游戏中心主页: 左列表(搜索过滤) + 右详情(选中即上下文)。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QListWidgetItem, QStackedWidget,
                               QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, FluentIcon, ListWidget,
                            PrimaryPushButton, SearchLineEdit,
                            StrongBodyLabel)

from backend import launcher, paths, registry
from ui.game_detail import GameDetailPage


class GamesPage(QWidget):
    log_line = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("games")
        self.runner = launcher.ProcessRunner(self)
        self.runner.line.connect(self.log_line)

        self.search = SearchLineEdit(self)
        self.search.setPlaceholderText("搜索游戏…")
        self.search.textChanged.connect(self._filter)
        self.btn_add = PrimaryPushButton(FluentIcon.ADD, "添加游戏", self)
        self.btn_add.clicked.connect(self._add_game)
        self.game_list = ListWidget(self)
        self.game_list.currentRowChanged.connect(self._on_select)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.addWidget(self.search)
        left.addWidget(self.game_list, 1)
        left.addWidget(self.btn_add)
        left_host = QWidget(self)
        left_host.setLayout(left)
        left_host.setFixedWidth(220)

        # 空状态
        empty = QWidget(self)
        el = QVBoxLayout(empty)
        el.addStretch(1)
        t = StrongBodyLabel("还没有游戏", empty)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c = CaptionLabel("点击左下角「添加游戏」, 四步完成接入", empty)
        c.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(t)
        el.addWidget(c)
        el.addStretch(1)

        self.detail = GameDetailPage(self.runner, self)
        self.detail.config_changed.connect(self._on_detail_changed)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(empty)    # index 0
        self.stack.addWidget(self.detail)  # index 1

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(left_host)
        lay.addWidget(self.stack, 1)

        self._games: dict[str, registry.GameEntry] = {}
        self.refresh()

    def refresh(self):
        self._games = registry.load_or_migrate(str(paths.GAMES_YAML))
        self.game_list.blockSignals(True)
        self.game_list.clear()
        for name, entry in self._games.items():
            mark = "● " if (entry.exe_exists and entry.config_exists) \
                else "○ "
            QListWidgetItem(mark + name, self.game_list)
        self.game_list.blockSignals(False)
        if self._games:
            self.game_list.setCurrentRow(0)
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)

    def _filter(self, text: str):
        for i in range(self.game_list.count()):
            item = self.game_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_select(self, row: int):
        if row < 0:
            return
        name = self.game_list.item(row).text()[2:]  # 去掉 "● " 前缀
        entry = self._games.get(name)
        if entry:
            self.stack.setCurrentIndex(1)
            self.detail.set_game(entry)

    def _on_detail_changed(self, _name: str):
        self.refresh()

    def _add_game(self):
        # Task 7 实现 AddGameDialog 后接线; 当前为占位
        from qfluentwidgets import InfoBar, InfoBarPosition
        InfoBar.info("添加游戏", "向导将在后续任务中实现",
                     parent=self, position=InfoBarPosition.TOP, duration=2000)
```

- [ ] **Step 5: 跑测试**

Run: `python -m pytest tests/ -v`
Expected: 全绿

- [ ] **Step 6: 接线主窗口**

修改 `ui/main_window.py`:删掉 `_placeholder("games")` 与占位逻辑,改为

```python
from ui.games_page import GamesPage
...
self.games_page = GamesPage(self)
```

`_placeholder` 只保留给 diagnostics 用。跑 `python -m pytest tests/test_smoke.py -v` 确认全绿。

- [ ] **Step 7: Commit**

```powershell
git add ui/games_page.py ui/game_detail.py ui/main_window.py tests/test_smoke.py
git commit -m "feat(ui): 游戏中心主页 + 详情状态卡(IFEO 开关/启动/移除)"
```

---

### Task 6: 配置卡(模式卡片 + 通俗解释 + 脏状态)

**Files:**
- Create: `ui/config_card.py`
- Modify: `ui/game_detail.py`(config_card 占位换真实件)
- Test: `tests/test_smoke.py`(追加配置卡 smoke)

**Interfaces:**
- Consumes: Task 3 `config_model`(FormState/load_form/apply_form/MODE_INFO/frames_to_ms/hus_to_ms),`backend.config`(load_config/save_config/validate/default_config),`backend.launcher.is_game_running`,Task 2 `APP_CFG.log_dir`
- Produces:
  - `ConfigCard(CardWidget)`:`set_game(self, entry: GameEntry)`;信号 `saved = Signal(str)`(保存成功发游戏名);脏状态:任一控件修改 → `self._dirty=True` 且 `btn_save.setEnabled(True)`;保存/加载后 `_dirty=False`
  - 控件:`mode_cards: dict[str, CardWidget]`(四张,选中态用边框色 themeColor)、`period_slider`(Slider 0–1000)、`period_label`、`buf_normal`(SpinBox 1–65536)、`buf_normal_ms`(CaptionLabel 实时换算)、`buf_ring`/`buf_ring_ms`、`raw_switch`、`force_switch`(SwitchButton)、`log_box`(ComboBox Error/Info)、`btn_save`(PrimaryPushButton,初始 disabled)、`btn_default`(PushButton)、`error_view`(PlainTextEdit 只读,解析失败时显示)
  - `is_dirty(self) -> bool`(供详情页切换游戏前询问)

- [ ] **Step 1: 写 smoke 测试(追加 tests/test_smoke.py)**

```python
def test_config_card_dirty_flow(qapp, tmp_path):
    from backend.config import default_config, save_config, load_config
    from backend.registry import GameEntry
    from ui.config_card import ConfigCard

    d = tmp_path / "g"
    d.mkdir()
    exe = d / "g.exe"
    exe.write_text("", encoding="utf-8")
    save_config(str(d), default_config())
    entry = GameEntry(name="g", exe=str(exe))

    card = ConfigCard()
    card.set_game(entry)
    assert not card.is_dirty()
    assert not card.btn_save.isEnabled()

    card.buf_normal.setValue(512)  # 模拟用户修改
    assert card.is_dirty()
    assert card.btn_save.isEnabled()

    card.btn_save.click()
    assert not card.is_dirty()
    assert load_config(str(d))["playback"]["target_buffer_len"]["48000"] == 512
    card.deleteLater()
```

注意:测试里 `btn_save.click()` 触发保存,保存成功会弹 InfoBar——InfoBar 在 offscreen 下可正常构造,无需处理。`is_game_running` 走 tasklist,`g.exe` 不存在返回 False,不会误提示。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_smoke.py::test_config_card_dirty_flow -v`
Expected: FAIL(ModuleNotFoundError: ui.config_card)

- [ ] **Step 3: 实现 config_card.py**

Create `ui/config_card.py`:

```python
"""注入配置卡: 模式四选一卡片 + 白话解释 + 缓冲实时毫秒换算 + 脏状态。

文案集中在 config_model.MODE_INFO; 本文件只做呈现与交互。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QGridLayout, QHBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, ComboBox,
                            InfoBar, InfoBarPosition, MessageBox,
                            PlainTextEdit, PrimaryPushButton, PushButton,
                            Slider, SpinBox, StrongBodyLabel, SwitchButton,
                            themeColor)

from backend import config, launcher
from backend.registry import GameEntry
from ui.app_config import APP_CFG
from ui.config_model import (MODE_INFO, FormState, apply_form, frames_to_ms,
                             hus_to_ms, load_form)


class _ModeCard(CardWidget):
    """单个模式选择卡: 标题 + 一句话简介; 点击选中。"""
    clicked = Signal(str)

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        info = MODE_INFO[mode]
        lay = QVBoxLayout(self)
        lay.addWidget(StrongBodyLabel(info["title"], self))
        brief = CaptionLabel(info["brief"], self)
        brief.setWordWrap(True)
        lay.addWidget(brief)

    def mouseReleaseEvent(self, e):
        self.clicked.emit(self.mode)
        super().mouseReleaseEvent(e)

    def set_selected(self, on: bool):
        # 用主题色描边表达选中, 不写死颜色(深色适配)
        c = themeColor().name()
        self.setStyleSheet(
            f"_ModeCard {{ border: 2px solid {c}; }}" if on else "")


class ConfigCard(CardWidget):
    saved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entry: GameEntry | None = None
        self.doc = None
        self._dirty = False
        self._loading = False

        lay = QVBoxLayout(self)
        lay.addWidget(StrongBodyLabel("注入配置", self))
        lay.addWidget(CaptionLabel(
            "修改后点「保存」生效; 游戏运行中保存需重启游戏。", self))

        # 模式四卡
        self.mode_cards: dict[str, _ModeCard] = {}
        grid = QGridLayout()
        from backend.config import MODES
        for i, m in enumerate(MODES):
            card = _ModeCard(m, self)
            card.clicked.connect(self._on_mode_card)
            self.mode_cards[m] = card
            grid.addWidget(card, i // 2, i % 2)
        lay.addLayout(grid)
        self.mode_detail = CaptionLabel("", self)
        self.mode_detail.setWordWrap(True)
        lay.addWidget(self.mode_detail)

        # 表单
        self.period_slider = Slider(Qt.Orientation.Horizontal, self)
        self.period_slider.setRange(0, 1000)
        self.period_label = BodyLabel("", self)
        self.period_slider.valueChanged.connect(self._on_period)
        period_row = QHBoxLayout()
        period_row.addWidget(self.period_slider, 1)
        period_row.addWidget(self.period_label)

        self.buf_normal = SpinBox(self)
        self.buf_normal.setRange(1, 65536)
        self.buf_normal_ms = CaptionLabel("", self)
        self.buf_normal.valueChanged.connect(self._on_buf_normal)
        bn_row = QHBoxLayout()
        bn_row.addWidget(self.buf_normal, 1)
        bn_row.addWidget(self.buf_normal_ms)

        self.buf_ring = SpinBox(self)
        self.buf_ring.setRange(1, 65536)
        self.buf_ring_ms = CaptionLabel("", self)
        self.buf_ring.valueChanged.connect(self._on_buf_ring)
        br_row = QHBoxLayout()
        br_row.addWidget(self.buf_ring, 1)
        br_row.addWidget(self.buf_ring_ms)

        self.raw_switch = SwitchButton(self)
        self.raw_switch.setOnText("开")
        self.raw_switch.setOffText("关")
        self.raw_switch.checkedChanged.connect(self._mark_dirty)
        self.force_switch = SwitchButton(self)
        self.force_switch.setOnText("开")
        self.force_switch.setOffText("关")
        self.force_switch.checkedChanged.connect(self._mark_dirty)

        self.log_box = ComboBox(self)
        self.log_box.addItems(["Error", "Info"])
        self.log_box.currentTextChanged.connect(self._on_log_level)

        form = QFormLayout()
        form.addRow("推送节奏", period_row)
        form.addRow("", CaptionLabel(
            "手柄多久收到一次音频。越小越跟手, 太小会破音; 最左 = 不干预(原生)。",
            self))
        form.addRow("缓冲大小", bn_row)
        form.addRow("", CaptionLabel(
            "普通模式用: 游戏能囤多少音频。小了破音, 大了拖延迟。", self))
        form.addRow("虚拟缓冲", br_row)
        form.addRow("", CaptionLabel(
            "虚拟缓冲模式用: 幕后接住游戏爆发写入的通道长度。", self))
        form.addRow("原始模式(raw)", self.raw_switch)
        form.addRow("", CaptionLabel("保持默认(开)即可, 出问题再动。", self))
        form.addRow("强制周期", self.force_switch)
        form.addRow("", CaptionLabel("强制按推送节奏发送。保持默认(开)即可。",
                                     self))
        form.addRow("日志级别", self.log_box)
        lay.addLayout(form)

        # 按钮
        self.btn_save = PrimaryPushButton("保存", self)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save)
        self.btn_default = PushButton("恢复默认", self)
        self.btn_default.clicked.connect(self._reset_default)
        btns = QHBoxLayout()
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_default)
        btns.addStretch(1)
        lay.addLayout(btns)

        self.error_view = PlainTextEdit(self)
        self.error_view.setReadOnly(True)
        self.error_view.hide()
        lay.addWidget(self.error_view)

    # ---- 数据装载 ----

    def set_game(self, entry: GameEntry):
        self.entry = entry
        self.error_view.hide()
        try:
            self.doc = config.load_config(entry.game_dir)
        except FileNotFoundError:
            self.doc = None
            box = MessageBox("无配置",
                             f"{entry.name} 还没有 redirect_config.toml,\n"
                             "生成默认配置?", self)
            if box.exec():
                self.doc = config.default_config(APP_CFG.log_dir.value)
                config.save_config(entry.game_dir, self.doc)
            else:
                self._set_form_enabled(False)
                return
        except Exception as e:  # tomlkit 解析失败: 显示原文, 禁表单
            self.doc = None
            self._set_form_enabled(False)
            self.error_view.show()
            with open(entry.config_path, encoding="utf-8") as f:
                self.error_view.setPlainText(f"配置解析失败: {e}\n\n"
                                             + f.read())
            return
        self._set_form_enabled(True)
        self._fill(load_form(self.doc))

    def _set_form_enabled(self, on: bool):
        for w in (*self.mode_cards.values(), self.period_slider,
                  self.buf_normal, self.buf_ring, self.raw_switch,
                  self.force_switch, self.log_box, self.btn_default):
            w.setEnabled(on)
        if not on:
            self.btn_save.setEnabled(False)

    def _fill(self, st: FormState):
        self._loading = True
        self._select_mode(st.mode)
        self.period_slider.setValue(st.period_hus)
        self.period_label.setText(
            "原生" if st.period_hus == 0 else f"{hus_to_ms(st.period_hus):.1f} ms")
        self.buf_normal.setValue(st.buf_normal)
        self.buf_ring.setValue(st.buf_ring)
        self.raw_switch.setChecked(st.raw)
        self.force_switch.setChecked(st.force_period)
        self.log_box.setCurrentText(st.log_level)
        self._loading = False
        self._dirty = False
        self.btn_save.setEnabled(False)

    # ---- 交互 ----

    def _select_mode(self, mode: str):
        for m, c in self.mode_cards.items():
            c.set_selected(m == mode)
        info = MODE_INFO.get(mode)
        self.mode_detail.setText(info["detail"] if info else "")
        self.buf_normal.setEnabled(mode == "Normal")
        self.buf_ring.setEnabled(mode == "Ringbuf")

    def _on_mode_card(self, mode: str):
        self._select_mode(mode)
        self._mark_dirty()

    def _on_period(self, v: int):
        self.period_label.setText(
            "原生" if v == 0 else f"{hus_to_ms(v):.1f} ms")
        self._mark_dirty()

    def _on_buf_normal(self, v: int):
        self.buf_normal_ms.setText(f"≈ {frames_to_ms(v):.1f} ms")
        self._mark_dirty()

    def _on_buf_ring(self, v: int):
        self.buf_ring_ms.setText(f"≈ {frames_to_ms(v):.1f} ms")
        self._mark_dirty()

    def _on_log_level(self, level: str):
        if self._loading:
            return
        if level != "Error":
            box = MessageBox(
                "日志级别",
                "Info 在 overflow 时可写 GB 级日志(实测一次会话 2.9GB)。\n"
                "仅排障临时使用, 确定切换?", self)
            if not box.exec():
                self._loading = True
                self.log_box.setCurrentText("Error")
                self._loading = False
                return
        self._mark_dirty()

    def _mark_dirty(self, *_args):
        if self._loading or self.doc is None:
            return
        self._dirty = True
        self.btn_save.setEnabled(True)

    def is_dirty(self) -> bool:
        return self._dirty

    # ---- 保存 ----

    def _current_state(self) -> FormState:
        return FormState(
            mode=self._selected_mode(),
            period_hus=self.period_slider.value(),
            buf_normal=self.buf_normal.value(),
            buf_ring=self.buf_ring.value(),
            raw=self.raw_switch.isChecked(),
            force_period=self.force_switch.isChecked(),
            log_level=self.log_box.currentText(),
        )

    def _selected_mode(self) -> str:
        for m, c in self.mode_cards.items():
            if c.styleSheet():
                return m
        return "Normal"

    def _save(self):
        if self.doc is None or self.entry is None:
            return
        state = self._current_state()
        apply_form(self.doc, state)
        problems = config.validate(self.doc)
        if problems:
            InfoBar.warning("校验失败", "\n".join(problems),
                            parent=self, position=InfoBarPosition.TOP,
                            duration=6000)
            return
        config.save_config(self.entry.game_dir, self.doc)
        self._dirty = False
        self.btn_save.setEnabled(False)
        msg = "配置已保存"
        if launcher.is_game_running(os.path.basename(self.entry.exe)):
            msg += "; 游戏正在运行, 重启后生效"
        InfoBar.success("保存", msg, parent=self,
                        position=InfoBarPosition.TOP, duration=3000)
        self.saved.emit(self.entry.name)

    def _reset_default(self):
        box = MessageBox("恢复默认", "用默认配置覆盖当前表单?(未保存前不影响文件)",
                         self)
        if box.exec():
            self.doc = config.default_config(APP_CFG.log_dir.value)
            self.error_view.hide()
            self._set_form_enabled(True)
            self._fill(load_form(self.doc))
            self._mark_dirty()
```

实现完成后删除 `_current_state` 里第一行死代码(`mode = next(...)` 那行是冗余的,保留 `_selected_mode` 路径即可)——直接写干净版本,不要留死代码。

- [ ] **Step 4: 接入 game_detail.py**

修改 `ui/game_detail.py`:
- 顶部 `from ui.config_card import ConfigCard`
- `self.config_card = QWidget(self)` 改为 `self.config_card = ConfigCard(self)`
- `set_game` 末尾(换游戏时)先检查 `self.config_card.is_dirty()`——脏则弹 `MessageBox`「有未保存修改,放弃?」,取消则不切换(详情页切换由 GamesPage 发起,接口改为 `set_game(entry) -> bool`,GamesPage._on_select 根据返回值决定是否回退列表选中);保存提示的简化方案:脏时切换直接弹确认,确认放弃则继续
- `set_game` 末尾调 `self.config_card.set_game(entry)`
- `self.config_card.saved.connect(self.config_changed)`

跑测试: `python -m pytest tests/ -v`,Expected: 全绿。

- [ ] **Step 5: Commit**

```powershell
git add ui/config_card.py ui/game_detail.py tests/test_smoke.py
git commit -m "feat(ui): 配置卡 — 模式四选卡/白话解释/毫秒换算/脏状态/保存"
```

---

### Task 7: 添加游戏向导对话框

**Files:**
- Create: `ui/add_game_dialog.py`(取代旧 `ui/add_wizard.py`,旧文件删除)
- Modify: `ui/games_page.py`(`_add_game` 接线)
- Test: `tests/test_smoke.py`(追加)

**Interfaces:**
- Consumes: `backend.anticheat.scan_exe`、`backend.config`、`backend.registry`、`backend.ifeo`、`backend.launcher`、Task 2 `APP_CFG.log_dir`
- Produces:
  - `AddGameDialog(MessageBoxBase)`:`__init__(self, parent=None)`;静态/实例方法 `exec() -> bool`(True = 完成注册);4 步 `QStackedWidget` + 顶部步骤标签("1 选择游戏 → 2 反作弊 → 3 配置 → 4 IFEO");字段访问 `self.game_name/self.game_exe/self.report`
  - 注册名正则沿用 `^[a-z0-9_]+$`;反作弊 known 需勾选知情同意;生成配置用 `config.default_config(APP_CFG.log_dir.value)`;IFEO 步轮询逻辑与详情页相同(单 QTimer 先停)

- [ ] **Step 1: 写 smoke 测试(追加 tests/test_smoke.py)**

```python
def test_add_game_dialog_instantiates(qapp):
    from ui.add_game_dialog import AddGameDialog
    dlg = AddGameDialog()
    assert dlg.stack.count() == 4
    dlg.deleteLater()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_smoke.py::test_add_game_dialog_instantiates -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现 add_game_dialog.py**

Create `ui/add_game_dialog.py`。逻辑逐页移植旧 `ui/add_wizard.py` 的 `validatePage/initializePage/_enable/_poll/accept`,结构如下(完整实现,不是骨架):

```python
"""添加游戏向导: 对话框内嵌 4 步(选择 exe → 反作弊 → 配置 → IFEO)。

逻辑移植自旧 ui/add_wizard.py(QWizard 版), 改为 MessageBoxBase +
QStackedWidget + 步骤标签, 视觉与 Fluent 一致。
"""
from __future__ import annotations

import os
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QFileDialog, QFormLayout, QHBoxLayout,
                               QStackedWidget, QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, CheckBox, ComboBox,
                            InfoBar, InfoBarPosition, LineEdit, MessageBox,
                            MessageBoxBase, PrimaryPushButton, PushButton,
                            SpinBox, StrongBodyLabel, SubtitleLabel)

from backend import anticheat, config, ifeo, launcher, registry
from backend.ifeo import IfeoState
from ui.app_config import APP_CFG

_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_STEPS = "1 选择游戏 → 2 反作弊 → 3 配置 → 4 IFEO"


class AddGameDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("添加游戏", self)
        self.step_label = CaptionLabel(_STEPS, self)

        self.runner = launcher.ProcessRunner(self)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll_ifeo)
        self._poll_count = 0
        self.report: anticheat.Report | None = None

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self._build_step_exe())
        self.stack.addWidget(self._build_step_anticheat())
        self.stack.addWidget(self._build_step_config())
        self.stack.addWidget(self._build_step_ifeo())

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.step_label)
        self.viewLayout.addWidget(self.stack)

        self.back_btn = PushButton("上一步", self)
        self.back_btn.clicked.connect(self._back)
        self.next_btn = PrimaryPushButton("下一步", self)
        self.next_btn.clicked.connect(self._next)
        self.buttonLayout.insertWidget(0, self.back_btn)
        self.buttonLayout.insertWidget(1, self.next_btn)
        self.yesButton.hide()  # 用 back/next 替代
        self.cancelButton.setText("取消")

        self.game_name = ""
        self.game_exe = ""
        self._sync_buttons()

    # ---- 步骤页 ----

    def _build_step_exe(self) -> QWidget:
        w = QWidget(self)
        self.name_edit = LineEdit(w)
        self.name_edit.setPlaceholderText(
            "注册名, 小写字母/数字/下划线, 如 ds2")
        self.exe_edit = LineEdit(w)
        self.exe_edit.setReadOnly(True)
        btn = PushButton("浏览…", w)
        btn.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.exe_edit, 1)
        row.addWidget(btn)
        lay = QFormLayout(w)
        lay.addRow("注册名", self.name_edit)
        lay.addRow("游戏 exe", row)
        return w

    def _build_step_anticheat(self) -> QWidget:
        w = QWidget(self)
        lay = QVBoxLayout(w)
        self.ac_result = BodyLabel("", w)
        self.ac_result.setWordWrap(True)
        self.ac_ack = CheckBox(
            "我已了解: 反作弊游戏注入有封禁风险, 后果自负", w)
        lay.addWidget(self.ac_result)
        lay.addWidget(self.ac_ack)
        lay.addStretch(1)
        return w

    def _build_step_config(self) -> QWidget:
        w = QWidget(self)
        self.mode_box = ComboBox(w)
        self.mode_box.addItems(config.MODES)
        self.buf_box = SpinBox(w)
        self.buf_box.setRange(1, 8192)
        self.buf_box.setValue(960)
        lay = QFormLayout(w)
        lay.addRow("模式", self.mode_box)
        lay.addRow("缓冲帧数", self.buf_box)
        note = CaptionLabel(
            "普通模式: 大多数游戏可用, 缓冲过小会破音\n"
            "虚拟缓冲: 《黑魂2》需要; UE5 会溢出刷屏; 绝区零丢扬声器声道\n"
            "每个游戏必须单独试, 没有通用最优解", w)
        note.setWordWrap(True)
        lay.addRow(note)
        return w

    def _build_step_ifeo(self) -> QWidget:
        w = QWidget(self)
        lay = QVBoxLayout(w)
        self.ifeo_status = BodyLabel("点击按钮启用(会弹 UAC 提权框)", w)
        self.ifeo_status.setWordWrap(True)
        btn = PrimaryPushButton("启用 IFEO", w)
        btn.clicked.connect(self._enable_ifeo)
        lay.addWidget(self.ifeo_status)
        lay.addWidget(btn)
        lay.addWidget(CaptionLabel(
            "完成后从 Steam/启动器正常启动游戏即自动注入。"
            "也可以稍后在游戏详情页开启。", w))
        lay.addStretch(1)
        return w

    # ---- 导航 ----

    def _sync_buttons(self):
        i = self.stack.currentIndex()
        self.back_btn.setEnabled(i > 0)
        self.next_btn.setText("完成" if i == 3 else "下一步")
        self.next_btn.setEnabled(i != 1 or self._anticheat_ok())

    def _back(self):
        self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
        self._sync_buttons()

    def _next(self):
        i = self.stack.currentIndex()
        if i == 0 and not self._validate_exe():
            return
        if i == 0:
            self._enter_anticheat()
        if i == 2 and not self._write_config():
            return
        if i == 3:
            self._finish()
            return
        self.stack.setCurrentIndex(i + 1)
        self._sync_buttons()

    # ---- 各步逻辑(移植旧 wizard) ----

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择游戏 exe", "",
                                              "Executables (*.exe)")
        if path:
            self.exe_edit.setText(path)

    def _validate_exe(self) -> bool:
        name = self.name_edit.text().strip()
        if not _NAME_RE.match(name):
            InfoBar.warning("注册名", "仅限小写字母/数字/下划线",
                            parent=self, position=InfoBarPosition.TOP)
            return False
        if not self.exe_edit.text():
            InfoBar.warning("游戏 exe", "请选择游戏可执行文件",
                            parent=self, position=InfoBarPosition.TOP)
            return False
        from backend import paths
        if name in registry.load_or_migrate(str(paths.GAMES_YAML)):
            InfoBar.warning("注册名", f"'{name}' 已被占用",
                            parent=self, position=InfoBarPosition.TOP)
            return False
        self.game_name = name
        self.game_exe = self.exe_edit.text()
        return True

    def _enter_anticheat(self):
        self.report = anticheat.scan_exe(self.game_exe)
        if self.report.risk == "known":
            self.ac_result.setText(
                "检测到反作弊特征:\n· " + "\n· ".join(self.report.hits) +
                "\n\n已知风险: HoYoKProtect 会剥离 OpenProcess 句柄并改名"
                "外来 DLL。本工具采用父进程注入可绕过句柄剥离, "
                "但仍有账号风险。")
            self.ac_ack.setChecked(False)
            self.ac_ack.show()
        else:
            self.ac_result.setText("未检测到已知反作弊特征。")
            self.ac_ack.hide()
        self.ac_ack.toggled.connect(lambda _c: self._sync_buttons())

    def _anticheat_ok(self) -> bool:
        return (self.report is not None and self.report.risk != "known") \
            or self.ac_ack.isChecked()

    def _write_config(self) -> bool:
        game_dir = os.path.dirname(self.game_exe)
        if os.path.isfile(config.config_file(game_dir)):
            box = MessageBox("配置已存在",
                             "redirect_config.toml 已存在, 覆盖?\n"
                             "(选「否」保留现有配置)", self)
            if not box.exec():
                return True
        doc = config.default_config(APP_CFG.log_dir.value)
        doc["playback"]["mode"] = self.mode_box.currentText()
        # tomlkit 点分键子表键是字符串 "48000", int 键 TypeError
        doc["playback"]["target_buffer_len"]["48000"] = self.buf_box.value()
        if self.mode_box.currentText() == "Ringbuf":
            doc["playback"]["ring_buffer_len"]["48000"] = \
                self.buf_box.value()
        config.save_config(game_dir, doc)
        return True

    def _enable_ifeo(self):
        launcher.set_ifeo(self.runner, self.game_name, True)
        self._poll_count = 0
        self._timer.stop()  # 重复点击先停旧定时器
        self._timer.start()
        self.ifeo_status.setText("等待提权与注册表写入…")

    def _poll_ifeo(self):
        self._poll_count += 1
        state = ifeo.query_ifeo(os.path.basename(self.game_exe))
        if state == IfeoState.ON_OURS:
            self._timer.stop()
            self.ifeo_status.setText("✓ IFEO 已启用")
        elif self._poll_count >= 10:
            self._timer.stop()
            self.ifeo_status.setText(
                "✗ 提权被取消或失败, 可稍后在游戏详情页重试")

    def _finish(self):
        registry.add_game(registry.GameEntry(
            name=self.game_name,
            exe=self.game_exe,
            mode_hint=self.mode_box.currentText(),
            buffer_hint=self.buf_box.value(),
            anticheat=self.report.risk == "known" if self.report else False,
        ))
        self.accept()
```

`anticheat.Report` 的类型名以 `backend/anticheat.py` 实际定义为准(若叫别的,按实际改标注)。

- [ ] **Step 4: 接线 + 删旧文件**

修改 `ui/games_page.py` 的 `_add_game`:

```python
def _add_game(self):
    from ui.add_game_dialog import AddGameDialog
    if AddGameDialog(self).exec():
        self.refresh()
```

删除 `ui/add_wizard.py`:`git rm ui/add_wizard.py`

跑测试: `python -m pytest tests/ -v`,Expected: 全绿。

- [ ] **Step 5: Commit**

```powershell
git add ui/add_game_dialog.py ui/games_page.py
git rm ui/add_wizard.py
git commit -m "feat(ui): 添加游戏向导对话框(4 步, Fluent 化)"
```

---

### Task 8: 诊断页

**Files:**
- Create: `ui/diagnostics_page.py`(取代旧 `ui/monitor_page.py`,旧文件删除)
- Modify: `ui/main_window.py`(diagnostics 占位换真实页)
- Test: `tests/test_smoke.py`(追加)

**Interfaces:**
- Consumes: `backend.monitor`(tail/read_result/LogWatcher)、`backend.paths`(INJECTOR_RESULT/INJECTOR_DEBUG_LOG)、Task 2 `APP_CFG`(relink 日志目录 = `APP_CFG.log_dir.value`)、Task 4 `SettingsPage.log_dir_changed`
- Produces:
  - `DiagnosticsPage(QWidget)`:objectName `"diagnostics"`;控件 `result_card`(CardWidget 内含 `result_label`)、`tabs`(Pivot,项 `"injector_debug"`/`"wasapi_relink"`)、`log_views: dict[str, PlainTextEdit]`、`btn_open`(PushButton「在资源管理器中打开」,对应当前选项卡文件)、`stack`(QStackedWidget 与 Pivot 联动)
  - 方法 `append_event(text: str)`(追加到 injector_debug 视图,兼容旧接线)、`relink_log_path(self) -> str`(`os.path.join(APP_CFG.log_dir.value, "wasapi_relink.log")`)、`rebuild_watcher(self)`(日志目录变化后重建 LogWatcher)
  - injector_debug 选项卡内放 CaptionLabel「此日志由注入器写入,位置固定于 specialk 目录」

- [ ] **Step 1: 写 smoke 测试(追加 tests/test_smoke.py)**

```python
def test_diagnostics_page(qapp, tmp_path, monkeypatch):
    from backend import paths, monitor
    result = tmp_path / "injector_result.txt"
    result.write_text("injected OK: test", encoding="utf-8")
    dbg = tmp_path / "injector_debug.log"
    dbg.write_text("line1\nline2\n", encoding="utf-8")
    monkeypatch.setattr(paths, "INJECTOR_RESULT", str(result))
    monkeypatch.setattr(paths, "INJECTOR_DEBUG_LOG", str(dbg))

    from ui.diagnostics_page import DiagnosticsPage
    page = DiagnosticsPage()
    assert "injected OK" in page.result_label.text()
    assert "line2" in page.log_views["injector_debug"].toPlainText()
    page.deleteLater()
```

同样注意默认参数绑定陷阱:`monitor.read_result(path=paths.INJECTOR_RESULT)` 默认值定义时绑定。实现时调用处显式传参:`monitor.read_result(str(paths.INJECTOR_RESULT))`、`monitor.tail(str(paths.INJECTOR_DEBUG_LOG), 200)`。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_smoke.py::test_diagnostics_page -v`
Expected: FAIL(ModuleNotFoundError)

- [ ] **Step 3: 实现 diagnostics_page.py**

Create `ui/diagnostics_page.py`:

```python
"""诊断页: 最近注入结果 + 两个日志选项卡(尾随 200 行 + 文件监视 +
资源管理器打开)。

monitor/paths 调用全部显式传参 — 默认参数在定义时绑定, monkeypatch 需显式。
"""
from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, Pivot,
                            PlainTextEdit, PushButton, StrongBodyLabel,
                            TitleLabel)

from backend import monitor, paths
from ui.app_config import APP_CFG

_TAIL_LINES = 200


class DiagnosticsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("diagnostics")

        # 最近注入
        self.result_card = CardWidget(self)
        rc = QVBoxLayout(self.result_card)
        rc.addWidget(StrongBodyLabel("最近注入", self.result_card))
        self.result_label = BodyLabel("", self.result_card)
        self.result_label.setWordWrap(True)
        rc.addWidget(self.result_label)

        # 日志选项卡
        self.tabs = Pivot(self)
        self.stack = QStackedWidget(self)
        self.log_views: dict[str, PlainTextEdit] = {}
        for key, fixed in (("injector_debug", True), ("wasapi_relink", False)):
            host = QWidget(self)
            vl = QVBoxLayout(host)
            vl.setContentsMargins(0, 0, 0, 0)
            if fixed:
                vl.addWidget(CaptionLabel(
                    "此日志由注入器写入, 位置固定于 specialk 目录", host))
            view = PlainTextEdit(host)
            view.setReadOnly(True)
            view.setMaximumBlockCount(500)
            vl.addWidget(view)
            self.log_views[key] = view
            self.stack.addWidget(host)
            self.tabs.addItem(
                routeKey=key,
                text=key,
                onClick=lambda k=key: self.stack.setCurrentIndex(
                    0 if k == "injector_debug" else 1),
            )
        self.tabs.setCurrentItem("injector_debug")

        self.btn_open = PushButton("在资源管理器中打开", self)
        self.btn_open.clicked.connect(self._open_current)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(10)
        lay.addWidget(TitleLabel("诊断", self))
        lay.addWidget(self.result_card)
        lay.addWidget(self.tabs)
        lay.addWidget(self.btn_open)
        lay.addWidget(self.stack, 1)

        self.watcher = None
        self.rebuild_watcher()
        self._refresh_result()
        self._reload("injector_debug")
        self._reload("wasapi_relink")

    def relink_log_path(self) -> str:
        return os.path.join(APP_CFG.log_dir.value, "wasapi_relink.log")

    def _path_of(self, key: str) -> str:
        return str(paths.INJECTOR_DEBUG_LOG) if key == "injector_debug" \
            else self.relink_log_path()

    def rebuild_watcher(self):
        """日志目录变化后重建监视(LogWatcher 不做动态增删路径)。"""
        if self.watcher is not None:
            self.watcher.deleteLater()
        self.watcher = monitor.LogWatcher(
            [str(paths.INJECTOR_RESULT), str(paths.INJECTOR_DEBUG_LOG),
             self.relink_log_path()], self)
        self.watcher.file_changed.connect(self._on_changed)

    def append_event(self, text: str):
        self.log_views["injector_debug"].appendPlainText(text)

    def _open_current(self):
        key = "injector_debug" if self.stack.currentIndex() == 0 \
            else "wasapi_relink"
        p = self._path_of(key)
        if os.path.isfile(p):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
        else:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            subprocess.Popen(["explorer", os.path.normpath(
                os.path.dirname(p))])

    def _on_changed(self, path: str):
        if path == str(paths.INJECTOR_RESULT):
            self._refresh_result()
        elif path == str(paths.INJECTOR_DEBUG_LOG):
            self._reload("injector_debug")
        elif path == self.relink_log_path():
            self._reload("wasapi_relink")

    def _refresh_result(self):
        mtime, text = monitor.read_result(str(paths.INJECTOR_RESULT))
        self.result_label.setText(
            f"{mtime:%Y-%m-%d %H:%M:%S} — {text}" if mtime and text
            else "暂无注入记录")

    def _reload(self, key: str):
        view = self.log_views[key]
        view.setPlainText("\n".join(monitor.tail(self._path_of(key),
                                                 _TAIL_LINES)))
        view.verticalScrollBar().setValue(
            view.verticalScrollBar().maximum())
```

- [ ] **Step 4: 接线 + 删旧文件**

`ui/main_window.py`:
- `from ui.diagnostics_page import DiagnosticsPage`
- `self.diagnostics_page = DiagnosticsPage(self)`
- 删除 `_placeholder` 函数及两处占位使用
- `SettingsPage.log_dir_changed` 接到 `DiagnosticsPage.rebuild_watcher`:
  `self.settings_page.log_dir_changed.connect(self.diagnostics_page.rebuild_watcher)`
- `self.games_page.log_line.connect(self.diagnostics_page.append_event)`

删除 `ui/monitor_page.py`、`ui/config_editor.py`(旧文件):`git rm ui/monitor_page.py ui/config_editor.py`

跑测试: `python -m pytest tests/ -v`,Expected: 全绿。

- [ ] **Step 5: Commit**

```powershell
git add ui/diagnostics_page.py ui/main_window.py tests/test_smoke.py
git rm ui/monitor_page.py ui/config_editor.py
git commit -m "feat(ui): 诊断页 — 最近注入卡 + Pivot 日志选项卡 + 资源管理器打开"
```

---

### Task 9: 收尾 — 入口、README、端到端验证

**Files:**
- Modify: `app.py`
- Modify: `README.md`
- Modify: `tests/test_smoke.py`(收尾断言)
- Check: `启动.bat`

**Interfaces:**
- Consumes: Task 4 `create_main_window`
- Produces: `app.py` 的 `main()` 创建 `create_main_window()` 并 show

- [ ] **Step 1: 更新 app.py**

```python
import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import create_main_window


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("HapticImproveManager")
    win = create_main_window()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 检查 启动.bat**

`启动.bat` 内容应为 `pythonw app.py`(或等价)。读文件确认无需改动;若引用了旧模块则改为 `app.py`。

- [ ] **Step 3: 全量测试**

Run: `python -m pytest tests/ -v`
Expected: 全绿

- [ ] **Step 4: 更新 README.md**

重写「运行」「功能」「架构」三节:

```markdown
## 运行
    python -m pip install -r requirements.txt
    python app.py

## 功能
- 游戏中心: 左侧游戏列表, 右侧详情(状态/IFEO 开关/启动/配置编辑), 选中即上下文
- 注入配置通俗化: 模式四选一卡片(Normal/Ringbuf/Compat/Bypass)带白话说明,
  缓冲帧数实时换算毫秒
- 添加游戏向导: exe 选择 → 反作弊检测 → 生成 redirect_config.toml → 开 IFEO
- 诊断: 最近注入结果 + injector_debug.log / wasapi_relink.log 尾随,
  一键在资源管理器打开
- 设置: 浅色/深色/跟随系统主题, Mica 云母背景, 日志目录可改并批量同步到所有游戏

## 架构
薄 GUI(PySide6 + qfluentwidgets)+ 子进程后端。
GUI 普通权限运行; ifeo on/off 由 haptic_launcher 自行 UAC 提权。
游戏注册表: specialk/games.yaml(GUI 与 CLI 共用)。
ui/config_model.py 为表单↔TOML 纯函数映射(可单测);
GUI 设置(主题/日志目录)存 %APPDATA%/HapticImproveManager/gui_config.json。
```

- [ ] **Step 5: 人工端到端验证(执行者按清单操作并记录结果)**

```powershell
python app.py
```

清单(每项浅色/深色各过一遍——设置页切换主题后立即检查):
1. 主窗口出现,导航三项(游戏/诊断/设置),Mica 背景生效(Win11)
2. 空列表显示空状态;添加游戏向导四步可走通到 IFEO 步(可取消 UAC)
3. 选中游戏 → 详情显示状态徽章;IFEO 开关弹出 UAC(可取消,10s 后 InfoBar 警告)
4. 配置卡:切换模式卡片,详情文字变化;拖推送节奏滑块标签变 ms;改缓冲帧数出现 ≈ms;保存按钮高亮 → 保存 → InfoBar 成功
5. 深色主题下:状态徽章、CaptionLabel 解释文字、模式卡选中边框均清晰可读
6. 诊断页:最近注入卡显示;两个日志选项卡可切换;「在资源管理器中打开」弹出资源管理器并选中日志文件
7. 设置页:改日志目录 → 弹确认 → 同步成功 InfoBar;「在资源管理器中打开」正常
8. 关闭重开:主题与日志目录被记住

把结果(含截图或文字记录)写入提交信息或 PR 描述。

- [ ] **Step 6: Commit**

```powershell
git add app.py README.md tests/test_smoke.py 启动.bat
git commit -m "feat: Fluent 重写收尾 — 新入口/README/端到端验证"
```

---

## Self-Review 记录

- Spec 覆盖:技术栈(Task 1)、结构(各 Task Files)、框架(Task 4)、游戏中心(Task 5/6/7)、诊断(Task 8)、设置与日志目录(Task 4)、错误处理 InfoBar/Dialog(各任务内嵌)、测试(每任务含)、风险(tomlkit/QTimer/颜色约束进 Global Constraints)。✓
- 占位扫描:无 TBD/TODO;Task 7/8 的代码为完整实现。✓
- 类型一致性:`FormState` 字段、`sync_log_dir` 返回 `(int, list[str])`、`DiagnosticsPage.relink_log_path`、`APP_CFG` 单例跨任务一致。✓
- Review Focus 5 项均有归属任务与测试/约束。✓
