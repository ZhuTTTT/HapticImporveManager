import os

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QMessageBox, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from backend import ifeo, launcher, registry
from backend.ifeo import IfeoState

_LAMP_STYLE = "border-radius:7px; min-width:14px; max-width:14px; min-height:14px; max-height:14px; background:%s;"


class GameCard(QFrame):
    edit_requested = Signal(str)
    removed = Signal()

    def __init__(self, entry: registry.GameEntry, runner: launcher.ProcessRunner,
                 parent=None):
        super().__init__(parent)
        self.entry = entry
        self.runner = runner
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(280)

        self.lamp = QLabel()
        title = QLabel(f"<b>{entry.name}</b>")
        path = QLabel(entry.exe)
        path.setToolTip(entry.exe)
        path.setStyleSheet("color:#888;")
        path.setMaximumWidth(260)

        hint = QLabel(f"模式 {entry.mode_hint} · 缓冲 {entry.buffer_hint}"
                      + (" · ⚠ 反作弊" if entry.anticheat else ""))
        self.ifeo_box = QCheckBox("IFEO 自动注入")
        self.ifeo_box.toggled.connect(self._on_ifeo_toggled)

        btn_launch = QPushButton("启动")
        btn_launch.clicked.connect(self._launch)
        btn_edit = QPushButton("编辑配置")
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(entry.name))
        btn_remove = QPushButton("移除")
        btn_remove.clicked.connect(self._remove)
        self._btn_launch = btn_launch

        top = QHBoxLayout()
        top.addWidget(self.lamp)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.ifeo_box)
        btns = QHBoxLayout()
        for b in (btn_launch, btn_edit, btn_remove):
            btns.addWidget(b)
        btns.addStretch(1)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(path)
        lay.addWidget(hint)
        lay.addLayout(btns)

        self.refresh_status()

    def refresh_status(self):
        e = self.entry
        state = ifeo.query_ifeo(os.path.basename(e.exe))
        if not e.exe_exists:
            color, tip = "#e5484d", "exe 丢失"
        elif e.config_exists and state == IfeoState.ON_OURS:
            color, tip = "#30a46c", "就绪"
        else:
            color, tip = "#f5b942", "配置/IFEO 未完成"
        if state == IfeoState.ON_OTHER:
            tip += "(IFEO 被其他调试器占用!)"
        self.lamp.setStyleSheet(_LAMP_STYLE % color)
        self.lamp.setToolTip(tip)
        self.ifeo_box.blockSignals(True)
        self.ifeo_box.setChecked(state == IfeoState.ON_OURS)
        self.ifeo_box.blockSignals(False)
        self._btn_launch.setEnabled(e.exe_exists)

    def _on_ifeo_toggled(self, checked: bool):
        launcher.set_ifeo(self.runner, self.entry.name, checked)
        self._poll_count = 0
        if getattr(self, "_poll", None) is not None:
            self._poll.stop()  # 重复勾选时先停旧定时器, 避免多个 QTimer 并发触发
        self._poll = QTimer(self)
        self._poll.setInterval(1000)
        self._poll.timeout.connect(self._poll_ifeo)
        self._poll.start()

    def _poll_ifeo(self):
        self._poll_count += 1
        state = ifeo.query_ifeo(os.path.basename(self.entry.exe))
        want = IfeoState.ON_OURS if self.ifeo_box.isChecked() else IfeoState.OFF
        if state == want or self._poll_count >= 10:
            self._poll.stop()
            if state != want:
                QMessageBox.warning(self, "IFEO", "提权被取消或操作失败, 状态未变更")
            self.refresh_status()

    def _launch(self):
        launcher.launch_game(self.runner, self.entry.name)

    def _remove(self):
        if QMessageBox.question(self, "移除游戏",
                                f"从列表移除 {self.entry.name}?"
                                "(不动游戏文件和 IFEO)") == QMessageBox.StandardButton.Yes:
            registry.remove_game(self.entry.name)
            self.removed.emit()


class GamesPage(QWidget):
    edit_requested = Signal(str)
    log_line = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.runner = launcher.ProcessRunner(self)
        self.runner.line.connect(self.log_line)
        self._cards_area = QWidget()
        self._grid = QGridLayout(self._cards_area)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._cards_area)
        lay = QVBoxLayout(self)
        btn_add = QPushButton("＋ 添加游戏")
        btn_add.clicked.connect(self._add_wizard)
        lay.addWidget(btn_add)
        lay.addWidget(scroll)
        self.refresh()

    def _add_wizard(self):
        from ui.add_wizard import AddGameWizard
        if AddGameWizard(self).exec():
            self.refresh()

    def refresh(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        games = registry.load_or_migrate()
        for i, entry in enumerate(games.values()):
            card = GameCard(entry, self.runner)
            card.edit_requested.connect(self.edit_requested)
            card.removed.connect(self.refresh)
            self._grid.addWidget(card, i // 3, i % 3)
