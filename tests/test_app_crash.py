"""app.py 启动崩溃兜底: --windowed(PyInstaller console=False)构建无控制台,
启动异常原本无声无息(用户只能说"打不开"); 必须写 %APPDATA%\\HapticImproveManager\\
crash.log 并弹窗告知日志位置。"""
import pytest


@pytest.fixture
def _fake_qapp(monkeypatch):
    """替换 QApplication: 测试进程可能已有 offscreen 单例, 且不能跑真实事件循环。"""
    import PySide6.QtWidgets as qw

    class _FakeApp:
        def __init__(self, argv):
            self.argv = argv

        def setApplicationName(self, _name):
            pass

        def setWindowIcon(self, _icon):
            pass

        def exec(self):
            return 0

    monkeypatch.setattr(qw, "QApplication", _FakeApp)
    # QIcon 无真实 QGuiApplication 构造会段错误(Qt 检查 QPixmap 前置条件) —
    # QApplication 已替身, QIcon 一并打桩
    import PySide6.QtGui as qg
    monkeypatch.setattr(qg, "QIcon", lambda *a, **k: object())
    return _FakeApp


def _patch_dialog(app_mod, monkeypatch):
    """挡住真实 MessageBoxW, 返回记录列表。"""
    dialogs = []
    monkeypatch.setattr(app_mod, "_show_crash_dialog",
                        lambda summary, path: dialogs.append((summary, path)))
    return dialogs


def test_startup_crash_writes_log_and_dialog(tmp_path, monkeypatch, _fake_qapp):
    """create_main_window 抛异常 → main() 返回 1, crash.log 落地含 traceback, 弹窗一次。"""
    import ui.main_window as mw

    def _boom():
        raise RuntimeError("boom-startup")

    monkeypatch.setattr(mw, "create_main_window", _boom)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    import app as app_mod
    dialogs = _patch_dialog(app_mod, monkeypatch)

    rc = app_mod.main()

    assert rc == 1
    log = tmp_path / "HapticImproveManager" / "crash.log"
    assert log.is_file()
    text = log.read_text(encoding="utf-8")
    assert "RuntimeError: boom-startup" in text
    assert "Traceback" in text
    assert len(dialogs) == 1
    assert "boom-startup" in dialogs[0][0]
    assert dialogs[0][1] == str(log)


def test_qt_load_failure_also_caught(tmp_path, monkeypatch):
    """PySide6/Qt 加载失败(未解压运行/缺 DLL 的死法)同样落日志 + 弹窗。"""
    import PySide6.QtWidgets as qw

    def _boom_init(_argv):
        raise ImportError("DLL load failed: Qt6Widgets.dll")

    monkeypatch.setattr(qw, "QApplication", _boom_init)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    import app as app_mod
    dialogs = _patch_dialog(app_mod, monkeypatch)

    assert app_mod.main() == 1
    text = (tmp_path / "HapticImproveManager" / "crash.log").read_text(
        encoding="utf-8")
    assert "Qt6Widgets" in text
    assert len(dialogs) == 1


def test_startup_success_no_crash_log(tmp_path, monkeypatch, _fake_qapp):
    """正常启动: 返回 exec() 退出码, 不写 crash.log, 不弹窗。"""
    import ui.main_window as mw

    class _FakeWin:
        shown = False

        def show(self):
            self.shown = True

    monkeypatch.setattr(mw, "create_main_window", lambda: _FakeWin())
    monkeypatch.setenv("APPDATA", str(tmp_path))

    import app as app_mod
    dialogs = _patch_dialog(app_mod, monkeypatch)

    assert app_mod.main() == 0
    assert not (tmp_path / "HapticImproveManager" / "crash.log").exists()
    assert dialogs == []
