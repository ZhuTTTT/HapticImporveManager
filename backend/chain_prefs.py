"""GUI ↔ 注入链共享的小配置桥: %APPDATA%\\HapticImproveManager\\chain_prefs.json。

GUI 侧读写自由;链(injector.exe)只读 — 它读不到 gui_config.json
(qfluentwidgets 格式), 以此文件拿到用户偏好。文件缺失/损坏一律回落默认。
"""
from __future__ import annotations

import json
import os

from . import paths

PREFS_PATH = os.path.join(paths.DATA_DIR, "chain_prefs.json")

# 键 → 默认值; 新键必须在此登记默认值, 读取方才有一致回退
_DEFAULTS = {
    "inject_success_toast": True,  # 注入成功的 toast 通知(失败通知不受控)
}


def get(name: str):
    """读单个偏好, 缺失/损坏回退 _DEFAULTS 登记值。"""
    try:
        with open(PREFS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get(name, _DEFAULTS[name])
    except Exception:
        return _DEFAULTS[name]


def set(name: str, value) -> None:
    """读-改-写单个偏好(原子替换, 与 registry.save_games 同一原则)。"""
    if name not in _DEFAULTS:
        raise KeyError(f"unregistered chain pref: {name}")
    try:
        with open(PREFS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    data[name] = value
    os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
    tmp = PREFS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, PREFS_PATH)
