"""游戏中心主页: 左列表(搜索过滤 + 状态点列表项) + 右详情(选中即上下文)。"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QListWidgetItem, QStackedWidget,
                               QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, FluentIcon, IconWidget,
                            ListWidget, PrimaryPushButton, SearchLineEdit,
                            StrongBodyLabel)

from backend import ifeo, launcher, paths, registry
from backend.config import MODES
from backend.ifeo import IfeoState
from i18n import tr
from ui import theme
from ui.game_detail import GameDetailPage


def _status_level(entry: registry.GameEntry) -> str:
    """列表状态点语义: err=exe 丢失, ok=就绪(配置+IFEO 就位), warn=其余。"""
    if not entry.exe_exists:
        return "err"
    if entry.config_exists and ifeo.query_ifeo(
            os.path.basename(entry.exe)) == IfeoState.ON_OURS:
        return "ok"
    return "warn"


class _GameItemWidget(QWidget):
    """列表项: 语义色状态点 + 游戏名 + 模式提示。"""

    def __init__(self, entry: registry.GameEntry, level: str, parent=None):
        super().__init__(parent)
        dot = QWidget(self)
        dot.setFixedSize(10, 10)
        c = theme.status_color(level)
        dot.setStyleSheet(f"background: {c}; border-radius: 5px;")
        name = BodyLabel(entry.name, self)
        # mode_hint 是注册表中的模式键(Normal/…), 显示时译为模式卡标题;
        # 意外值(手改 yaml)原样显示而不露出消息键
        mode_titles = {m: tr(f"mode.{m}.title") for m in MODES}
        hint = CaptionLabel(
            f"{mode_titles.get(entry.mode_hint, entry.mode_hint)} · "
            f"{tr('unit.frames', n=entry.buffer_hint)}", self)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        text_col.addWidget(name)
        text_col.addWidget(hint)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(text_col, 1)
        lay.addStretch(0)


class GamesPage(QWidget):
    log_line = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("games")
        self.runner = launcher.ProcessRunner(self)
        self.runner.line.connect(self.log_line)

        self.search = SearchLineEdit(self)
        self.search.setPlaceholderText(tr("games.search_placeholder"))
        self.search.textChanged.connect(self._filter)
        self.btn_add = PrimaryPushButton(FluentIcon.ADD, tr("games.add"), self)
        self.btn_add.clicked.connect(self._add_game)
        self.game_list = ListWidget(self)
        self.game_list.currentRowChanged.connect(self._on_select)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(8)
        left.addWidget(self.search)
        left.addWidget(self.game_list, 1)
        left.addWidget(self.btn_add)
        left_host = QWidget(self)
        left_host.setLayout(left)
        left_host.setFixedWidth(240)

        # 空状态: 图标 + 引导
        empty = QWidget(self)
        el = QVBoxLayout(empty)
        el.addStretch(1)
        icon = IconWidget(FluentIcon.GAME, empty)
        icon.setFixedSize(64, 64)
        el.addWidget(icon, 0, Qt.AlignmentFlag.AlignCenter)
        el.addSpacing(12)
        t = StrongBodyLabel(tr("games.empty_title"), empty)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c = CaptionLabel(tr("games.empty_caption"), empty)
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

    def _item_name(self, row: int) -> str | None:
        item = self.game_list.item(row)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def refresh(self):
        # 记住当前上下文, 重建列表后按名恢复选中(保存配置不跳回第一款)
        prev = self.detail.entry.name if self.detail.entry is not None else None
        self._games = registry.load_or_migrate(str(paths.GAMES_YAML))
        self.game_list.blockSignals(True)
        self.game_list.clear()
        for name, entry in self._games.items():
            item = QListWidgetItem(self.game_list)
            item.setData(Qt.ItemDataRole.UserRole, name)
            w = _GameItemWidget(entry, _status_level(entry))
            item.setSizeHint(w.sizeHint())
            self.game_list.setItemWidget(item, w)
        self.game_list.blockSignals(False)
        if self._games:
            row = 0
            if prev is not None:
                for i in range(self.game_list.count()):
                    if self._item_name(i) == prev:
                        row = i
                        break
            self.game_list.setCurrentRow(row)
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)

    def _filter(self, text: str):
        for i in range(self.game_list.count()):
            item = self.game_list.item(i)
            item.setHidden(text.lower() not in
                           str(self._item_name(i)).lower())

    def _on_select(self, row: int):
        if row < 0:
            return
        entry = self._games.get(self._item_name(row))
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
                if self._item_name(i) == cur.name:
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
