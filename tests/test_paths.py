import os
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
