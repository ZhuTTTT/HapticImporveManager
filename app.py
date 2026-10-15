"""程序入口。

--windowed(PyInstaller console=False)构建下, 启动阶段任何异常都无控制台可见,
用户只能说"打不开"。main() 全段包 try: 异常追加写 %APPDATA%\\HapticImproveManager\\
crash.log 并弹窗告知日志位置, 让"打不开"可诊断。

崩溃兜底路径故意零项目依赖(不 import app_config/i18n 等)——崩溃源可能正是
这些模块; APPDATA 目录逻辑与 ui/app_config.py 的 _default_path 有意重复。
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime


def _crash_log_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "HapticImproveManager")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "crash.log")


def _show_crash_dialog(summary: str, log_path: str | None) -> None:
    """ctypes 兜底弹窗: 不依赖 Qt(Qt 加载失败本身就可能是崩溃源)。

    文案中英直写: i18n 模块在崩溃路径上同样不可信。
    """
    try:
        import ctypes
        text = f"启动失败 / Failed to start:\n{summary}"
        if log_path:
            text += (f"\n\n详细日志 / Details:\n{log_path}\n"
                     "请把此文件发给开发者 / Please send this file to the developer.")
        ctypes.windll.user32.MessageBoxW(
            0, text, "HapticImproveManager", 0x10)  # MB_ICONERROR
    except Exception:
        pass  # 弹窗也失败则放弃——日志已尽力写过


def _report_crash(tb: str) -> None:
    lines = tb.strip().splitlines()
    summary = lines[-1] if lines else "unknown error"
    try:
        path = _crash_log_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"=== {datetime.now().isoformat(timespec='seconds')} ===\n")
            f.write(tb if tb.endswith("\n") else tb + "\n")
    except OSError:
        path = None  # 日志写不了(权限/盘满)也要弹窗
    _show_crash_dialog(summary, path)


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
        from ui.main_window import create_main_window

        app = QApplication(sys.argv)
        app.setApplicationName("HapticImproveManager")
        win = create_main_window()
        win.show()
        return app.exec()
    except Exception:
        _report_crash(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
