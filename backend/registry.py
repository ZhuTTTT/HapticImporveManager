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
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)  # 用户数据目录可能尚未创建
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


def update_exe(name: str, new_path: str, path: str = paths.GAMES_YAML) -> None:
    """更新已注册游戏的 exe 路径(同步重建的骨架条目「定位 exe」用)。"""
    games = _try_load(path)
    if name not in games:
        return
    games[name].exe = new_path
    save_games(games, path)


def sync_from_registry(path: str = paths.GAMES_YAML
                       ) -> tuple[list[str], list[str]]:
    """从 IFEO 注册表重建游戏列表(单向: 注册表 → games.yaml)。

    凡带我们签名的 IFEO 项(当前值/旧位置值都算, 见 ifeo.scan_ours)且
    列表中尚无同名 exe 的, 建骨架条目: exe 暂存文件名(非全路径,
    状态点显示「exe 丢失」, 用户在详情页「定位 exe」补全路径)。
    返回 (新增的名字, 已存在而跳过的名字)。"""
    from . import ifeo  # 函数内导入: registry ← ifeo 单向依赖, 防循环
    games = _try_load(path)
    known_exes = {os.path.basename(e.exe).lower() for e in games.values()}
    added, skipped = [], []
    for exe_name in ifeo.scan_ours_exe_names():
        if exe_name.lower() in known_exes:
            skipped.append(exe_name)
            continue
        name = os.path.splitext(exe_name)[0].lower()
        base, i = name, 2
        while name in games:  # 同名不同 exe 的极小概率冲突: 加序号
            name = f"{base}{i}"
            i += 1
        games[name] = GameEntry(name=name, exe=exe_name)
        added.append(name)
    if added:
        save_games(games, path)
    return added, skipped


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


def load_or_migrate(path: str = paths.GAMES_YAML,
                    legacy: str = paths.LEGACY_GAMES_YAML
                    ) -> dict[str, GameEntry]:
    """读 games.yaml; 缺失从空注册表起步, 损坏则备份 .bak 后从空表起步。

    一次性迁移: 新位置(用户数据目录)缺失而旧位置(chain/games.yaml)
    存在 → 移动过来(升级/换安装位置后游戏列表不丢)。"""
    if not os.path.exists(path) and os.path.isfile(legacy):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            shutil.move(legacy, path)
        except OSError:
            shutil.copy2(legacy, path)  # 移动失败(跨盘/占用)退化为复制
    try:
        return load_games(path)
    except FileNotFoundError:
        return {}
    except (yaml.YAMLError, KeyError, TypeError, ValueError):
        # ValueError: buffer_hint 等非整数字段 int() 转换失败, 同样备份后恢复
        shutil.copy(path, path + ".bak")  # 损坏文件保留
        return {}
