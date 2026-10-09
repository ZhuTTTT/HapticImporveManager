"""表单状态 ↔ redirect_config.toml doc 的纯函数映射(无 Qt, 可单测)。

tomlkit 点分键陷阱: target_buffer_len.48000 解析后子表键是字符串 "48000";
赋值必须原位改值且用字符串键, int 键 TypeError, 整体替换丢注释。
"""
from __future__ import annotations

from dataclasses import dataclass

import tomlkit
from tomlkit import TOMLDocument

# 模式文案 — spec「配置卡」一节, 改动需同步 spec
MODE_INFO: dict[str, dict[str, str]] = {
    "Normal": {
        "title": "普通模式",
        "brief": "延迟最低, 绝大多数游戏直接用(剑星、绝区零已验证)",
        "detail": "游戏直接面对真实的小缓冲区。破音就把下面的缓冲调大。"
                  "默认先试这个。",
    },
    "Ringbuf": {
        "title": "虚拟缓冲",
        "brief": "给“爆发式写音频”的游戏兜底(《黑魂2》必须用)",
        "detail": "游戏以为自己面前有一条很长的缓冲通道, 可以一口气猛写一大批音频;"
                  "注入层在幕后接住, 再按推送节奏匀速喂给手柄。\n"
                  "什么时候用它: 普通模式下声音破音、卡顿, 或游戏写入节奏本身不均匀。\n"
                  "代价: 多一层缓冲, 延迟略高于普通模式。\n"
                  "已知问题: UE5 游戏爆发写入太大会撑爆虚拟缓冲、日志刷屏;"
                  "绝区零会丢失手柄扬声器声道——这两款不要用。\n"
                  "怎么调: 虚拟缓冲帧数 ÷ 48 = 毫秒, 默认 4320 帧 ≈ 90ms。",
    },
    "Compat": {
        "title": "兼容模式",
        "brief": "上面两种都出问题再试",
        "detail": "兼容性优先的折中模式, 延迟不如普通模式。",
    },
    "Bypass": {
        "title": "不干预",
        "brief": "跳过音频处理, 保持原生延迟",
        "detail": "不修改任何音频行为, 用来对比排障。",
    },
}


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
