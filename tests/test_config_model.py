import tomlkit

from backend.config import default_config, validate
from ui.config_model import (FormState, MODE_INFO, apply_form, frames_to_ms,
                             hus_to_ms, load_form)


def test_load_defaults():
    st = load_form(default_config())
    assert st == FormState(mode="Normal", period_hus=100, buf_normal=960,
                           buf_ring=4320, raw=True, force_period=True,
                           log_level="Error")


def test_apply_round_trip_preserves_comments():
    doc = default_config()
    st = load_form(doc)
    st.mode = "Ringbuf"
    st.buf_ring = 2048
    apply_form(doc, st)
    text = tomlkit.dumps(doc)
    assert 'mode = "Ringbuf"' in text
    assert "ring_buffer_len.48000 = 2048" in text
    assert "# Ringbuf 用" in text  # 注释保留
    assert validate(doc) == []


def test_apply_dotted_key_str():
    """点分键子表键必须保持字符串, 不得变成 int(会 TypeError)或丢失。"""
    doc = default_config()
    st = load_form(doc)
    st.buf_normal = 256
    apply_form(doc, st)
    tbl = doc["playback"]["target_buffer_len"]
    assert list(tbl.keys()) == ["48000"]
    assert tbl["48000"] == 256


def test_apply_missing_buffer_subtable():
    """配置缺 target_buffer_len 子表时 apply 要新建且不炸。"""
    doc = default_config()
    del doc["playback"]["target_buffer_len"]
    st = load_form(doc)
    assert st.buf_normal == 960  # 缺省回退
    st.buf_normal = 512
    apply_form(doc, st)
    assert doc["playback"]["target_buffer_len"]["48000"] == 512


def test_conversions():
    assert frames_to_ms(960) == 20.0
    assert frames_to_ms(4320) == 90.0
    assert hus_to_ms(100) == 10.0
    assert hus_to_ms(0) == 0.0


def test_mode_info_covers_all_modes():
    from backend.config import MODES
    for m in MODES:
        assert MODE_INFO[m]["title"]
        assert MODE_INFO[m]["brief"]
        assert MODE_INFO[m]["detail"]
