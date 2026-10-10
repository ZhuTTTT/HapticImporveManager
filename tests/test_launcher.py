"""_python_exe 冻结态解释器解析。

launcher 内 `import shutil` 在函数体内, 故 monkeypatch 目标是 shutil 模块属性
(函数执行时从 sys.modules 取同一模块对象, 补丁可见)。
"""
import sys

from backend import launcher


def test_python_exe_not_frozen():
    assert launcher._python_exe() == sys.executable


def test_python_exe_frozen_prefers_pythonw(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        "shutil.which",
        lambda name: "C:/fake/pythonw.exe" if name == "pythonw" else None)
    assert launcher._python_exe() == "C:/fake/pythonw.exe"


def test_python_exe_frozen_falls_back_to_python(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        "shutil.which",
        lambda name: "C:/fake/python.exe" if name == "python" else None)
    assert launcher._python_exe() == "C:/fake/python.exe"


def test_python_exe_frozen_no_system_python(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert launcher._python_exe() == sys.executable
