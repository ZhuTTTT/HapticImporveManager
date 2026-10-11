"""多语言(i18n)字典目录模块。

纯 Python 实现,不依赖 Qt,可被 ui 与 backend 双向导入(根级模块,
不破坏 ui → backend 单向依赖)。每键中英并排,对照可见、完整性可单测。

键命名按页面分层:app.* / nav.* / settings.* / games.* / detail.* /
config.* / mode.<Mode>.* / wizard.* / diag.* / validate.* / ac.* /
common.* / unit.*。

铁律:tr() 只在运行时调用,禁止模块级调用——模块级常量在 import 时
求值,会冻结在当时的 _LANG,之后 set_language 对其无效。
"""

_MESSAGES: dict[str, dict[str, str]] = {
    "app.title":   {"zh": "Haptic 低延迟管理器", "en": "Haptic Low-Latency Manager"},
    "unit.frames": {"zh": "{n} 帧", "en": "{n} frames"},
}

_LANG = "zh"  # 模块级默认值;仅启动时由 set_language 覆盖一次

_VALID_LANGUAGES = ("zh", "en")


def tr(key: str, **params) -> str:
    """返回当前语言文案。

    回退链:当前语言缺失 → zh → 返回 key 本身(查找过程不抛异常)。
    params 非空时对结果做 .format(**params) 插值;占位符与参数不匹配
    属调用方错误,由 format 抛出的异常暴露(目录完整性由测试保证)。
    """
    entry = _MESSAGES.get(key) or {}
    text = entry.get(_LANG) or entry.get("zh") or key
    return text.format(**params) if params else text


def set_language(lang: str) -> None:
    """设置当前语言。只接受 "zh" / "en",其他值 raise ValueError。"""
    if lang not in _VALID_LANGUAGES:
        raise ValueError(f"不支持的语言: {lang!r}(只接受 zh / en)")
    global _LANG
    _LANG = lang


def current_language() -> str:
    """返回当前语言代码("zh" / "en")。"""
    return _LANG


def resolve_language(setting: str, system_locale: str) -> str:
    """把配置项解析为实际语言代码。

    setting ∈ "System" / "zh" / "en":
    - 显式 "zh" / "en" 原样返回
    - "System" 或未知值(手改配置):system_locale 以 "zh" 开头 → "zh",
      否则 → "en"

    system_locale 由调用方(QLocale.system().name())注入,
    保持本模块无 Qt 可单测。
    """
    if setting in _VALID_LANGUAGES:
        return setting
    return "zh" if system_locale.startswith("zh") else "en"
