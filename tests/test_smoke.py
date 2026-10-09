import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_instantiates(qapp, tmp_path):
    from ui.app_config import load_app_config
    from ui.main_window import MainWindow
    cfg = load_app_config(str(tmp_path / "gui.json"))
    win = MainWindow(cfg)
    assert win.windowTitle() == "Haptic 低延迟管理器"
    assert win.settings_page.theme_box.count() == 3
    win.close()
    win.deleteLater()
