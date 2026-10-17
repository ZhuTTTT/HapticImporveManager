"""游戏注册表: chain/games.yaml 读写, GUI 与 haptic_launcher 共用。"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, asdict

import yaml

from . import paths


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


def load_or_migrate(path: str = paths.GAMES_YAML) -> dict[str, GameEntry]:
    """读 games.yaml; 缺失从空注册表起步, 损坏则备份 .bak 后从空表起步
    (冻结/源码两态统一, 应用自包含, 不向外部目录迁移)。"""
    try:
        return load_games(path)
    except FileNotFoundError:
        return {}
    except (yaml.YAMLError, KeyError, TypeError, ValueError):
        # ValueError: buffer_hint 等非整数字段 int() 转换失败, 同样备份后恢复
        shutil.copy(path, path + ".bak")  # 损坏文件保留
        return {}
