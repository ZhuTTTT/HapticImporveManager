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


def _try_load(path: str) -> dict[str, GameEntry]:
    """读 games.yaml; 文件不存在时视为空表(用于增量编辑)。"""
    try:
        return load_games(path)
    except FileNotFoundError:
        return {}


def add_game(entry: GameEntry, path: str = paths.GAMES_YAML) -> None:
    games = _try_load(path)
    games[entry.name] = entry
    save_games(games, path)


def update_hints(name: str, mode_hint: str, buffer_hint: int,
                 path: str = paths.GAMES_YAML) -> None:
    """回写列表展示用 hint(配置保存后调用, 否则列表永远显示注册时旧值)。
    未注册的名字不动作(配置卡可先于注册表写入的场景)。"""
    games = _try_load(path)
    if name not in games:
        return
    games[name].mode_hint = mode_hint
    games[name].buffer_hint = buffer_hint
    save_games(games, path)


def remove_game(name: str, path: str = paths.GAMES_YAML) -> None:
    games = _try_load(path)
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


def migrate_legacy_chain_yaml(games_yaml_path: str, legacy_dir: str) -> bool:
    """从旧链目录(源码/≤v0.2.0 的 specialk 目录)迁移 games.yaml。

    目标不存在且 <legacy_dir>/games.yaml 存在 → 复制(保留原件)并返回 True;
    其他情况不动作返回 False。绝不覆盖已存在的目标。"""
    if os.path.exists(games_yaml_path):
        return False
    legacy = os.path.join(legacy_dir, "games.yaml")
    if not os.path.isfile(legacy):
        return False
    shutil.copy2(legacy, games_yaml_path)
    return True


def load_or_migrate(path: str = paths.GAMES_YAML) -> dict[str, GameEntry]:
    """优先读 games.yaml; 缺失/损坏时按运行态恢复:
    冻结态没有 haptic_launcher.py 可迁移(用户机器零依赖), 从空注册表起步;
    源码态(备份 .bak 后)从 launcher 硬编码 GAMES 迁移。
    冻结态前置一步: 旧 specialk 目录的 games.yaml 复制迁移(真实用户机器上
    旧目录不存在, 自然跳过; 仅开发机从源码/旧版切到冻结版时触发一次)。"""
    frozen = getattr(sys, "frozen", False)
    if frozen:
        migrate_legacy_chain_yaml(path, paths.DEV_SPECIALK_DIR)
    try:
        return load_games(path)
    except FileNotFoundError:
        if frozen:
            return {}
        return migrate_from_launcher(path)
    except (yaml.YAMLError, KeyError, TypeError, ValueError):
        # ValueError: buffer_hint 等非整数字段 int() 转换失败, 同样备份后恢复
        shutil.copy(path, path + ".bak")  # 损坏文件两态都保留
        if frozen:
            return {}
        return migrate_from_launcher(path)
