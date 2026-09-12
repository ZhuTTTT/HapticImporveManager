import os
import re

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QSpinBox, QVBoxLayout, QWizard,
                               QWizardPage)

from backend import anticheat, config, ifeo, launcher, registry
from backend.ifeo import IfeoState

_NAME_RE = re.compile(r"^[a-z0-9_]+$")


class PageExe(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("选择游戏")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("注册名, 小写字母/数字/下划线, 如 ds2")
        self.exe_edit = QLineEdit()
        self.exe_edit.setReadOnly(True)
        btn = QPushButton("浏览…")
        btn.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.exe_edit, 1)
        row.addWidget(btn)
        lay = QFormLayout(self)
        lay.addRow("注册名", self.name_edit)
        lay.addRow("游戏 exe", row)
        self.registerField("game_name*", self.name_edit)
        self.registerField("game_exe*", self.exe_edit)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择游戏 exe", "", "Executables (*.exe)")
        if path:
            self.exe_edit.setText(path)

    def validatePage(self):
        name = self.name_edit.text().strip()
        if not _NAME_RE.match(name):
            QMessageBox.warning(self, "注册名", "仅限小写字母/数字/下划线")
            return False
        if name in registry.load_or_migrate():
            QMessageBox.warning(self, "注册名", f"'{name}' 已被占用")
            return False
        return True


class PageAnticheat(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("反作弊检测")
        self.result = QLabel()
        self.result.setWordWrap(True)
        self.ack = QCheckBox("我已了解: 反作弊游戏注入有封禁风险, 后果自负")
        self.ack.toggled.connect(self.completeChanged)
        lay = QVBoxLayout(self)
        lay.addWidget(self.result)
        lay.addWidget(self.ack)

    def initializePage(self):
        exe = self.field("game_exe")
        self.report = anticheat.scan_exe(exe)
        if self.report.risk == "known":
            self.result.setStyleSheet("color:#e5484d;")
            self.result.setText(
                "检测到反作弊特征:\n· " + "\n· ".join(self.report.hits) +
                "\n\n已知风险: HoYoKProtect 会剥离 OpenProcess 句柄并改名外来 DLL。"
                "本工具采用父进程注入可绕过句柄剥离, 但仍有账号风险。")
            self.ack.setChecked(False)
            self.ack.show()
        else:
            self.result.setStyleSheet("color:#30a46c;")
            self.result.setText("未检测到已知反作弊特征。")
            self.ack.hide()

    def isComplete(self):
        return self.report.risk != "known" or self.ack.isChecked()


class PageConfig(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("生成 redirect_config.toml")
        self.mode = QComboBox()
        self.mode.addItems(config.MODES)
        self.buf = QSpinBox()
        self.buf.setRange(1, 8192)
        self.buf.setValue(960)
        note = QLabel("Normal: 大多数游戏可用, 缓冲过小会破音\n"
                      "Ringbuf: DS2 需要; UE5 爆发写入会溢出刷屏; ZZZ 丢扬声器声道\n"
                      "每个游戏必须单独试, 没有通用最优解")
        note.setStyleSheet("color:#888;")
        note.setWordWrap(True)
        lay = QFormLayout(self)
        lay.addRow("模式", self.mode)
        lay.addRow("缓冲帧数", self.buf)
        lay.addRow(note)

    def validatePage(self):
        game_dir = os.path.dirname(self.field("game_exe"))
        cfg_path = config.config_file(game_dir)
        if os.path.isfile(cfg_path):
            r = QMessageBox.question(
                self, "配置已存在",
                "redirect_config.toml 已存在, 覆盖?\n(选 No 保留现有配置)")
            if r != QMessageBox.StandardButton.Yes:
                return True
        doc = config.default_config()
        doc["playback"]["mode"] = self.mode.currentText()
        # tomlkit 要求字符串键 — 点分键 target_buffer_len.48000 解析后为 str
        doc["playback"]["target_buffer_len"]["48000"] = self.buf.value()
        if self.mode.currentText() == "Ringbuf":
            doc["playback"]["ring_buffer_len"]["48000"] = self.buf.value()
        config.save_config(game_dir, doc)
        return True


class PageIfeo(QWizardPage):
    def __init__(self, runner: launcher.ProcessRunner):
        super().__init__()
        self.setTitle("启用 IFEO 自动注入")
        self.runner = runner
        self.status = QLabel("点击按钮启用(会弹 UAC 提权框)")
        self.status.setWordWrap(True)
        btn = QPushButton("启用 IFEO")
        btn.clicked.connect(self._enable)
        lay = QVBoxLayout(self)
        lay.addWidget(self.status)
        lay.addWidget(btn)
        note = QLabel("完成后从 Steam/启动器正常启动游戏即自动注入。")
        note.setStyleSheet("color:#888;")
        lay.addWidget(note)

    def _enable(self):
        launcher.set_ifeo(self.runner, self.field("game_name").strip(), True)
        self._poll_count = 0
        if getattr(self, "_timer", None) is not None:
            self._timer.stop()  # 重复点击时先停旧定时器, 避免多个 QTimer 并发触发
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self.status.setText("等待提权与注册表写入…")

    def _poll(self):
        self._poll_count += 1
        exe_name = os.path.basename(self.field("game_exe"))
        state = ifeo.query_ifeo(exe_name)
        if state == IfeoState.ON_OURS:
            self._timer.stop()
            self.status.setText("✓ IFEO 已启用")
        elif self._poll_count >= 10:
            self._timer.stop()
            self.status.setText("✗ 提权被取消或失败, 可稍后在游戏列表页重试")


class AddGameWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加游戏")
        self.runner = launcher.ProcessRunner(self)
        self.addPage(PageExe())
        self.addPage(PageAnticheat())
        self.addPage(PageConfig())
        self.addPage(PageIfeo(self.runner))

    def accept(self):
        registry.add_game(registry.GameEntry(
            name=self.field("game_name").strip(),
            exe=self.field("game_exe"),
            mode_hint=self.page(2).mode.currentText(),
            buffer_hint=self.page(2).buf.value(),
            anticheat=self.page(1).report.risk == "known",
        ))
        super().accept()
