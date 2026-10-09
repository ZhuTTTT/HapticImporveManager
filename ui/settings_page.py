"""设置页: 主题 / Mica / 日志目录(可改 + 一键打开 + 批量同步)。"""
from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, ComboBox, LineEdit,
                            MessageBox, PushButton, StrongBodyLabel,
                            SwitchButton, TitleLabel, InfoBar,
                            InfoBarPosition)

from backend import paths, registry
from ui.app_config import AppConfig, apply_theme
from ui.log_dir_sync import sync_log_dir

_THEME_LABELS = ["浅色", "深色", "跟随系统"]
_THEME_VALUES = ["Light", "Dark", "Auto"]


class SettingsPage(QWidget):
    log_dir_changed = Signal(str)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.setObjectName("settings")
        self.cfg = cfg

        title = TitleLabel("设置", self)

        # 主题
        self.theme_box = ComboBox(self)
        self.theme_box.addItems(_THEME_LABELS)
        self.theme_box.setCurrentIndex(
            _THEME_VALUES.index(cfg.theme_mode.value))
        self.theme_box.currentIndexChanged.connect(self._on_theme)

        # Mica
        self.mica_switch = SwitchButton(self)
        self.mica_switch.setChecked(cfg.mica_enabled.value)
        self.mica_switch.setOnText("开")
        self.mica_switch.setOffText("关")
        self.mica_switch.checkedChanged.connect(self._on_mica)

        # 日志目录
        self.log_dir_edit = LineEdit(self)
        self.log_dir_edit.setReadOnly(True)
        self.log_dir_edit.setText(cfg.log_dir.value)
        self.btn_change_dir = PushButton("更改…", self)
        self.btn_change_dir.clicked.connect(self._change_dir)
        self.btn_open_dir = PushButton("在资源管理器中打开", self)
        self.btn_open_dir.clicked.connect(self._open_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.log_dir_edit, 1)
        dir_row.addWidget(self.btn_change_dir)
        dir_row.addWidget(self.btn_open_dir)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(12)
        lay.addWidget(title)
        lay.addWidget(StrongBodyLabel("主题", self))
        lay.addWidget(self.theme_box)
        lay.addWidget(StrongBodyLabel("云母背景(Win11)", self))
        lay.addWidget(self.mica_switch)
        lay.addWidget(StrongBodyLabel("日志目录", self))
        lay.addWidget(CaptionLabel(
            "wasapi_relink.log 的存放位置。更改后可同步到所有已注册游戏的配置。",
            self))
        lay.addLayout(dir_row)
        lay.addStretch(1)

    def _on_theme(self, idx: int):
        self.cfg.theme_mode.value = _THEME_VALUES[idx]
        self.cfg.save()
        apply_theme(self.cfg)

    def _on_mica(self, on: bool):
        self.cfg.mica_enabled.value = on
        self.cfg.save()
        win = self.window()
        if hasattr(win, "apply_mica"):
            win.apply_mica()

    def _change_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择日志目录",
                                             self.cfg.log_dir.value)
        if not d:
            return
        games = registry.load_or_migrate(str(paths.GAMES_YAML))
        box = MessageBox("同步日志目录",
                         f"新目录: {d}\n\n是否同步更新所有已注册游戏"
                         f"({len(games)} 个)的 redirect_config.toml?\n"
                         "选「否」则只影响以后新添加的游戏。", self)
        box.yesButton.setText("同步所有游戏")
        box.cancelButton.setText("仅以后生效")
        self.cfg.log_dir.value = d
        self.cfg.save()
        self.log_dir_edit.setText(d)
        if box.exec():
            ok, failed = sync_log_dir(d, games)
            if failed:
                InfoBar.warning("部分同步失败",
                                f"已同步 {ok} 个; 失败: {', '.join(failed)}"
                                "(配置缺失或损坏, 请到对应游戏详情修复)",
                                parent=self, position=InfoBarPosition.TOP,
                                duration=6000)
            else:
                InfoBar.success("已同步", f"已更新 {ok} 个游戏的配置",
                                parent=self, position=InfoBarPosition.TOP,
                                duration=3000)
        # 无论是否批量同步, 设置里的目录已变 — 诊断页 watcher 需重建到新路径
        self.log_dir_changed.emit(d)

    def _open_dir(self):
        d = self.cfg.log_dir.value
        os.makedirs(d, exist_ok=True)
        subprocess.Popen(["explorer", d])
