"""i18n 核心模块单元测试(纯 Python,不碰 Qt)。

覆盖:目录完整性、占位符一致性、resolve_language 映射、
tr 回退链与插值、set_language 校验。
"""

import string

import pytest

import i18n


@pytest.fixture(autouse=True)
def _preserve_lang():
    """每个测试前后保存/恢复 i18n._LANG,不污染同进程其他测试文件。"""
    old = i18n._LANG
    try:
        yield
    finally:
        i18n._LANG = old


def test_catalog_completeness():
    """_MESSAGES 每个键都含非空 zh 与 en。"""
    for key, entry in i18n._MESSAGES.items():
        assert entry.get("zh"), f"{key} 缺少 zh 文案"
        assert entry.get("en"), f"{key} 缺少 en 文案"


def test_placeholder_consistency():
    """同一键 zh/en 的 {...} 占位符字段名集合必须一致(防漏参致 KeyError)。"""
    formatter = string.Formatter()

    def fields(text):
        return {field for _, field, _, _ in formatter.parse(text)
                if field is not None}

    for key, entry in i18n._MESSAGES.items():
        assert fields(entry["zh"]) == fields(entry["en"]), \
            f"{key} 中英占位符不一致"


@pytest.mark.parametrize(("setting", "locale", "expected"), [
    ("System", "zh_CN", "zh"),
    ("System", "zh_TW", "zh"),
    ("System", "en_US", "en"),
    ("System", "ja_JP", "en"),
    ("zh", "en_US", "zh"),
    ("en", "zh_CN", "en"),
    ("Weird", "en_US", "en"),
])
def test_resolve_language(setting, locale, expected):
    assert i18n.resolve_language(setting, locale) == expected


def test_tr_unknown_key_returns_key():
    """未收录键原样返回 key 本身。"""
    assert i18n.tr("no.such.key") == "no.such.key"


def test_tr_falls_back_to_zh(monkeypatch):
    """当前语言缺失条目时回退 zh。"""
    monkeypatch.setitem(i18n._MESSAGES, "test.only_zh", {"zh": "仅中文"})
    i18n.set_language("en")
    assert i18n.tr("test.only_zh") == "仅中文"


def test_tr_with_params():
    """带参插值:{n} 占位符在两种语言下都正确格式化。"""
    i18n.set_language("zh")
    assert i18n.tr("unit.frames", n=5) == "5 帧"
    i18n.set_language("en")
    assert i18n.tr("unit.frames", n=5) == "5 frames"


def test_set_language_round_trip():
    """zh/en 往返切换,tr 与 current_language 跟随生效。"""
    i18n.set_language("en")
    assert i18n.current_language() == "en"
    assert i18n.tr("app.title") == "Haptic Low-Latency Manager"
    i18n.set_language("zh")
    assert i18n.current_language() == "zh"
    assert i18n.tr("app.title") == "Haptic 低延迟管理器"


def test_set_language_rejects_unknown():
    """非法语言代码 raise ValueError,且不改当前语言。"""
    i18n.set_language("zh")
    with pytest.raises(ValueError):
        i18n.set_language("fr")
    assert i18n.current_language() == "zh"
