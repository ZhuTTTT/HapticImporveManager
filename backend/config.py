"""redirect_config.toml 读写。用 tomlkit 保留注释与格式(tomllib 只读不写)。

字段规则(HANDOVER 第 3/4 节):
- log_level 常驻 Error — Info 在 overflow 时可写 GB 级日志
- mode ∈ Normal | Ringbuf | Compat | Bypass
- target_period_hus: 0 = 原生, 100 = 10ms (单位 0.1ms), 上限 1000
"""
from __future__ import annotations

import os

import tomlkit
from tomlkit import TOMLDocument

from . import paths

MODES = ("Normal", "Ringbuf", "Compat", "Bypass")

def _default_text(log_dir: str | None = None) -> str:
    log_path = (log_dir or paths.RELINK_LOG_DIR).replace(os.sep, "/")
    return f'''\
# wasapi_relink 配置 — 由 HapticImproveManager 生成
log_path = "{log_path}"
log_level = "Error"        # 必须 Error! Info 在溢出时会写 GB 级日志
only_log_stdout = false

[playback]
mode = "Normal"            # Normal | Ringbuf | Compat | Bypass
target_period_hus = 100    # 100 = 10ms (单位 0.1ms); 0 = 原生
target_buffer_len.48000 = 960   # Normal 用, 帧数. 256→5.3ms 可能破音
ring_buffer_len.48000 = 4320    # Ringbuf 用, 给应用的虚拟缓冲帧数
raw = true
force_period = true

[capture]
mode = "Bypass"
'''


def default_config(log_dir: str | None = None) -> TOMLDocument:
    """log_dir 缺省保持 paths.RELINK_LOG_DIR(现状不变)。"""
    return tomlkit.parse(_default_text(log_dir))


def set_log_dir(game_dir: str, log_dir: str) -> None:
    """原位改 redirect_config.toml 的 log_path, 保留注释。"""
    doc = load_config(game_dir)  # 缺失抛 FileNotFoundError, 损坏抛解析异常
    doc["log_path"] = log_dir.replace(os.sep, "/")
    save_config(game_dir, doc)


def config_file(game_dir: str) -> str:
    return os.path.join(game_dir, "redirect_config.toml")


def load_config(game_dir: str) -> TOMLDocument:
    with open(config_file(game_dir), encoding="utf-8") as f:
        return tomlkit.parse(f.read())


def save_config(game_dir: str, doc: TOMLDocument) -> None:
    # newline="": 保留 tomlkit 输出的 LF, 避免 Windows 文本模式转成 CRLF
    with open(config_file(game_dir), "w", encoding="utf-8", newline="") as f:
        f.write(tomlkit.dumps(doc))


def _iter_dotted(table: dict):
    """target_buffer_len.48000 在 tomlkit 里键可能是 int 48000 或 str "48000"。"""
    for k, v in table.items():
        yield k, v


def validate(doc: TOMLDocument) -> list[str]:
    problems: list[str] = []
    pb = doc.get("playback", {})

    mode = pb.get("mode")
    if mode not in MODES:
        problems.append(f"playback.mode 必须是 {'/'.join(MODES)}, 当前: {mode!r}")

    period = pb.get("target_period_hus", 100)
    if not isinstance(period, int) or not (0 <= period <= 1000):
        problems.append(f"target_period_hus 必须在 0–1000, 当前: {period!r}")

    for key in ("target_buffer_len", "ring_buffer_len"):
        sub = pb.get(key)
        if sub is None:
            continue
        for rate, frames in _iter_dotted(sub):
            if not isinstance(frames, int) or frames <= 0:
                problems.append(f"{key}.{rate} 必须是正整数帧数, 当前: {frames!r}")

    if doc.get("log_level") != "Error":
        problems.append("log_level 必须为 Error — Info 在 overflow 时可写 GB 级日志"
                        "(仅排障时临时使用)")

    return problems
