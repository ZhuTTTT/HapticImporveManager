from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QMainWindow,
                               QStackedWidget, QWidget)

from ui.config_editor import ConfigEditorPage
from ui.games_page import GamesPage
from ui.monitor_page import MonitorPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Haptic 低延迟管理器")
        self.resize(1000, 640)

        self.nav = QListWidget()
        self.nav.setFixedWidth(140)
        self.nav.addItems(["游戏", "配置编辑", "状态监控"])

        self.pages = QStackedWidget()
        # 占位页, 后续任务按索引替换为真实页面
        self.pages.addWidget(QLabel("游戏列表(待实现)"))
        self.pages.addWidget(QLabel("配置编辑(待实现)"))
        self.pages.addWidget(QLabel("状态监控(待实现)"))

        self.games_page = GamesPage()
        self.replace_page(0, self.games_page)

        self.config_page = ConfigEditorPage()
        self.replace_page(1, self.config_page)
        self.games_page.edit_requested.connect(self._goto_config)

        self.monitor_page = MonitorPage()
        self.replace_page(2, self.monitor_page)
        self.games_page.runner.line.connect(self.monitor_page.append_event)

        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.nav)
        lay.addWidget(self.pages, 1)
        self.setCentralWidget(central)

    def replace_page(self, index: int, widget: QWidget):
        old = self.pages.widget(index)
        self.pages.removeWidget(old)
        old.deleteLater()
        self.pages.insertWidget(index, widget)

    def _goto_config(self, name: str):
        self.config_page.select_game(name)
        self.nav.setCurrentRow(1)
