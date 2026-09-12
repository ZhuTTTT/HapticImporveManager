"""反作弊静态检测: pefile 读导入表 + 扫描游戏目录同目录文件名。

命中只警告不阻止(HANDOVER 4.9: 反作弊游戏注入有封禁风险, 用户须知情确认)。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

KNOWN_SIGNATURES = {
    "easyanticheat": "EasyAntiCheat (EAC)",
    "beservice": "BattlEye (BEService)",
    "battleye": "BattlEye",
    "hoyokprotect": "HoYoKProtect (米哈游)",
    "mhyprot": "HoYoKProtect (米哈游 mhyprot)",
    "xigncode": "XIGNCODE",
    "ace-basis": "腾讯 ACE",
    "sentry": "腾讯 ACE (Sentry)",
    "nprotect": "nProtect GameGuard",
}


@dataclass
class AnticheatReport:
    risk: str                 # "none" | "known"
    hits: list[str] = field(default_factory=list)


def _imported_dll_names(path: str) -> set[str]:
    import pefile
    try:
        pe = pefile.PE(path, fast_load=True)
    except Exception:
        return set()
    try:
        pe.parse_data_directories(directories=[
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        return {e.dll.decode(errors="ignore").lower()
                for e in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])}
    except Exception:
        return set()
    finally:
        pe.close()


def _sibling_names(path: str) -> set[str]:
    try:
        return {n.lower() for n in os.listdir(os.path.dirname(path))}
    except OSError:
        return set()


def scan_exe(path: str) -> AnticheatReport:
    names = _imported_dll_names(path) | _sibling_names(path)
    hits = sorted({label for key, label in KNOWN_SIGNATURES.items()
                   if any(key in n for n in names)})
    return AnticheatReport(risk="known" if hits else "none", hits=hits)
