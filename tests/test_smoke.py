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


def test_games_page_instantiates(qapp, tmp_path, monkeypatch):
    from backend import paths
    # 造一个临时 games.yaml, 避免读真实注册表
    games_yaml = tmp_path / "games.yaml"
    games_yaml.write_text("games: {}\n", encoding="utf-8")
    monkeypatch.setattr(paths, "GAMES_YAML", str(games_yaml))

    from ui.games_page import GamesPage
    page = GamesPage()
    assert page.game_list.count() == 0
    assert page.stack.currentIndex() == 0  # 空状态
    page.deleteLater()


def test_config_card_dirty_flow(qapp, tmp_path):
    from backend.config import default_config, save_config, load_config
    from backend.registry import GameEntry
    from ui.config_card import ConfigCard

    d = tmp_path / "g"
    d.mkdir()
    exe = d / "g.exe"
    exe.write_text("", encoding="utf-8")
    save_config(str(d), default_config())
    entry = GameEntry(name="g", exe=str(exe))

    card = ConfigCard()
    card.set_game(entry)
    assert not card.is_dirty()
    assert not card.btn_save.isEnabled()

    card.buf_normal.setValue(512)  # 模拟用户修改
    assert card.is_dirty()
    assert card.btn_save.isEnabled()

    card.btn_save.click()
    assert not card.is_dirty()
    assert load_config(str(d))["playback"]["target_buffer_len"]["48000"] == 512
    card.deleteLater()
