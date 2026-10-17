import os

import pytest
import tomlkit
from backend import paths
from backend.config import (MODES, default_config, config_file, load_config,
                            save_config, validate)


def test_default_config_valid():
    doc = default_config()
    assert validate(doc) == []
    assert doc["log_level"] == "Error"
    assert doc["playback"]["mode"] == "Normal"
    assert doc["capture"]["mode"] == "Bypass"


def test_round_trip_preserves_comment(tmp_path):
    text = '# 我的注释\nlog_level = "Error"\n\n[playback]\nmode = "Ringbuf"\n'
    cfg = tmp_path / "redirect_config.toml"
    cfg.write_text(text, encoding="utf-8")
    doc = load_config(str(tmp_path))
    doc["playback"]["mode"] = "Normal"
    save_config(str(tmp_path), doc)
    out = cfg.read_text(encoding="utf-8")
    assert "# 我的注释" in out
    assert 'mode = "Normal"' in out


def test_load_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(str(tmp_path))

def test_validate_rejects_bad_mode():
    doc = default_config()
    doc["playback"]["mode"] = "Turbo"
    assert any("mode" in p for p in validate(doc))


def test_read_display_hint_normal(tmp_path):
    """Normal 模式: 帧数取 target_buffer_len。"""
    doc = default_config()
    doc["playback"]["target_buffer_len"]["48000"] = 512
    save_config(str(tmp_path), doc)
    from backend.config import read_display_hint
    assert read_display_hint(str(tmp_path)) == ("Normal", 512)


def test_read_display_hint_ringbuf_uses_ring_buffer(tmp_path):
    """Ringbuf 模式: 帧数取 ring_buffer_len 而非 target_buffer_len。"""
    doc = default_config()
    doc["playback"]["mode"] = "Ringbuf"
    doc["playback"]["ring_buffer_len"]["48000"] = 2048
    save_config(str(tmp_path), doc)
    from backend.config import read_display_hint
    assert read_display_hint(str(tmp_path)) == ("Ringbuf", 2048)


def test_read_display_hint_missing_or_corrupt_returns_none(tmp_path):
    from backend.config import read_display_hint
    assert read_display_hint(str(tmp_path)) is None  # 文件缺失
    (tmp_path / "redirect_config.toml").write_text("[broken{", encoding="utf-8")
    assert read_display_hint(str(tmp_path)) is None  # 解析失败


def test_read_display_hint_returns_plain_builtin_types(tmp_path):
    """返回值必须是内建 str/int — tomlkit String 是 str 子类,
    yaml.safe_dump 无法表示(启动时 hint 收敛写 games.yaml 直接
    RepresenterError 崩启动的回归)。"""
    from backend import registry
    doc = default_config()
    save_config(str(tmp_path), doc)
    from backend.config import read_display_hint
    mode, frames = read_display_hint(str(tmp_path))
    assert type(mode) is str
    assert type(frames) is int
    # 端到端: 返回值可直接写回 games.yaml 不炸
    p = str(tmp_path / "games.yaml")
    registry.save_games({"g": registry.GameEntry(name="g", exe="x.exe")}, p)
    registry.update_hints("g", mode, frames, p)


def test_validate_rejects_bad_period():
    doc = default_config()
    doc["playback"]["target_period_hus"] = 5000
    assert any("target_period_hus" in p for p in validate(doc))


def test_validate_rejects_nonpositive_buffer():
    doc = default_config()
    doc["playback"]["target_buffer_len"]["48000"] = 0
    assert any("target_buffer_len" in p for p in validate(doc))


def test_validate_enforces_error_log_level():
    doc = default_config()
    doc["log_level"] = "Info"
    problems = validate(doc)
    assert any("log_level" in p for p in problems)


def test_default_config_with_log_dir():
    from backend.config import default_config
    doc = default_config(log_dir="D:/mylogs")
    assert doc["log_path"] == "D:/mylogs"
    assert validate(doc) == []


def test_default_config_no_arg_unchanged():
    from backend.config import default_config
    doc = default_config()
    assert doc["log_path"] == paths.RELINK_LOG_DIR.replace(os.sep, "/")


def test_set_log_dir(tmp_path):
    from backend.config import set_log_dir
    cfg = tmp_path / "redirect_config.toml"
    cfg.write_text('# 注释\nlog_path = "C:/old"\nlog_level = "Error"\n',
                   encoding="utf-8")
    set_log_dir(str(tmp_path), "D:/new")
    out = cfg.read_text(encoding="utf-8")
    assert 'log_path = "D:/new"' in out
    assert "# 注释" in out  # 注释保留


def test_set_log_dir_missing_raises(tmp_path):
    from backend.config import set_log_dir
    import pytest as _pt
    with _pt.raises(FileNotFoundError):
        set_log_dir(str(tmp_path), "D:/new")
