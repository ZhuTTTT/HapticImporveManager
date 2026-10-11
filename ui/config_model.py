"""表单状态 ↔ redirect_config.toml doc 的纯函数映射(无 Qt, 可单测)。

模式展示文案已迁入 i18n 目录(mode.<Mode>.<title|brief|detail> 键),
本文件只做数据映射, 不再持有文案。

tomlkit 点分键陷阱: target_buffer_len.48000 解析后子表键是字符串 "48000";
赋值必须原位改值且用字符串键, int 键 TypeError, 整体替换丢注释。
"""
from __future__ import annotations

from dataclasses import dataclass

import tomlkit
from tomlkit import TOMLDocument


@dataclass
class FormState:
    mode: str = "Normal"
    period_hus: int = 100
    buf_normal: int = 960
    buf_ring: int = 4320
    raw: bool = True
    force_period: bool = True
    log_level: str = "Error"


def frames_to_ms(frames: int, rate: int = 48000) -> float:
    return frames * 1000 / rate


def hus_to_ms(hus: int) -> float:
    return hus / 10


def _first_int(sub: dict, default: int) -> int:
    """点分键子表(如 target_buffer_len.48000)取第一个值, 缺失回退默认。"""
    return int(next(iter(sub.values()), default))


def load_form(doc: TOMLDocument) -> FormState:
    pb = doc.get("playback", {})
    return FormState(
        mode=pb.get("mode", "Normal"),
        period_hus=int(pb.get("target_period_hus", 100)),
        buf_normal=_first_int(pb.get("target_buffer_len", {}), 960),
        buf_ring=_first_int(pb.get("ring_buffer_len", {}), 4320),
        raw=bool(pb.get("raw", True)),
        force_period=bool(pb.get("force_period", True)),
        log_level=doc.get("log_level", "Error"),
    )


def _set_buf(pb, field: str, value: int) -> None:
    """原位改帧数; 子表不存在则新建。键必须字符串(tomlkit 点分键)。"""
    tbl = pb.get(field)
    if tbl is None:
        tbl = tomlkit.table()
        pb[field] = tbl
    key = next(iter(tbl.keys()), "48000")
    tbl[str(key)] = value


def apply_form(doc: TOMLDocument, state: FormState) -> None:
    pb = doc["playback"]
    pb["mode"] = state.mode
    pb["target_period_hus"] = state.period_hus
    _set_buf(pb, "target_buffer_len", state.buf_normal)
    _set_buf(pb, "ring_buffer_len", state.buf_ring)
    pb["raw"] = state.raw
    pb["force_period"] = state.force_period
    doc["log_level"] = state.log_level
