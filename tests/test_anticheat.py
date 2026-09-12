import os
import shutil
from backend.anticheat import scan_exe, AnticheatReport, KNOWN_SIGNATURES


def test_notepad_is_clean(tmp_path):
    # System32 里存在 hoyokprotect.sys(本机 ZZZ 反作弊驱动), 会污染同目录扫描;
    # 复制到干净临时目录, 既解析真实 PE 导入表又避开系统目录噪声
    exe = tmp_path / "notepad.exe"
    shutil.copy(r"C:\Windows\System32\notepad.exe", exe)
    report = scan_exe(str(exe))
    assert report.risk == "none"
    assert report.hits == []


def test_known_signature_matching(monkeypatch, tmp_path):
    exe = tmp_path / "game.exe"
    exe.write_bytes(b"MZ")  # pefile 会解析失败 → 走 sibling 扫描
    (tmp_path / "EasyAntiCheat").mkdir()
    (tmp_path / "HoYoKProtect.sys").write_bytes(b"x")
    report = scan_exe(str(exe))
    assert report.risk == "known"
    assert any("EasyAntiCheat" in h for h in report.hits)
    assert any("HoYoKProtect" in h or "mhyprot" in h.lower() for h in report.hits)


def test_nonexistent_exe(tmp_path):
    report = scan_exe(str(tmp_path / "nope.exe"))
    assert report.risk == "none"
