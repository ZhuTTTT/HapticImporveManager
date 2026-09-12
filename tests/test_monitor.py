import os
from backend.monitor import tail, read_result


def test_tail_last_n(tmp_path):
    p = tmp_path / "log.txt"
    p.write_text("\n".join(f"line{i}" for i in range(100)), encoding="utf-8")
    lines = tail(str(p), 5)
    assert lines == ["line95", "line96", "line97", "line98", "line99"]


def test_tail_missing_file(tmp_path):
    assert tail(str(tmp_path / "nope.log")) == []


def test_tail_utf8(tmp_path):
    p = tmp_path / "log.txt"
    p.write_text("注入成功 ✓\n第二行\n", encoding="utf-8")
    assert tail(str(p), 1) == ["第二行"]


def test_read_result(tmp_path):
    p = tmp_path / "injector_result.txt"
    p.write_text("injected OK (module handle 0x7ff)\n", encoding="utf-8")
    mtime, text = read_result(str(p))
    assert mtime is not None
    assert text.startswith("injected OK")


def test_read_result_missing(tmp_path):
    mtime, text = read_result(str(tmp_path / "none.txt"))
    assert mtime is None and text == ""
