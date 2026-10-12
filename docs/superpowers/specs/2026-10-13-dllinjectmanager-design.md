# DllInjectManager 设计文档 — HapticImporveManager fork 为通用 DLL 注入管理器

日期: 2026-10-13
状态: 待评审
上游: HapticImporveManager v0.3.0 (ZhuTTTT/HapticImporveManager)

## 1. 背景与目标

HapticImporveManager 的注入链(injector + launcher + IFEO)经 v0.3.0 验证是通用的:
`injector.exe launch <exe> <dll>` 接受任意 DLL。唯一硬编码是 IFEO 自动注入的载荷
(wasapi_relink.dll)与触觉调参 UI。

本设计将其 fork 为 **DllInjectManager**: 统一管理器,每个游戏维护一个**有序载荷
列表**(任意 DLL),IFEO 自动注入按列表顺序全部注入;载荷可声明**控制适配器**
(per-DLL 设置面板),首发两个适配器:

- `wasapi_relink.dll` → 现有触觉调参面板(编辑游戏目录 redirect_config.toml)原样搬入
- `dlss5-feed.addon64` → DLSS5-Feeder 12 参数面板(原子改写 dlss5-feed.cfg,
  Feeder 1.17.0 每 60 帧热重载,游戏内即时生效)

驱动用例: DLSS5 破解/替换生态(DLSS 5 Swapper 已装,其 Feeder 路线的设置面
板;以及任意第三方 DLL 的注入管理)。

## 2. 范围

### 包含
- fork 全部既有能力: 游戏注册表、IFEO 自动注入(含提权/ACL 授权)、手动启动+注入、
  状态点、日志页、设置页(主题/语言)、中英双语、冻结打包(onedir GUI + onefile 链)
- 每游戏有序载荷列表(增删、排序、启用开关、路径校验、PE 架构校验 x64/x86)
- IFEO/手动注入按列表顺序注入全部启用载荷,逐载荷报告结果
- 适配器机制 + 两个首发适配器(wasapi_relink / dlss5-feed)
- 从旧应用(HapticImporveManager)games.yaml 的一次性导入(含 IFEO 接管提示)
- 全部 i18n(新增键双语)、测试适配与新增

### 不包含(YAGNI)
- DLSS5-Feeder 路线的**安装/部署**(ReShade/dgVoodoo/备份体系复杂,继续由
  DLSS 5 Swapper 负责;本工具只在检测到 Feeder 已部署时提供控制面板)
- 游戏内 overlay(官方 F8 面板已存在;像素流管道不复刻)
- 第三方 DLL 的获取/下载(用户自备)
- 卸载旧应用(仅提示)
- RenoDX 路由面板(官方 overlay 才有桥,文件面未公开,后续版本再评)

## 3. 架构

### 3.1 fork 方式
- `git clone` 本地仓库到新目录 `C:\Users\ZhuTT\Workspace\DllInjectManager`(保留历史),
  改 remote 或先无 remote,首个提交做品牌改名
- 注入链源码(injector.py / launcher.py)从 `specialk\` **迁入新仓库** `chain\` 目录,
  单一仓库拥有全部源码;wasapi_relink.dll 以二进制资产存 `payloads\` 并附 README
  注明源码已佚失、勿删
- 旧仓库保持不动,v0.3.0 继续可用

### 3.2 复用清单(原样或改名)
| 模块 | 处置 |
|---|---|
| backend/ifeo.py(IFEO on/off/status/提权) | 原样,改产品名引用 |
| backend/launcher.py(ProcessRunner/启动) | 适配多载荷 |
| backend/registry.py(games.yaml CRUD/迁移) | schema 升级,迁移逻辑改写 |
| backend/paths.py(冻结两态路径) | 改名 + CHAIN_DIR 指向新结构 |
| ui/main_window, settings_page, logs_page, theme, restart, add_game_dialog | 原样/改文案 |
| ui/config_card.py(触觉面板) | 变为 wasapi_relink 适配器面板,游戏目录 redirect_config.toml 语义不变 |
| ui/game_detail.py, games_page.py | 详情页重构(载荷列表+适配器面板),列表 hint 改载荷摘要 |
| i18n.py 机制 | 原样,键增删 |
| packaging/build_exe.bat | 适配新链结构与 payloads 拷贝 |
| 94 个测试 | 触觉专属改适配,新增见 §8 |

### 3.3 注入链改动(chain/,冻结为 onefile exe)
- `injector.exe ifeo` 模式: 不再写死 DEFAULT_DLL;按 `basename(game_exe)` 反查
  CHAIN_DIR 旁 games.yaml,取该游戏**启用的载荷有序列表**,逐个 `_do_inject`;
  单个失败不阻断后续;injector_result.txt 逐载荷记录;toast 文案参数化
  (产品名+游戏名+成功/失败计数)
- `launch` 子命令扩展: `injector.exe launch <exe> --dll a --dll b -- <游戏参数>`;
  兼容旧形式(单 dll 位置参数)
- 保留 `injector.exe <process> <dll>`(注入运行中进程),供"立即注入"按钮
- launcher 读 games.yaml 载荷列表,组装 injector 命令(list 传参,无 shell 引号问题)
- `_elevate` 冻结 argv 修复、--windowed、CREATE_NO_WINDOW 全部保留

### 3.4 数据模型(games.yaml v2)
```yaml
games:
  ds2:
    exe: C:\...\DS2.exe
    payloads:
      - path: C:\...\DllInjectManager\payloads\wasapi_relink.dll
        adapter: wasapi_relink   # 可省略 = 无面板
        enabled: true
      - path: D:\mods\some-unlocker.dll
        enabled: false
```
- 旧字段(mode_hint/buffer_hint/config_path)废弃;导入时转换(见 §6)
- 列表 hint 由注册表 payloads 派生(数量+名称摘要),不再冗余存储

### 3.5 适配器机制
- `backend/adapters.py`: 注册表 `{"wasapi_relink": HapticAdapter, "dlss5_feed": FeederAdapter}`,
  适配器接口: `detect(game_dir) -> bool`、`panel_class`(UI 面板)、状态摘要
- **dlss5_feed 特殊**: 不由我们注入(ReShade addon);按"检测到的工具"挂在游戏详情页:
  检测 `<exe_dir>\dlss5-feed.addon64`/`addon32` 存在即出面板
- 适配器面板编辑的是**各自载荷自己的配置文件**,本工具不碰进程内存

### 3.6 DLSS5-Feeder 面板(12 参数,源自 feeder-controls.hpp)
落地文件: `<exe_dir>\dlss5-feed.cfg`(key=value 纯文本,Feeder 每 60 帧热重载)。

| key | 名称 | 范围/步长 | 备注 |
|---|---|---|---|
| enabled | Feeder 启用 | 0/1 | **只读状态**,不提供开关(cfg 关断后无法自愈) |
| work_resolution | 工作分辨率 % | 50–100 / 1 | DX11 only |
| work_sharpness | 锐度 | 0–1 / .01 | DX11 only |
| mv_scale_x/y | 运动矢量缩放 | -2–2 / .01 | |
| hdr | HDR 契约 | -1–1 / 1 | |
| depth_inverted | 深度约定 | -1/0/1 | |
| work_upscale | 升采样 | 0 bilinear/1 FSR1/2 DLSS SR | DX11 only |
| hdr_bridge | HDR10 桥 | -1/0/1 | DX11 only |
| hdr_paper_white | HDR 纸白 nits | 50–1000 / 1 | DX11 only |
| hold_strength | 输出稳定器 | 0–1 / .01 | |
| hold_tolerance | 稳定容差 | 0–1 / .01 | |

写纪律(照官方 accept()): 先备份 `dlss5-feed.cfg.lab-original`(存在则不覆盖)→
写临时文件 → 复读校验未被并发修改 → MoveFileEx 原子替换。DX11-only 项给提示文案
(外部无法可靠探测游戏 API,不做硬禁用)。状态行: addon 存在? cfg 存在?
enabled+mode∈{1,2} → "喂帧中/未激活"。

## 4. UI 结构

- **列表页**: 状态点语义改为 exe 存在+IFEO  ours+全部启用载荷路径存在且架构匹配;
  hint = "N 个载荷 · wasapi_relink 等"
- **详情页**(填满右侧,沿用现布局):
  1. 信息卡(exe/IFEO 开关/启动/立即注入)
  2. **载荷卡**: 有序列表(上下移/启用开关/删除/添加文件对话框),每行显示名称+
     架构徽标+路径校验;带适配器的行有"设置"展开
  3. 适配器面板区: wasapi_relink → 现 ConfigCard;dlss5_feed → §3.6 面板
- 设置页/日志页/导航不变;窗口标题与品牌文案全换

## 5. 命名与品牌
- 产品名 DllInjectManager: exe、安装目录、窗口标题、`%APPDATA%\DllInjectManager\`、
  toast NOTIFIER_NAME、IFEO Debugger 指向新链
- 仓库 ZhuTTTT/DllInjectManager(推送时机由用户决定)

## 6. 迁移与共存
- 首次启动检测旧应用 games.yaml(旧 CHAIN_DIR 路径): 导入各游戏 exe,为每个
  游戏自动挂 wasapi_relink 载荷(指向新 payloads 目录副本),config 文件不动
  (留在游戏目录)
- 若某游戏 IFEO Debugger 指向旧 injector: 导入向导逐项提示"接管/保持",
  接管=改写为新链(等价于 IFEO off→on)
- 新旧应用可同时安装;同一游戏的 IFEO 后写者胜,提示中说明

## 7. 打包
- build_exe.bat: GUI onedir + injector/launcher onefile(--windowed,
  --collect-all winsdk)→ dist\DllInjectManager\chain\;wasapi_relink.dll →
  dist\DllInjectManager\payloads\;完整性检查后 [OK]
- release zip 同现流程

## 8. 测试策略
- 既有 94 测试: 触觉专属用例改为适配器层用例(语义不变);注册表/IFEO/路径/链
  测试适配新 schema
- 新增:
  - games.yaml v2 读写/旧版导入转换
  - injector ifeo 多载荷查表(含未知 exe → 空列表不注入)
  - launch 子命令新旧两种 argv 形式解析
  - cfg 原子写: 备份不覆盖、并发修改拒绝、temp 残留清理
  - 12 字段边界(min/max/step/整数约束)
  - PE 架构校验(x64/x86/非 PE)
  - Feeder 检测三态(无 addon / 有 addon 无 cfg / 齐全)
- e2e(用户在环): DS2 挂 wasapi_relink + IFEO on → Steam 启动 → toast+日志;
  Feeder 部署后(用户自行用 DLSS 5 Swapper 装)面板改 work_resolution 游戏内生效

## 9. 风险
| 风险 | 缓解 |
|---|---|
| 反作弊检测注入 | 文档与 UI 明示仅限无反作弊单机;现机制不变 |
| 新旧应用 IFEO 互踩 | 导入向导明示;状态点可识别"IFEO 指向他方" |
| wasapi_relink.dll 源码佚失 | 二进制入 git 资产保护;面板只碰 toml 不动 dll |
| dlss5-feed.cfg 键名随 Feeder 版本漂移 | 面板显示"检测到但未识别"兜底;schema 集中一处便于跟进 |
| 用户显卡非 50 系需 modded nvngx_dlssnr | 不在本工具范围,文档指路 DLSS 5 Swapper |
