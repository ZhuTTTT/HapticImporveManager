"""主窗口: FluentWindow + 导航(游戏/诊断/设置) + 主题与 Mica。"""
from __future__ import annotations

from qfluentwidgets import (FluentIcon, FluentWindow, NavigationItemPosition)

from ui.app_config import APP_CFG, AppConfig, apply_theme
from ui.diagnostics_page import DiagnosticsPage
from ui.games_page import GamesPage
from ui.settings_page import SettingsPage


class MainWindow(FluentWindow):
    def __init__(self, cfg: AppConfig = APP_CFG):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("Haptic 低延迟管理器")
        self.resize(1100, 720)

        self.games_page = GamesPage(self)
        self.diagnostics_page = DiagnosticsPage(self)
        self.settings_page = SettingsPage(cfg, self)

        self.addSubInterface(self.games_page, FluentIcon.GAME, "游戏")
        self.addSubInterface(self.diagnostics_page, FluentIcon.SPEED_HIGH,
                             "诊断")
        self.addSubInterface(self.settings_page, FluentIcon.SETTING, "设置",
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
