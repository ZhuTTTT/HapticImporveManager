"""QProcess 子进程执行器 — GUI 与 haptic_launcher CLI 的唯一通道。

强制 PYTHONIOENCODING=utf-8, 否则 Windows 控制台 GBK 输出会解码失败。
"""
from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from . import ifeo, paths


def _python_exe() -> str:
    """冻结态(PyInstaller exe)下 sys.executable 是 GUI 自身, 不能跑 .py,
    改用系统 Python; 找不到则返回 sys.executable 兜底(子进程会报错并在日志可见)。"""
    if getattr(sys, "frozen", False):
        import shutil
        return shutil.which("pythonw") or shutil.which("python") or sys.executable
    return sys.executable


def _launcher_cmd() -> list[str]:
    """haptic_launcher 子进程命令前缀: 冻结 → 随包 exe; 源码 → 解释器 + .py。"""
    if getattr(sys, "frozen", False):
        return [paths.LAUNCHER_EXE]
    return [_python_exe(), paths.LAUNCHER_PY]


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
    runner.start(_launcher_cmd() + [name])


def set_ifeo(runner: ProcessRunner, name: str, on: bool) -> None:
    # 冻结/源码两态分支由 build_ifeo_args 内部处理, 与 _launcher_cmd 对齐
    runner.start(ifeo.build_ifeo_args(name, "on" if on else "off"))


def is_game_running(exe_name: str) -> bool:
    """tasklist 查进程, 无第三方依赖。"""
    proc = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH"],
        capture_output=True)
    # 手动解码: text=True 走区域代码页(GBK), 遇非法字节会 UnicodeDecodeError
    out = proc.stdout.decode("utf-8", errors="replace")
    return exe_name.lower() in out.lower()
