"""后端路径与常量集中定义。

按运行态解析注入链目录: 冻结(PyInstaller)→ 随包 <exe目录>/chain;
源码 → 本机 specialk 开发目录。IFEO_VALUE 源码分支必须与
specialk/injector.py 的源码态常量逐字一致。
"""
import os
import sys

# 源码态链目录(本机开发常量, 真实用户机器上不存在)
DEV_SPECIALK_DIR = r"C:\Users\ZhuTT\Workspace\specialk"
# 兼容别名: specialk 源码目录, migrate_from_launcher 据此导入 haptic_launcher.py
SPECIALK_DIR = DEV_SPECIALK_DIR


def _chain_dir() -> str:
    """注入链目录: 冻结态取 <sys.executable目录>/chain, 源码态取开发目录。"""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "chain")
    return DEV_SPECIALK_DIR


CHAIN_DIR = _chain_dir()
GAMES_YAML = os.path.join(CHAIN_DIR, "games.yaml")
LAUNCHER_PY = os.path.join(CHAIN_DIR, "haptic_launcher.py")
INJECTOR_PY = os.path.join(CHAIN_DIR, "injector.py")
DEFAULT_DLL = os.path.join(CHAIN_DIR, "zzz_inject", "wasapi_relink.dll")

INJECTOR_RESULT = os.path.join(CHAIN_DIR, "injector_result.txt")
INJECTOR_DEBUG_LOG = os.path.join(CHAIN_DIR, "injector_debug.log")
RELINK_LOG_DIR = os.path.join(CHAIN_DIR, "logs")
RELINK_LOG = os.path.join(RELINK_LOG_DIR, "wasapi_relink.log")

LAUNCHER_EXE = os.path.join(CHAIN_DIR, "haptic_launcher.exe")
INJECTOR_EXE = os.path.join(CHAIN_DIR, "injector.exe")

IFEO_BASE = (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
             r"\Image File Execution Options")
# 冻结态指向随包 injector.exe; 源码分支与 injector.py 的源码态常量逐字一致
# — 源码分支修改必须两处同改
IFEO_VALUE = (f'"{INJECTOR_EXE}" ifeo' if getattr(sys, "frozen", False)
              else ('"C:\\Users\\ZhuTT\\AppData\\Local\\Python\\bin\\pythonw.exe" '
                    '"C:\\Users\\ZhuTT\\Workspace\\specialk\\injector.py" ifeo'))
