"""立即重启应用(语言切换等"重启后生效"的设置用)。"""
from __future__ import annotations

import subprocess
import sys

from PySide6.QtWidgets import QApplication


def restart_app() -> None:
    """拉起同名新进程,然后退出当前进程。

    冻结态(PyInstaller): sys.executable 即 exe 本体, 直接拉起;
    源码运行: sys.executable 是 python, 需带上 sys.argv 里的脚本路径。
    Popen 继承 cwd 与环境, 新进程与原启动方式等价。
    """
    if getattr(sys, "frozen", False):
        subprocess.Popen([sys.executable])
    else:
        subprocess.Popen([sys.executable, *sys.argv])
    QApplication.quit()
