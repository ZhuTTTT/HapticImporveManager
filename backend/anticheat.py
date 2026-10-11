"""反作弊静态检测: pefile 读导入表 + 扫描游戏目录同目录文件名。

命中只警告不阻止(HANDOVER 4.9: 反作弊游戏注入有封禁风险, 用户须知情确认)。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from i18n import tr

# 值为 i18n 消息键(ac.*), 显示文案在 scan_exe 运行时 tr() 解析 —
# 模块级不 tr: import 时求值会冻结在当时的语言
KNOWN_SIGNATURES = {
    "easyanticheat": "ac.eac",
    "beservice": "ac.battleye_service",
    "battleye": "ac.battleye",
    "hoyokprotect": "ac.hoyokprotect",
    "mhyprot": "ac.mhyprot",
    "xigncode": "ac.xigncode",
    "ace-basis": "ac.ace",
    "sentry": "ac.ace_sentry",
    "nprotect": "ac.nprotect",
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
    hits = sorted({tr(msg_key) for key, msg_key in KNOWN_SIGNATURES.items()
                   if any(key in n for n in names)})
    return AnticheatReport(risk="known" if hits else "none", hits=hits)
