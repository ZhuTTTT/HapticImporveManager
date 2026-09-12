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
