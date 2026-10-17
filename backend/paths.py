"""后端路径与常量集中定义。

注入链目录 chain/: 冻结(PyInstaller)→ 随包 <exe目录>/chain;
源码 → 仓库根/chain(链源码收编在本仓库, 两种运行态布局一致)。
IFEO_VALUE 源码分支与 chain/injector.py、chain/haptic_launcher.py
的 _source_ifeo_value() 保持同一套计算规则 — 修改必须三处同改。
"""
import os
import sys


def _chain_dir() -> str:
    """注入链目录: 冻结态取 <sys.executable目录>/chain, 源码态取仓库根/chain。"""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "chain")
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chain")


CHAIN_DIR = _chain_dir()
GAMES_YAML = os.path.join(CHAIN_DIR, "games.yaml")
LAUNCHER_PY = os.path.join(CHAIN_DIR, "haptic_launcher.py")
INJECTOR_PY = os.path.join(CHAIN_DIR, "injector.py")
DEFAULT_DLL = os.path.join(CHAIN_DIR, "wasapi_relink.dll")

INJECTOR_RESULT = os.path.join(CHAIN_DIR, "injector_result.txt")
INJECTOR_DEBUG_LOG = os.path.join(CHAIN_DIR, "injector_debug.log")
RELINK_LOG_DIR = os.path.join(CHAIN_DIR, "logs")
RELINK_LOG = os.path.join(RELINK_LOG_DIR, "wasapi_relink.log")

LAUNCHER_EXE = os.path.join(CHAIN_DIR, "haptic_launcher.exe")
INJECTOR_EXE = os.path.join(CHAIN_DIR, "injector.exe")

IFEO_BASE = (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
             r"\Image File Execution Options")


def _source_ifeo_value() -> str:
    """源码态 IFEO Debugger 值: 优先用 pythonw(无窗) + chain/injector.py。"""
    exe = sys.executable
    if os.path.basename(exe).lower() != "pythonw.exe":
        sibling = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(sibling):
            exe = sibling
    return f'"{exe}" "{INJECTOR_PY}" ifeo'


# 冻结态指向随包 injector.exe; 源码分支与链源码的同名函数同规则 — 三处同改
IFEO_VALUE = (f'"{INJECTOR_EXE}" ifeo' if getattr(sys, "frozen", False)
              else _source_ifeo_value())
