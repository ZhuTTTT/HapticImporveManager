; HapticImproveManager 安装程序 — Inno Setup 6
; 系统级安装(Program Files): 安装时给 chain\ 授 Users 可写(运行时要写
; games.yaml/注入日志), 应用本体永远普通权限运行。
; 升级 = 覆盖安装文件: games.yaml/日志不是安装清单内的文件, 天然保留;
; 同路径下 IFEO 注册表项(path 字符串)自动继承, 无需重新开关。
; 卸载时自动清理指向本安装目录的 IFEO Debugger 值(否则游戏无法启动)。

#ifndef AppVersion
  #define AppVersion "0.4.6"
#endif

[Setup]
AppId={{B7E2A914-6C3F-4D58-9A21-1F0E8C5D7B63}
AppName=HapticImproveManager
AppVersion={#AppVersion}
AppPublisher=ZhuTTTT
AppSupportURL=https://github.com/ZhuTTTT/HapticImporveManager
DefaultDirName={autopf}\HapticImproveManager
DefaultGroupName=HapticImproveManager
PrivilegesRequired=admin
OutputDir=dist
OutputBaseFilename=HapticImproveManager-Setup-{#AppVersion}
SourceDir=..
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\HapticImproveManager.exe
SetupIconFile=packaging\icon.ico
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
; 简体中文语言文件随仓库分发(官方编译器不自带), 保证任何机器可构建
Name: "chinesesimplified"; MessagesFile: "packaging\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Dirs]
; 运行时数据(games.yaml/日志/注入结果)全部写在 chain\ 下 — 授 Users 可写,
; 应用免管理员运行(Program Files 默认只读)
Name: "{app}\chain"; Permissions: users-modify

[Files]
; 排除运行残留, 与 build_exe.bat 的出包卫生同一原则
Source: "dist\HapticImproveManager\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs; \
  Excludes: "chain\games.yaml,chain\logs\*,chain\injector_result.txt,chain\injector_debug.log"

[Icons]
Name: "{group}\HapticImproveManager"; Filename: "{app}\HapticImproveManager.exe"
Name: "{autodesktop}\HapticImproveManager"; Filename: "{app}\HapticImproveManager.exe"; Tasks: desktopicon

[Run]
; 完成页「打开应用」勾选框(默认勾上)。runasoriginaluser: 安装器是提权
; 运行的, 必须以原始用户身份拉起 — 应用本体永远普通权限运行;
; skipifsilent: 静默安装不拉起
Filename: "{app}\HapticImproveManager.exe"; \
  Description: "{cm:LaunchProgram,HapticImproveManager}"; \
  Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
{ 卸载时清理指向本安装目录的 IFEO Debugger 值:
  值是路径字符串, 逐 IFEO 子键扫描比对; 只删 Debugger 值(与 launcher 的
  ifeo off 行为一致), 不删子键本身, 不碰指向其他路径的项 }
procedure CleanupOurIfeoEntries();
var
  SubkeyNames: TArrayOfString;
  I: Integer;
  IfeoBase, KeyPath, DebuggerVal, Needle: String;
begin
  IfeoBase := 'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options';
  Needle := Lowercase(ExpandConstant('{app}') + '\chain\injector.exe');
  if RegGetSubkeyNames(HKLM, IfeoBase, SubkeyNames) then
    for I := 0 to GetArrayLength(SubkeyNames) - 1 do
    begin
      KeyPath := IfeoBase + '\' + SubkeyNames[I];
      if RegQueryStringValue(HKLM, KeyPath, 'Debugger', DebuggerVal) then
        if Pos(Needle, Lowercase(DebuggerVal)) > 0 then
          RegDeleteValue(HKLM, KeyPath, 'Debugger');
    end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    CleanupOurIfeoEntries();
    { games.yaml/日志不是安装清单文件, 卸载默认保留; 询问是否一并删除 }
    if MsgBox('是否同时删除游戏注册表(games.yaml)与注入日志?' + #13#10 +
              '选「否」保留在 ' + ExpandConstant('{app}') + '\chain, 重装后可继续使用。',
              mbConfirmation, MB_YESNO) = IDYES then
      DelTree(ExpandConstant('{app}') + '\chain', True, True, True);
  end;
end;
