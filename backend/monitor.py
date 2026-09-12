"""日志读取(tail / 最近注入结果)与 QFileSystemWatcher 包装。"""
from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import QFileSystemWatcher, QObject, Signal

from . import paths


def tail(path: str, n: int = 50) -> list[str]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()[-n:]


def read_result(path: str = paths.INJECTOR_RESULT) -> tuple[datetime | None, str]:
    if not os.path.isfile(path):
        return None, ""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read().strip()
    return datetime.fromtimestamp(os.path.getmtime(path)), text


class LogWatcher(QObject):
    """监视日志文件; 文件被删除重建后自动重挂(QFileSystemWatcher 会丢监视)。"""
    file_changed = Signal(str)

    def __init__(self, watch_paths: list[str], parent=None):
        super().__init__(parent)
        self._paths = list(watch_paths)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_changed)
        for p in self._paths:
            if os.path.isfile(p):
                self._watcher.addPath(p)

    def _on_changed(self, path: str):
        if path not in self._watcher.files() and os.path.isfile(path):
            self._watcher.addPath(path)
        self.file_changed.emit(path)
