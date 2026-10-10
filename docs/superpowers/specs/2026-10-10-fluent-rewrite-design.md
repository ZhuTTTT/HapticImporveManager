# HapticImproveManager Fluent 重写设计

日期: 2026-10-10
状态: 已获用户批准

## 背景与目标

现有 GUI 用裸 PySide6 手写,界面简陋、深色模式适配差。整体重写 UI 层,
技术栈仍为 Python,后端 `backend/` 与测试 `tests/` 保持不动。

目标:
1. 现代 Fluent Design 界面,浅色/深色/跟随系统主题,深色适配不再出问题
2. 信息架构改为「游戏中心式」:选中游戏即上下文,配置/状态/日志都属于当前游戏,
   消灭现有三页之间的割裂跳转(配置页靠下拉框选游戏)
3. 配置项通俗化:每个字段有中文名 + 白话解释,用户不看源码也能懂
4. 日志目录用户可配置,一键在资源管理器打开

非目标(YAGNI):
- 不改 backend 业务逻辑(IFEO/注册表/启动器/反作弊扫描)
- 不做打包分发(exe 打包)、自动更新
- 不引入 qfluentwidgets Pro 付费组件
- 游戏详情页不做内嵌日志区(日志统一在诊断页)

## 技术栈

- PySide6(沿用现有依赖)
- PySide6-Fluent-Widgets(qfluentwidgets 免费版):FluentWindow、NavigationInterface、
  CardWidget、InfoBar、SwitchButton、Dialog、Pivot、QConfig 等
- 主题: `qfluentwidgets.setTheme()`,浅色/深色/跟随系统三选,
  QConfig 持久化,重启记住

## 项目结构变更

```
app.py                  # 入口更新为新主窗口
requirements.txt        # 增加 PySide6-Fluent-Widgets
backend/                # 仅做加法(见「backend 变更」),现有行为不变
tests/                  # 现有测试不动;新增 ui 层测试
ui/                     # 整体重写(旧文件删除,git 历史保留)
  __init__.py
  main_window.py        # FluentWindow + 导航 + 主题
  games_page.py         # 游戏中心主页(列表 + 详情)
  game_detail.py        # 详情滚动页:头部/状态卡/配置卡
  config_card.py        # 配置卡(表单 + 白话解释 + 脏状态)
  config_model.py       # 表单 ↔ TOML doc 映射纯函数(可单测)
  add_game_dialog.py    # 4 步添加向导对话框
  diagnostics_page.py   # 诊断页
  settings_page.py      # 设置页
  app_config.py         # GUI 设置持久化(QConfig 包装)
```

## 整体框架

- `FluentWindow`:左侧导航 = 游戏 / 诊断,底部 = 设置
- Windows 11 下启用 Mica 云母背景(`setMicaEffectEnabled`)
- 标题栏右侧放主题切换按钮(循环:浅色→深色→跟随系统)
- 主题设置持久化于 `app_config.py`(QConfig,json 文件存用户配置目录)

## 游戏中心主页

左侧:游戏列表(自定义列表项,名称 + 状态点),顶部搜索框过滤,
「+ 添加游戏」主按钮。无游戏时显示空状态(说明文字 + 添加按钮)。

右侧:选中游戏的详情滚动页(`game_detail.py`):

### 头部
游戏名(大字)、exe 路径(省略显示 + tooltip)、
主按钮「启动游戏」、次级按钮「移除」(Fluent Dialog 确认,不动游戏文件和 IFEO)。

### 状态卡
- 状态徽章:绿=就绪 / 黄=配置或 IFEO 未完成 / 红=exe 丢失;
  IFEO 被其他调试器占用时红色警告文字
- IFEO 自动注入 SwitchButton:复用现有 `launcher.set_ifeo` + 1s 轮询逻辑
  (最多 10 次,失败提示"提权被取消或操作失败")
- 反作弊游戏显示警告标记

### 配置卡(config_card.py + config_model.py)
每项配置 = 中文名 + 一行白话解释(灰字)。表单脏状态跟踪:
有未保存修改时保存按钮高亮,切换游戏时提示"有未保存修改"。

**注入模式** — 四张可点选卡片(单选),决策路径:先试普通 → 破音调大缓冲 → 还不行再 Ringbuf。

- 普通模式 Normal:
  「延迟最低,绝大多数游戏直接用(剑星、绝区零已验证)。破音就把下面的缓冲调大。」
- 虚拟缓冲 Ringbuf(详细说明,本设计重点):
  > 给"爆发式写音频"的游戏兜底。游戏以为自己面前有一条很长的缓冲通道,
  > 可以一口气猛写一大批音频;注入层在幕后接住,再按推送节奏匀速喂给手柄。
  > 什么时候用它:普通模式下声音破音、卡顿,或游戏音频写入节奏本身不均匀
  > (已知《黑魂2》必须用)。
  > 代价:多一层缓冲,延迟略高于普通模式。
  > 已知问题:UE5 游戏爆发写入量太大时会撑爆虚拟缓冲、日志刷屏;
  > 绝区零会丢失手柄扬声器声道——这两款游戏不要用。
  > 怎么调:下面的"虚拟缓冲帧数"÷ 48 = 毫秒,默认 4320 帧 ≈ 90ms。
- 兼容模式 Compat:「不伪造缓冲大小, 最温和。普通/虚拟缓冲都出现无声、崩溃时再试;
  缓冲不被压缩, 延迟接近原生——保“能用”而不是保“低延迟”。」
- 不干预 Bypass:「跳过音频处理,保持原生延迟,用来对比排障。」

**其余字段**(当前模式不适用时禁用,保留现有 enable 逻辑):
- 推送节奏(target_period_hus):滑块 0–1000,
  「手柄多久收到一次音频。越小越跟手,太小会破音;调到最左 = 不干预(原生)」,
  标签实时显示 `X.X ms`
- 缓冲大小(target_buffer_len,Normal 用):数字框,
  「游戏能囤多少音频。小了破音,大了拖延迟」,旁边实时显示换算毫秒(帧数 ÷ 48)
- 虚拟缓冲(ring_buffer_len,Ringbuf 用):同上
- raw:「原始模式。保持默认(开)即可,出问题再动」
- 强制周期(force_period):「强制按推送节奏发送。保持默认(开)即可」
- 日志级别:Error / Info;选 Info 时保留现有警告
  (overflow 时可写 GB 级日志,实测一次会话 2.9GB,仅排障临时使用)

**保存 / 恢复默认**:
- 保存前走 `config.validate`,失败用 InfoBar 逐条列出问题
- 游戏运行中保存,追加提示"游戏正在运行,重启后生效"(复用 `launcher.is_game_running`)
- 恢复默认需确认,只覆盖表单未保存

**配置缺失/损坏**:
- 无 redirect_config.toml:InfoBar 提示并可一键生成默认配置
- TOML 解析失败:表单禁用,显示原文 + 错误(保留现有行为)

### 添加游戏向导(add_game_dialog.py)
对话框内嵌 4 步(QStackedWidget + 顶部步骤条),逻辑从旧 `add_wizard.py` 移植:
1. 选择 exe(注册名小写字母/数字/下划线、查重)
2. 反作弊检测(known 风险需勾选知情同意)
3. 生成 redirect_config.toml(模式 + 缓冲帧数;已存在时询问是否覆盖;
   log_path 用设置里的日志目录)
4. 启用 IFEO(按钮 + UAC 轮询)
完成后注册进 games.yaml。

## 诊断页

- 顶部「最近注入」大卡:成功绿 / 失败红,含时间;无记录显示灰色占位
- 日志区:Pivot 选项卡 = injector_debug.log / wasapi_relink.log,
  各显示尾随 200 行、自动滚到底,文件监视复用 `backend/monitor.LogWatcher`
  (监视路径按设置的日志目录动态计算)
- 每个选项卡附「在资源管理器中打开」按钮(`explorer /select,` 定位到文件)
- injector_debug.log 选项卡内标注"此日志由注入器写入,位置固定"

## 设置页

- 主题:浅色 / 深色 / 跟随系统(三选,立即生效并持久化)
- Mica 云母背景开关
- **日志目录**(本设计新增):
  - 显示当前目录,默认 `specialk/logs`
  - 【更改…】系统文件夹选择框;【在资源管理器中打开】
  - 更改时弹确认:「是否同步更新所有已注册游戏的配置?」
    - 是:批量改写每个游戏 `redirect_config.toml` 的 `log_path`
      (走 `config.load_config/save_config`,注释保留),
      完成后 InfoBar「已同步 N 个游戏」
    - 否:只影响以后新添加的游戏
  - 持久化于 GUI 设置;添加游戏向导生成配置时读取该值
- 打开日志目录、关于(版本/项目说明)

## backend 变更(仅加法,不改现有函数行为)

- `config.default_config(log_dir: str | None = None)`:
  可选参数,缺省保持现状(`paths.RELINK_LOG_DIR`);传入时写 `log_path = <log_dir>`
- 新增 `config.set_log_dir(game_dir, log_dir)`(或等价小函数):
  原位改 `log_path` 值并保存(保留注释)
- `paths.py`、`ifeo.py`、`launcher.py`、`registry.py`、`anticheat.py`、`monitor.py` 不动
- GUI 设置持久化放 ui 层(`ui/app_config.py`),不进 backend

## 错误处理与反馈

- 通知类(保存成功/校验失败/IFEO 失败等)一律 InfoBar(顶部滑入,自动消失)
- 破坏性确认(移除游戏、覆盖配置、恢复默认、批量改日志目录)用 Fluent Dialog
- 不再使用裸 QMessageBox
- 子进程输出仍走 `launcher.ProcessRunner` 信号,接到诊断页 debug 日志视图

## 测试

- 现有 `tests/`(backend 单测)不动,必须保持全绿
- `ui/config_model.py`:表单 ↔ TOML 映射纯函数,新增 pytest 单测
  (含点分键 `target_buffer_len.48000` 字符串键、注释保留往返)
- 新增 offscreen smoke test:主窗口能实例化(QT_QPA_PLATFORM=offscreen)
- `config.default_config(log_dir=...)` 与批量改 log_path 的单测

## 风险与注意

- qfluentwidgets 免费版 API 以 `PySide6-Fluent-Widgets` 包为准;
  若某组件(如 RadioCard)免费版没有,用普通卡 + 单选自绘,不引入 Pro
- tomlkit 点分键陷阱:子表键必须是字符串 `"48000"`,int 键 TypeError
  (现有代码注释已踩过,迁移时保留该处理)
- `save_config` 必须 `newline=""` 保留 LF
- IFEO 轮询的 QTimer 泄漏已修过一次(旧代码),移植时保留"先停旧定时器"逻辑
- 深色模式下所有自定义颜色(状态点/徽章)不得硬编码 QSS 十六进制,
  用 qfluentwidgets 主题色或 FluentIcon,保证双主题可读
