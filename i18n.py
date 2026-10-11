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

    # 主导航
    "nav.games":       {"zh": "游戏", "en": "Games"},
    "nav.diagnostics": {"zh": "诊断", "en": "Diagnostics"},
    "nav.settings":    {"zh": "设置", "en": "Settings"},

    # 设置页
    "settings.title":       {"zh": "设置", "en": "Settings"},
    "settings.language":    {"zh": "语言", "en": "Language"},
    "settings.lang_system": {"zh": "跟随系统", "en": "Follow system"},
    "settings.lang_restart_title": {
        "zh": "语言已更改",
        "en": "Language changed",
    },
    "settings.lang_restart_msg": {
        "zh": "界面语言将在重启应用后生效。",
        "en": "The interface language will take effect after restarting the app.",
    },
    "settings.theme":       {"zh": "主题", "en": "Theme"},
    "settings.theme_light": {"zh": "浅色", "en": "Light"},
    "settings.theme_dark":  {"zh": "深色", "en": "Dark"},
    "settings.theme_auto":  {"zh": "跟随系统", "en": "Follow system"},
    "settings.mica": {"zh": "云母背景(Win11)", "en": "Mica background (Win11)"},
    "settings.log_dir": {"zh": "日志目录", "en": "Log directory"},
    "settings.log_dir_caption": {
        "zh": "wasapi_relink.log 的存放位置。更改后可同步到所有已注册游戏的配置。",
        "en": "Where wasapi_relink.log is written. After changing it, you can "
              "sync the new location to all registered games' configs.",
    },
    "settings.log_dir_change": {"zh": "更改…", "en": "Change…"},
    "settings.log_dir_open": {
        "zh": "在资源管理器中打开",
        "en": "Open in Explorer",
    },
    "settings.log_dir_pick": {
        "zh": "选择日志目录",
        "en": "Choose log directory",
    },
    "settings.sync_title": {"zh": "同步日志目录", "en": "Sync log directory"},
    "settings.sync_msg": {
        "zh": "新目录: {d}\n\n是否同步更新所有已注册游戏({n} 个)的 "
              "redirect_config.toml?\n选「否」则只影响以后新添加的游戏。",
        "en": "New directory: {d}\n\nAlso update redirect_config.toml for all "
              "{n} registered games?\nChoose \"Only future games\" to leave "
              "existing games unchanged.",
    },
    "settings.sync_yes": {"zh": "同步所有游戏", "en": "Sync all games"},
    "settings.sync_no":  {"zh": "仅以后生效", "en": "Only future games"},
    "settings.sync_ok_title": {"zh": "已同步", "en": "Synced"},
    "settings.sync_ok_msg": {
        "zh": "已更新 {ok} 个游戏的配置",
        "en": "Updated configs for {ok} games",
    },
    "settings.sync_partial_title": {
        "zh": "部分同步失败",
        "en": "Partial sync failed",
    },
    "settings.sync_partial_msg": {
        "zh": "已同步 {ok} 个; 失败: {failed}"
              "(配置缺失或损坏, 请到对应游戏详情修复)",
        "en": "Synced {ok}; failed: {failed} "
              "(config missing or corrupt — fix it from the game's detail page)",
    },

    # 通用开关
    "common.on":  {"zh": "开", "en": "On"},
    "common.off": {"zh": "关", "en": "Off"},
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
