"""chain_prefs 配置桥 + injector 成功通知开关逻辑。"""
import importlib
import json
import os
import sys

from backend import chain_prefs, paths


def test_round_trip(tmp_path, monkeypatch):
    p = str(tmp_path / "chain_prefs.json")
    monkeypatch.setattr(chain_prefs, "PREFS_PATH", p)
    assert chain_prefs.get("inject_success_toast") is True  # 缺文件默认开
    chain_prefs.set("inject_success_toast", False)
    assert chain_prefs.get("inject_success_toast") is False
    with open(p, encoding="utf-8") as f:
        assert json.load(f)["inject_success_toast"] is False  # 落盘


def test_corrupt_falls_back_to_default(tmp_path, monkeypatch):
    p = tmp_path / "chain_prefs.json"
    p.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(chain_prefs, "PREFS_PATH", str(p))
    assert chain_prefs.get("inject_success_toast") is True


def test_unregistered_key_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(chain_prefs, "PREFS_PATH",
                        str(tmp_path / "x.json"))
    import pytest
    with pytest.raises(KeyError):
        chain_prefs.set("nope", 1)


def _import_injector():
    sys.path.insert(0, paths.CHAIN_DIR)
    try:
        return importlib.import_module("injector")
    finally:
        sys.path.remove(paths.CHAIN_DIR)


def test_injector_success_toast_pref(tmp_path, monkeypatch):
    """injector 读共享偏好: 文件缺失默认开, false 则关, 损坏回退开。"""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    injector = _import_injector()
    assert injector._success_toast_enabled() is True  # 无文件 → 开
    d = tmp_path / "HapticImproveManager"
    d.mkdir()
    (d / "chain_prefs.json").write_text(
        '{"inject_success_toast": false}', encoding="utf-8")
    assert injector._success_toast_enabled() is False
    (d / "chain_prefs.json").write_text("{broken", encoding="utf-8")
    assert injector._success_toast_enabled() is True  # 损坏 → 回退开