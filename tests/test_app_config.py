import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from backend import paths
from ui.app_config import AppConfig, load_app_config


def test_defaults_when_file_missing(tmp_path):
    cfg = load_app_config(str(tmp_path / "nonexistent.json"))
    assert cfg.theme_mode.value == "Auto"
    assert cfg.mica_enabled.value is True
    assert cfg.log_dir.value == paths.RELINK_LOG_DIR


def test_round_trip(tmp_path):
    p = str(tmp_path / "cfg.json")
    cfg = load_app_config(p)
    cfg.theme_mode.value = "Dark"
    cfg.log_dir.value = "D:/logs"
    cfg.save()

    cfg2 = load_app_config(p)
    assert cfg2.theme_mode.value == "Dark"
    assert cfg2.log_dir.value == "D:/logs"
