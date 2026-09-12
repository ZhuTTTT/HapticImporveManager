"""QProcess 子进程执行器 — GUI 与 haptic_launcher CLI 的唯一通道。

强制 PYTHONIOENCODING=utf-8, 否则 Windows 控制台 GBK 输出会解码失败。
"""
from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from . import ifeo, paths


class ProcessRunner(QObject):
    line = Signal(str)
    done = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")
        self._proc.setProcessEnvironment(env)
        self._proc.readyReadStandardOutput.connect(self._emit)
        self._proc.readyReadStandardError.connect(self._emit)
        self._proc.finished.connect(lambda code, _status: self.done.emit(code))

    def start(self, args: list[str]) -> None:
        if self.is_running():
            self._proc.kill()
            self._proc.waitForFinished(1000)
        self._proc.start(args[0], args[1:])

    def is_running(self) -> bool:
        return self._proc.state() != QProcess.ProcessState.NotRunning

    def _emit(self):
        for chunk in (bytes(self._proc.readAllStandardOutput()),
                      bytes(self._proc.readAllStandardError())):
            for ln in chunk.decode("utf-8", errors="replace").splitlines():
                if ln.strip():
                    self.line.emit(ln)


def launch_game(runner: ProcessRunner, name: str) -> None:
    runner.start([sys.executable, paths.LAUNCHER_PY, name])


def set_ifeo(runner: ProcessRunner, name: str, on: bool) -> None:
    runner.start(ifeo.build_ifeo_args(name, "on" if on else "off"))


def is_game_running(exe_name: str) -> bool:
    """tasklist 查进程, 无第三方依赖。"""
    out = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
        capture_output=True, text=True).stdout
    return exe_name.lower() in out.lower()
