"""GUI 自身设置(主题/Mica/语言/日志目录)持久化。qconfig 存 json。"""
from __future__ import annotations

import os

from qfluentwidgets import (BoolValidator, ConfigItem, OptionsConfigItem,
                            OptionsValidator, QConfig, Theme, qconfig,
                            setTheme)

from backend import paths


class AppConfig(QConfig):
    theme_mode = OptionsConfigItem(
        "MainWindow", "ThemeMode", "Auto",
        OptionsValidator(["Light", "Dark", "Auto"]))
    mica_enabled = ConfigItem(
        "MainWindow", "MicaEnabled", True, BoolValidator())
    log_dir = ConfigItem("Paths", "LogDir", paths.RELINK_LOG_DIR)
    language = OptionsConfigItem(
        "MainWindow", "Language", "System",
        OptionsValidator(["System", "zh", "en"]))


def _default_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "HapticImproveManager")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "gui_config.json")


def load_app_config(path: str | None = None) -> AppConfig:
    cfg = AppConfig()
    qconfig.load(path or _default_path(), cfg)
    return cfg


def apply_theme(cfg: AppConfig) -> None:
    setTheme(Theme[cfg.theme_mode.value.upper()])  # "Auto" -> Theme.AUTO


APP_CFG = load_app_config()
