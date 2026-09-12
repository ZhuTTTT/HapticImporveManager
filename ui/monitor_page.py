from PySide6.QtWidgets import (QLabel, QPlainTextEdit, QPushButton,
                               QVBoxLayout, QWidget)

from backend import monitor, paths


class MonitorPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_label = QLabel()
        self.result_label.setWordWrap(True)

        self.debug_view = QPlainTextEdit()
        self.debug_view.setReadOnly(True)
        self.debug_view.setMaximumBlockCount(500)

        self.relink_view = QPlainTextEdit()
        self.relink_view.setReadOnly(True)
        self.relink_view.setMaximumBlockCount(500)
        self.relink_view.hide()
        self.btn_toggle = QPushButton("▸ wasapi_relink.log(排障用)")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.toggled.connect(self._toggle_relink)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>最近注入</b>"))
        lay.addWidget(self.result_label)
        lay.addWidget(QLabel("<b>injector_debug.log</b>"))
        lay.addWidget(self.debug_view, 1)
        lay.addWidget(self.btn_toggle)
        lay.addWidget(self.relink_view, 1)

        self.watcher = monitor.LogWatcher(
            [paths.INJECTOR_RESULT, paths.INJECTOR_DEBUG_LOG, paths.RELINK_LOG],
            self)
        self.watcher.file_changed.connect(self._on_changed)

        self._refresh_result()
        self._reload(self.debug_view, paths.INJECTOR_DEBUG_LOG)

    def _toggle_relink(self, on: bool):
        self.relink_view.setVisible(on)
        self.btn_toggle.setText(("▾" if on else "▸") + " wasapi_relink.log(排障用)")
        if on:
            self._reload(self.relink_view, paths.RELINK_LOG)

    def _on_changed(self, path: str):
        if path == paths.INJECTOR_RESULT:
            self._refresh_result()
        elif path == paths.INJECTOR_DEBUG_LOG:
            self._reload(self.debug_view, path)
        elif path == paths.RELINK_LOG and self.relink_view.isVisible():
            self._reload(self.relink_view, path)

    def _refresh_result(self):
        mtime, text = monitor.read_result()
        if mtime is None:
            self.result_label.setStyleSheet("color:#888;")
            self.result_label.setText("暂无注入记录")
            return
        color = "#30a46c" if "injected OK" in text else "#e5484d"
        self.result_label.setStyleSheet(f"color:{color};")
        self.result_label.setText(f"{mtime:%Y-%m-%d %H:%M:%S} — {text}")

    def _reload(self, view: QPlainTextEdit, path: str):
        view.setPlainText("\n".join(monitor.tail(path, 200)))
        view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())

    def append_event(self, text: str):
        """GUI 会话内的启动器输出事件(可选接线)。"""
        self.debug_view.appendPlainText(text)
