"""Minimal LoadLibrary injector — the XXMI/3DMigoto approach.

Instead of placing a proxy DLL in the game directory (which miHoYo's
anti-DLL wrapper renames/blocks), inject wasapi_relink.dll directly into
the game process. Nothing is written to the game directory.

HoYoKProtect strips OpenProcess access to the running game, so injecting
into an already-running process fails with access denied. The mod-loader
trick: WE launch the game — the creator's process handle from
CreateProcess keeps full access, bypassing handle stripping.

Usage:
    python injector.py launch <game_exe> <dll_path>   # launch + inject
    python injector.py <process_name> <dll_path>      # inject into running
"""
import ctypes
import os
import sys
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# 冻结为 onefile exe 后 __file__ 指向每次运行随机解包的临时目录,
# 须以 sys.executable 所在目录为基准
if getattr(sys, "frozen", False):
    HERE = os.path.dirname(sys.executable)
else:
    HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DLL = os.path.join(HERE, "wasapi_relink.dll")

# ctypes defaults to 32-bit int returns — on x64 this truncates pointers and
# causes phantom ERROR_NOACCESS (998) failures. Declare pointer types properly.
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.VirtualAllocEx.restype = wintypes.LPVOID
kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
                                    ctypes.c_size_t, wintypes.DWORD,
                                    wintypes.DWORD]
kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
                                        wintypes.LPCVOID, ctypes.c_size_t,
                                        ctypes.POINTER(ctypes.c_size_t)]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetProcAddress.restype = wintypes.LPVOID
kernel32.GetProcAddress.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]
kernel32.CreateRemoteThread.restype = wintypes.HANDLE
kernel32.CreateRemoteThread.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
                                        ctypes.c_size_t, wintypes.LPVOID,
                                        wintypes.LPVOID, wintypes.DWORD,
                                        wintypes.LPDWORD]
kernel32.CreateProcessW.restype = wintypes.BOOL
kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR,
                                    wintypes.LPVOID, wintypes.LPVOID,
                                    wintypes.BOOL, wintypes.DWORD,
                                    wintypes.LPVOID, wintypes.LPCWSTR,
                                    wintypes.LPVOID, wintypes.LPVOID]

PROCESS_CREATE_THREAD = 0x0002
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_READWRITE = 0x04


def find_pid(name: str) -> int:
    import subprocess
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-Process -Name '{name.replace('.exe', '')}' "
         "-ErrorAction SilentlyContinue).Id"],
        capture_output=True, text=True).stdout.strip()
    if not out:
        raise SystemExit(f"process {name} not found — is the game running?")
    return int(out.split()[0])


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [(n, wintypes.DWORD if n not in (
        "lpReserved", "lpDesktop", "lpTitle") else wintypes.LPWSTR)
        for n in ("cb", "lpReserved", "lpDesktop", "lpTitle")] + [
        ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", wintypes.LPVOID),
        ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]


def launch_and_inject(game_exe: str, dll_path: str, extra_args: str = "",
                      suspend_ifeo: bool = False) -> None:
    """CreateProcess gives the parent a full-access handle — the anti-cheat's
    OpenProcess stripping can't touch a handle we already hold.

    suspend_ifeo: temporarily remove the IFEO Debugger value while we create
    the process — otherwise our own CreateProcess re-triggers IFEO and
    recurses forever."""
    exe_name = os.path.basename(game_exe)
    if suspend_ifeo:
        _ifeo_off(exe_name)
    try:
        si = STARTUPINFOW()
        si.cb = ctypes.sizeof(STARTUPINFOW)
        pi = PROCESS_INFORMATION()
        cmdline = f'"{game_exe}" {extra_args}'.strip()
        # CreateProcessW requires lpCommandLine to be WRITABLE — a Python
        # str's buffer is read-only and can silently mangle argument parsing.
        cmdbuf = ctypes.create_unicode_buffer(cmdline)
        ok = kernel32.CreateProcessW(
            None, cmdbuf, None, None, False, 0, None,
            os.path.dirname(game_exe),
            ctypes.byref(si), ctypes.byref(pi))
        if not ok:
            _report(f"CreateProcess failed: {ctypes.get_last_error()}")
            raise SystemExit(1)
        print(f"launched pid={pi.dwProcessId}, injecting via parent handle...")
        _do_inject(pi.hProcess, dll_path)
        kernel32.CloseHandle(pi.hThread)
        kernel32.CloseHandle(pi.hProcess)
    finally:
        if suspend_ifeo:
            _ifeo_on(exe_name)


IFEO_BASE = (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
             r"\Image File Execution Options")


def _source_ifeo_value() -> str:
    """源码态 IFEO Debugger 值: 优先用 pythonw(无窗) + 同目录 injector.py。

    与 GUI 侧 backend/paths.py 的同名函数保持同一套计算规则 — 两处同改。
    """
    exe = sys.executable
    if os.path.basename(exe).lower() != "pythonw.exe":
        sibling = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(sibling):
            exe = sibling
    return f'"{exe}" "{os.path.join(HERE, "injector.py")}" ifeo'


# IFEO Debugger 值: 冻结态指向随包的 injector.exe, 源码态动态计算 pythonw 命令行
IFEO_VALUE = (f'"{os.path.join(HERE, "injector.exe")}" ifeo'
              if getattr(sys, "frozen", False) else _source_ifeo_value())


def _ifeo_off(exe_name: str):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            IFEO_BASE + "\\" + exe_name, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, "Debugger")
    except PermissionError:
        _notify("Haptics 注入失败",
                f"无权限修改 IFEO 键 ({exe_name})，请重新运行 ifeo on 授权")
        raise


def _ifeo_on(exe_name: str):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            IFEO_BASE + "\\" + exe_name, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "Debugger", 0, winreg.REG_SZ, IFEO_VALUE)
    except PermissionError:
        pass  # best-effort restore; 用户在管理器里重新开启 IFEO 即可


NOTIFIER_NAME = "Haptics"   # 通知栏显示的来源名称


def _notify(title: str, message: str) -> None:
    """Native WinRT toast via python-winsdk — no PowerShell subprocess,
    so no console window flash at all. show() hands the toast to the
    system broker, so the injector may exit immediately after."""
    import html
    try:
        from winsdk.windows.data.xml.dom import XmlDocument
        from winsdk.windows.ui.notifications import (
            ToastNotification, ToastNotificationManager)
        t, m = html.escape(title), html.escape(message)
        xml = XmlDocument()
        xml.load_xml(
            f"<toast><visual><binding template='ToastText02'>"
            f"<text id='1'>{t}</text><text id='2'>{m}</text>"
            f"</binding></visual></toast>")
        ToastNotificationManager.create_toast_notifier(
            NOTIFIER_NAME).show(ToastNotification(xml))
        _report_debug(f"notify shown: {title}")
    except Exception as e:
        _report_debug(f"notify failed: {e}")


def _report_debug(msg: str) -> None:
    import datetime
    with open(os.path.join(HERE, "injector_debug.log"), "a") as f:
        f.write(f"{datetime.datetime.now():%H:%M:%S} {msg}\n")


def _report(msg: str) -> None:
    """Elevated runs have no visible console — persist results to a file."""
    print(msg)
    with open(os.path.join(HERE, "injector_result.txt"), "w") as f:
        f.write(msg + "\n")


def _do_inject(h, dll_path: str) -> None:
    path_bytes = dll_path.encode("utf-16-le") + b"\x00\x00"

    mem = kernel32.VirtualAllocEx(h, None, len(path_bytes),
                                  MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
    if not mem:
        _report(f"VirtualAllocEx failed: {ctypes.get_last_error()}")
        _notify("Haptics 注入失败", "内存分配被拒（反作弊拦截）")
        raise SystemExit(1)

    written = ctypes.c_size_t(0)
    if not kernel32.WriteProcessMemory(h, mem, path_bytes, len(path_bytes),
                                       ctypes.byref(written)):
        _report(f"WriteProcessMemory failed: {ctypes.get_last_error()}")
        _notify("Haptics 注入失败", "内存写入失败")
        raise SystemExit(1)

    loadlib = kernel32.GetProcAddress(
        kernel32.GetModuleHandleW("kernel32.dll"), b"LoadLibraryW")
    thread = kernel32.CreateRemoteThread(h, None, 0, loadlib, mem, 0, None)
    if not thread:
        _report(f"CreateRemoteThread failed: {ctypes.get_last_error()} "
                "(anti-cheat may be blocking injection)")
        _notify("Haptics 注入失败", "远程线程创建被拒（反作弊拦截）")
        raise SystemExit(1)

    kernel32.WaitForSingleObject(thread, 10000)
    exit_code = wintypes.DWORD(0)
    kernel32.GetExitCodeThread(thread, ctypes.byref(exit_code))
    kernel32.CloseHandle(thread)

    if exit_code.value:
        _report(f"injected OK (module handle 0x{exit_code.value:x})")
        _notify("Haptics 低延迟已激活", "wasapi_relink 注入成功，震动延迟已优化")
    else:
        _report("LoadLibrary returned NULL — DLL failed to load in target")
        _notify("Haptics 注入失败", "DLL 加载失败，游戏以原生模式运行")


def inject(pid: int, dll_path: str) -> None:
    h = kernel32.OpenProcess(
        PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION | PROCESS_VM_WRITE
        | PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess failed: {ctypes.get_last_error()} "
                         "(try running as admin)")
    _do_inject(h, dll_path)
    kernel32.CloseHandle(h)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "launch":
        launch_and_inject(sys.argv[2], sys.argv[3],
                          sys.argv[4] if len(sys.argv) > 4 else "")
    elif len(sys.argv) >= 3 and sys.argv[1] == "ifeo":
        # Invoked by Windows as the IFEO "debugger":
        # argv = [script, "ifeo", game_exe, ...original launcher args]
        # Forward the original args verbatim (this also lets us LOG what
        # the launcher actually passes — e.g. how it enables DX12).
        game_exe = sys.argv[2]
        orig_args = " ".join(sys.argv[3:])
        _report(f"ifeo launch: {game_exe} args=[{orig_args}]")
        launch_and_inject(game_exe, DEFAULT_DLL, orig_args, suspend_ifeo=True)
    elif len(sys.argv) == 3:
        pid = find_pid(sys.argv[1])
        print(f"target pid: {pid}")
        inject(pid, sys.argv[2])
    else:
        raise SystemExit(__doc__)
