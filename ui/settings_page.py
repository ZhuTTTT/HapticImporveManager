"""设置页: 语言 / 主题 / Mica / 日志目录(可改 + 一键打开 + 批量同步)。"""
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
from i18n import tr
from ui.app_config import AppConfig, apply_theme
from ui.log_dir_sync import sync_log_dir

# 值为配置枚举, 非显示文案, 可留模块级; 显示标签必须在 __init__ 里 tr()
_THEME_VALUES = ["Light", "Dark", "Auto"]
_LANG_VALUES = ["System", "zh", "en"]


class SettingsPage(QWidget):
    log_dir_changed = Signal(str)

    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.setObjectName("settings")
        self.cfg = cfg

        title = TitleLabel(tr("settings.title"), self)

        # 语言(重启后生效): 首项随当前语言翻译, 后两项用各语言自称,
        # 保证用户在任何语言界面下都能认出自己的语言
        self.lang_box = ComboBox(self)
        self.lang_box.addItems([tr("settings.lang_system"), "中文", "English"])
        self.lang_box.setCurrentIndex(_LANG_VALUES.index(cfg.language.value))
        self.lang_box.currentIndexChanged.connect(self._on_language)

        # 主题
        self.theme_box = ComboBox(self)
        self.theme_box.addItems([tr("settings.theme_light"),
                                 tr("settings.theme_dark"),
                                 tr("settings.theme_auto")])
        self.theme_box.setCurrentIndex(
            _THEME_VALUES.index(cfg.theme_mode.value))
        self.theme_box.currentIndexChanged.connect(self._on_theme)

        # Mica
        self.mica_switch = SwitchButton(self)
        self.mica_switch.setChecked(cfg.mica_enabled.value)
        self.mica_switch.setOnText(tr("common.on"))
        self.mica_switch.setOffText(tr("common.off"))
        self.mica_switch.checkedChanged.connect(self._on_mica)

        # 日志目录
        self.log_dir_edit = LineEdit(self)
        self.log_dir_edit.setReadOnly(True)
        self.log_dir_edit.setText(cfg.log_dir.value)
        self.btn_change_dir = PushButton(tr("settings.log_dir_change"), self)
        self.btn_change_dir.clicked.connect(self._change_dir)
        self.btn_open_dir = PushButton(tr("settings.log_dir_open"), self)
        self.btn_open_dir.clicked.connect(self._open_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.log_dir_edit, 1)
        dir_row.addWidget(self.btn_change_dir)
        dir_row.addWidget(self.btn_open_dir)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(12)
        lay.addWidget(title)
        lay.addWidget(StrongBodyLabel(tr("settings.language"), self))
        lay.addWidget(self.lang_box)
        lay.addWidget(StrongBodyLabel(tr("settings.theme"), self))
        lay.addWidget(self.theme_box)
        lay.addWidget(StrongBodyLabel(tr("settings.mica"), self))
        lay.addWidget(self.mica_switch)
        lay.addWidget(StrongBodyLabel(tr("settings.log_dir"), self))
        lay.addWidget(CaptionLabel(tr("settings.log_dir_caption"), self))
        lay.addLayout(dir_row)
        lay.addStretch(1)

    def _on_language(self, idx: int):
        # 只写盘、不碰运行中的 _LANG: 避免半中半英, 重启应用后生效
        self.cfg.language.value = _LANG_VALUES[idx]
        self.cfg.save()
        InfoBar.info(tr("settings.lang_restart_title"),
                     tr("settings.lang_restart_msg"),
                     parent=self, position=InfoBarPosition.TOP, duration=4000)

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
        d = QFileDialog.getExistingDirectory(self, tr("settings.log_dir_pick"),
                                             self.cfg.log_dir.value)
        if not d:
            return
        games = registry.load_or_migrate(str(paths.GAMES_YAML))
        box = MessageBox(tr("settings.sync_title"),
                         tr("settings.sync_msg", d=d, n=len(games)), self)
        box.yesButton.setText(tr("settings.sync_yes"))
        box.cancelButton.setText(tr("settings.sync_no"))
        self.cfg.log_dir.value = d
        self.cfg.save()
        self.log_dir_edit.setText(d)
        if box.exec():
            ok, failed = sync_log_dir(d, games)
            if failed:
                InfoBar.warning(tr("settings.sync_partial_title"),
                                tr("settings.sync_partial_msg", ok=ok,
                                   failed=", ".join(failed)),
                                parent=self, position=InfoBarPosition.TOP,
                                duration=6000)
            else:
                InfoBar.success(tr("settings.sync_ok_title"),
                                tr("settings.sync_ok_msg", ok=ok),
                                parent=self, position=InfoBarPosition.TOP,
                                duration=3000)
        # 无论是否批量同步, 设置里的目录已变 — 诊断页 watcher 需重建到新路径
        self.log_dir_changed.emit(d)

    def _open_dir(self):
        d = self.cfg.log_dir.value
        os.makedirs(d, exist_ok=True)
        subprocess.Popen(["explorer", d])
