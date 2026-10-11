import os
import sys
import pytest
import yaml
from backend import paths
from backend.registry import (GameEntry, load_games, save_games, add_game,
                              remove_game, migrate_from_launcher,
                              load_or_migrate, migrate_legacy_chain_yaml)


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


# --- migrate_legacy_chain_yaml: 冻结版首启从旧 specialk 目录复制 games.yaml ---

def _write_yaml(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f)


def test_migrate_legacy_copies_when_target_missing(tmp_path):
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    _write_yaml(legacy_dir / "games.yaml",
                {"games": {"ds2": {"exe": r"E:\DS2.exe"}}})
    chain_dir = tmp_path / "chain"
    chain_dir.mkdir()
    target = str(chain_dir / "games.yaml")
    assert migrate_legacy_chain_yaml(target, str(legacy_dir)) is True
    assert os.path.isfile(target)          # 已复制
    assert (legacy_dir / "games.yaml").is_file()  # 原件保留
    assert "ds2" in load_games(target)


def test_migrate_legacy_never_overwrites_existing_target(tmp_path):
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    _write_yaml(legacy_dir / "games.yaml",
                {"games": {"legacy_game": {"exe": r"E:\old.exe"}}})
    target = str(tmp_path / "games.yaml")
    _write_yaml(target, {"games": {"mine": {"exe": r"E:\mine.exe"}}})
    assert migrate_legacy_chain_yaml(target, str(legacy_dir)) is False
    assert set(load_games(target)) == {"mine"}  # 目标原封不动


def test_migrate_legacy_missing_legacy_dir(tmp_path):
    target = str(tmp_path / "games.yaml")
    assert migrate_legacy_chain_yaml(target, str(tmp_path / "nope")) is False
    assert not os.path.exists(target)


def test_load_or_migrate_frozen_migrates_legacy(monkeypatch, tmp_path):
    """冻结态: load_or_migrate 前置 legacy 复制, 然后正常读取。"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    _write_yaml(legacy_dir / "games.yaml",
                {"games": {"legacy_game": {"exe": r"E:\old.exe"}}})
    monkeypatch.setattr(paths, "DEV_SPECIALK_DIR", str(legacy_dir))
    chain_dir = tmp_path / "chain"
    chain_dir.mkdir()
    target = str(chain_dir / "games.yaml")
    games = load_or_migrate(target)
    assert "legacy_game" in games
    assert (legacy_dir / "games.yaml").is_file()  # 原件保留


def test_load_or_migrate_source_state_skips_legacy(monkeypatch, tmp_path):
    """源码态: 即使 legacy 目录存在也不做复制(走 launcher 迁移)。"""
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    _write_yaml(legacy_dir / "games.yaml",
                {"games": {"only_legacy": {"exe": r"E:\x.exe"}}})
    monkeypatch.setattr(paths, "DEV_SPECIALK_DIR", str(legacy_dir))
    chain_dir = tmp_path / "chain"
    chain_dir.mkdir()
    target = str(chain_dir / "games.yaml")
    games = load_or_migrate(target)
    assert "only_legacy" not in games  # 未复制 legacy, 走了 launcher 迁移
