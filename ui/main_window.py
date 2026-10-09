"""主窗口: FluentWindow + 导航(游戏/诊断/设置) + 主题与 Mica。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from qfluentwidgets import (FluentIcon, FluentWindow, NavigationItemPosition)

from ui.app_config import APP_CFG, AppConfig, apply_theme
from ui.settings_page import SettingsPage


class MainWindow(FluentWindow):
    def __init__(self, cfg: AppConfig = APP_CFG):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("Haptic 低延迟管理器")
        self.resize(1100, 720)

        # 占位页 — Task 5/8 替换为真实页面
        self.games_page = _placeholder("games")
        self.diagnostics_page = _placeholder("diagnostics")
        self.settings_page = SettingsPage(cfg, self)

        self.addSubInterface(self.games_page, FluentIcon.GAME, "游戏")
        self.addSubInterface(self.diagnostics_page, FluentIcon.SPEED_HIGH,
                             "诊断")
        self.addSubInterface(self.settings_page, FluentIcon.SETTING, "设置",
                             position=NavigationItemPosition.BOTTOM)

        apply_theme(cfg)
        self.apply_mica()

    def apply_mica(self):
        self.setMicaEffectEnabled(bool(self.cfg.mica_enabled.value))


def _placeholder(name: str) -> QWidget:
    w = QWidget()
    w.setObjectName(name)
    return w


def create_main_window() -> MainWindow:
    return MainWindow()
