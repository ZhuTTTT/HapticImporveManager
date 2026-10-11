import importlib
import os
import sys

import pytest

from backend import paths


def test_specialk_paths_exist():
    assert os.path.isdir(paths.SPECIALK_DIR)
    assert os.path.isfile(paths.LAUNCHER_PY)
    assert os.path.isfile(paths.INJECTOR_PY)
    assert os.path.isfile(paths.DEFAULT_DLL)


def test_ifeo_value_matches_injector():
    """IFEO_VALUE 必须与 injector.py 中的常量逐字一致(踩坑 #2)。"""
    with open(paths.INJECTOR_PY, encoding="utf-8") as f:
        src = f.read()
    # injector.py 里常量是拼接字符串, 逐段检查关键部分
    assert "pythonw.exe" in paths.IFEO_VALUE
    assert "injector.py\" ifeo" in paths.IFEO_VALUE
    frag = paths.IFEO_VALUE.split('"')[3]  # injector.py 路径段
    assert frag.replace("\\\\", "\\") in src.replace("\\\\", "\\")


def test_chain_dir_source_state():
    """源码态: CHAIN_DIR 即本机 specialk 开发目录, 派生路径全部在其下。"""
    assert paths.CHAIN_DIR == paths.DEV_SPECIALK_DIR
    assert paths.GAMES_YAML == os.path.join(paths.CHAIN_DIR, "games.yaml")
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
    assert paths.GAMES_YAML == os.path.join(chain, "games.yaml")
    assert paths.LAUNCHER_PY == os.path.join(chain, "haptic_launcher.py")
    assert paths.INJECTOR_PY == os.path.join(chain, "injector.py")
    assert paths.DEFAULT_DLL == os.path.join(chain, "zzz_inject",
                                             "wasapi_relink.dll")
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
