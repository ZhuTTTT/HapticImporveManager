import os

from backend.config import default_config, save_config
from backend.registry import GameEntry
from ui.log_dir_sync import sync_log_dir


def _mk_game(tmp_path, name, with_config=True):
    d = tmp_path / name
    d.mkdir()
    exe = d / f"{name}.exe"
    exe.write_text("", encoding="utf-8")
    if with_config:
        save_config(str(d), default_config())
    return GameEntry(name=name, exe=str(exe))


def test_sync_all_ok(tmp_path):
    games = {n: _mk_game(tmp_path, n) for n in ("a", "b")}
    ok, failed = sync_log_dir("D:/logs", games)
    assert (ok, failed) == (2, [])
    from backend.config import load_config
    assert load_config(games["a"].game_dir)["log_path"] == "D:/logs"


def test_sync_skips_broken(tmp_path):
    good = _mk_game(tmp_path, "good")
    broken = _mk_game(tmp_path, "broken", with_config=False)
    # 损坏的 toml
    with open(broken.config_path, "w", encoding="utf-8") as f:
        f.write("log_path = [not valid")
    ok, failed = sync_log_dir("D:/logs", {"good": good, "broken": broken})
    assert ok == 1
    assert failed == ["broken"]
