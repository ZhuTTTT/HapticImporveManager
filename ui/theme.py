"""主题令牌: 强调色、双主题语义状态色、等宽字体。

状态色按 Fluent 语义色双主题配对(light/dark 各一份), 不写死单份 —
这是深色适配红线(qfluentwidgets 主题色管 accent, 语义色我们自己管)。
"""
from __future__ import annotations

from PySide6.QtGui import QFont
from qfluentwidgets import isDarkTheme, setThemeColor

# 声波紫罗兰 — 音频/脉冲联想, 深浅主题下均有辨识度
ACCENT = "#7C6CF0"

_LIGHT = {"ok": "#107C10", "warn": "#B25009", "err": "#C42B1C"}
_DARK = {"ok": "#6CCB5F", "warn": "#FAA06B", "err": "#F1707B"}


def apply_accent() -> None:
    """设全局强调色(进 qconfig, 影响按钮/滑块/开关等所有组件)。"""
    setThemeColor(ACCENT)


def status_color(level: str) -> str:
    """level ∈ ok / warn / err, 返回当前主题下可读的语义色。"""
    return (_DARK if isDarkTheme() else _LIGHT)[level]


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def accent_tint(alpha: float = 0.08) -> str:
    """强调色的淡底色(选中卡背景等)。"""
    return _rgba(ACCENT, alpha)


def pill_style(level: str) -> str:
    """状态徽章样式: 语义色文字 + 同色系 12% 淡底圆角胶囊。"""
    c = status_color(level)
    return (f"QLabel {{ color: {c}; background: {_rgba(c, 0.12)};"
            f" border-radius: 10px; padding: 2px 10px; }}")


def mono_font(point_size: int = 10) -> QFont:
    """日志/毫秒数字用等宽字体(Cascadia Mono, 缺失时回退系统等宽)。"""
    f = QFont("Cascadia Mono")
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setPointSize(point_size)
    return f
