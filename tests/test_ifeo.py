import sys
from backend import ifeo, paths
from backend.ifeo import IfeoState, query_ifeo, build_ifeo_args


class _FakeKey:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _patch_winreg(monkeypatch, value=None):
    """value=None 模拟键不存在。"""
    class FakeWinreg:
        HKEY_LOCAL_MACHINE = 0
        @staticmethod
        def OpenKey(*a, **kw):
            if value is None:
                raise FileNotFoundError
            return _FakeKey()
        @staticmethod
        def QueryValueEx(k, name):
            return value, 1
    monkeypatch.setattr(ifeo, "winreg", FakeWinreg)


def test_state_off(monkeypatch):
    _patch_winreg(monkeypatch, None)
    assert query_ifeo("DS2.exe") == IfeoState.OFF


def test_state_on_ours(monkeypatch):
    _patch_winreg(monkeypatch, paths.IFEO_VALUE)
    assert query_ifeo("DS2.exe") == IfeoState.ON_OURS


def test_state_on_other(monkeypatch):
    _patch_winreg(monkeypatch, '"C:\\other\\debugger.exe"')
    assert query_ifeo("DS2.exe") == IfeoState.ON_OTHER


def test_build_args():
    args = build_ifeo_args("ds2", "on")
    assert args[0] == sys.executable
    assert args[1] == paths.LAUNCHER_PY
    assert args[2:] == ["ifeo", "ds2", "on"]


def test_real_registry_readable():
    """真实注册表只读查询不抛异常(无需管理员)。"""
    assert query_ifeo("DS2.exe") in set(IfeoState)
