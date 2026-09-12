import pytest
import tomlkit
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
