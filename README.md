# HapticImproveManager

中文 | [English](README_EN.md)

DualSense 触觉(haptic)低延迟注入系统的可视化管理器 — 把 PC 游戏写给手柄的
haptic 音频缓冲从原生 20–85ms 压到 ~10ms,用图形界面管理整个注入链路。

![深色主题](docs/screenshots/dark.png)

<details>
<summary>浅色主题截图</summary>

![浅色主题](docs/screenshots/light.png)
</details>

## 功能

- **游戏中心**:左侧游戏列表(状态点 + 搜索),右侧详情页,选中即上下文——
  状态徽章、IFEO 自动注入开关、启动游戏、注入配置都归属于当前游戏;
  移除游戏时自动关闭其 IFEO 自动注入,不留注册表残留
- **注入配置通俗化**:四种模式(普通 / 虚拟缓冲 / 兼容 / 不干预)卡片式单选,
  每项配置带白话说明,缓冲帧数实时换算毫秒,不适用当前模式的项自动隐藏
- **添加游戏向导**:选择 exe → 反作弊特征检测(HoYoKProtect/EAC/BattlEye 风险提示)
  → 生成 `redirect_config.toml` → 一键开启 IFEO
- **诊断页**:最近注入结果 + `injector_debug.log` / `wasapi_relink.log` 尾随监视,
  一键在资源管理器中打开
- **设置页**:浅色 / 深色 / 跟随系统主题,Mica 云母背景,日志目录可更改并
  批量同步到所有已注册游戏
- **多语言**:设置页切换 跟随系统 / 中文 / English,重启应用后生效

## 安装与运行

### 方式一:下载成品(推荐)

从 [Releases](../../releases) 下载:

- **`HapticImproveManager-Setup-x.y.z.exe`(安装程序,推荐)**——双击安装到
  `C:\Program Files\HapticImproveManager`(安装需一次 UAC;自动创建开始菜单
  快捷方式、给 `chain\` 目录授写权限使应用免管理员运行)。升级直接覆盖安装,
  游戏注册表与 IFEO 设置自动保留;卸载时自动清理 IFEO 注册表项
- **`HapticImproveManager.zip`(便携版)**——解压后双击
  `HapticImproveManager.exe`(整目录拷走才可用,勿只拷 exe;解压位置需可写,
  不要放进 Program Files)

> 零依赖,解压即用:注入链已随包冻结分发——`chain/` 下的 `injector.exe`、
> `haptic_launcher.exe` 与 `wasapi_relink.dll`,无需安装 Python
> 或任何外部依赖。

### 方式二:源码运行

要求 Windows 10/11 + Python 3.11+:

```bash
python -m pip install -r requirements.txt
python app.py
```

## 权限说明(什么时候会弹 UAC)

本软件本体**始终以普通权限运行**,不需要用管理员身份启动。但 IFEO 自动注入
写在 `HKLM` 注册表项下,修改它需要管理员权限,由随包的 launcher 按需自行
提权——以下场景会弹一次 UAC,属正常现象:

1. **开启 IFEO 自动注入**(添加游戏向导最后一步,或详情页的 IFEO 开关)
2. **关闭 IFEO 自动注入**(详情页的 IFEO 开关)
3. **移除游戏**且其自动注入处于开启状态——会先自动关闭 IFEO 再移除;
   此时若在 UAC 弹窗点「取消」,移除会中止、游戏保留在列表中
   (避免留下 GUI 里看不见的注册表残留)

另外,个别游戏(如《绝区零》)的 exe 自带"要求管理员"清单,启动时 Windows
会对游戏本身弹 UAC——这是游戏自身的行为,与本工具无关。

使用安装程序时,**安装/卸载本身**也会各弹一次 UAC(写入 Program Files 与
开始菜单需要管理员权限),这属于安装器行为,与应用运行无关。

## 工作原理

PC 游戏把 DualSense haptic 渲染成音频流,经 WASAPI 共享模式送入手柄音频端点
(4 声道:ch1/2 = 扬声器,ch3/4 = haptic 马达)。游戏申请的音频缓冲
(20–85ms)是 haptic 延迟的主要来源。

本工具的注入链(源码就在本仓库 `chain/` 目录,构建时冻结为 exe 随包分发)把
[wasapi_relink](https://github.com/Litttlefish/wasapi_relink) DLL 注入游戏进程,
在 WASAPI 层面压缩缓冲、约束写入节奏。本 GUI 负责游戏注册、配置编辑
(`redirect_config.toml`)、IFEO 自动注入管理与日志诊断。

## 项目结构

```
HapticImporveManager/
├─ app.py                   # 入口
├─ backend/                 # 后端: 路径常量 / 游戏注册表 / IFEO / 配置 / 日志
├─ ui/                      # PySide6 + Fluent Widgets 界面(薄 GUI, 普通权限)
├─ chain/                   # 注入链(唯一源码真相, 随包冻结分发)
│   ├─ injector.py          #   IFEO 拉起, 无窗; 负责创建进程 + 远程线程注入
│   ├─ haptic_launcher.py   #   GUI 子进程 / CLI; IFEO 开关时自行 UAC 提权
│   └─ wasapi_relink.dll    #   被注入的核心 DLL(第三方, Apache-2.0)
├─ i18n.py                  # 中英双语文案
├─ tests/                   # pytest 测试套件
├─ packaging/               # 打包: build_exe.bat(应用+链 zip)
│                           #         installer.iss + build_installer.bat(Inno 安装程序)
├─ licenses/                # 第三方组件许可证文本
└─ docs/superpowers/        # 设计与实现文档
```

运行时数据分三处:游戏注册表 `games.yaml` 与 GUI 设置存
`%APPDATA%/HapticImproveManager/`(升级/换安装位置不丢,旧版 chain 位置的
注册表首次启动自动迁移);注入日志在应用目录 `chain/`(`logs/`、
`injector_result.txt` 等,随安装走);`redirect_config.toml`(wasapi_relink
读取的注入配置)写在各游戏目录。

## 二次开发

```bash
python -m pip install -r requirements.txt
python app.py                    # 源码态运行(GUI 直接使用 chain/ 下的 .py 链)
python -m pytest tests/ -v       # 测试
packaging\build_exe.bat          # 打包: dist\HapticImproveManager\ + 发布 zip
packaging\build_installer.bat    # 完整发版: 上一条 + Inno 安装程序(需 Inno Setup 6)
```

打包完全自包含:GUI 冻结为 onedir exe,`chain/` 链源码冻结为
`injector.exe` / `haptic_launcher.exe` 并连同 `wasapi_relink.dll` 一起收进
`dist\HapticImproveManager\chain\`,无任何机器相关的路径常量。`chain\` 每次
构建整目录重建,本机试跑留下的 `games.yaml` 等运行残留不会进 zip;脚本构建
失败时会明确报 `[FAIL]`(例如 exe 正在运行导致 `dist\` 被占用)。

修改链源码时注意:`IFEO_VALUE` 在 `backend/paths.py`、`chain/injector.py`、
`chain/haptic_launcher.py` 三处按同一规则计算(GUI 靠它识别注册表里的
Debugger 值是不是自己的),改动必须三处同步——`tests/test_paths.py` 有一致性
测试兜底。

## 致谢

- [wasapi_relink](https://github.com/Litttlefish/wasapi_relink) (Litttlefish) —
  haptic 低延迟的核心:被注入游戏进程、在 WASAPI 层面压缩音频缓冲的 DLL,
  以 Apache-2.0 许可证随包再分发(许可证文本见 `licenses/`)
- [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PySide6-Fluent-Widgets)
  (zhiyiYo) — 整个界面的 Fluent Design 组件库
- [XXMI](https://github.com/SpectrumQT/XXMI) / [3DMigoto](https://github.com/bo3b/3DMigoto)
  社区 — `chain/injector.py` 的注入思路来源:以创建者身份拉起游戏进程,
  借 CreateProcess 返回的全权限句柄绕过反作弊的句柄剥离

## 许可证

[MIT](LICENSE) — 可自由使用、修改、再分发(包括商用),只需保留版权声明。

第三方组件:`wasapi_relink.dll` 以 [Apache-2.0](licenses/wasapi_relink.LICENSE.txt)
许可证随包再分发,版权归 Litttlefish 所有。
