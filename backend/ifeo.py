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


def build_ifeo_args(name: str, action: str, python: str | None = None) -> list[str]:
    """action: "on" | "off"。launcher 内部会自行 UAC 提权。
    python=None 时用 sys.executable; 冻结态由调用方传入系统 Python。"""
    assert action in ("on", "off")
    return [python or sys.executable, paths.LAUNCHER_PY, "ifeo", name, action]
