"""诊断页: 最近注入结果 + 两个日志选项卡(尾随 200 行 + 文件监视 +
资源管理器打开)。

monitor/paths 调用全部显式传参 — 默认参数在定义时绑定, monkeypatch 需显式。
"""
from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, Pivot,
                            PlainTextEdit, PushButton, StrongBodyLabel,
                            TitleLabel)

from backend import monitor, paths
from ui.app_config import APP_CFG

_TAIL_LINES = 200


class DiagnosticsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("diagnostics")

        # 最近注入
        self.result_card = CardWidget(self)
        rc = QVBoxLayout(self.result_card)
        rc.addWidget(StrongBodyLabel("最近注入", self.result_card))
        self.result_label = BodyLabel("", self.result_card)
        self.result_label.setWordWrap(True)
        rc.addWidget(self.result_label)

        # 日志选项卡
        self.tabs = Pivot(self)
        self.stack = QStackedWidget(self)
        self.log_views: dict[str, PlainTextEdit] = {}
        for key, fixed in (("injector_debug", True), ("wasapi_relink", False)):
            host = QWidget(self)
            vl = QVBoxLayout(host)
            vl.setContentsMargins(0, 0, 0, 0)
            if fixed:
                vl.addWidget(CaptionLabel(
                    "此日志由注入器写入, 位置固定于 specialk 目录", host))
            view = PlainTextEdit(host)
            view.setReadOnly(True)
            view.setMaximumBlockCount(500)
            vl.addWidget(view)
            self.log_views[key] = view
            self.stack.addWidget(host)
            self.tabs.addItem(
                routeKey=key,
                text=key,
                onClick=lambda k=key: self.stack.setCurrentIndex(
                    0 if k == "injector_debug" else 1),
            )
        self.tabs.setCurrentItem("injector_debug")

        self.btn_open = PushButton("在资源管理器中打开", self)
        self.btn_open.clicked.connect(self._open_current)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(10)
        lay.addWidget(TitleLabel("诊断", self))
        lay.addWidget(self.result_card)
        lay.addWidget(self.tabs)
        lay.addWidget(self.btn_open)
        lay.addWidget(self.stack, 1)

        self.watcher = None
        self.rebuild_watcher()
        self._refresh_result()
        self._reload("injector_debug")
        self._reload("wasapi_relink")

    def relink_log_path(self) -> str:
        return os.path.join(APP_CFG.log_dir.value, "wasapi_relink.log")

    def _path_of(self, key: str) -> str:
        return str(paths.INJECTOR_DEBUG_LOG) if key == "injector_debug" \
            else self.relink_log_path()

    def rebuild_watcher(self):
        """日志目录变化后重建监视(LogWatcher 不做动态增删路径)。"""
        if self.watcher is not None:
            self.watcher.deleteLater()
        self.watcher = monitor.LogWatcher(
            [str(paths.INJECTOR_RESULT), str(paths.INJECTOR_DEBUG_LOG),
             self.relink_log_path()], self)
        self.watcher.file_changed.connect(self._on_changed)

    def append_event(self, text: str):
        self.log_views["injector_debug"].appendPlainText(text)

    def _open_current(self):
        key = "injector_debug" if self.stack.currentIndex() == 0 \
            else "wasapi_relink"
        p = self._path_of(key)
        if os.path.isfile(p):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
        else:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            subprocess.Popen(["explorer", os.path.normpath(
                os.path.dirname(p))])

    def _on_changed(self, path: str):
        if path == str(paths.INJECTOR_RESULT):
            self._refresh_result()
        elif path == str(paths.INJECTOR_DEBUG_LOG):
            self._reload("injector_debug")
        elif path == self.relink_log_path():
            self._reload("wasapi_relink")

    def _refresh_result(self):
        mtime, text = monitor.read_result(str(paths.INJECTOR_RESULT))
        self.result_label.setText(
            f"{mtime:%Y-%m-%d %H:%M:%S} — {text}" if mtime and text
            else "暂无注入记录")

    def _reload(self, key: str):
        view = self.log_views[key]
        view.setPlainText("\n".join(monitor.tail(self._path_of(key),
                                                 _TAIL_LINES)))
        view.verticalScrollBar().setValue(
            view.verticalScrollBar().maximum())
