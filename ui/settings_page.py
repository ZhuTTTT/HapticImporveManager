"""设置页: 语言 / 主题 / Mica / 日志目录(可改 + 一键打开 + 批量同步)
/ 旧版注册表残留清理。"""
from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, ComboBox, LineEdit,
                            MessageBox, PlainTextEdit, PushButton,
                            StrongBodyLabel, SwitchButton, TitleLabel,
                            InfoBar, InfoBarPosition)

from backend import chain_prefs, ifeo, launcher, paths, registry
from i18n import tr
from ui.app_config import AppConfig, apply_theme
from ui.log_dir_sync import sync_log_dir
from ui.restart import restart_app

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

        # 注入成功通知(失败通知始终发送; 开关同步给注入链)
        self.toast_switch = SwitchButton(self)
        self.toast_switch.setChecked(cfg.inject_toast.value)
        self.toast_switch.setOnText(tr("common.on"))
        self.toast_switch.setOffText(tr("common.off"))
        self.toast_switch.checkedChanged.connect(self._on_toast)

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
        lay.addWidget(StrongBodyLabel(tr("settings.inject_toast"), self))
        lay.addWidget(CaptionLabel(tr("settings.inject_toast_caption"), self))
        lay.addWidget(self.toast_switch)
        lay.addWidget(StrongBodyLabel(tr("settings.log_dir"), self))
        lay.addWidget(CaptionLabel(tr("settings.log_dir_caption"), self))
        lay.addLayout(dir_row)

        # 旧版注册表残留清理
        lay.addWidget(StrongBodyLabel(tr("settings.cleanup"), self))
        lay.addWidget(CaptionLabel(tr("settings.cleanup_caption"), self))
        self.legacy_view = PlainTextEdit(self)
        self.legacy_view.setReadOnly(True)
        self.legacy_view.setMaximumHeight(120)
        lay.addWidget(self.legacy_view)
        self.btn_rescan = PushButton(tr("settings.cleanup_rescan"), self)
        self.btn_rescan.clicked.connect(self._scan_legacy)
        self.btn_cleanup = PushButton(tr("settings.cleanup_run"), self)
        self.btn_cleanup.clicked.connect(self._cleanup_legacy)
        cleanup_row = QHBoxLayout()
        cleanup_row.addWidget(self.btn_rescan)
        cleanup_row.addWidget(self.btn_cleanup)
        cleanup_row.addStretch(1)
        lay.addLayout(cleanup_row)
        self._legacy: list[ifeo.LegacyEntry] = []
        self.runner = launcher.ProcessRunner(self)
        self.runner.done.connect(self._on_cleanup_done)
        self._scan_legacy()

        lay.addStretch(1)

    def _on_language(self, idx: int):
        # 只写盘、不碰运行中的 _LANG: 避免半中半英; 弹框给用户「立即重启」选项
        self.cfg.language.value = _LANG_VALUES[idx]
        self.cfg.save()
        box = MessageBox(tr("settings.lang_restart_title"),
                         tr("settings.lang_restart_msg"), self)
        box.yesButton.setText(tr("settings.lang_restart_now"))
        box.cancelButton.setText(tr("settings.lang_restart_later"))
        if box.exec():
            restart_app()

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

    def _on_toast(self, on: bool):
        self.cfg.inject_toast.value = on
        self.cfg.save()
        # 注入链(injector.exe)读不到 gui_config, 经共享偏好文件同步
        chain_prefs.set("inject_success_toast", on)

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

    # --- 旧版注册表残留清理 ---

    def _scan_legacy(self):
        self._legacy = ifeo.scan_legacy()
        if not self._legacy:
            self.legacy_view.setPlainText(tr("settings.cleanup_empty"))
        else:
            lines = []
            for e in self._legacy:
                tag = tr("settings.cleanup_broken" if e.broken
                         else "settings.cleanup_legacy")
                lines.append(f"{e.exe_name}  [{tag}]\n    {e.debugger}")
            self.legacy_view.setPlainText("\n".join(lines))
        self.btn_cleanup.setEnabled(bool(self._legacy))

    def _cleanup_legacy(self):
        if not self._legacy:
            return
        n_broken = sum(1 for e in self._legacy if e.broken)
        box = MessageBox(
            tr("settings.cleanup_confirm_title"),
            tr("settings.cleanup_confirm_msg",
               n=len(self._legacy), broken=n_broken),
            self)
        if not box.exec():
            return
        self.btn_cleanup.setEnabled(False)
        launcher.remove_ifeo_entries(
            self.runner, [e.exe_name for e in self._legacy])

    def _on_cleanup_done(self, _code: int):
        # launcher 提权后原进程直接 exit(0), 完成码不代表删除结果 —
        # 提权进程异步写注册表, 稍候重扫以实际状态为准
        QTimer.singleShot(1500, self._verify_cleanup)

    def _verify_cleanup(self):
        before = {e.exe_name for e in self._legacy}
        self._scan_legacy()
        remaining = before & {e.exe_name for e in self._legacy}
        if remaining:
            InfoBar.warning(tr("settings.cleanup_confirm_title"),
                            tr("settings.cleanup_failed_msg"),
                            parent=self, position=InfoBarPosition.TOP,
                            duration=4000)
        else:
            InfoBar.success(tr("settings.cleanup_confirm_title"),
                            tr("settings.cleanup_done_msg"),
                            parent=self, position=InfoBarPosition.TOP,
                            duration=3000)
