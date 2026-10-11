"""主窗口: FluentWindow + 导航(游戏/诊断/设置) + 主题与 Mica。"""
from __future__ import annotations

from PySide6.QtCore import QLocale
from qfluentwidgets import (FluentIcon, FluentWindow, NavigationItemPosition)

import i18n
from i18n import tr
from ui.app_config import APP_CFG, AppConfig, apply_theme
from ui.diagnostics_page import DiagnosticsPage
from ui.games_page import GamesPage
from ui.settings_page import SettingsPage
from ui.theme import apply_accent


class MainWindow(FluentWindow):
    def __init__(self, cfg: AppConfig = APP_CFG):
        super().__init__()
        self.cfg = cfg
        # 语言必须在构建任何页面之前解析好;
        # 放在这里而非 create_main_window: 测试也直接构造 MainWindow(cfg)
        i18n.set_language(i18n.resolve_language(cfg.language.value,
                                                QLocale.system().name()))
        self.setWindowTitle(tr("app.title"))
        self.resize(1100, 720)

        apply_accent()  # 先设强调色, 再建页面, 组件即刻吃到主题色

        self.games_page = GamesPage(self)
        self.diagnostics_page = DiagnosticsPage(self)
        self.settings_page = SettingsPage(cfg, self)

        self.addSubInterface(self.games_page, FluentIcon.GAME,
                             tr("nav.games"))
        self.addSubInterface(self.diagnostics_page, FluentIcon.SPEED_HIGH,
                             tr("nav.diagnostics"))
        self.addSubInterface(self.settings_page, FluentIcon.SETTING,
                             tr("nav.settings"),
                             position=NavigationItemPosition.BOTTOM)

        # 日志目录变化 → 诊断页重建文件监视
        self.settings_page.log_dir_changed.connect(
            self.diagnostics_page.rebuild_watcher)
        # 启动器输出 → 诊断页 injector_debug 视图
        self.games_page.log_line.connect(self.diagnostics_page.append_event)

        apply_theme(cfg)
        self.apply_mica()

    def apply_mica(self):
        self.setMicaEffectEnabled(bool(self.cfg.mica_enabled.value))


def create_main_window() -> MainWindow:
    return MainWindow()
