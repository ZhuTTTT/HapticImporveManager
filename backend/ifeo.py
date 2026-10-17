"""IFEO 状态查询(只读, 无需管理员)。on/off 经 haptic_launcher CLI 执行。"""
from __future__ import annotations

import enum
import os
import re
import sys
import winreg  # 模块级导入, 测试用 monkeypatch 替换
from dataclasses import dataclass

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
    """action: "on" | "off"。launcher 内部会自行 UAC 提权。
    冻结态直接调随包 haptic_launcher.exe; 源码态走 sys.executable + .py。"""
    assert action in ("on", "off")
    if getattr(sys, "frozen", False):
        return [paths.LAUNCHER_EXE, "ifeo", name, action]
    return [sys.executable, paths.LAUNCHER_PY, "ifeo", name, action]


# --- 旧版残留扫描(只读) + 提权清理 ---

@dataclass
class LegacyEntry:
    """一条旧版/旧位置留下的 IFEO Debugger 项。"""
    exe_name: str
    debugger: str
    target_exists: bool  # False=失效残留(目标已删, 游戏会无法启动)

    @property
    def broken(self) -> bool:
        return not self.target_exists


# 我们的 Debugger 值签名: 冻结态 "...injector.exe" ifeo,
# 源码/旧版 "...pythonw.exe" "...injector.py" ifeo — 共同点是 injector + ifeo 参数
_OUR_SIGNATURES = ('injector.exe" ifeo', 'injector.py" ifeo')


def _extract_target(debugger: str) -> str | None:
    """Debugger 值中取 injector 目标路径(最后一个引号段; pythonw 两段式的
    第一段是解释器, 第二段才是 injector.py)。"""
    parts = re.findall(r'"([^"]+)"', debugger)
    return parts[-1] if parts else None


def scan_legacy() -> list[LegacyEntry]:
    """扫全量 IFEO 子键, 返回带我们签名但不等于当前运行态值的残留项。

    当前值(paths.IFEO_VALUE)由详情页开关正常管理, 不算残留;
    别人的调试器(不带签名)一律不碰。"""
    results: list[LegacyEntry] = []
    try:
        base = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, paths.IFEO_BASE)
    except FileNotFoundError:
        return results
    with base:
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(base, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(base, sub) as k:
                    val, _ = winreg.QueryValueEx(k, "Debugger")
            except (FileNotFoundError, OSError):
                continue
            low = val.lower()
            if not any(sig in low for sig in _OUR_SIGNATURES):
                continue
            if val == paths.IFEO_VALUE:
                continue
            target = _extract_target(val)
            results.append(LegacyEntry(
                sub, val,
                os.path.isfile(target) if target else False))
    return results


def build_ifeo_rm_args(exe_names: list[str]) -> list[str]:
    """按 IFEO 子键名(exe 文件名)批量删除 Debugger 值, launcher 内自行提权。"""
    assert exe_names
    if getattr(sys, "frozen", False):
        return [paths.LAUNCHER_EXE, "ifeo-rm"] + list(exe_names)
    return [sys.executable, paths.LAUNCHER_PY, "ifeo-rm"] + list(exe_names)
