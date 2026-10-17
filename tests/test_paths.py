import importlib
import os
import sys

import pytest

from backend import paths


def test_chain_sources_exist():
    """链源码三件套收编在仓库 chain/ 下(唯一源码真相)。"""
    assert os.path.isdir(paths.CHAIN_DIR)
    assert os.path.isfile(paths.LAUNCHER_PY)
    assert os.path.isfile(paths.INJECTOR_PY)
    assert os.path.isfile(paths.DEFAULT_DLL)


def test_ifeo_value_matches_chain_sources():
    """GUI 的 IFEO_VALUE 必须与链源码计算值逐字一致(三处同规则)。"""
    sys.path.insert(0, paths.CHAIN_DIR)
    try:
        launcher_mod = importlib.import_module("haptic_launcher")
        injector_mod = importlib.import_module("injector")
    finally:
        sys.path.remove(paths.CHAIN_DIR)
    assert paths.IFEO_VALUE == launcher_mod.IFEO_VALUE
    assert paths.IFEO_VALUE == injector_mod.IFEO_VALUE
    assert paths.IFEO_VALUE.endswith('injector.py" ifeo')
    # 游戏注册表位置同样两处同规则(用户数据目录)
    assert paths.GAMES_YAML == launcher_mod.GAMES_YAML


def test_injector_ctypes_argtypes_complete():
    """chain/injector.py 的 ctypes 声明参数个数必须与真实 Win32 API 一致。

    v0.4.0/0.4.1 回归: VirtualAllocEx.argtypes 少一个 DWORD(4/5),
    ctypes 调用即 TypeError, 全线注入失败 — 此类错误只有显式断言能拦住。"""
    sys.path.insert(0, paths.CHAIN_DIR)
    try:
        injector_mod = importlib.import_module("injector")
    finally:
        sys.path.remove(paths.CHAIN_DIR)
    k = injector_mod.kernel32
    expected = {"OpenProcess": 3, "VirtualAllocEx": 5,
                "WriteProcessMemory": 5,
                "GetProcAddress": 2, "CreateRemoteThread": 7,
                "CreateProcessW": 10}
    for func, n in expected.items():
        assert len(getattr(k, func).argtypes) == n, func


def test_chain_dir_source_state():
    """源码态: CHAIN_DIR 即仓库根/chain, 派生路径全部在其下;
    游戏注册表例外 — 在用户数据目录(升级不丢), chain 下为旧位置。"""
    repo_root = os.path.dirname(os.path.dirname(
        os.path.abspath(paths.__file__)))
    assert paths.CHAIN_DIR == os.path.join(repo_root, "chain")
    assert paths.GAMES_YAML == os.path.join(paths.DATA_DIR, "games.yaml")
    assert paths.LEGACY_GAMES_YAML == os.path.join(paths.CHAIN_DIR,
                                                   "games.yaml")
    assert paths.LAUNCHER_EXE == os.path.join(paths.CHAIN_DIR,
                                              "haptic_launcher.exe")
    assert paths.INJECTOR_EXE == os.path.join(paths.CHAIN_DIR, "injector.exe")


@pytest.fixture
def frozen_paths(monkeypatch, tmp_path):
    """模拟 PyInstaller 冻结态 reload paths 模块。

    用例结束先撤销 monkeypatch 再 reload 回源码态, 避免模块级常量
    污染同进程的其他测试(paths 是单例模块, reload 就地生效)。"""
    fake_exe = tmp_path / "pkg" / "HapticImproveManager.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    importlib.reload(paths)
    yield fake_exe
    monkeypatch.undo()
    importlib.reload(paths)


def test_frozen_chain_dir(frozen_paths, tmp_path):
    """冻结态: 链目录解析为 <exe目录>/chain, 不真建目录/文件, 纯路径断言。"""
    chain = os.path.join(str(tmp_path), "pkg", "chain")
    assert paths.CHAIN_DIR == chain
    assert paths.GAMES_YAML == os.path.join(paths.DATA_DIR, "games.yaml")
    assert paths.LEGACY_GAMES_YAML == os.path.join(chain, "games.yaml")
    assert paths.LAUNCHER_PY == os.path.join(chain, "haptic_launcher.py")
    assert paths.INJECTOR_PY == os.path.join(chain, "injector.py")
    assert paths.DEFAULT_DLL == os.path.join(chain, "wasapi_relink.dll")
    assert paths.INJECTOR_RESULT == os.path.join(chain, "injector_result.txt")
    assert paths.INJECTOR_DEBUG_LOG == os.path.join(chain,
                                                    "injector_debug.log")
    assert paths.RELINK_LOG_DIR == os.path.join(chain, "logs")
    assert paths.RELINK_LOG == os.path.join(chain, "logs",
                                            "wasapi_relink.log")


def test_frozen_exe_paths(frozen_paths, tmp_path):
    chain = os.path.join(str(tmp_path), "pkg", "chain")
    assert paths.LAUNCHER_EXE == os.path.join(chain, "haptic_launcher.exe")
    assert paths.INJECTOR_EXE == os.path.join(chain, "injector.exe")
    assert paths.LAUNCHER_EXE.endswith("\\haptic_launcher.exe")
    assert paths.INJECTOR_EXE.endswith("\\injector.exe")


def test_frozen_ifeo_value(frozen_paths):
    """冻结态 IFEO_VALUE 指向随包 injector.exe(与 injector.py 冻结分支同构)。"""
    assert paths.IFEO_VALUE == f'"{paths.INJECTOR_EXE}" ifeo'
    assert paths.IFEO_VALUE.endswith('\\injector.exe" ifeo')
