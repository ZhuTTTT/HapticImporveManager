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


def test_save_games_atomic_on_dump_failure(yaml_path, monkeypatch):
    """序列化中途抛异常不损坏原文件(先 dump 成字符串再原子替换 —
    真实事故: RepresenterError 曾把注册表清空, 引发连锁启动崩溃)。"""
    save_games({"a": GameEntry(name="a", exe="x.exe")}, yaml_path)
    with open(yaml_path, encoding="utf-8") as f:
        original = f.read()

    def _boom(*a, **k):
        raise ValueError("dump failed")

    monkeypatch.setattr(yaml, "safe_dump", _boom)
    with pytest.raises(ValueError):
        save_games({"b": GameEntry(name="b", exe="y.exe")}, yaml_path)
    with open(yaml_path, encoding="utf-8") as f:
        assert f.read() == original


def test_derived_properties():
    e = GameEntry(name="x", exe=r"E:\game dir\game.exe")
    assert e.game_dir == r"E:\game dir"
    assert e.config_path == r"E:\game dir\redirect_config.toml"
    assert e.exe_exists is False  # 路径不存在


def test_load_or_migrate_missing_starts_empty(yaml_path):
    """games.yaml 缺失: 从空注册表起步, 不抛异常不写盘(两态统一)。"""
    games = load_or_migrate(yaml_path, legacy=yaml_path + ".none")
    assert games == {}
    assert not os.path.exists(yaml_path)
    assert not os.path.exists(yaml_path + ".bak")


def test_load_or_migrate_backs_up_corrupt(yaml_path):
    """yaml 损坏: 备份 .bak 后从空注册表起步。"""
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("games: [broken yaml{")
    games = load_or_migrate(yaml_path, legacy=yaml_path + ".none")
    assert games == {}
    assert os.path.isfile(yaml_path + ".bak")


def test_load_or_migrate_recovers_bad_buffer_hint(yaml_path):
    # buffer_hint 为非整数字符串时 int() 抛 ValueError, 应备份 .bak 并恢复
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"games": {"bad": {"exe": r"C:\bad.exe",
                                          "buffer_hint": "abc"}}}, f)
    games = load_or_migrate(yaml_path, legacy=yaml_path + ".none")
    assert games == {}
    assert os.path.isfile(yaml_path + ".bak")


def test_load_or_migrate_moves_legacy(tmp_path):
    """一次性迁移: 新位置缺失 + 旧位置(chain/games.yaml)存在 → 移动过来。"""
    from backend import registry
    legacy = tmp_path / "chain" / "games.yaml"
    legacy.parent.mkdir()
    registry.save_games(
        {"ds2": registry.GameEntry(name="ds2", exe=r"E:\DS2.exe")},
        str(legacy))
    target = tmp_path / "appdata" / "HapticImproveManager" / "games.yaml"
    games = registry.load_or_migrate(str(target), str(legacy))
    assert "ds2" in games
    assert not legacy.exists()      # 已移动而非复制
    assert target.is_file()


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


# --- sync_from_registry: 从 IFEO 注册表重建游戏列表 ---

def test_sync_from_registry_adds_skeletons(monkeypatch, tmp_path):
    """注册表里带我们签名的项 → 骨架条目(exe 暂存文件名, 待「定位 exe」)。"""
    from backend import ifeo, registry
    monkeypatch.setattr(ifeo, "scan_ours_exe_names",
                        lambda: ["DS2.exe", "SB-Win64-Shipping.exe"])
    p = str(tmp_path / "games.yaml")
    added, skipped = registry.sync_from_registry(p)
    assert added == ["ds2", "sb-win64-shipping"]
    assert skipped == []
    games = registry.load_games(p)
    assert games["ds2"].exe == "DS2.exe"
    assert not games["ds2"].exe_exists  # 非全路径: 状态点显示 exe 丢失


def test_sync_from_registry_skips_known_and_keeps_paths(monkeypatch, tmp_path):
    """exe 已注册的跳过(不覆盖既有全路径); 只增量补新。"""
    from backend import ifeo, registry
    monkeypatch.setattr(ifeo, "scan_ours_exe_names",
                        lambda: ["DS2.exe", "New.exe"])
    p = str(tmp_path / "games.yaml")
    registry.save_games(
        {"ds2": registry.GameEntry(name="ds2", exe=r"E:\games\DS2.exe")}, p)
    added, skipped = registry.sync_from_registry(p)
    assert added == ["new"]
    assert skipped == ["DS2.exe"]
    assert registry.load_games(p)["ds2"].exe == r"E:\games\DS2.exe"


def test_update_exe(tmp_path):
    from backend import registry
    p = str(tmp_path / "games.yaml")
    registry.save_games({"g": registry.GameEntry(name="g", exe="G.exe")}, p)
    registry.update_exe("g", r"E:\games\G.exe", p)
    assert registry.load_games(p)["g"].exe == r"E:\games\G.exe"
    registry.update_exe("ghost", r"E:\x.exe", p)  # 未注册名不动作
    assert list(registry.load_games(p)) == ["g"]
