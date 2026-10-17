import os
import pytest
import yaml
from backend.registry import (GameEntry, load_games, save_games, add_game,
                              remove_game, load_or_migrate)


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


def test_load_or_migrate_missing_starts_empty(yaml_path):
    """games.yaml 缺失: 从空注册表起步, 不抛异常不写盘(两态统一)。"""
    games = load_or_migrate(yaml_path)
    assert games == {}
    assert not os.path.exists(yaml_path)
    assert not os.path.exists(yaml_path + ".bak")


def test_load_or_migrate_backs_up_corrupt(yaml_path):
    """yaml 损坏: 备份 .bak 后从空注册表起步。"""
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("games: [broken yaml{")
    games = load_or_migrate(yaml_path)
    assert games == {}
    assert os.path.isfile(yaml_path + ".bak")


def test_load_or_migrate_recovers_bad_buffer_hint(yaml_path):
    # buffer_hint 为非整数字符串时 int() 抛 ValueError, 应备份 .bak 并恢复
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"games": {"bad": {"exe": r"C:\bad.exe",
                                          "buffer_hint": "abc"}}}, f)
    games = load_or_migrate(yaml_path)
    assert games == {}
    assert os.path.isfile(yaml_path + ".bak")


def test_update_hints_persists_and_noop_for_unknown(tmp_path):
    """保存配置后回写列表 hint: 已注册游戏更新 mode/buffer, 未注册名不动作。"""
    from backend import registry
    p = str(tmp_path / "games.yaml")
    registry.save_games({"g": registry.GameEntry(name="g", exe="x.exe")}, p)

    registry.update_hints("g", "Ringbuf", 2048, p)
    e = registry.load_games(p)["g"]
    assert e.mode_hint == "Ringbuf"
    assert e.buffer_hint == 2048

    registry.update_hints("ghost", "Normal", 960, p)  # 不存在: 不炸不新增
    assert list(registry.load_games(p)) == ["g"]
