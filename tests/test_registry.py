import os
import pytest
import yaml
from backend.registry import (GameEntry, load_games, save_games, add_game,
                              remove_game, migrate_from_launcher,
                              load_or_migrate)


@pytest.fixture
def yaml_path(tmp_path):
    return str(tmp_path / "games.yaml")


def test_round_trip(yaml_path):
    games = {"ds2": GameEntry(name="ds2", exe=r"E:\games\DS2.exe",
                              mode_hint="Ringbuf", buffer_hint=2048)}
    save_games(games, yaml_path)
    loaded = load_games(yaml_path)
    assert loaded["ds2"].exe == games["ds2"].exe
    assert loaded["ds2"].mode_hint == "Ringbuf"
    assert loaded["ds2"].buffer_hint == 2048
    assert loaded["ds2"].anticheat is False


def test_name_is_yaml_key_not_field(yaml_path):
    save_games({"sb": GameEntry(name="sb", exe=r"E:\SB.exe")}, yaml_path)
    with open(yaml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    assert "name" not in raw["games"]["sb"]


def test_add_and_remove(yaml_path):
    add_game(GameEntry(name="a", exe=r"C:\a.exe"), yaml_path)
    add_game(GameEntry(name="b", exe=r"C:\b.exe"), yaml_path)
    assert set(load_games(yaml_path)) == {"a", "b"}
    remove_game("a", yaml_path)
    assert set(load_games(yaml_path)) == {"b"}


def test_derived_properties():
    e = GameEntry(name="x", exe=r"E:\game dir\game.exe")
    assert e.game_dir == r"E:\game dir"
    assert e.config_path == r"E:\game dir\redirect_config.toml"
    assert e.exe_exists is False  # 路径不存在


def test_migrate_from_launcher(yaml_path):
    games = migrate_from_launcher(yaml_path)
    assert set(games) == {"ds2", "sb", "zzz"}
    assert games["ds2"].mode_hint == "Ringbuf"
    assert games["zzz"].anticheat is True
    assert os.path.isfile(yaml_path)


def test_load_or_migrate_backs_up_corrupt(yaml_path):
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("games: [broken yaml{")
    games = load_or_migrate(yaml_path)
    assert "ds2" in games
    assert os.path.isfile(yaml_path + ".bak")


def test_load_or_migrate_recovers_bad_buffer_hint(yaml_path):
    # buffer_hint 为非整数字符串时 int() 抛 ValueError, 应备份 .bak 并迁移恢复
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"games": {"bad": {"exe": r"C:\bad.exe",
                                          "buffer_hint": "abc"}}}, f)
    games = load_or_migrate(yaml_path)
    assert "ds2" in games
    assert os.path.isfile(yaml_path + ".bak")
