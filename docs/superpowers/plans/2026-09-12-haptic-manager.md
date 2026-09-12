# HapticImproveManager 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 specialk 下的 haptic 低延迟注入系统(injector.py + haptic_launcher.py)包装成 PySide6 可视化管理桌面应用,含游戏列表、添加向导、配置编辑、状态监控四页。

**Architecture:** 薄 GUI + 子进程后端。GUI 不 import 注入逻辑;写操作(启动游戏、ifeo on/off)经 QProcess 调 `haptic_launcher.py` CLI;只读查询(winreg/pefile/toml)在 backend 内直接实现、纯函数可测。游戏注册表从硬编码 GAMES 字典迁移到 `specialk/games.yaml`,GUI 与 CLI 共享。

**Tech Stack:** Python 3 + PySide6 (Qt) / PyYAML / pefile / tomlkit / pytest

**Spec:** `docs/superpowers/specs/2026-09-12-haptic-manager-design.md`

## Global Constraints

- 平台:Windows 11,Python 解释器 `C:\Users\ZhuTT\AppData\Local\Python\bin\python.exe`(与 injector 用的 pythonw 同安装)
- 后端目录常量:`specialk/` 绝对路径、`games.yaml` 位置、`IFEO_VALUE` 全部集中在 `backend/paths.py`
- `IFEO_VALUE` 必须与 `specialk/injector.py` 中常量逐字一致(HANDOVER 踩坑 #2:两处不一致会被覆盖回旧值)
- 游戏目录只放 `redirect_config.toml` 纯文本,**永不放 DLL**(HANDOVER 踩坑 #9/#10)
- `redirect_config.toml` 的 `log_level` 常驻 `Error`;写 `Info` 必须强确认(HANDOVER 踩坑 #8:overflow 可写 GB 级日志)
- GUI 本体普通权限运行;只有 `ifeo on/off` 走 launcher 自带 `_elevate()` 提权
- 反作弊游戏(HoYoKProtect/EAC/BattlEye)只警告不阻止,用户须勾选知情确认
- 所有 backend 纯逻辑模块(registry/config/anticheat/ifeo 查询/monitor 工具函数)**不依赖 PySide6**,可用 pytest 在无显示环境测试;Qt 依赖集中在 `backend/launcher.py`、`backend/monitor.py` 的 watcher 类和 `ui/`
- 工作目录:`C:\Users\ZhuTT\Workspace\HapticImporveManager`(已 git init,身份已配置)
- 提交信息用中文,conventional commits 前缀(feat/fix/test/docs/chore)

---

### Task 1: 项目脚手架 + paths.py

**Files:**
- Create: `requirements.txt`
- Create: `conftest.py`(空文件,让 pytest 把仓库根加入 sys.path)
- Create: `backend/__init__.py`(空)、`ui/__init__.py`(空)、`tests/__init__.py`(空)
- Create: `backend/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Produces(后续所有任务依赖):
  - `paths.SPECIALK_DIR / GAMES_YAML / LAUNCHER_PY / INJECTOR_PY / DEFAULT_DLL`(str 绝对路径)
  - `paths.INJECTOR_RESULT / INJECTOR_DEBUG_LOG / RELINK_LOG_DIR / RELINK_LOG`(str)
  - `paths.IFEO_BASE`(str)、`paths.IFEO_VALUE`(str,与 injector.py 逐字一致)

- [ ] **Step 1: 写 requirements.txt 和包骨架**

`requirements.txt`:
```
PySide6>=6.7
PyYAML>=6.0
pefile>=2023.2.7
tomlkit>=0.12
pytest>=8.0
```

`conftest.py`、三个 `__init__.py` 均为空文件。

- [ ] **Step 2: 写失败测试**

`tests/test_paths.py`:
```python
import os
from backend import paths


def test_specialk_paths_exist():
    assert os.path.isdir(paths.SPECIALK_DIR)
    assert os.path.isfile(paths.LAUNCHER_PY)
    assert os.path.isfile(paths.INJECTOR_PY)
    assert os.path.isfile(paths.DEFAULT_DLL)


def test_ifeo_value_matches_injector():
    """IFEO_VALUE 必须与 injector.py 中的常量逐字一致(踩坑 #2)。"""
    with open(paths.INJECTOR_PY, encoding="utf-8") as f:
        src = f.read()
    # injector.py 里常量是拼接字符串, 逐段检查关键部分
    assert "pythonw.exe" in paths.IFEO_VALUE
    assert "injector.py\" ifeo" in paths.IFEO_VALUE
    frag = paths.IFEO_VALUE.split('"')[3]  # injector.py 路径段
    assert frag.replace("\\\\", "\\") in src.replace("\\\\", "\\")
```

- [ ] **Step 3: 运行确认失败**

Run: `python -m pytest tests/test_paths.py -v`
Expected: FAIL(ModuleNotFoundError: backend.paths)

- [ ] **Step 4: 实现 paths.py**

`backend/paths.py`:
```python
"""后端路径与常量集中定义。IFEO_VALUE 必须与 specialk/injector.py 逐字一致。"""
import os

SPECIALK_DIR = r"C:\Users\ZhuTT\Workspace\specialk"
GAMES_YAML = os.path.join(SPECIALK_DIR, "games.yaml")
LAUNCHER_PY = os.path.join(SPECIALK_DIR, "haptic_launcher.py")
INJECTOR_PY = os.path.join(SPECIALK_DIR, "injector.py")
DEFAULT_DLL = os.path.join(SPECIALK_DIR, "zzz_inject", "wasapi_relink.dll")

INJECTOR_RESULT = os.path.join(SPECIALK_DIR, "injector_result.txt")
INJECTOR_DEBUG_LOG = os.path.join(SPECIALK_DIR, "injector_debug.log")
RELINK_LOG_DIR = os.path.join(SPECIALK_DIR, "logs")
RELINK_LOG = os.path.join(RELINK_LOG_DIR, "wasapi_relink.log")

IFEO_BASE = (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
             r"\Image File Execution Options")
# 与 injector.py 的 IFEO_VALUE 逐字一致 — 修改必须两处同改
IFEO_VALUE = ('"C:\\Users\\ZhuTT\\AppData\\Local\\Python\\bin\\pythonw.exe" '
              '"C:\\Users\\ZhuTT\\Workspace\\specialk\\injector.py" ifeo')
```

- [ ] **Step 5: 安装依赖并跑测试**

Run:
```
python -m pip install -r requirements.txt
python -m pytest tests/test_paths.py -v
```
Expected: 2 PASSED

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "chore: 项目脚手架 + backend/paths.py 路径常量"
```

---

### Task 2: backend/registry.py — 游戏注册表(YAML)

**Files:**
- Create: `backend/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: `paths.GAMES_YAML`、`paths.SPECIALK_DIR`
- Produces:
  - `@dataclass GameEntry(name: str, exe: str, mode_hint: str = "Normal", buffer_hint: int = 960, anticheat: bool = False)`,属性 `.game_dir` / `.config_path` / `.exe_exists` / `.config_exists`
  - `load_games(path: str = paths.GAMES_YAML) -> dict[str, GameEntry]`
  - `save_games(games: dict[str, GameEntry], path: str = paths.GAMES_YAML) -> None`
  - `add_game(entry: GameEntry, path: str = ...) -> None` / `remove_game(name: str, path: str = ...) -> None`
  - `migrate_from_launcher(path: str = ..., launcher_dir: str = paths.SPECIALK_DIR) -> dict[str, GameEntry]`
  - `load_or_migrate(path: str = ...) -> dict[str, GameEntry]`(损坏时备份 `.bak` 再迁移)

- [ ] **Step 1: 写失败测试**

`tests/test_registry.py`:
```python
import os
import pytest
import yaml
from backend.registry import (GameEntry, load_games, save_games, add_game,
                              remove_game, migrate_from_launcher,
                              load_or_migrate)


@pytest.fixture
def yaml_path(tmp_path):
    return str(tmp_path / "games.yaml")


def test_round_trip(yaml_path):
    games = {"ds2": GameEntry(name="ds2", exe=r"E:\games\DS2.exe",
                              mode_hint="Ringbuf", buffer_hint=2048)}
    save_games(games, yaml_path)
    loaded = load_games(yaml_path)
    assert loaded["ds2"].exe == games["ds2"].exe
    assert loaded["ds2"].mode_hint == "Ringbuf"
    assert loaded["ds2"].buffer_hint == 2048
    assert loaded["ds2"].anticheat is False


def test_name_is_yaml_key_not_field(yaml_path):
    save_games({"sb": GameEntry(name="sb", exe=r"E:\SB.exe")}, yaml_path)
    with open(yaml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    assert "name" not in raw["games"]["sb"]


def test_add_and_remove(yaml_path):
    add_game(GameEntry(name="a", exe=r"C:\a.exe"), yaml_path)
    add_game(GameEntry(name="b", exe=r"C:\b.exe"), yaml_path)
    assert set(load_games(yaml_path)) == {"a", "b"}
    remove_game("a", yaml_path)
    assert set(load_games(yaml_path)) == {"b"}


def test_derived_properties():
    e = GameEntry(name="x", exe=r"E:\game dir\game.exe")
    assert e.game_dir == r"E:\game dir"
    assert e.config_path == r"E:\game dir\redirect_config.toml"
    assert e.exe_exists is False  # 路径不存在


def test_migrate_from_launcher(yaml_path):
    games = migrate_from_launcher(yaml_path)
    assert set(games) == {"ds2", "sb", "zzz"}
    assert games["ds2"].mode_hint == "Ringbuf"
    assert games["zzz"].anticheat is True
    assert os.path.isfile(yaml_path)


def test_load_or_migrate_backs_up_corrupt(yaml_path):
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("games: [broken yaml{")
    games = load_or_migrate(yaml_path)
    assert "ds2" in games
    assert os.path.isfile(yaml_path + ".bak")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_registry.py -v`
Expected: FAIL(ModuleNotFoundError: backend.registry)

- [ ] **Step 3: 实现 registry.py**

`backend/registry.py`:
```python
"""游戏注册表: specialk/games.yaml 读写, GUI 与 haptic_launcher.py 共用。"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, asdict

import yaml

from . import paths

# 已知游戏的展示用经验值(HANDOVER 第 2 节)
_HINTS = {
    "ds2": {"mode_hint": "Ringbuf", "buffer_hint": 2048, "anticheat": False},
    "sb": {"mode_hint": "Normal", "buffer_hint": 256, "anticheat": False},
    "zzz": {"mode_hint": "Normal", "buffer_hint": 960, "anticheat": True},
}


@dataclass
class GameEntry:
    name: str
    exe: str
    mode_hint: str = "Normal"
    buffer_hint: int = 960
    anticheat: bool = False

    @property
    def game_dir(self) -> str:
        return os.path.dirname(self.exe)

    @property
    def config_path(self) -> str:
        return os.path.join(self.game_dir, "redirect_config.toml")

    @property
    def exe_exists(self) -> bool:
        return os.path.isfile(self.exe)

    @property
    def config_exists(self) -> bool:
        return os.path.isfile(self.config_path)


def _to_entry(name: str, raw: dict) -> GameEntry:
    return GameEntry(
        name=name,
        exe=raw["exe"],
        mode_hint=raw.get("mode_hint", "Normal"),
        buffer_hint=int(raw.get("buffer_hint", 960)),
        anticheat=bool(raw.get("anticheat", False)),
    )


def load_games(path: str = paths.GAMES_YAML) -> dict[str, GameEntry]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {n: _to_entry(n, r) for n, r in (data.get("games") or {}).items()}


def save_games(games: dict[str, GameEntry], path: str = paths.GAMES_YAML) -> None:
    payload = {"games": {}}
    for name, e in games.items():
        d = asdict(e)
        d.pop("name")  # name 是 YAML 键, 不重复存为字段
        payload["games"][name] = d
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)


def add_game(entry: GameEntry, path: str = paths.GAMES_YAML) -> None:
    games = load_games(path)
    games[entry.name] = entry
    save_games(games, path)


def remove_game(name: str, path: str = paths.GAMES_YAML) -> None:
    games = load_games(path)
    games.pop(name, None)
    save_games(games, path)


def migrate_from_launcher(path: str = paths.GAMES_YAML,
                          launcher_dir: str = paths.SPECIALK_DIR
                          ) -> dict[str, GameEntry]:
    """从 haptic_launcher.py 的硬编码 GAMES 生成 games.yaml(含已知经验值)。"""
    if launcher_dir not in sys.path:
        sys.path.insert(0, launcher_dir)
    import haptic_launcher  # noqa: E402 — 动态加入 sys.path 后导入
    games = {}
    for name, exe in haptic_launcher.GAMES.items():
        games[name] = GameEntry(name=name, exe=exe, **_HINTS.get(name, {}))
    save_games(games, path)
    return games


def load_or_migrate(path: str = paths.GAMES_YAML) -> dict[str, GameEntry]:
    """优先读 games.yaml; 不存在或损坏时(备份 .bak 后)从 launcher 迁移。"""
    try:
        return load_games(path)
    except FileNotFoundError:
        return migrate_from_launcher(path)
    except (yaml.YAMLError, KeyError, TypeError):
        shutil.copy(path, path + ".bak")
        return migrate_from_launcher(path)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_registry.py -v`
Expected: 6 PASSED(`test_migrate_from_launcher` 需要 specialk 目录可导入,本机满足)

- [ ] **Step 5: 提交**

```bash
git add backend/registry.py tests/test_registry.py
git commit -m "feat: games.yaml 注册表读写与 launcher 迁移"
```

---

### Task 3: backend/config.py — redirect_config.toml 读写

**Files:**
- Create: `backend/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `paths.RELINK_LOG_DIR`
- Produces:
  - `MODES: tuple = ("Normal", "Ringbuf", "Compat", "Bypass")`
  - `default_config() -> tomlkit.TOMLDocument`
  - `config_file(game_dir: str) -> str`
  - `load_config(game_dir: str) -> tomlkit.TOMLDocument`(文件不存在抛 FileNotFoundError;语法错误抛 tomlkit 异常,由 UI 捕获)
  - `save_config(game_dir: str, doc: tomlkit.TOMLDocument) -> None`
  - `validate(doc: tomlkit.TOMLDocument) -> list[str]`(返回问题列表,空 = 通过;`log_level != "Error"` 必报)

- [ ] **Step 1: 写失败测试**

`tests/test_config.py`:
```python
import pytest
import tomlkit
from backend.config import (MODES, default_config, config_file, load_config,
                            save_config, validate)


def test_default_config_valid():
    doc = default_config()
    assert validate(doc) == []
    assert doc["log_level"] == "Error"
    assert doc["playback"]["mode"] == "Normal"
    assert doc["capture"]["mode"] == "Bypass"


def test_round_trip_preserves_comment(tmp_path):
    text = '# 我的注释\nlog_level = "Error"\n\n[playback]\nmode = "Ringbuf"\n'
    cfg = tmp_path / "redirect_config.toml"
    cfg.write_text(text, encoding="utf-8")
    doc = load_config(str(tmp_path))
    doc["playback"]["mode"] = "Normal"
    save_config(str(tmp_path), doc)
    out = cfg.read_text(encoding="utf-8")
    assert "# 我的注释" in out
    assert 'mode = "Normal"' in out


def test_load_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(str(tmp_path))


def test_validate_rejects_bad_mode():
    doc = default_config()
    doc["playback"]["mode"] = "Turbo"
    assert any("mode" in p for p in validate(doc))


def test_validate_rejects_bad_period():
    doc = default_config()
    doc["playback"]["target_period_hus"] = 5000
    assert any("target_period_hus" in p for p in validate(doc))


def test_validate_rejects_nonpositive_buffer():
    doc = default_config()
    doc["playback"]["target_buffer_len"][48000] = 0
    assert any("target_buffer_len" in p for p in validate(doc))


def test_validate_enforces_error_log_level():
    doc = default_config()
    doc["log_level"] = "Info"
    problems = validate(doc)
    assert any("log_level" in p for p in problems)
```

注意:tomlkit 中 `target_buffer_len.48000 = 960` 解析为 `doc["playback"]["target_buffer_len"][48000]`(整数键)或字符串键 `"48000"`,实现时两者都要兼容(见下)。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL(ModuleNotFoundError: backend.config)

- [ ] **Step 3: 实现 config.py**

`backend/config.py`:
```python
"""redirect_config.toml 读写。用 tomlkit 保留注释与格式(tomllib 只读不写)。

字段规则(HANDOVER 第 3/4 节):
- log_level 常驻 Error — Info 在 overflow 时可写 GB 级日志
- mode ∈ Normal | Ringbuf | Compat | Bypass
- target_period_hus: 0 = 原生, 100 = 10ms (单位 0.1ms), 上限 1000
"""
from __future__ import annotations

import os

import tomlkit
from tomlkit import TOMLDocument

from . import paths

MODES = ("Normal", "Ringbuf", "Compat", "Bypass")

_DEFAULT_TEXT = f'''\
# wasapi_relink 配置 — 由 HapticImproveManager 生成
log_path = "{paths.RELINK_LOG_DIR.replace(os.sep, "/")}"
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


def default_config() -> TOMLDocument:
    return tomlkit.parse(_DEFAULT_TEXT)


def config_file(game_dir: str) -> str:
    return os.path.join(game_dir, "redirect_config.toml")


def load_config(game_dir: str) -> TOMLDocument:
    with open(config_file(game_dir), encoding="utf-8") as f:
        return tomlkit.parse(f.read())


def save_config(game_dir: str, doc: TOMLDocument) -> None:
    with open(config_file(game_dir), "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(doc))


def _iter_dotted(table: dict):
    """target_buffer_len.48000 在 tomlkit 里键可能是 int 48000 或 str "48000"。"""
    for k, v in table.items():
        yield k, v


def validate(doc: TOMLDocument) -> list[str]:
    problems: list[str] = []
    pb = doc.get("playback", {})

    mode = pb.get("mode")
    if mode not in MODES:
        problems.append(f"playback.mode 必须是 {'/'.join(MODES)}, 当前: {mode!r}")

    period = pb.get("target_period_hus", 100)
    if not isinstance(period, int) or not (0 <= period <= 1000):
        problems.append(f"target_period_hus 必须在 0–1000, 当前: {period!r}")

    for key in ("target_buffer_len", "ring_buffer_len"):
        sub = pb.get(key)
        if sub is None:
            continue
        for rate, frames in _iter_dotted(sub):
            if not isinstance(frames, int) or frames <= 0:
                problems.append(f"{key}.{rate} 必须是正整数帧数, 当前: {frames!r}")

    if doc.get("log_level") != "Error":
        problems.append("log_level 必须为 Error — Info 在 overflow 时可写 GB 级日志"
                        "(仅排障时临时使用)")

    return problems
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_config.py -v`
Expected: 7 PASSED。若 `doc["playback"]["target_buffer_len"][48000] = 0` 因整数键报错,把测试改为 `doc["playback"]["target_buffer_len"]["48000"] = 0`(以 tomlkit 实际键类型为准,保持实现不变)。

- [ ] **Step 5: 提交**

```bash
git add backend/config.py tests/test_config.py
git commit -m "feat: redirect_config.toml 读写与校验(tomlkit 保留注释)"
```

---

### Task 4: backend/anticheat.py — 反作弊静态扫描

**Files:**
- Create: `backend/anticheat.py`
- Test: `tests/test_anticheat.py`

**Interfaces:**
- Consumes: 无(只读目标 exe 与其所在目录)
- Produces:
  - `@dataclass AnticheatReport(risk: str, hits: list[str])`,`risk ∈ {"none", "known"}`
  - `scan_exe(path: str) -> AnticheatReport`(扫描导入表 DLL 名 + 游戏目录同目录文件名;pefile 解析失败返回 `AnticheatReport("none", [])` 并打印警告,不抛)
  - `KNOWN_SIGNATURES: dict[str, str]`(匹配子串 → 展示名)

- [ ] **Step 1: 写失败测试**

`tests/test_anticheat.py`:
```python
import os
from backend.anticheat import scan_exe, AnticheatReport, KNOWN_SIGNATURES


def test_notepad_is_clean():
    report = scan_exe(r"C:\Windows\System32\notepad.exe")
    assert report.risk == "none"
    assert report.hits == []


def test_known_signature_matching(monkeypatch, tmp_path):
    exe = tmp_path / "game.exe"
    exe.write_bytes(b"MZ")  # pefile 会解析失败 → 走 sibling 扫描
    (tmp_path / "EasyAntiCheat").mkdir()
    (tmp_path / "HoYoKProtect.sys").write_bytes(b"x")
    report = scan_exe(str(exe))
    assert report.risk == "known"
    assert any("EasyAntiCheat" in h for h in report.hits)
    assert any("HoYoKProtect" in h or "mhyprot" in h.lower() for h in report.hits)


def test_nonexistent_exe(tmp_path):
    report = scan_exe(str(tmp_path / "nope.exe"))
    assert report.risk == "none"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_anticheat.py -v`
Expected: FAIL(ModuleNotFoundError: backend.anticheat)

- [ ] **Step 3: 实现 anticheat.py**

`backend/anticheat.py`:
```python
"""反作弊静态检测: pefile 读导入表 + 扫描游戏目录同目录文件名。

命中只警告不阻止(HANDOVER 4.9: 反作弊游戏注入有封禁风险, 用户须知情确认)。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

KNOWN_SIGNATURES = {
    "easyanticheat": "EasyAntiCheat (EAC)",
    "beservice": "BattlEye (BEService)",
    "battleye": "BattlEye",
    "hoyokprotect": "HoYoKProtect (米哈游)",
    "mhyprot": "HoYoKProtect (米哈游 mhyprot)",
    "xigncode": "XIGNCODE",
    "ace-basis": "腾讯 ACE",
    "sentry": "腾讯 ACE (Sentry)",
    "nprotect": "nProtect GameGuard",
}


@dataclass
class AnticheatReport:
    risk: str                 # "none" | "known"
    hits: list[str] = field(default_factory=list)


def _imported_dll_names(path: str) -> set[str]:
    import pefile
    try:
        pe = pefile.PE(path, fast_load=True)
    except Exception:
        return set()
    try:
        pe.parse_data_directories(directories=[
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        return {e.dll.decode(errors="ignore").lower()
                for e in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])}
    except Exception:
        return set()
    finally:
        pe.close()


def _sibling_names(path: str) -> set[str]:
    try:
        return {n.lower() for n in os.listdir(os.path.dirname(path))}
    except OSError:
        return set()


def scan_exe(path: str) -> AnticheatReport:
    names = _imported_dll_names(path) | _sibling_names(path)
    hits = sorted({label for key, label in KNOWN_SIGNATURES.items()
                   if any(key in n for n in names)})
    return AnticheatReport(risk="known" if hits else "none", hits=hits)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_anticheat.py -v`
Expected: 3 PASSED

- [ ] **Step 5: 提交**

```bash
git add backend/anticheat.py tests/test_anticheat.py
git commit -m "feat: pefile 反作弊导入表/目录静态扫描"
```

---

### Task 5: backend/ifeo.py — IFEO 状态查询 + 命令构造

**Files:**
- Create: `backend/ifeo.py`
- Test: `tests/test_ifeo.py`

**Interfaces:**
- Consumes: `paths.IFEO_BASE`、`paths.IFEO_VALUE`、`paths.LAUNCHER_PY`
- Produces:
  - `class IfeoState(enum.Enum): OFF / ON_OURS / ON_OTHER`
  - `query_ifeo(exe_name: str) -> IfeoState`(读 HKLM 只读,无需管理员;winreg 调用经模块级别名便于 monkeypatch)
  - `build_ifeo_args(name: str, action: str) -> list[str]`(action ∈ {"on","off"};返回 `[sys.executable, LAUNCHER_PY, "ifeo", name, action]`)
  - 说明:实际执行走 Task 6 的 `ProcessRunner`;提权后状态异步落地,UI 轮询 `query_ifeo` 确认

- [ ] **Step 1: 写失败测试**

`tests/test_ifeo.py`:
```python
import sys
from backend import ifeo, paths
from backend.ifeo import IfeoState, query_ifeo, build_ifeo_args


class _FakeKey:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _patch_winreg(monkeypatch, value=None):
    """value=None 模拟键不存在。"""
    class FakeWinreg:
        HKEY_LOCAL_MACHINE = 0
        @staticmethod
        def OpenKey(*a, **kw):
            if value is None:
                raise FileNotFoundError
            return _FakeKey()
        @staticmethod
        def QueryValueEx(k, name):
            return value, 1
    monkeypatch.setattr(ifeo, "winreg", FakeWinreg)


def test_state_off(monkeypatch):
    _patch_winreg(monkeypatch, None)
    assert query_ifeo("DS2.exe") == IfeoState.OFF


def test_state_on_ours(monkeypatch):
    _patch_winreg(monkeypatch, paths.IFEO_VALUE)
    assert query_ifeo("DS2.exe") == IfeoState.ON_OURS


def test_state_on_other(monkeypatch):
    _patch_winreg(monkeypatch, '"C:\\other\\debugger.exe"')
    assert query_ifeo("DS2.exe") == IfeoState.ON_OTHER


def test_build_args():
    args = build_ifeo_args("ds2", "on")
    assert args[0] == sys.executable
    assert args[1] == paths.LAUNCHER_PY
    assert args[2:] == ["ifeo", "ds2", "on"]


def test_real_registry_readable():
    """真实注册表只读查询不抛异常(无需管理员)。"""
    assert query_ifeo("DS2.exe") in set(IfeoState)
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_ifeo.py -v`
Expected: FAIL(ModuleNotFoundError: backend.ifeo)

- [ ] **Step 3: 实现 ifeo.py**

`backend/ifeo.py`:
```python
"""IFEO 状态查询(只读, 无需管理员)。on/off 经 haptic_launcher CLI 执行。"""
from __future__ import annotations

import enum
import sys
import winreg  # 模块级导入, 测试用 monkeypatch 替换

from . import paths


class IfeoState(enum.Enum):
    OFF = "off"
    ON_OURS = "on_ours"      # Debugger 指向我们的 injector
    ON_OTHER = "on_other"    # Debugger 被其他调试器占用(告警)


def query_ifeo(exe_name: str) -> IfeoState:
    key_path = paths.IFEO_BASE + "\\" + exe_name
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
            val, _ = winreg.QueryValueEx(k, "Debugger")
    except FileNotFoundError:
        return IfeoState.OFF
    return IfeoState.ON_OURS if paths.IFEO_VALUE in val else IfeoState.ON_OTHER


def build_ifeo_args(name: str, action: str) -> list[str]:
    """action: "on" | "off"。launcher 内部会自行 UAC 提权。"""
    assert action in ("on", "off")
    return [sys.executable, paths.LAUNCHER_PY, "ifeo", name, action]
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_ifeo.py -v`
Expected: 5 PASSED

- [ ] **Step 5: 提交**

```bash
git add backend/ifeo.py tests/test_ifeo.py
git commit -m "feat: IFEO 状态查询(off/我方/他方)与命令构造"
```

---

### Task 6: backend/launcher.py — QProcess 进程执行器

**Files:**
- Create: `backend/launcher.py`

**Interfaces:**
- Consumes: `paths.LAUNCHER_PY`、`ifeo.build_ifeo_args`
- Produces:
  - `class ProcessRunner(QObject)`:`line = Signal(str)`(stdout/stderr 逐行,UTF-8)、`done = Signal(int)`(退出码);`start(args: list[str]) -> None`;`is_running() -> bool`;同一时刻只跑一个进程,运行中再 `start` 先 kill 旧的
  - `launch_game(runner: ProcessRunner, name: str) -> None`
  - `set_ifeo(runner: ProcessRunner, name: str, on: bool) -> None`
  - `is_game_running(exe_name: str) -> bool`(tasklist,无新依赖)

- [ ] **Step 1: 实现 launcher.py**

`backend/launcher.py`:
```python
"""QProcess 子进程执行器 — GUI 与 haptic_launcher CLI 的唯一通道。

强制 PYTHONIOENCODING=utf-8, 否则 Windows 控制台 GBK 输出会解码失败。
"""
from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from . import ifeo, paths


class ProcessRunner(QObject):
    line = Signal(str)
    done = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        self._proc.setProcessEnvironment(env)
        self._proc.readyReadStandardOutput.connect(self._emit)
        self._proc.readyReadStandardError.connect(self._emit)
        self._proc.finished.connect(lambda code, _status: self.done.emit(code))

    def start(self, args: list[str]) -> None:
        if self.is_running():
            self._proc.kill()
            self._proc.waitForFinished(1000)
        self._proc.start(args[0], args[1:])

    def is_running(self) -> bool:
        return self._proc.state() != QProcess.ProcessState.NotRunning

    def _emit(self):
        for chunk in (bytes(self._proc.readAllStandardOutput()),
                      bytes(self._proc.readAllStandardError())):
            for ln in chunk.decode("utf-8", errors="replace").splitlines():
                if ln.strip():
                    self.line.emit(ln)


def launch_game(runner: ProcessRunner, name: str) -> None:
    runner.start([sys.executable, paths.LAUNCHER_PY, name])


def set_ifeo(runner: ProcessRunner, name: str, on: bool) -> None:
    runner.start(ifeo.build_ifeo_args(name, "on" if on else "off"))


def is_game_running(exe_name: str) -> bool:
    """tasklist 查进程, 无第三方依赖。"""
    out = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
        capture_output=True, text=True).stdout
    return exe_name.lower() in out.lower()
```

- [ ] **Step 2: 手动验证(交互脚本,不进 pytest)**

写一个临时脚本 `verify_runner.py`(验证后删除):
```python
import sys
from PySide6.QtCore import QCoreApplication, QTimer
from backend.launcher import ProcessRunner

app = QCoreApplication(sys.argv)
r = ProcessRunner()
r.line.connect(lambda ln: print("LINE:", ln))
r.done.connect(lambda code: (print("DONE:", code), app.quit()))
r.start([sys.executable, "-c", "print('你好 haptic')"])
QTimer.singleShot(5000, app.quit)  # 兜底退出
app.exec()
```

Run: `python verify_runner.py`
Expected: 输出 `LINE: 你好 haptic` 和 `DONE: 0`,无乱码。验证后删除脚本。

- [ ] **Step 3: 提交**

```bash
git add backend/launcher.py
git commit -m "feat: QProcess 子进程执行器(launcher/ifeo 通道)"
```

---

### Task 7: backend/monitor.py — 日志读取与监视

**Files:**
- Create: `backend/monitor.py`
- Test: `tests/test_monitor.py`

**Interfaces:**
- Consumes: `paths.INJECTOR_RESULT / INJECTOR_DEBUG_LOG / RELINK_LOG`
- Produces:
  - `tail(path: str, n: int = 50) -> list[str]`(文件不存在返回 `[]`;按行尾utf-8 errors=replace)
  - `read_result(path: str = paths.INJECTOR_RESULT) -> tuple[datetime | None, str]`(mtime + 全文 strip;不存在返回 `(None, "")`)
  - `class LogWatcher(QObject)`:`file_changed = Signal(str)`;`watch(paths: list[str]) -> None`;变更后若文件被重建则自动重挂监视(QFileSystemWatcher 在文件替换后可能丢监视)

- [ ] **Step 1: 写失败测试**

`tests/test_monitor.py`:
```python
import os
from backend.monitor import tail, read_result


def test_tail_last_n(tmp_path):
    p = tmp_path / "log.txt"
    p.write_text("\n".join(f"line{i}" for i in range(100)), encoding="utf-8")
    lines = tail(str(p), 5)
    assert lines == ["line95", "line96", "line97", "line98", "line99"]


def test_tail_missing_file(tmp_path):
    assert tail(str(tmp_path / "nope.log")) == []


def test_tail_utf8(tmp_path):
    p = tmp_path / "log.txt"
    p.write_text("注入成功 ✓\n第二行\n", encoding="utf-8")
    assert tail(str(p), 1) == ["第二行"]


def test_read_result(tmp_path):
    p = tmp_path / "injector_result.txt"
    p.write_text("injected OK (module handle 0x7ff)\n", encoding="utf-8")
    mtime, text = read_result(str(p))
    assert mtime is not None
    assert text.startswith("injected OK")


def test_read_result_missing(tmp_path):
    mtime, text = read_result(str(tmp_path / "none.txt"))
    assert mtime is None and text == ""
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_monitor.py -v`
Expected: FAIL(ModuleNotFoundError: backend.monitor)

- [ ] **Step 3: 实现 monitor.py**

`backend/monitor.py`:
```python
"""日志读取(tail / 最近注入结果)与 QFileSystemWatcher 包装。"""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import QFileSystemWatcher, QObject, Signal

from . import paths


def tail(path: str, n: int = 50) -> list[str]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()[-n:]


def read_result(path: str = paths.INJECTOR_RESULT) -> tuple[datetime | None, str]:
    if not os.path.isfile(path):
        return None, ""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read().strip()
    return datetime.fromtimestamp(os.path.getmtime(path)), text


class LogWatcher(QObject):
    """监视日志文件; 文件被删除重建后自动重挂(QFileSystemWatcher 会丢监视)。"""
    file_changed = Signal(str)

    def __init__(self, watch_paths: list[str], parent=None):
        super().__init__(parent)
        self._paths = list(watch_paths)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_changed)
        for p in self._paths:
            if os.path.isfile(p):
                self._watcher.addPath(p)

    def _on_changed(self, path: str):
        if path not in self._watcher.files() and os.path.isfile(path):
            self._watcher.addPath(path)
        self.file_changed.emit(path)
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_monitor.py -v`
Expected: 5 PASSED(LogWatcher 不进 pytest,UI 联调时验证)

- [ ] **Step 5: 提交**

```bash
git add backend/monitor.py tests/test_monitor.py
git commit -m "feat: 日志 tail/最近注入结果读取与文件监视器"
```

---

### Task 8: 改造 haptic_launcher.py 读 games.yaml + 生成初始注册表

**Files:**
- Modify: `C:\Users\ZhuTT\Workspace\specialk\haptic_launcher.py`(GAMES 定义后加 `load_games()`,三处用法改写)

**Interfaces:**
- Consumes: Task 2 的 `registry.migrate_from_launcher`
- Produces: `specialk/games.yaml`(由迁移函数生成);`haptic_launcher.load_games() -> dict[str, str]`(name → exe 路径)

- [ ] **Step 1: 修改 haptic_launcher.py**

在 `GAMES = {...}` 字典之后插入:
```python
GAMES_YAML = os.path.join(HERE, "games.yaml")


def load_games() -> dict:
    """games.yaml 存在则以它为准(GUI 与 CLI 共用单一数据源),
    否则回落到上方硬编码 GAMES。"""
    if os.path.exists(GAMES_YAML):
        import yaml
        with open(GAMES_YAML, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {name: entry["exe"]
                for name, entry in (data.get("games") or {}).items()}
    return GAMES
```

三处用法改写:
1. `ifeo()` 内 `exe = GAMES[name]` → `exe = load_games()[name]`
2. `main()` 的 `ifeo` 分支 `if name not in GAMES:` → `if name not in load_games():`
3. `main()` 的 list 分支 `for name, path in GAMES.items():` → `for name, path in load_games().items():`
4. `main()` 末尾 `name = sys.argv[1].lower()` 之后 `if name not in GAMES:` → `load_games()`;`exe = GAMES[name]` → `exe = load_games()[name]`(合并为函数开头 `games = load_games()` 一次调用亦可,保持改动最小则逐处替换)

- [ ] **Step 2: 生成 games.yaml 并验证 CLI 行为不变**

Run:
```
python -c "from backend.registry import migrate_from_launcher; migrate_from_launcher()"
type "C:\Users\ZhuTT\Workspace\specialk\games.yaml"
python "C:\Users\ZhuTT\Workspace\specialk\haptic_launcher.py" list
python "C:\Users\ZhuTT\Workspace\specialk\haptic_launcher.py" ifeo ds2 status
```
Expected: yaml 含 ds2/sb/zzz 三个游戏及经验值;`list` 输出三个游戏且 exe 均 `[OK]`;`ifeo ds2 status` 显示 `IFEO ON`(与迁移前一致)。

注意:不要运行 `ifeo on/off`(会改动注册表),只查 status。

- [ ] **Step 3: 提交(HapticImporveManager 仓库只记测试)**

`games.yaml` 在 specialk 目录(非本仓库),不提交。本任务在 HapticImporveManager 仓库无文件变更则跳过提交;若修改了 registry.py 则提交。

---

### Task 9: app.py + 主窗口骨架(导航 + 占位页)

**Files:**
- Create: `app.py`
- Create: `ui/main_window.py`

**Interfaces:**
- Consumes: 无(占位页,Task 10/12/13 替换)
- Produces:
  - `class MainWindow(QMainWindow)`,左导航 `QListWidget`(固定宽 140,项:`游戏` / `配置编辑` / `状态监控`)+ 右 `QStackedWidget`;`nav.currentRowChanged` → `setCurrentIndex`
  - `app.main()` 入口
  - 后续任务约定:占位页按索引替换——0=GamesPage, 1=ConfigEditorPage, 2=MonitorPage

- [ ] **Step 1: 实现 main_window.py**

`ui/main_window.py`:
```python
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QMainWindow,
                               QStackedWidget, QWidget)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Haptic 低延迟管理器")
        self.resize(1000, 640)

        self.nav = QListWidget()
        self.nav.setFixedWidth(140)
        self.nav.addItems(["游戏", "配置编辑", "状态监控"])

        self.pages = QStackedWidget()
        # 占位页, 后续任务按索引替换为真实页面
        self.pages.addWidget(QLabel("游戏列表(待实现)"))
        self.pages.addWidget(QLabel("配置编辑(待实现)"))
        self.pages.addWidget(QLabel("状态监控(待实现)"))

        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.nav)
        lay.addWidget(self.pages, 1)
        self.setCentralWidget(central)

    def replace_page(self, index: int, widget: QWidget):
        old = self.pages.widget(index)
        self.pages.removeWidget(old)
        old.deleteLater()
        self.pages.insertWidget(index, widget)
```

- [ ] **Step 2: 实现 app.py**

`app.py`:
```python
import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("HapticImproveManager")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 手动验证**

Run: `python app.py`
Expected: 窗口弹出,左侧三项导航,点击切换右侧占位文本;关闭正常退出。

- [ ] **Step 4: 提交**

```bash
git add app.py ui/main_window.py
git commit -m "feat: 主窗口骨架(导航 + 占位页)"
```

---

### Task 10: 游戏列表页(卡片 + IFEO 开关 + 启动/移除)

**Files:**
- Create: `ui/games_page.py`
- Modify: `ui/main_window.py`(索引 0 替换为 GamesPage)

**Interfaces:**
- Consumes: `registry.load_or_migrate / remove_game`、`ifeo.query_ifeo / IfeoState`、`launcher.ProcessRunner / launch_game / set_ifeo`、`monitor`(不需要)
- Produces:
  - `class GamesPage(QWidget)`,信号 `edit_requested = Signal(str)`(游戏名,主窗口连到配置编辑页切换)、`log_line = Signal(str)`(转发 ProcessRunner 输出,供监控页可选使用)
  - `refresh()` 公开方法(主窗口切回本页时重查状态)

**卡片状态灯逻辑:** 绿 = `exe_exists and config_exists and ifeo==ON_OURS`;黄 = 三者缺一或 `ON_OTHER`;红 = `not exe_exists`。

**IFEO 切换流程:** 点击复选框 → `set_ifeo(runner, name, on)` → launcher 内部 UAC → 用 `QTimer` 每 1s 轮询 `query_ifeo`,最多 10s;超时未变提示"提权被取消或失败",复选框回弹到实际状态(`setCheckState` 前用 `blockSignals`)。

- [ ] **Step 1: 实现 games_page.py**

`ui/games_page.py`:
```python
import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from backend import ifeo, launcher, registry
from backend.ifeo import IfeoState

_LAMP_STYLE = "border-radius:7px; min-width:14px; max-width:14px; min-height:14px; max-height:14px; background:%s;"


class GameCard(QFrame):
    edit_requested = Signal(str)
    removed = Signal()

    def __init__(self, entry: registry.GameEntry, runner: launcher.ProcessRunner,
                 parent=None):
        super().__init__(parent)
        self.entry = entry
        self.runner = runner
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(280)

        self.lamp = QLabel()
        title = QLabel(f"<b>{entry.name}</b>")
        path = QLabel(entry.exe)
        path.setToolTip(entry.exe)
        path.setStyleSheet("color:#888;")
        path.setMaximumWidth(260)

        hint = QLabel(f"模式 {entry.mode_hint} · 缓冲 {entry.buffer_hint}"
                      + (" · ⚠ 反作弊" if entry.anticheat else ""))
        self.ifeo_box = QCheckBox("IFEO 自动注入")
        self.ifeo_box.toggled.connect(self._on_ifeo_toggled)

        btn_launch = QPushButton("启动")
        btn_launch.clicked.connect(self._launch)
        btn_edit = QPushButton("编辑配置")
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(entry.name))
        btn_remove = QPushButton("移除")
        btn_remove.clicked.connect(self._remove)
        self._btn_launch = btn_launch

        top = QHBoxLayout()
        top.addWidget(self.lamp)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.ifeo_box)
        btns = QHBoxLayout()
        for b in (btn_launch, btn_edit, btn_remove):
            btns.addWidget(b)
        btns.addStretch(1)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(path)
        lay.addWidget(hint)
        lay.addLayout(btns)

        self.refresh_status()

    def refresh_status(self):
        e = self.entry
        state = ifeo.query_ifeo(os.path.basename(e.exe))
        if not e.exe_exists:
            color, tip = "#e5484d", "exe 丢失"
        elif e.config_exists and state == IfeoState.ON_OURS:
            color, tip = "#30a46c", "就绪"
        else:
            color, tip = "#f5b942", "配置/IFEO 未完成"
        if state == IfeoState.ON_OTHER:
            tip += "(IFEO 被其他调试器占用!)"
        self.lamp.setStyleSheet(_LAMP_STYLE % color)
        self.lamp.setToolTip(tip)
        self.ifeo_box.blockSignals(True)
        self.ifeo_box.setChecked(state == IfeoState.ON_OURS)
        self.ifeo_box.blockSignals(False)
        self._btn_launch.setEnabled(e.exe_exists)

    def _on_ifeo_toggled(self, checked: bool):
        launcher.set_ifeo(self.runner, self.entry.name, checked)
        self._poll_count = 0
        self._poll = QTimer(self)
        self._poll.setInterval(1000)
        self._poll.timeout.connect(self._poll_ifeo)
        self._poll.start()

    def _poll_ifeo(self):
        self._poll_count += 1
        state = ifeo.query_ifeo(os.path.basename(self.entry.exe))
        want = IfeoState.ON_OURS if self.ifeo_box.isChecked() else IfeoState.OFF
        if state == want or self._poll_count >= 10:
            self._poll.stop()
            if state != want:
                QMessageBox.warning(self, "IFEO", "提权被取消或操作失败, 状态未变更")
            self.refresh_status()

    def _launch(self):
        launcher.launch_game(self.runner, self.entry.name)

    def _remove(self):
        if QMessageBox.question(self, "移除游戏",
                                f"从注册表移除 {self.entry.name}?"
                                "(不动游戏文件和 IFEO)") == QMessageBox.StandardButton.Yes:
            registry.remove_game(self.entry.name)
            self.removed.emit()


class GamesPage(QWidget):
    edit_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.runner = launcher.ProcessRunner(self)
        self._cards_area = QWidget()
        self._grid = QGridLayout(self._cards_area)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._cards_area)
        lay = QVBoxLayout(self)
        lay.addWidget(scroll)
        self.refresh()

    def refresh(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        games = registry.load_or_migrate()
        for i, entry in enumerate(games.values()):
            card = GameCard(entry, self.runner)
            card.edit_requested.connect(self.edit_requested)
            card.removed.connect(self.refresh)
            self._grid.addWidget(card, i // 3, i % 3)
```

- [ ] **Step 2: 接入主窗口**

`ui/main_window.py` 顶部加 `from ui.games_page import GamesPage`,`__init__` 中三行占位页之后加:
```python
        self.games_page = GamesPage()
        self.replace_page(0, self.games_page)
```
(`replace_page` 在 Task 9 已定义。)

- [ ] **Step 3: 手动验证**

Run: `python app.py`
Expected:
- 显示 ds2/sb/zzz 三张卡片,ds2 卡片 hint 行显示"模式 Ringbuf · 缓冲 2048",zzz 显示"⚠ 反作弊"
- 三卡 IFEO 复选框为勾选状态(交接文档:三者 IFEO 均已启用)、灯为绿/黄(取决于 redirect_config.toml 是否存在)
- 点"启动"启动 ds2(会真拉起游戏+注入,可选验证);不想拉起游戏则只验证 UI 状态
- **不要**在验证时点 IFEO 复选框(会真改注册表),如需验证先 off 再 on 并确认 `haptic_launcher.py ifeo ds2 status` 结果

- [ ] **Step 4: 提交**

```bash
git add ui/games_page.py ui/main_window.py
git commit -m "feat: 游戏卡片列表页(状态灯/IFEO 开关/启动/移除)"
```

---

### Task 11: 添加游戏向导(4 步 QWizard)

**Files:**
- Create: `ui/add_wizard.py`
- Modify: `ui/games_page.py`(顶部加"添加游戏"按钮,弹向导,接受后 `refresh()`)

**Interfaces:**
- Consumes: `anticheat.scan_exe`、`config.default_config / save_config / MODES`、`registry.add_game / load_or_migrate`、`launcher.ProcessRunner / set_ifeo`、`ifeo.query_ifeo`
- Produces: `class AddGameWizard(QWizard)`;`exec()` 接受后游戏已入 `games.yaml`

**4 页:**
1. `PageExe`:注册名输入(`QLineEdit`,正则 `[a-z0-9_]+`)+ exe 选择(`QFileDialog.getOpenFileName`);`isComplete` 两者非空且注册名未被占用
2. `PageAnticheat`:`initializePage` 时跑 `scan_exe`;命中 → 红字列 hits + 风险说明(HANDOVER 4.9)+ "我已了解注入风险"复选框,勾选才能 Next;未命中 → 绿字直接过
3. `PageConfig`:模式下拉(MODES)+ 缓冲 `QSpinBox`(1–8192,默认 960)+ "生成 redirect_config.toml"说明;`validatePage` 时若文件已存在弹"保留/覆盖"询问,覆盖则 `save_config(game_dir, default_config())` 并写入所选 mode/缓冲
4. `PageIfeo`:按钮"启用 IFEO 自动注入"(`set_ifeo` + 轮询同 Task 10)+ 状态标签;完成页文案"之后从 Steam/启动器正常启动即自动注入"

`accept` 时 `add_game(GameEntry(name, exe, mode, buffer, anticheat=(risk=="known")))`。

- [ ] **Step 1: 实现 add_wizard.py**

`ui/add_wizard.py`:
```python
import os
import re

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QSpinBox, QVBoxLayout, QWizard,
                               QWizardPage)

from backend import anticheat, config, ifeo, launcher, registry
from backend.ifeo import IfeoState

_NAME_RE = re.compile(r"^[a-z0-9_]+$")


class PageExe(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("选择游戏")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("注册名, 小写字母/数字/下划线, 如 ds2")
        self.exe_edit = QLineEdit()
        self.exe_edit.setReadOnly(True)
        btn = QPushButton("浏览…")
        btn.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.exe_edit, 1)
        row.addWidget(btn)
        lay = QFormLayout(self)
        lay.addRow("注册名", self.name_edit)
        lay.addRow("游戏 exe", row)
        self.registerField("game_name*", self.name_edit)
        self.registerField("game_exe*", self.exe_edit)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择游戏 exe", "", "Executables (*.exe)")
        if path:
            self.exe_edit.setText(path)

    def validatePage(self):
        name = self.name_edit.text().strip()
        if not _NAME_RE.match(name):
            QMessageBox.warning(self, "注册名", "仅限小写字母/数字/下划线")
            return False
        if name in registry.load_or_migrate():
            QMessageBox.warning(self, "注册名", f"'{name}' 已被占用")
            return False
        return True


class PageAnticheat(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("反作弊检测")
        self.result = QLabel()
        self.result.setWordWrap(True)
        self.ack = QCheckBox("我已了解: 反作弊游戏注入有封禁风险, 后果自负")
        lay = QVBoxLayout(self)
        lay.addWidget(self.result)
        lay.addWidget(self.ack)

    def initializePage(self):
        exe = self.field("game_exe")
        self.report = anticheat.scan_exe(exe)
        if self.report.risk == "known":
            self.result.setStyleSheet("color:#e5484d;")
            self.result.setText(
                "检测到反作弊特征:\n· " + "\n· ".join(self.report.hits) +
                "\n\n已知风险: HoYoKProtect 会剥离 OpenProcess 句柄并改名外来 DLL。"
                "本工具采用父进程注入可绕过句柄剥离, 但仍有账号风险。")
            self.ack.setChecked(False)
            self.ack.show()
        else:
            self.result.setStyleSheet("color:#30a46c;")
            self.result.setText("未检测到已知反作弊特征。")
            self.ack.hide()

    def isComplete(self):
        return self.report.risk != "known" or self.ack.isChecked()


class PageConfig(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("生成 redirect_config.toml")
        self.mode = QComboBox()
        self.mode.addItems(config.MODES)
        self.buf = QSpinBox()
        self.buf.setRange(1, 8192)
        self.buf.setValue(960)
        note = QLabel("Normal: 大多数游戏可用, 缓冲过小会破音\n"
                      "Ringbuf: DS2 需要; UE5 爆发写入会溢出刷屏; ZZZ 丢扬声器声道\n"
                      "每个游戏必须单独试, 没有通用最优解")
        note.setStyleSheet("color:#888;")
        note.setWordWrap(True)
        lay = QFormLayout(self)
        lay.addRow("模式", self.mode)
        lay.addRow("缓冲帧数", self.buf)
        lay.addRow(note)

    def validatePage(self):
        game_dir = os.path.dirname(self.field("game_exe"))
        cfg_path = config.config_file(game_dir)
        if os.path.isfile(cfg_path):
            r = QMessageBox.question(
                self, "配置已存在",
                "redirect_config.toml 已存在, 覆盖?\n(选 No 保留现有配置)")
            if r != QMessageBox.StandardButton.Yes:
                return True
        doc = config.default_config()
        doc["playback"]["mode"] = self.mode.currentText()
        doc["playback"]["target_buffer_len"][48000] = self.buf.value()
        config.save_config(game_dir, doc)
        return True


class PageIfeo(QWizardPage):
    def __init__(self, runner: launcher.ProcessRunner):
        super().__init__()
        self.setTitle("启用 IFEO 自动注入")
        self.runner = runner
        self.status = QLabel("点击按钮启用(会弹 UAC 提权框)")
        self.status.setWordWrap(True)
        btn = QPushButton("启用 IFEO")
        btn.clicked.connect(self._enable)
        lay = QVBoxLayout(self)
        lay.addWidget(self.status)
        lay.addWidget(btn)
        note = QLabel("完成后从 Steam/启动器正常启动游戏即自动注入。")
        note.setStyleSheet("color:#888;")
        lay.addWidget(note)

    def _enable(self):
        launcher.set_ifeo(self.runner, self.field("game_name"), True)
        self._poll_count = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self.status.setText("等待提权与注册表写入…")

    def _poll(self):
        self._poll_count += 1
        exe_name = os.path.basename(self.field("game_exe"))
        state = ifeo.query_ifeo(exe_name)
        if state == IfeoState.ON_OURS:
            self._timer.stop()
            self.status.setText("✓ IFEO 已启用")
        elif self._poll_count >= 10:
            self._timer.stop()
            self.status.setText("✗ 提权被取消或失败, 可稍后在游戏列表页重试")


class AddGameWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加游戏")
        self.runner = launcher.ProcessRunner(self)
        self.addPage(PageExe())
        self.addPage(PageAnticheat())
        self.addPage(PageConfig())
        self.addPage(PageIfeo())

    def accept(self):
        registry.add_game(registry.GameEntry(
            name=self.field("game_name"),
            exe=self.field("game_exe"),
            mode_hint=self.page(2).mode.currentText(),
            buffer_hint=self.page(2).buf.value(),
            anticheat=self.page(1).report.risk == "known",
        ))
        super().accept()
```

- [ ] **Step 2: games_page.py 加"添加游戏"按钮**

`GamesPage.__init__` 中 `lay.addWidget(scroll)` 之前加:
```python
        btn_add = QPushButton("＋ 添加游戏")
        btn_add.clicked.connect(self._add_wizard)
        lay.addWidget(btn_add)
```
方法:
```python
    def _add_wizard(self):
        from ui.add_wizard import AddGameWizard
        if AddGameWizard(self).exec():
            self.refresh()
```

- [ ] **Step 3: 手动验证**

Run: `python app.py` → 点"＋ 添加游戏"
Expected:
- 用 notepad.exe 走一遍:注册名 `testnp`,反作弊页绿色通过,配置生成,IFEO 页**不点启用**(notepad 无需注入),直接 Finish;列表出现 testnp 卡片
- 验证后移除 testnp 卡片
- 再走到 PageAnticheat 时选 ZZZ 的 exe(不完成向导,Cancel 退出),确认红色警告与知情复选框出现

- [ ] **Step 4: 提交**

```bash
git add ui/add_wizard.py ui/games_page.py
git commit -m "feat: 添加游戏四步向导(exe/反作弊/配置/IFEO)"
```

---

### Task 12: 配置编辑页

**Files:**
- Create: `ui/config_editor.py`
- Modify: `ui/main_window.py`(索引 1 替换;GamesPage.edit_requested → 切页并选中游戏)

**Interfaces:**
- Consumes: `registry.load_or_migrate`、`config.load_config / save_config / default_config / validate / MODES / config_file`、`launcher.is_game_running`
- Produces: `class ConfigEditorPage(QWidget)`,`select_game(name: str) -> None` 公开方法

**行为:**
- 顶栏游戏下拉(无配置文件的条目标注"无配置")
- 载入失败(tomlkit 语法错误)→ 显示原始文本(只读 `QPlainTextEdit`)+ 错误信息,禁用表单与保存
- 字段:模式下拉、`target_period_hus` 滑块(0–1000 + 数值标签,显示换算 ms=值/10)、`target_buffer_len.48000` 与 `ring_buffer_len.48000` 两个 `QSpinBox`(按当前模式启用对应一个)、`raw`/`force_period` 复选框、`log_level` 下拉(默认锁定 Error;选 Info 时 `QMessageBox.warning` 强确认,取消则回弹 Error)
- 保存:`validate(doc)` 非空 → 弹问题列表不保存;游戏运行中(`is_game_running(os.path.basename(exe))`)→ 保存后提示"重启游戏后生效"
- "恢复默认"按钮:确认后用 `default_config()` 覆盖表单(不直接写盘,需再点保存)

- [ ] **Step 1: 实现 config_editor.py**

`ui/config_editor.py`:
```python
import os

import tomlkit
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout,
                               QLabel, QMessageBox, QPlainTextEdit, QPushButton,
                               QSlider, QSpinBox, QVBoxLayout, QWidget)

from backend import config, launcher, registry


class ConfigEditorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.games: dict[str, registry.GameEntry] = {}
        self.doc = None

        self.game_box = QComboBox()
        self.game_box.currentTextChanged.connect(self._load)

        self.mode = QComboBox()
        self.mode.addItems(config.MODES)
        self.mode.currentTextChanged.connect(self._on_mode_changed)
        self.period = QSlider(Qt.Orientation.Horizontal)
        self.period.setRange(0, 1000)
        self.period.setValue(100)
        self.period_label = QLabel("10.0 ms")
        self.period.valueChanged.connect(
            lambda v: self.period_label.setText(
                "原生" if v == 0 else f"{v / 10:.1f} ms"))
        period_row = QHBoxLayout()
        period_row.addWidget(self.period, 1)
        period_row.addWidget(self.period_label)

        self.buf_normal = QSpinBox()
        self.buf_normal.setRange(1, 65536)
        self.buf_ring = QSpinBox()
        self.buf_ring.setRange(1, 65536)
        self.raw = QCheckBox("raw")
        self.force_period = QCheckBox("force_period")
        self.log_level = QComboBox()
        self.log_level.addItems(["Error", "Info"])
        self.log_level.currentTextChanged.connect(self._on_log_level)

        self.form = QFormLayout()
        self.form.addRow("模式", self.mode)
        self.form.addRow("目标周期", period_row)
        self.form.addRow("Normal 缓冲帧数", self.buf_normal)
        self.form.addRow("Ringbuf 虚拟缓冲帧数", self.buf_ring)
        self.form.addRow(self.raw)
        self.form.addRow(self.force_period)
        self.form.addRow("日志级别", self.log_level)

        self.mode_hint = QLabel()
        self.mode_hint.setWordWrap(True)
        self.mode_hint.setStyleSheet("color:#888;")

        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save)
        btn_default = QPushButton("恢复默认")
        btn_default.clicked.connect(self._reset_default)
        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_default)
        btn_row.addStretch(1)

        self.error_view = QPlainTextEdit()
        self.error_view.setReadOnly(True)
        self.error_view.hide()

        self.form_host = QWidget()
        self.form_host.setLayout(self.form)

        lay = QVBoxLayout(self)
        lay.addWidget(self.game_box)
        lay.addWidget(self.form_host)
        lay.addWidget(self.mode_hint)
        lay.addLayout(btn_row)
        lay.addWidget(self.error_view, 1)

        self.reload_games()

    def reload_games(self):
        self.games = registry.load_or_migrate()
        self.game_box.blockSignals(True)
        self.game_box.clear()
        for name, e in self.games.items():
            self.game_box.addItem(name + ("" if e.config_exists else " (无配置)"))
        self.game_box.blockSignals(False)
        if self.games:
            self._load(self.game_box.currentText())

    def select_game(self, name: str):
        self.reload_games()
        for i in range(self.game_box.count()):
            if self.game_box.itemText(i).startswith(name):
                self.game_box.setCurrentIndex(i)
                break

    def _entry(self) -> registry.GameEntry:
        return self.games[self.game_box.currentText().split(" ")[0]]

    def _load(self, _text: str):
        entry = self._entry()
        try:
            self.doc = config.load_config(entry.game_dir)
        except FileNotFoundError:
            if QMessageBox.question(
                    self, "无配置",
                    f"{entry.name} 没有 redirect_config.toml, 生成默认配置?"
                    ) == QMessageBox.StandardButton.Yes:
                self.doc = config.default_config()
                config.save_config(entry.game_dir, self.doc)
            else:
                return
        except Exception as e:  # tomlkit 语法错误: 显示原文, 禁表单
            self.form_host.setEnabled(False)
            self.error_view.show()
            self.error_view.setPlainText(
                f"配置解析失败: {e}\n\n"
                + open(entry.config_path, encoding="utf-8").read())
            return
        self.error_view.hide()
        self.form_host.setEnabled(True)
        pb = self.doc.get("playback", {})
        self.mode.setCurrentText(pb.get("mode", "Normal"))
        self.period.setValue(int(pb.get("target_period_hus", 100)))
        tbl = pb.get("target_buffer_len", {})
        self.buf_normal.setValue(int(next(iter(tbl.values()), 960)))
        rbl = pb.get("ring_buffer_len", {})
        self.buf_ring.setValue(int(next(iter(rbl.values()), 4320)))
        self.raw.setChecked(bool(pb.get("raw", True)))
        self.force_period.setChecked(bool(pb.get("force_period", True)))
        self.log_level.blockSignals(True)
        self.log_level.setCurrentText(self.doc.get("log_level", "Error"))
        self.log_level.blockSignals(False)
        self._on_mode_changed(self.mode.currentText())

    def _on_mode_changed(self, mode: str):
        self.buf_normal.setEnabled(mode == "Normal")
        self.buf_ring.setEnabled(mode == "Ringbuf")
        hints = {
            "Normal": "游戏直接面对真实小缓冲。大多数游戏可用(剑星/ZZZ 验证), 缓冲过小会破音。",
            "Ringbuf": "给游戏虚拟大缓冲。DS2 需要它; UE5 大爆发写入会溢出刷屏; ZZZ 丢手柄扬声器声道。",
            "Compat": "兼容模式, 遇到问题再试。",
            "Bypass": "不干预, 原生延迟。",
        }
        self.mode_hint.setText(hints.get(mode, ""))

    def _on_log_level(self, level: str):
        if level != "Error":
            r = QMessageBox.warning(
                self, "日志级别",
                "Info 在 overflow 时可写 GB 级日志(实测一次会话 2.9GB)。\n"
                "仅排障临时使用, 确定切换?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if r != QMessageBox.StandardButton.Ok:
                self.log_level.blockSignals(True)
                self.log_level.setCurrentText("Error")
                self.log_level.blockSignals(False)

    def _reset_default(self):
        if QMessageBox.question(self, "恢复默认",
                                "用默认配置覆盖当前表单?(未保存)") \
                == QMessageBox.StandardButton.Yes:
            self.doc = config.default_config()
            pb = self.doc["playback"]
            self.mode.setCurrentText(pb["mode"])
            self.period.setValue(pb["target_period_hus"])
            self.buf_normal.setValue(960)
            self.buf_ring.setValue(4320)
            self.raw.setChecked(True)
            self.force_period.setChecked(True)
            self.log_level.setCurrentText("Error")

    def _save(self):
        if self.doc is None:
            return
        entry = self._entry()
        pb = self.doc["playback"]
        pb["mode"] = self.mode.currentText()
        pb["target_period_hus"] = self.period.value()
        key = next(iter(pb.get("target_buffer_len", {48000: None}).keys()), 48000)
        pb["target_buffer_len"] = {key: self.buf_normal.value()}
        rkey = next(iter(pb.get("ring_buffer_len", {48000: None}).keys()), 48000)
        pb["ring_buffer_len"] = {rkey: self.buf_ring.value()}
        pb["raw"] = self.raw.isChecked()
        pb["force_period"] = self.force_period.isChecked()
        self.doc["log_level"] = self.log_level.currentText()

        problems = config.validate(self.doc)
        if problems:
            QMessageBox.warning(self, "校验失败", "\n".join(problems))
            return
        config.save_config(entry.game_dir, self.doc)
        msg = "已保存。"
        if launcher.is_game_running(os.path.basename(entry.exe)):
            msg += "\n游戏正在运行, 重启后生效。"
        QMessageBox.information(self, "保存", msg)
```

- [ ] **Step 2: 接入主窗口 + 联动**

`ui/main_window.py` 顶部加 `from ui.config_editor import ConfigEditorPage`;`__init__` 中 games_page 接入后加:
```python
        self.config_page = ConfigEditorPage()
        self.replace_page(1, self.config_page)
        self.games_page.edit_requested.connect(self._goto_config)
```
方法:
```python
    def _goto_config(self, name: str):
        self.config_page.select_game(name)
        self.nav.setCurrentRow(1)
```

- [ ] **Step 3: 手动验证**

Run: `python app.py` → 配置编辑页
Expected:
- 下拉显示 ds2/sb/zzz;选 ds2 载入其真实配置,模式/缓冲值与文件一致
- 模式切 Ringbuf → Normal 缓冲框禁用、Ringbuf 框启用,提示文字切换
- 日志级别选 Info → 弹强确认,取消则回弹 Error
- 改一个缓冲值点保存 → 打开游戏目录 `redirect_config.toml` 确认已写且注释保留
- 从游戏卡片点"编辑配置"→ 自动跳到配置页并选中该游戏

- [ ] **Step 4: 提交**

```bash
git add ui/config_editor.py ui/main_window.py
git commit -m "feat: redirect_config.toml 可视化编辑页(模式/缓冲/日志级别)"
```

---

### Task 13: 状态监控页

**Files:**
- Create: `ui/monitor_page.py`
- Modify: `ui/main_window.py`(索引 2 替换)

**Interfaces:**
- Consumes: `monitor.tail / read_result / LogWatcher`、`paths.INJECTOR_RESULT / INJECTOR_DEBUG_LOG / RELINK_LOG`
- Produces: `class MonitorPage(QWidget)`;`append_event(text: str)` 公开方法(供主窗口转发 GamesPage 的 runner 输出)

**布局:**
- 顶部"最近注入"卡片:`read_result()` 的 mtime + 文本;含 `injected OK` → 绿字,含 `failed` → 红字,空 → 灰"暂无注入记录"
- 中部 `injector_debug.log` 尾随(`QPlainTextEdit` 只读,初载 tail 50 行,变更时增量重读 tail 并整体替换,自动滚底)
- 底部 `wasapi_relink.log` 尾随,默认折叠(`QPushButton` 切换 visibility)
- `LogWatcher` 监视两文件 + `injector_result.txt`;`file_changed` → 对应刷新

- [ ] **Step 1: 实现 monitor_page.py**

`ui/monitor_page.py`:
```python
from PySide6.QtWidgets import (QLabel, QPlainTextEdit, QPushButton,
                               QVBoxLayout, QWidget)

from backend import monitor, paths


class MonitorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)

        self.debug_view = QPlainTextEdit()
        self.debug_view.setReadOnly(True)
        self.debug_view.setMaximumBlockCount(500)

        self.relink_view = QPlainTextEdit()
        self.relink_view.setReadOnly(True)
        self.relink_view.setMaximumBlockCount(500)
        self.relink_view.hide()
        self.btn_toggle = QPushButton("▸ wasapi_relink.log(排障用)")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.toggled.connect(self._toggle_relink)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>最近注入</b>"))
        lay.addWidget(self.result_label)
        lay.addWidget(QLabel("<b>injector_debug.log</b>"))
        lay.addWidget(self.debug_view, 1)
        lay.addWidget(self.btn_toggle)
        lay.addWidget(self.relink_view, 1)

        self.watcher = monitor.LogWatcher(
            [paths.INJECTOR_RESULT, paths.INJECTOR_DEBUG_LOG, paths.RELINK_LOG],
            self)
        self.watcher.file_changed.connect(self._on_changed)

        self._refresh_result()
        self._reload(self.debug_view, paths.INJECTOR_DEBUG_LOG)

    def _toggle_relink(self, on: bool):
        self.relink_view.setVisible(on)
        self.btn_toggle.setText(("▾" if on else "▸") + " wasapi_relink.log(排障用)")
        if on:
            self._reload(self.relink_view, paths.RELINK_LOG)

    def _on_changed(self, path: str):
        if path == paths.INJECTOR_RESULT:
            self._refresh_result()
        elif path == paths.INJECTOR_DEBUG_LOG:
            self._reload(self.debug_view, path)
        elif path == paths.RELINK_LOG and self.relink_view.isVisible():
            self._reload(self.relink_view, path)

    def _refresh_result(self):
        mtime, text = monitor.read_result()
        if mtime is None:
            self.result_label.setStyleSheet("color:#888;")
            self.result_label.setText("暂无注入记录")
            return
        color = "#30a46c" if "injected OK" in text else "#e5484d"
        self.result_label.setStyleSheet(f"color:{color};")
        self.result_label.setText(f"{mtime:%Y-%m-%d %H:%M:%S} — {text}")

    def _reload(self, view: QPlainTextEdit, path: str):
        view.setPlainText("\n".join(monitor.tail(path, 200)))
        view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())

    def append_event(self, text: str):
        """GUI 会话内的启动器输出事件(可选接线)。"""
        self.debug_view.appendPlainText(text)
```

- [ ] **Step 2: 接入主窗口**

`ui/main_window.py` 顶部加 `from ui.monitor_page import MonitorPage`;`__init__` 中追加:
```python
        self.monitor_page = MonitorPage()
        self.replace_page(2, self.monitor_page)
        self.games_page.runner.line.connect(self.monitor_page.append_event)
```

- [ ] **Step 3: 手动验证**

Run: `python app.py` → 状态监控页
Expected:
- 最近注入卡片显示 `injector_result.txt` 当前内容与修改时间(本机已有记录)
- debug 视图显示 `injector_debug.log` 尾部
- 另开终端执行 `echo test >> "C:\Users\ZhuTT\Workspace\specialk\injector_debug.log"`,监控页 1–2s 内出现新行
- 点排障按钮展开/折叠 relink 日志区

- [ ] **Step 4: 提交**

```bash
git add ui/monitor_page.py ui/main_window.py
git commit -m "feat: 状态监控页(最近注入/日志尾随/文件监视)"
```

---

### Task 14: 收尾 — 全量测试 + README + 端到端验证

**Files:**
- Create: `README.md`

- [ ] **Step 1: 全量测试**

Run: `python -m pytest tests/ -v`
Expected: 全部 PASSED(test_paths 2 + registry 6 + config 7 + anticheat 3 + ifeo 5 + monitor 5 = 28)

- [ ] **Step 2: 写 README.md**

```markdown
# HapticImproveManager

DualSense haptic 低延迟注入系统的可视化管理器。
包装 `C:\Users\ZhuTT\Workspace\specialk\` 下的 injector.py / haptic_launcher.py。

## 运行
    python -m pip install -r requirements.txt
    python app.py

## 功能
- 游戏列表: IFEO 状态灯 / 一键启停自动注入 / 启动游戏
- 添加游戏向导: exe 选择 → 反作弊检测 → 生成 redirect_config.toml → 开 IFEO
- 配置编辑: wasapi_relink 模式/缓冲可视化编辑(保留注释)
- 状态监控: 最近注入结果 + injector_debug.log / wasapi_relink.log 尾随

## 架构
薄 GUI + 子进程后端。GUI 普通权限运行; ifeo on/off 由 haptic_launcher 自行 UAC 提权。
游戏注册表: specialk/games.yaml(GUI 与 CLI 共用)。

## 测试
    python -m pytest tests/ -v
```

- [ ] **Step 3: 端到端验证(不改注册表的安全路径)**

1. `python app.py` 正常启动,四区(游戏/配置/监控)均可切换
2. 游戏页三张卡片状态与 `haptic_launcher.py ifeo <name> status` 一致
3. 配置页修改 ds2 缓冲 → 保存 → `type` 游戏目录配置确认 → 改回原值再保存
4. 添加向导用 notepad.exe 走完(不开 IFEO)→ 移除
5. 监控页时间戳与 `injector_result.txt` mtime 一致

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "docs: README 与端到端验证收尾"
```

---

## Self-Review 记录

- **Spec 覆盖**:§5.1 游戏列表→Task 10;§5.2 向导→Task 11;§5.3 配置编辑→Task 12;§5.4 监控→Task 13;§3 launcher 改动→Task 8;§6 结构→Task 1;§8 测试→各 Task + Task 14。诊断页为非目标,未覆盖(符合 spec §9)。
- **占位符**:无 TBD/TODO;所有代码步骤含完整代码。
- **类型一致性**:`GameEntry` 字段与 Task 11 `add_game` 调用一致;`IfeoState.ON_OURS` 在 Task 5/10/11 一致;`ProcessRunner.line/done` 在 Task 6 定义、Task 10/11/13 使用一致;`config_file` 在 Task 3 定义、Task 11/12 使用一致;`monitor.read_result` 返回 `(datetime|None, str)` 与 Task 13 解构一致。
- **已知取舍**:winreg 提权后落地是异步的,UI 用轮询而非退出码判断(Task 10/11 已注明);tomlkit 整数键兼容性在 Task 3 Step 4 留有调整说明。
