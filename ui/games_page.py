"""游戏中心主页: 左列表(搜索过滤) + 右详情(选中即上下文)。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QListWidgetItem, QStackedWidget,
                               QVBoxLayout, QWidget)
from qfluentwidgets import (CaptionLabel, FluentIcon, ListWidget,
                            PrimaryPushButton, SearchLineEdit,
                            StrongBodyLabel)

from backend import launcher, paths, registry
from ui.game_detail import GameDetailPage


class GamesPage(QWidget):
    log_line = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("games")
        self.runner = launcher.ProcessRunner(self)
        self.runner.line.connect(self.log_line)

        self.search = SearchLineEdit(self)
        self.search.setPlaceholderText("搜索游戏…")
        self.search.textChanged.connect(self._filter)
        self.btn_add = PrimaryPushButton(FluentIcon.ADD, "添加游戏", self)
        self.btn_add.clicked.connect(self._add_game)
        self.game_list = ListWidget(self)
        self.game_list.currentRowChanged.connect(self._on_select)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.addWidget(self.search)
        left.addWidget(self.game_list, 1)
        left.addWidget(self.btn_add)
        left_host = QWidget(self)
        left_host.setLayout(left)
        left_host.setFixedWidth(220)

        # 空状态
        empty = QWidget(self)
        el = QVBoxLayout(empty)
        el.addStretch(1)
        t = StrongBodyLabel("还没有游戏", empty)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c = CaptionLabel("点击左下角「添加游戏」, 四步完成接入", empty)
        c.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addWidget(t)
        el.addWidget(c)
        el.addStretch(1)

        self.detail = GameDetailPage(self.runner, self)
        self.detail.config_changed.connect(self._on_detail_changed)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(empty)    # index 0
        self.stack.addWidget(self.detail)  # index 1

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(left_host)
        lay.addWidget(self.stack, 1)

        self._games: dict[str, registry.GameEntry] = {}
        self.refresh()

    def refresh(self):
        self._games = registry.load_or_migrate(str(paths.GAMES_YAML))
        self.game_list.blockSignals(True)
        self.game_list.clear()
        for name, entry in self._games.items():
            mark = "● " if (entry.exe_exists and entry.config_exists) \
                else "○ "
            QListWidgetItem(mark + name, self.game_list)
        self.game_list.blockSignals(False)
        if self._games:
            self.game_list.setCurrentRow(0)
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)

    def _filter(self, text: str):
        for i in range(self.game_list.count()):
            item = self.game_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_select(self, row: int):
        if row < 0:
            return
        name = self.game_list.item(row).text()[2:]  # 去掉 "● " 前缀
        entry = self._games.get(name)
        if entry is None:
            return
        if self.detail.set_game(entry):
            self.stack.setCurrentIndex(1)
        else:
            # 用户不放弃未保存修改: 回退列表选中到详情页当前游戏
            cur = self.detail.entry
            if cur is None:
                return
            for i in range(self.game_list.count()):
                if self.game_list.item(i).text()[2:] == cur.name:
                    self.game_list.blockSignals(True)
                    self.game_list.setCurrentRow(i)
                    self.game_list.blockSignals(False)
                    break

    def _on_detail_changed(self, _name: str):
        self.refresh()

    def _add_game(self):
        from ui.add_game_dialog import AddGameDialog
        if AddGameDialog(self).exec():
            self.refresh()
