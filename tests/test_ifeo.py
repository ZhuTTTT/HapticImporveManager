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
    """源码态: 走 sys.executable + haptic_launcher.py。"""
    args = build_ifeo_args("ds2", "on")
    assert args[0] == sys.executable
    assert args[1] == paths.LAUNCHER_PY
    assert args[2:] == ["ifeo", "ds2", "on"]


def test_build_args_frozen(monkeypatch):
    """冻结态: 直接调随包 haptic_launcher.exe, 不再经 Python 解释器。"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths, "LAUNCHER_EXE",
                        r"C:\pkg\chain\haptic_launcher.exe")
    args = build_ifeo_args("ds2", "off")
    assert args == [r"C:\pkg\chain\haptic_launcher.exe", "ifeo", "ds2", "off"]


def test_real_registry_readable():
    """真实注册表只读查询不抛异常(无需管理员)。"""
    assert query_ifeo("DS2.exe") in set(IfeoState)


# --- scan_legacy: 旧版/旧位置 IFEO 残留扫描 ---

def _patch_winreg_scan(monkeypatch, entries: dict):
    """entries: {IFEO 子键名: Debugger 值}。"""
    class FakeKey:
        def __init__(self, name=None):
            self._name = name

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeWinreg:
        HKEY_LOCAL_MACHINE = 0

        @staticmethod
        def OpenKey(root, path, *a, **kw):
            if path == paths.IFEO_BASE:
                return FakeKey()
            sub = path.split("\\")[-1]
            if sub not in entries:
                raise FileNotFoundError
            return FakeKey(sub)

        @staticmethod
        def EnumKey(key, i):
            names = list(entries)
            if i >= len(names):
                raise OSError
            return names[i]

        @staticmethod
        def QueryValueEx(k, name):
            return entries[k._name], 1

    monkeypatch.setattr(ifeo, "winreg", FakeWinreg)


def test_scan_legacy_filters_and_marks_broken(monkeypatch):
    """签名匹配但≠当前值 → 残留(目标缺失标 broken); 当前值与他人调试器排除。"""
    _patch_winreg_scan(monkeypatch, {
        "Old.exe": '"C:\\old_install\\chain\\injector.exe" ifeo',
        "Keep.exe": paths.IFEO_VALUE,
        "Other.exe": '"C:\\other\\debugger.exe"',
    })
    monkeypatch.setattr(ifeo.os.path, "isfile", lambda _p: False)
    found = ifeo.scan_legacy()
    assert [e.exe_name for e in found] == ["Old.exe"]
    assert found[0].broken is True


def test_scan_legacy_marks_functional_old_location(monkeypatch):
    """目标仍存在的旧位置项: 检出但 broken=False(警示而非建议删)。"""
    _patch_winreg_scan(monkeypatch, {
        "Old.exe": '"D:\\portable\\chain\\injector.exe" ifeo',
    })
    monkeypatch.setattr(ifeo.os.path, "isfile", lambda _p: True)
    found = ifeo.scan_legacy()
    assert len(found) == 1
    assert found[0].broken is False


def test_scan_legacy_pythonw_era_signature(monkeypatch):
    """旧版 pythonw 两段式值: 识别为我们的残留, 目标取 injector.py 段。"""
    val = ('"C:\\Py\\pythonw.exe" '
           '"C:\\old\\specialk\\injector.py" ifeo')
    _patch_winreg_scan(monkeypatch, {"DS2.exe": val})
    monkeypatch.setattr(ifeo.os.path, "isfile", lambda p: p.endswith(".py"))
    found = ifeo.scan_legacy()
    assert len(found) == 1
    assert found[0].broken is False
    assert ifeo._extract_target(val) == r"C:\old\specialk\injector.py"


def test_build_ifeo_rm_args():
    args = ifeo.build_ifeo_rm_args(["A.exe", "B.exe"])
    assert args[0] == sys.executable
    assert args[1] == paths.LAUNCHER_PY
    assert args[2:] == ["ifeo-rm", "A.exe", "B.exe"]
