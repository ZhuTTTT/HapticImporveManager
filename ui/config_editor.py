"""redirect_config.toml 可视化编辑页。

tomlkit 键注意: 点分键 target_buffer_len.48000 解析后子表键是字符串 "48000"
(与 tests/test_config.py 一致); 赋值也必须用字符串键, int 键会 TypeError。
保存用原位改值(tbl[key] = v), 整体替换子表会丢注释并把点分键变成子表段。
"""
import os

import tomlkit
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout,
                               QLabel, QMessageBox, QPlainTextEdit, QPushButton,
                               QSlider, QSpinBox, QVBoxLayout, QWidget)

from backend import config, launcher, registry


class ConfigEditorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.games: dict[str, registry.GameEntry] = {}
        self.doc = None

        self.game_box = QComboBox()
        self.game_box.currentTextChanged.connect(self._load)

        self.mode = QComboBox()
        self.mode.addItems(config.MODES)
        self.mode.currentTextChanged.connect(self._on_mode_changed)
        self.period = QSlider(Qt.Orientation.Horizontal)
        self.period.setRange(0, 1000)
        self.period.setValue(100)
        self.period_label = QLabel("10.0 ms")
        self.period.valueChanged.connect(
            lambda v: self.period_label.setText(
                "原生" if v == 0 else f"{v / 10:.1f} ms"))
        period_row = QHBoxLayout()
        period_row.addWidget(self.period, 1)
        period_row.addWidget(self.period_label)

        self.buf_normal = QSpinBox()
        self.buf_normal.setRange(1, 65536)
        self.buf_ring = QSpinBox()
        self.buf_ring.setRange(1, 65536)
        self.raw = QCheckBox("raw")
        self.force_period = QCheckBox("force_period")
        self.log_level = QComboBox()
        self.log_level.addItems(["Error", "Info"])
        self.log_level.currentTextChanged.connect(self._on_log_level)

        self.form = QFormLayout()
        self.form.addRow("模式", self.mode)
        self.form.addRow("目标周期", period_row)
        self.form.addRow("Normal 缓冲帧数", self.buf_normal)
        self.form.addRow("Ringbuf 虚拟缓冲帧数", self.buf_ring)
        self.form.addRow(self.raw)
        self.form.addRow(self.force_period)
        self.form.addRow("日志级别", self.log_level)

        self.mode_hint = QLabel()
        self.mode_hint.setWordWrap(True)
        self.mode_hint.setStyleSheet("color:#888;")

        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self._save)
        btn_default = QPushButton("恢复默认")
        btn_default.clicked.connect(self._reset_default)
        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_default)
        btn_row.addStretch(1)

        self.error_view = QPlainTextEdit()
        self.error_view.setReadOnly(True)
        self.error_view.hide()

        self.form_host = QWidget()
        self.form_host.setLayout(self.form)

        lay = QVBoxLayout(self)
        lay.addWidget(self.game_box)
        lay.addWidget(self.form_host)
        lay.addWidget(self.mode_hint)
        lay.addLayout(btn_row)
        lay.addWidget(self.error_view, 1)

        self.reload_games()

    def reload_games(self):
        self.games = registry.load_or_migrate()
        self.game_box.blockSignals(True)
        self.game_box.clear()
        for name, e in self.games.items():
            self.game_box.addItem(name + ("" if e.config_exists else " (无配置)"))
        self.game_box.blockSignals(False)
        if self.games:
            self._load(self.game_box.currentText())

    def select_game(self, name: str):
        self.reload_games()
        for i in range(self.game_box.count()):
            if self.game_box.itemText(i).startswith(name):
                self.game_box.setCurrentIndex(i)
                break

    def _entry(self) -> registry.GameEntry:
        return self.games[self.game_box.currentText().split(" ")[0]]

    def _load(self, _text: str):
        entry = self._entry()
        try:
            self.doc = config.load_config(entry.game_dir)
        except FileNotFoundError:
            if QMessageBox.question(
                    self, "无配置",
                    f"{entry.name} 没有 redirect_config.toml, 生成默认配置?"
                    ) == QMessageBox.StandardButton.Yes:
                self.doc = config.default_config()
                config.save_config(entry.game_dir, self.doc)
            else:
                return
        except Exception as e:  # tomlkit 语法错误: 显示原文, 禁表单与保存
            self.doc = None
            self.form_host.setEnabled(False)
            self.error_view.show()
            self.error_view.setPlainText(
                f"配置解析失败: {e}\n\n"
                + open(entry.config_path, encoding="utf-8").read())
            return
        self.error_view.hide()
        self.form_host.setEnabled(True)
        pb = self.doc.get("playback", {})
        self.mode.setCurrentText(pb.get("mode", "Normal"))
        self.period.setValue(int(pb.get("target_period_hus", 100)))
        tbl = pb.get("target_buffer_len", {})
        self.buf_normal.setValue(int(next(iter(tbl.values()), 960)))
        rbl = pb.get("ring_buffer_len", {})
        self.buf_ring.setValue(int(next(iter(rbl.values()), 4320)))
        self.raw.setChecked(bool(pb.get("raw", True)))
        self.force_period.setChecked(bool(pb.get("force_period", True)))
        self.log_level.blockSignals(True)
        self.log_level.setCurrentText(self.doc.get("log_level", "Error"))
        self.log_level.blockSignals(False)
        self._on_mode_changed(self.mode.currentText())

    def _on_mode_changed(self, mode: str):
        self.buf_normal.setEnabled(mode == "Normal")
        self.buf_ring.setEnabled(mode == "Ringbuf")
        hints = {
            "Normal": "游戏直接面对真实小缓冲。大多数游戏可用(剑星/ZZZ 验证), 缓冲过小会破音。",
            "Ringbuf": "给游戏虚拟大缓冲。DS2 需要它; UE5 大爆发写入会溢出刷屏; ZZZ 丢手柄扬声器声道。",
            "Compat": "兼容模式, 遇到问题再试。",
            "Bypass": "不干预, 原生延迟。",
        }
        self.mode_hint.setText(hints.get(mode, ""))

    def _on_log_level(self, level: str):
        if level != "Error":
            r = QMessageBox.warning(
                self, "日志级别",
                "Info 在 overflow 时可写 GB 级日志(实测一次会话 2.9GB)。\n"
                "仅排障临时使用, 确定切换?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if r != QMessageBox.StandardButton.Ok:
                self.log_level.blockSignals(True)
                self.log_level.setCurrentText("Error")
                self.log_level.blockSignals(False)

    def _reset_default(self):
        if QMessageBox.question(self, "恢复默认",
                                "用默认配置覆盖当前表单?(未保存)") \
                == QMessageBox.StandardButton.Yes:
            self.doc = config.default_config()
            pb = self.doc["playback"]
            self.mode.setCurrentText(pb["mode"])
            self.period.setValue(pb["target_period_hus"])
            self.buf_normal.setValue(960)
            self.buf_ring.setValue(4320)
            self.raw.setChecked(True)
            self.force_period.setChecked(True)
            self.log_level.setCurrentText("Error")

    @staticmethod
    def _set_buf(pb, field: str, value: int):
        """原位改 target_buffer_len/ring_buffer_len 的帧数, 保留注释与点分格式。"""
        tbl = pb.get(field)
        if tbl is None:
            tbl = tomlkit.table()
            pb[field] = tbl
        key = next(iter(tbl.keys()), "48000")
        tbl[str(key)] = value  # tomlkit 子表键是字符串 "48000", int 键会 TypeError

    def _save(self):
        if self.doc is None:
            return
        entry = self._entry()
        pb = self.doc["playback"]
        pb["mode"] = self.mode.currentText()
        pb["target_period_hus"] = self.period.value()
        self._set_buf(pb, "target_buffer_len", self.buf_normal.value())
        self._set_buf(pb, "ring_buffer_len", self.buf_ring.value())
        pb["raw"] = self.raw.isChecked()
        pb["force_period"] = self.force_period.isChecked()
        self.doc["log_level"] = self.log_level.currentText()

        problems = config.validate(self.doc)
        if problems:
            QMessageBox.warning(self, "校验失败", "\n".join(problems))
            return
        config.save_config(entry.game_dir, self.doc)
        msg = "已保存。"
        if launcher.is_game_running(os.path.basename(entry.exe)):
            msg += "\n游戏正在运行, 重启后生效。"
        QMessageBox.information(self, "保存", msg)
