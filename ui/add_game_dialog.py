"""添加游戏向导: 对话框内嵌 4 步(选择 exe → 反作弊 → 配置 → IFEO)。

逻辑移植自旧 ui/add_wizard.py(QWizard 版), 改为 MessageBoxBase +
QStackedWidget + 步骤标签, 视觉与 Fluent 一致。
"""
from __future__ import annotations

import os
import re

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QFileDialog, QFormLayout, QHBoxLayout,
                               QStackedWidget, QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, CheckBox, ComboBox,
                            InfoBar, InfoBarPosition, LineEdit, MessageBox,
                            MessageBoxBase, PrimaryPushButton, PushButton,
                            SpinBox, SubtitleLabel)

from backend import anticheat, config, ifeo, launcher, paths, registry
from backend.ifeo import IfeoState
from i18n import tr
from ui.app_config import APP_CFG

_NAME_RE = re.compile(r"^[a-z0-9_]+$")


class AddGameDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(tr("wizard.title"), self)
        # 步骤标签是文案, 必须在运行时 tr — 模块级常量在 import 时求值,
        # 会冻结在当时的语言(默认 zh), 之后 set_language 对其无效
        self.step_label = CaptionLabel(tr("wizard.steps"), self)

        self.runner = launcher.ProcessRunner(self)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll_ifeo)
        self._poll_count = 0
        self.report: anticheat.AnticheatReport | None = None

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self._build_step_exe())
        self.stack.addWidget(self._build_step_anticheat())
        self.stack.addWidget(self._build_step_config())
        self.stack.addWidget(self._build_step_ifeo())

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.step_label)
        self.viewLayout.addWidget(self.stack)

        self.back_btn = PushButton(tr("wizard.back"), self)
        self.back_btn.clicked.connect(self._back)
        self.next_btn = PrimaryPushButton(tr("wizard.next"), self)
        self.next_btn.clicked.connect(self._next)
        self.buttonLayout.insertWidget(0, self.back_btn)
        self.buttonLayout.insertWidget(1, self.next_btn)
        self.yesButton.hide()  # 用 back/next 替代
        self.cancelButton.setText(tr("wizard.cancel"))

        self.game_name = ""
        self.game_exe = ""
        self._sync_buttons()

    # ---- 步骤页 ----

    def _build_step_exe(self) -> QWidget:
        w = QWidget(self)
        self.name_edit = LineEdit(w)
        self.name_edit.setPlaceholderText(tr("wizard.name_placeholder"))
        self.exe_edit = LineEdit(w)
        self.exe_edit.setReadOnly(True)
        btn = PushButton(tr("wizard.browse"), w)
        btn.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.exe_edit, 1)
        row.addWidget(btn)
        lay = QFormLayout(w)
        lay.addRow(tr("wizard.name_label"), self.name_edit)
        lay.addRow(tr("wizard.exe_label"), row)
        return w

    def _build_step_anticheat(self) -> QWidget:
        w = QWidget(self)
        lay = QVBoxLayout(w)
        self.ac_result = BodyLabel("", w)
        self.ac_result.setWordWrap(True)
        self.ac_ack = CheckBox(tr("wizard.ac_ack"), w)
        # 只连一次: 在 _enter_anticheat 里连会因来回导航累积重复连接
        self.ac_ack.toggled.connect(lambda _c: self._sync_buttons())
        lay.addWidget(self.ac_result)
        lay.addWidget(self.ac_ack)
        lay.addStretch(1)
        return w

    def _build_step_config(self) -> QWidget:
        w = QWidget(self)
        self.mode_box = ComboBox(w)
        # mode 项是 TOML 配置值(backend.config.MODES), 保持英文原文不翻
        self.mode_box.addItems(config.MODES)
        self.buf_box = SpinBox(w)
        self.buf_box.setRange(1, 8192)
        self.buf_box.setValue(960)
        lay = QFormLayout(w)
        lay.addRow(tr("wizard.mode"), self.mode_box)
        lay.addRow(tr("wizard.buffer"), self.buf_box)
        note = CaptionLabel(tr("wizard.config_note"), w)
        note.setWordWrap(True)
        lay.addRow(note)
        return w

    def _build_step_ifeo(self) -> QWidget:
        w = QWidget(self)
        lay = QVBoxLayout(w)
        self.ifeo_status = BodyLabel(tr("wizard.ifeo_hint"), w)
        self.ifeo_status.setWordWrap(True)
        btn = PrimaryPushButton(tr("wizard.ifeo_enable"), w)
        btn.clicked.connect(self._enable_ifeo)
        lay.addWidget(self.ifeo_status)
        lay.addWidget(btn)
        lay.addWidget(CaptionLabel(tr("wizard.ifeo_caption"), w))
        lay.addStretch(1)
        return w

    # ---- 导航 ----

    def _sync_buttons(self):
        i = self.stack.currentIndex()
        self.back_btn.setEnabled(i > 0)
        self.next_btn.setText(tr("wizard.finish") if i == 3
                              else tr("wizard.next"))
        self.next_btn.setEnabled(i != 1 or self._anticheat_ok())

    def _back(self):
        self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
        self._sync_buttons()

    def _next(self):
        i = self.stack.currentIndex()
        if i == 0 and not self._validate_exe():
            return
        if i == 0:
            self._enter_anticheat()
        if i == 2 and not self._write_config():
            return
        if i == 3:
            self._finish()
            return
        self.stack.setCurrentIndex(i + 1)
        self._sync_buttons()

    # ---- 各步逻辑(移植旧 wizard) ----

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("wizard.pick_exe"), "",
                                              "Executables (*.exe)")
        if path:
            self.exe_edit.setText(path)

    def _validate_exe(self) -> bool:
        name = self.name_edit.text().strip()
        if not _NAME_RE.match(name):
            InfoBar.warning(tr("wizard.name_label"),
                            tr("wizard.name_invalid"),
                            parent=self, position=InfoBarPosition.TOP)
            return False
        if not self.exe_edit.text():
            InfoBar.warning(tr("wizard.exe_label"),
                            tr("wizard.exe_missing"),
                            parent=self, position=InfoBarPosition.TOP)
            return False
        if name in registry.load_or_migrate(str(paths.GAMES_YAML)):
            InfoBar.warning(tr("wizard.name_label"),
                            tr("wizard.name_taken", name=name),
                            parent=self, position=InfoBarPosition.TOP)
            return False
        self.game_name = name
        self.game_exe = self.exe_edit.text()
        return True

    def _enter_anticheat(self):
        self.report = anticheat.scan_exe(self.game_exe)
        if self.report.risk == "known":
            # hits 由 backend 翻译(anticheat.scan_exe 运行时 tr), 直接拼入
            self.ac_result.setText(
                tr("wizard.ac_known", hits="\n· ".join(self.report.hits)))
            self.ac_ack.setChecked(False)
            self.ac_ack.show()
        else:
            self.ac_result.setText(tr("wizard.ac_none"))
            self.ac_ack.hide()

    def _anticheat_ok(self) -> bool:
        return (self.report is not None and self.report.risk != "known") \
            or self.ac_ack.isChecked()

    def _write_config(self) -> bool:
        game_dir = os.path.dirname(self.game_exe)
        if os.path.isfile(config.config_file(game_dir)):
            box = MessageBox(tr("wizard.config_exists_title"),
                             tr("wizard.config_exists_msg"), self)
            if not box.exec():
                return True
        doc = config.default_config(APP_CFG.log_dir.value)
        doc["playback"]["mode"] = self.mode_box.currentText()
        # tomlkit 点分键子表键是字符串 "48000", int 键 TypeError
        doc["playback"]["target_buffer_len"]["48000"] = self.buf_box.value()
        if self.mode_box.currentText() == "Ringbuf":
            doc["playback"]["ring_buffer_len"]["48000"] = \
                self.buf_box.value()
        config.save_config(game_dir, doc)
        return True

    def _enable_ifeo(self):
        launcher.set_ifeo(self.runner, self.game_name, True)
        self._poll_count = 0
        self._timer.stop()  # 重复点击先停旧定时器
        self._timer.start()
        self.ifeo_status.setText(tr("wizard.ifeo_pending"))

    def _poll_ifeo(self):
        self._poll_count += 1
        state = ifeo.query_ifeo(os.path.basename(self.game_exe))
        if state == IfeoState.ON_OURS:
            self._timer.stop()
            self.ifeo_status.setText(tr("wizard.ifeo_ok"))
        elif self._poll_count >= 10:
            self._timer.stop()
            self.ifeo_status.setText(tr("wizard.ifeo_fail"))

    def _finish(self):
        registry.add_game(registry.GameEntry(
            name=self.game_name,
            exe=self.game_exe,
            mode_hint=self.mode_box.currentText(),
            buffer_hint=self.buf_box.value(),
            anticheat=self.report.risk == "known" if self.report else False,
        ), str(paths.GAMES_YAML))
        self.accept()
