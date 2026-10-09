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
