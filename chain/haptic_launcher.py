# 通用低延迟 haptic 启动器 — 无反作弊单机游戏通用
# 原理: 父进程拉起游戏 + 注入 wasapi_relink (压缩游戏音频缓冲)
# 游戏目录只需放 redirect_config.toml (纯文本), 不放任何 DLL
#
# 用法:
#   python haptic_launcher.py list          # 列出已注册游戏
#   python haptic_launcher.py ds2           # 启动 DS2
#   注册新游戏: 用 HapticImproveManager GUI, 或直接编辑同目录 games.yaml

import os
import subprocess
import sys

# 冻结为 onefile exe 后 __file__ 指向每次运行随机解包的临时目录,
# 须以 sys.executable 所在目录为基准
if getattr(sys, "frozen", False):
    HERE = os.path.dirname(sys.executable)
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
DLL = os.path.join(HERE, "wasapi_relink.dll")


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

def _data_dir() -> str:
    """用户数据目录: %APPDATA%\\HapticImproveManager — 与 GUI 侧
    backend/paths.py 的 _data_dir 同一规则(两处同改)。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "HapticImproveManager")


# 游戏注册表在用户数据目录(升级/换安装位置不丢), 与 GUI 共用单一数据源;
# 旧位置(chain/games.yaml)的迁移由 GUI 启动时完成(load_or_migrate)
GAMES_YAML = os.path.join(_data_dir(), "games.yaml")


def load_games() -> dict:
    """读同目录 games.yaml(GUI 与 CLI 共用单一数据源); 缺失视为空表。"""
    if os.path.exists(GAMES_YAML):
        import yaml
        with open(GAMES_YAML, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {name: entry["exe"]
                for name, entry in (data.get("games") or {}).items()}
    return {}


IFEO_BASE = (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
             r"\Image File Execution Options")


def _is_admin() -> bool:
    import ctypes as ct
    return bool(ct.windll.shell32.IsUserAnAdmin())


def _elevate():
    import ctypes as ct
    # ShellExecute 会把 lpFile(exe 本体)自动设为 argv[0]:
    # 冻结态 lpParameters 再带 argv[0], 新进程 argv[1] 变成 exe 路径,
    # 子命令解析错位(ifeo on 静默失效); 源码态 python 需要 argv[0] 定位脚本
    params = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
    ct.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join(f'"{a}"' for a in params), None, 1)
    sys.exit(0)


def _grant_user_write(exe_name: str):
    """Grant the current user FullControl on this game's IFEO subkey, so the
    (non-elevated) injector can suspend/restore the Debugger value when the
    game starts from Steam."""
    import subprocess
    import getpass
    user = f"{os.environ.get('USERDOMAIN')}\\{getpass.getuser()}"
    # Get-Acl/Set-Acl need the PSDrive form "HKLM:\" — "HKLM\\" fails silently
    key = ("HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion"
           f"\\Image File Execution Options\\{exe_name}")
    ps = (
        f"$acl = Get-Acl '{key}'; "
        f"$rule = New-Object System.Security.AccessControl.RegistryAccessRule("
        f"'{user}','FullControl','Allow'); "
        f"$acl.AddAccessRule($rule); Set-Acl '{key}' $acl")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)


def ifeo(name: str, action: str):
    import winreg
    exe = load_games()[name]
    exe_name = os.path.basename(exe)
    key_path = IFEO_BASE + "\\" + exe_name
    if action == "status":
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
                val, _ = winreg.QueryValueEx(k, "Debugger")
            print(f"{name}: IFEO ON  ({val})")
        except FileNotFoundError:
            print(f"{name}: IFEO off")
        return
    if not _is_admin():
        _elevate()
    if action == "on":
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
            winreg.SetValueEx(k, "Debugger", 0, winreg.REG_SZ, IFEO_VALUE)
        _grant_user_write(exe_name)
        print(f"{name}: IFEO enabled — Steam launches will now auto-inject")
    elif action == "off":
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                                winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, "Debugger")
        except FileNotFoundError:
            pass
        print(f"{name}: IFEO disabled")
    else:
        raise SystemExit("action must be on|off|status")


def ifeo_rm(subkey_names: list[str]):
    """按 IFEO 子键名(exe 文件名)批量删除 Debugger 值 — GUI 旧版残留清理。

    与 ifeo off 不同: 不按游戏名反查 games.yaml(残留项的游戏可能早已
    不在注册表), 直接操作子键; 只删 Debugger 值, 不动子键与其他值。"""
    import winreg
    if not _is_admin():
        _elevate()
    for sub in subkey_names:
        key_path = IFEO_BASE + "\\" + sub
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0,
                                winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, "Debugger")
            print(f"{sub}: Debugger removed")
        except FileNotFoundError:
            print(f"{sub}: no entry")


def _injector_cmd() -> list[str]:
    """启动注入器的命令行前缀: 冻结态直接调随包的 injector.exe,
    源码态走当前解释器跑 injector.py。"""
    if getattr(sys, "frozen", False):
        return [os.path.join(HERE, "injector.exe")]
    return [sys.executable, os.path.join(HERE, "injector.py")]


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "ifeo-rm":
        ifeo_rm(sys.argv[2:])
        return
    if len(sys.argv) >= 3 and sys.argv[1] == "ifeo":
        name = sys.argv[2].lower()
        if name not in load_games():
            raise SystemExit(f"unknown game '{name}' — run with 'list'")
        ifeo(name, sys.argv[3] if len(sys.argv) > 3 else "status")
        return
    if len(sys.argv) != 2 or sys.argv[1] == "list":
        print("registered games:")
        for name, path in load_games().items():
            ok = "OK" if os.path.exists(path) else "MISSING"
            print(f"  {name:6s} [{ok}] {path}")
        print("\nusage: haptic_launcher.py <name>           launch + inject")
        print("       haptic_launcher.py ifeo <name> on   Steam/任何方式启动都自动注入")
        print("       haptic_launcher.py ifeo <name> off  关闭自动注入")
        print("       haptic_launcher.py ifeo <name>      查询状态")
        return
    name = sys.argv[1].lower()
    if name not in load_games():
        raise SystemExit(f"unknown game '{name}' — run with 'list'")
    exe = load_games()[name]
    if not os.path.exists(exe):
        raise SystemExit(f"exe not found: {exe}")
    cfg = os.path.join(os.path.dirname(exe), "redirect_config.toml")
    if not os.path.exists(cfg):
        print(f"warning: no redirect_config.toml next to the exe,\n"
              f"         wasapi_relink will run with DEFAULT config")
    # 单机游戏不需要管理员; 个别游戏 exe 自身 manifest 要求管理员(由
    # Windows 对该 exe 弹 UAC), 与启动方式无关
    subprocess.run(_injector_cmd() + ["launch", exe, DLL])


if __name__ == "__main__":
    main()
