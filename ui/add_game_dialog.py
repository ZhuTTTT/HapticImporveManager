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
from ui.app_config import APP_CFG

_NAME_RE = re.compile(r"^[a-z0-9_]+$")
_STEPS = "1 选择游戏 → 2 反作弊 → 3 配置 → 4 IFEO"


class AddGameDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("添加游戏", self)
        self.step_label = CaptionLabel(_STEPS, self)

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

        self.back_btn = PushButton("上一步", self)
        self.back_btn.clicked.connect(self._back)
        self.next_btn = PrimaryPushButton("下一步", self)
        self.next_btn.clicked.connect(self._next)
        self.buttonLayout.insertWidget(0, self.back_btn)
        self.buttonLayout.insertWidget(1, self.next_btn)
        self.yesButton.hide()  # 用 back/next 替代
        self.cancelButton.setText("取消")

        self.game_name = ""
        self.game_exe = ""
        self._sync_buttons()

    # ---- 步骤页 ----

    def _build_step_exe(self) -> QWidget:
        w = QWidget(self)
        self.name_edit = LineEdit(w)
        self.name_edit.setPlaceholderText(
            "注册名, 小写字母/数字/下划线, 如 ds2")
        self.exe_edit = LineEdit(w)
        self.exe_edit.setReadOnly(True)
        btn = PushButton("浏览…", w)
        btn.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.exe_edit, 1)
        row.addWidget(btn)
        lay = QFormLayout(w)
        lay.addRow("注册名", self.name_edit)
        lay.addRow("游戏 exe", row)
        return w

    def _build_step_anticheat(self) -> QWidget:
        w = QWidget(self)
        lay = QVBoxLayout(w)
        self.ac_result = BodyLabel("", w)
        self.ac_result.setWordWrap(True)
        self.ac_ack = CheckBox(
            "我已了解: 反作弊游戏注入有封禁风险, 后果自负", w)
        # 只连一次: 在 _enter_anticheat 里连会因来回导航累积重复连接
        self.ac_ack.toggled.connect(lambda _c: self._sync_buttons())
        lay.addWidget(self.ac_result)
        lay.addWidget(self.ac_ack)
        lay.addStretch(1)
        return w

    def _build_step_config(self) -> QWidget:
        w = QWidget(self)
        self.mode_box = ComboBox(w)
        self.mode_box.addItems(config.MODES)
        self.buf_box = SpinBox(w)
        self.buf_box.setRange(1, 8192)
        self.buf_box.setValue(960)
        lay = QFormLayout(w)
        lay.addRow("模式", self.mode_box)
        lay.addRow("缓冲帧数", self.buf_box)
        note = CaptionLabel(
            "普通模式: 大多数游戏可用, 缓冲过小会破音\n"
            "虚拟缓冲: 《黑魂2》需要; UE5 会溢出刷屏; 绝区零丢扬声器声道\n"
            "每个游戏必须单独试, 没有通用最优解", w)
        note.setWordWrap(True)
        lay.addRow(note)
        return w

    def _build_step_ifeo(self) -> QWidget:
        w = QWidget(self)
        lay = QVBoxLayout(w)
        self.ifeo_status = BodyLabel("点击按钮启用(会弹 UAC 提权框)", w)
        self.ifeo_status.setWordWrap(True)
        btn = PrimaryPushButton("启用 IFEO", w)
        btn.clicked.connect(self._enable_ifeo)
        lay.addWidget(self.ifeo_status)
        lay.addWidget(btn)
        lay.addWidget(CaptionLabel(
            "完成后从 Steam/启动器正常启动游戏即自动注入。"
            "也可以稍后在游戏详情页开启。", w))
        lay.addStretch(1)
        return w

    # ---- 导航 ----

    def _sync_buttons(self):
        i = self.stack.currentIndex()
        self.back_btn.setEnabled(i > 0)
        self.next_btn.setText("完成" if i == 3 else "下一步")
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
        path, _ = QFileDialog.getOpenFileName(self, "选择游戏 exe", "",
                                              "Executables (*.exe)")
        if path:
            self.exe_edit.setText(path)

    def _validate_exe(self) -> bool:
        name = self.name_edit.text().strip()
        if not _NAME_RE.match(name):
            InfoBar.warning("注册名", "仅限小写字母/数字/下划线",
                            parent=self, position=InfoBarPosition.TOP)
            return False
        if not self.exe_edit.text():
            InfoBar.warning("游戏 exe", "请选择游戏可执行文件",
                            parent=self, position=InfoBarPosition.TOP)
            return False
        if name in registry.load_or_migrate(str(paths.GAMES_YAML)):
            InfoBar.warning("注册名", f"'{name}' 已被占用",
                            parent=self, position=InfoBarPosition.TOP)
            return False
        self.game_name = name
        self.game_exe = self.exe_edit.text()
        return True

    def _enter_anticheat(self):
        self.report = anticheat.scan_exe(self.game_exe)
        if self.report.risk == "known":
            self.ac_result.setText(
                "检测到反作弊特征:\n· " + "\n· ".join(self.report.hits) +
                "\n\n已知风险: HoYoKProtect 会剥离 OpenProcess 句柄并改名"
                "外来 DLL。本工具采用父进程注入可绕过句柄剥离, "
                "但仍有账号风险。")
            self.ac_ack.setChecked(False)
            self.ac_ack.show()
        else:
            self.ac_result.setText("未检测到已知反作弊特征。")
            self.ac_ack.hide()

    def _anticheat_ok(self) -> bool:
        return (self.report is not None and self.report.risk != "known") \
            or self.ac_ack.isChecked()

    def _write_config(self) -> bool:
        game_dir = os.path.dirname(self.game_exe)
        if os.path.isfile(config.config_file(game_dir)):
            box = MessageBox("配置已存在",
                             "redirect_config.toml 已存在, 覆盖?\n"
                             "(选「否」保留现有配置)", self)
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
        self.ifeo_status.setText("等待提权与注册表写入…")

    def _poll_ifeo(self):
        self._poll_count += 1
        state = ifeo.query_ifeo(os.path.basename(self.game_exe))
        if state == IfeoState.ON_OURS:
            self._timer.stop()
            self.ifeo_status.setText("✓ IFEO 已启用")
        elif self._poll_count >= 10:
            self._timer.stop()
            self.ifeo_status.setText(
                "✗ 提权被取消或失败, 可稍后在游戏详情页重试")

    def _finish(self):
        registry.add_game(registry.GameEntry(
            name=self.game_name,
            exe=self.game_exe,
            mode_hint=self.mode_box.currentText(),
            buffer_hint=self.buf_box.value(),
            anticheat=self.report.risk == "known" if self.report else False,
        ), str(paths.GAMES_YAML))
        self.accept()
