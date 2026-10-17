"""多语言(i18n)字典目录模块。

纯 Python 实现,不依赖 Qt,可被 ui 与 backend 双向导入(根级模块,
不破坏 ui → backend 单向依赖)。每键中英并排,对照可见、完整性可单测。

键命名按页面分层:app.* / nav.* / settings.* / games.* / detail.* /
config.* / mode.<Mode>.* / wizard.* / diag.* / validate.* / ac.* /
common.* / unit.*。

铁律:tr() 只在运行时调用,禁止模块级调用——模块级常量在 import 时
求值,会冻结在当时的 _LANG,之后 set_language 对其无效。
"""

_MESSAGES: dict[str, dict[str, str]] = {
    "app.title":   {"zh": "Haptic 低延迟管理器", "en": "Haptic Low-Latency Manager"},
    "unit.frames": {"zh": "{n} 帧", "en": "{n} frames"},

    # 主导航
    "nav.games":       {"zh": "游戏", "en": "Games"},
    "nav.diagnostics": {"zh": "诊断", "en": "Diagnostics"},
    "nav.settings":    {"zh": "设置", "en": "Settings"},

    # 设置页
    "settings.title":       {"zh": "设置", "en": "Settings"},
    "settings.language":    {"zh": "语言", "en": "Language"},
    "settings.lang_system": {"zh": "跟随系统", "en": "Follow system"},
    "settings.lang_restart_title": {
        "zh": "语言已更改",
        "en": "Language changed",
    },
    "settings.lang_restart_msg": {
        "zh": "界面语言将在重启应用后生效。现在重启吗?",
        "en": "The interface language will take effect after restarting the "
              "app. Restart now?",
    },
    "settings.lang_restart_now":   {"zh": "立即重启", "en": "Restart now"},
    "settings.lang_restart_later": {"zh": "稍后", "en": "Later"},
    "settings.theme":       {"zh": "主题", "en": "Theme"},
    "settings.theme_light": {"zh": "浅色", "en": "Light"},
    "settings.theme_dark":  {"zh": "深色", "en": "Dark"},
    "settings.theme_auto":  {"zh": "跟随系统", "en": "Follow system"},
    "settings.mica": {"zh": "云母背景(Win11)", "en": "Mica background (Win11)"},
    "settings.log_dir": {"zh": "日志目录", "en": "Log directory"},
    "settings.log_dir_caption": {
        "zh": "wasapi_relink.log 的存放位置。更改后可同步到所有已注册游戏的配置。",
        "en": "Where wasapi_relink.log is written. After changing it, you can "
              "sync the new location to all registered games' configs.",
    },
    "settings.log_dir_change": {"zh": "更改…", "en": "Change…"},
    "settings.log_dir_open": {
        "zh": "在资源管理器中打开",
        "en": "Open in Explorer",
    },
    "settings.log_dir_pick": {
        "zh": "选择日志目录",
        "en": "Choose log directory",
    },
    "settings.sync_title": {"zh": "同步日志目录", "en": "Sync log directory"},
    "settings.sync_msg": {
        "zh": "新目录: {d}\n\n是否同步更新所有已注册游戏({n} 个)的 "
              "redirect_config.toml?\n选「否」则只影响以后新添加的游戏。",
        "en": "New directory: {d}\n\nAlso update redirect_config.toml for all "
              "{n} registered games?\nChoose \"Only future games\" to leave "
              "existing games unchanged.",
    },
    "settings.sync_yes": {"zh": "同步所有游戏", "en": "Sync all games"},
    "settings.sync_no":  {"zh": "仅以后生效", "en": "Only future games"},
    "settings.sync_ok_title": {"zh": "已同步", "en": "Synced"},
    "settings.sync_ok_msg": {
        "zh": "已更新 {ok} 个游戏的配置",
        "en": "Updated configs for {ok} games",
    },
    "settings.sync_partial_title": {
        "zh": "部分同步失败",
        "en": "Partial sync failed",
    },
    "settings.sync_partial_msg": {
        "zh": "已同步 {ok} 个; 失败: {failed}"
              "(配置缺失或损坏, 请到对应游戏详情修复)",
        "en": "Synced {ok}; failed: {failed} "
              "(config missing or corrupt — fix it from the game's detail page)",
    },

    # 旧版注册表残留清理
    "settings.cleanup": {"zh": "旧版注册表残留", "en": "Legacy registry leftovers"},
    "settings.cleanup_caption": {
        "zh": "旧版本/旧安装位置留下的 IFEO 自动注入项。失效残留会让游戏"
              "无法启动, 建议清理; 清理需一次 UAC 提权。",
        "en": "IFEO auto-inject entries left by old versions or old install "
              "locations. Broken leftovers prevent games from launching — "
              "cleaning is recommended and needs one UAC elevation.",
    },
    "settings.cleanup_rescan": {"zh": "重新扫描", "en": "Rescan"},
    "settings.cleanup_run": {"zh": "清理全部", "en": "Clean up all"},
    "settings.cleanup_empty": {
        "zh": "未发现旧版残留 ✓",
        "en": "No legacy leftovers found ✓",
    },
    "settings.cleanup_broken": {
        "zh": "失效: 目标已删除, 该游戏会无法启动",
        "en": "Broken: target deleted — this game will fail to launch",
    },
    "settings.cleanup_legacy": {
        "zh": "旧位置: 仍可用, 指向另一处安装",
        "en": "Old location: still functional, points to another install",
    },
    "settings.cleanup_confirm_title": {
        "zh": "清理注册表残留",
        "en": "Clean up registry leftovers",
    },
    "settings.cleanup_confirm_msg": {
        "zh": "将删除 {n} 条 IFEO 自动注入项(其中 {broken} 条已失效), "
              "对应游戏将不再被自动注入。\n需要一次 UAC 提权, 继续?",
        "en": "This will delete {n} IFEO auto-inject entries ({broken} of "
              "them broken); the affected games will no longer be "
              "auto-injected.\nOne UAC elevation is required. Continue?",
    },
    "settings.cleanup_done_msg": {
        "zh": "清理完成, 注册表残留已删除",
        "en": "Done — registry leftovers removed",
    },
    "settings.cleanup_failed_msg": {
        "zh": "部分项未删除(提权被取消或操作失败), 请重试",
        "en": "Some entries were not removed (elevation cancelled or the "
              "operation failed) — please retry",
    },

    # 通用开关
    "common.on":  {"zh": "开", "en": "On"},
    "common.off": {"zh": "关", "en": "Off"},

    # 游戏页
    "games.search_placeholder": {"zh": "搜索游戏…", "en": "Search games…"},
    "games.add":         {"zh": "添加游戏", "en": "Add game"},
    "games.empty_title": {"zh": "还没有游戏", "en": "No games yet"},
    "games.empty_caption": {
        "zh": "点击左下角「添加游戏」, 四步完成接入",
        "en": "Click \"Add game\" at the bottom left — "
              "a four-step wizard finishes the setup",
    },

    # 详情页
    "detail.launch": {"zh": "启动游戏", "en": "Launch"},
    "detail.remove": {"zh": "移除", "en": "Remove"},
    "detail.status": {"zh": "状态", "en": "Status"},
    "detail.ifeo_label": {"zh": "IFEO 自动注入", "en": "IFEO auto-inject"},
    "detail.anticheat_warn": {
        "zh": "⚠ 检测到反作弊特征, 注入有账号封禁风险",
        "en": "⚠ Anti-cheat signatures detected — "
              "injection risks an account ban",
    },
    "detail.ifeo_caption": {
        "zh": "开启后从 Steam/启动器正常启动游戏即自动注入(需 UAC 提权)。",
        "en": "Once enabled, launching the game normally from Steam/its "
              "launcher auto-injects (requires UAC elevation).",
    },
    "detail.badge_exe_missing": {"zh": "exe 丢失", "en": "exe missing"},
    "detail.badge_exe_missing_tip": {
        "zh": "找不到游戏可执行文件, 请检查路径",
        "en": "Game executable not found — please check the path",
    },
    "detail.badge_ready": {"zh": "就绪", "en": "Ready"},
    "detail.badge_ready_tip": {
        "zh": "配置与 IFEO 均已就位",
        "en": "Config and IFEO are both in place",
    },
    "detail.badge_incomplete": {"zh": "未完成", "en": "Incomplete"},
    "detail.badge_incomplete_tip": {
        "zh": "配置或 IFEO 未就位",
        "en": "Config or IFEO is not in place yet",
    },
    # 徽章后缀: zh 无缝拼接, en 需前导空格
    "detail.badge_ifeo_occupied": {
        "zh": "(IFEO 被其他调试器占用!)",
        "en": " (IFEO is taken by another debugger!)",
    },
    "detail.unsaved_title": {"zh": "未保存修改", "en": "Unsaved changes"},
    "detail.unsaved_msg": {
        "zh": "当前配置有未保存修改, 放弃并切换?",
        "en": "The current config has unsaved changes. Discard and switch?",
    },
    "detail.remove_title": {"zh": "移除游戏", "en": "Remove game"},
    "detail.remove_confirm": {
        "zh": "从列表移除 {name}?\n(不动游戏文件; 若自动注入已开启会先关闭, "
              "需一次 UAC 提权)",
        "en": "Remove {name} from the list?\n(Game files are left untouched; "
              "if auto-inject is on it will be turned off first, which "
              "requires one UAC elevation.)",
    },
    "detail.remove_ifeo_failed": {
        "zh": "未能关闭自动注入(提权被取消或操作失败), 游戏未移除, 请重试",
        "en": "Could not turn off auto-inject (elevation cancelled or the "
              "operation failed). The game was NOT removed — please retry.",
    },
    "detail.ifeo_failed_msg": {
        "zh": "提权被取消或操作失败, 状态未变更",
        "en": "Elevation was cancelled or the operation failed; "
              "state unchanged",
    },

    # 模式卡(键名段 = backend.config.MODES 的注册值)
    "mode.Normal.title": {"zh": "普通模式", "en": "Normal"},
    "mode.Normal.brief": {
        "zh": "延迟最低, 绝大多数游戏直接用(剑星、绝区零已验证)",
        "en": "Lowest latency — works for most games as-is "
              "(verified on Stellar Blade and Zenless Zone Zero)",
    },
    "mode.Normal.detail": {
        "zh": "游戏直接面对真实的小缓冲区。破音就把下面的缓冲调大。"
              "默认先试这个。",
        "en": "The game faces the real small buffer directly. If audio "
              "crackles, raise the buffer below. Try this one first.",
    },
    "mode.Ringbuf.title": {"zh": "虚拟缓冲", "en": "Virtual buffer"},
    "mode.Ringbuf.brief": {
        "zh": "给“爆发式写音频”的游戏兜底(《死亡搁浅2》必须用)",
        "en": "Safety net for games that write audio in bursts "
              "(required for Death Stranding 2)",
    },
    "mode.Ringbuf.detail": {
        "zh": "游戏以为自己面前有一条很长的缓冲通道, 可以一口气猛写一大批音频;"
              "注入层在幕后接住, 再按推送节奏匀速喂给手柄。\n"
              "什么时候用它: 普通模式下声音破音、卡顿, 或游戏写入节奏本身不均匀。\n"
              "代价: 多一层缓冲, 延迟略高于普通模式。\n"
              "已知问题: UE5 游戏爆发写入太大会撑爆虚拟缓冲、日志刷屏;"
              "绝区零会丢失手柄扬声器声道——这两款不要用。\n"
              "怎么调: 虚拟缓冲帧数 ÷ 48 = 毫秒, 默认 4320 帧 ≈ 90ms。",
        "en": "The game believes a very long buffer channel lies ahead and "
              "can dump a large batch of audio in one go; the injection "
              "layer catches it behind the scenes, then feeds the "
              "controller steadily at the send pacing.\n"
              "When to use: crackling or stuttering in Normal mode, or "
              "the game writes audio at an uneven pace.\n"
              "Cost: one extra buffer layer — slightly higher latency "
              "than Normal mode.\n"
              "Known issues: UE5 games can burst-write enough to overflow "
              "the virtual buffer and flood the log; Zenless Zone Zero "
              "loses the controller speaker channel — do not use it for "
              "these two.\n"
              "Tuning: virtual buffer frames ÷ 48 = milliseconds; "
              "the default 4320 frames ≈ 90 ms.",
    },
    "mode.Compat.title": {"zh": "兼容模式", "en": "Compat"},
    "mode.Compat.brief": {
        "zh": "缓冲协商不撒谎, 最温和; 普通/虚拟缓冲都出问题再用",
        "en": "No lying in buffer negotiation — the gentlest; use when "
              "both Normal and Virtual buffer misbehave",
    },
    "mode.Compat.detail": {
        "zh": "普通模式会把缓冲长度“谎报”成小值, 逼游戏小批量写音频——"
              "有些游戏对此敏感(初始化失败、无声、崩溃)。\n"
              "兼容模式在协商层面完全不撒谎, 游戏看到的缓冲参数全是真实值;"
              "但写入的音频仍会经过注入层的暂存缓冲, "
              "按推送节奏转发给手柄——写入依然被约束, 只是约束得更隐蔽温和。\n"
              "什么时候用它: 普通模式和虚拟缓冲都出问题时。\n"
              "代价: 延迟改善不如前两者直接。它保的是“能用”, "
              "不是“最低延迟”。",
        "en": "Normal mode \"lies\" about the buffer length, reporting a "
              "small value to force the game into small audio writes — "
              "some games are sensitive to that (init failure, silence, "
              "crashes).\n"
              "Compat mode never lies at the negotiation layer: the game "
              "sees real buffer parameters, yet written audio still "
              "passes through the injection layer's staging buffer and "
              "is forwarded to the controller at the send pacing — "
              "writes remain constrained, just more discreetly and "
              "gently.\n"
              "When to use: when both Normal mode and Virtual buffer "
              "cause problems.\n"
              "Cost: latency improvement is less direct than the other "
              "two. It guarantees \"it works\", not \"lowest latency\".",
    },
    "mode.Bypass.title": {"zh": "不干预", "en": "Bypass"},
    "mode.Bypass.brief": {
        "zh": "跳过音频处理, 保持原生延迟",
        "en": "Skip audio processing, keep native latency",
    },
    "mode.Bypass.detail": {
        "zh": "不修改任何音频行为, 用来对比排障。",
        "en": "Leaves all audio behavior untouched; used for comparison "
              "and troubleshooting.",
    },

    # 配置卡
    "config.title": {"zh": "注入配置", "en": "Injection config"},
    "config.caption": {
        "zh": "修改后点「保存」生效; 游戏运行中保存需重启游戏。",
        "en": "Changes apply after clicking \"Save\"; saving while the "
              "game is running takes effect on the next launch.",
    },
    "config.period": {"zh": "推送节奏", "en": "Send pacing"},
    "config.period_hint": {
        "zh": "手柄多久收到一次音频。越小越跟手, 太小会破音; "
              "最左 = 不干预(原生)。",
        "en": "How often the controller receives audio. Lower is more "
              "responsive; too low crackles. Far left = native "
              "(no intervention).",
    },
    "config.buffer": {"zh": "缓冲大小", "en": "Buffer size"},
    "config.buffer_hint": {
        "zh": "普通模式用: 游戏能囤多少音频。小了破音, 大了拖延迟。",
        "en": "For Normal mode: how much audio the game may stockpile. "
              "Too small crackles; too large adds latency.",
    },
    "config.ring_buffer": {"zh": "虚拟缓冲", "en": "Virtual buffer"},
    "config.ring_buffer_hint": {
        "zh": "虚拟缓冲模式用: 幕后接住游戏爆发写入的通道长度。",
        "en": "For Virtual buffer mode: length of the channel that "
              "catches the game's burst writes behind the scenes.",
    },
    "config.raw": {"zh": "原始模式(raw)", "en": "Raw mode"},
    "config.raw_hint": {
        "zh": "保持默认(开)即可, 出问题再动。",
        "en": "Keep the default (On); only change it if something "
              "goes wrong.",
    },
    "config.force_period": {"zh": "强制周期", "en": "Force period"},
    "config.force_period_hint": {
        "zh": "强制按推送节奏发送。保持默认(开)即可。",
        "en": "Force sending at the send pacing. Keep the default (On).",
    },
    "config.log_level": {"zh": "日志级别", "en": "Log level"},
    "config.period_native": {"zh": "原生", "en": "Native"},
    "config.save": {"zh": "保存", "en": "Save"},
    "config.reset": {"zh": "恢复默认", "en": "Reset defaults"},
    "config.saving_title": {"zh": "保存中", "en": "Saving"},
    "config.saving_msg": {"zh": "正在写入配置…", "en": "Writing config…"},
    "config.saved_title": {"zh": "保存完成", "en": "Saved"},
    "config.invalid_title": {"zh": "校验失败", "en": "Validation failed"},
    "config.missing_title": {"zh": "无配置", "en": "No config"},
    "config.missing_msg": {
        "zh": "{name} 还没有 redirect_config.toml,\n生成默认配置?",
        "en": "{name} has no redirect_config.toml yet.\n"
              "Generate a default config?",
    },
    "config.log_info_warn": {
        "zh": "Info 在 overflow 时可写 GB 级日志(实测一次会话 2.9GB)。\n"
              "仅排障临时使用, 确定切换?",
        "en": "Info can write GB-scale logs on overflow (2.9 GB measured "
              "in a single session).\nUse it only temporarily for "
              "troubleshooting. Switch anyway?",
    },
    "config.reset_msg": {
        "zh": "用默认配置覆盖当前表单?(未保存前不影响文件)",
        "en": "Overwrite the current form with defaults? "
              "(The file is untouched until you save.)",
    },
    "config.saved_msg": {"zh": "配置已保存", "en": "Config saved"},
    # 保存成功但游戏正在运行时追加的后缀
    "config.saved_running_suffix": {
        "zh": "; 游戏正在运行, 重启后生效",
        "en": "; the game is running — takes effect after restarting it",
    },
    "config.parse_failed": {
        "zh": "配置解析失败: {err}",
        "en": "Failed to parse config: {err}",
    },

    # 添加游戏向导
    "wizard.steps": {
        "zh": "1 选择游戏 → 2 反作弊 → 3 配置 → 4 IFEO",
        "en": "1 Game → 2 Anti-cheat → 3 Config → 4 IFEO",
    },
    "wizard.title":  {"zh": "添加游戏", "en": "Add game"},
    "wizard.back":   {"zh": "上一步", "en": "Back"},
    "wizard.next":   {"zh": "下一步", "en": "Next"},
    "wizard.finish": {"zh": "完成", "en": "Finish"},
    "wizard.cancel": {"zh": "取消", "en": "Cancel"},
    "wizard.name_placeholder": {
        "zh": "注册名, 小写字母/数字/下划线, 如 ds2",
        "en": "Internal name: lowercase letters/digits/underscore, "
              "e.g. ds2",
    },
    "wizard.browse": {"zh": "浏览…", "en": "Browse…"},
    "wizard.name_label": {"zh": "注册名", "en": "Name"},
    "wizard.exe_label":  {"zh": "游戏 exe", "en": "Game exe"},
    "wizard.ac_ack": {
        "zh": "我已了解: 反作弊游戏注入有封禁风险, 后果自负",
        "en": "I understand: injecting into a game with anti-cheat "
              "risks an account ban; I accept the consequences",
    },
    "wizard.ac_known": {
        "zh": "检测到反作弊特征:\n· {hits}\n\n"
              "已知风险: HoYoKProtect 会剥离 OpenProcess 句柄并改名"
              "外来 DLL。本工具采用父进程注入可绕过句柄剥离, "
              "但仍有账号风险。",
        "en": "Anti-cheat signatures detected:\n· {hits}\n\n"
              "Known risk: HoYoKProtect strips OpenProcess handles and "
              "renames foreign DLLs. This tool injects via the parent "
              "process, which bypasses handle stripping, but account "
              "risk remains.",
    },
    "wizard.ac_none": {
        "zh": "未检测到已知反作弊特征。",
        "en": "No known anti-cheat signatures detected.",
    },
    "wizard.mode":   {"zh": "模式", "en": "Mode"},
    "wizard.buffer": {"zh": "缓冲帧数", "en": "Buffer frames"},
    "wizard.config_note": {
        "zh": "普通模式: 大多数游戏可用, 缓冲过小会破音\n"
              "虚拟缓冲: 《死亡搁浅2》需要; UE5 会溢出刷屏; 绝区零丢扬声器声道\n"
              "每个游戏必须单独试, 没有通用最优解",
        "en": "Normal: works for most games; too small a buffer crackles\n"
              "Virtual buffer: required for Death Stranding 2; overflows "
              "and floods logs on UE5; loses the controller speaker channel "
              "on Zenless Zone Zero\n"
              "Every game must be tested individually — there is no "
              "universal optimum",
    },
    "wizard.ifeo_hint": {
        "zh": "点击按钮启用(会弹 UAC 提权框)",
        "en": "Click the button to enable (a UAC elevation prompt "
              "will pop up)",
    },
    "wizard.ifeo_enable": {"zh": "启用 IFEO", "en": "Enable IFEO"},
    "wizard.ifeo_caption": {
        "zh": "完成后从 Steam/启动器正常启动游戏即自动注入。"
              "也可以稍后在游戏详情页开启。",
        "en": "Once done, launching the game normally from Steam/its "
              "launcher auto-injects. You can also enable it later on "
              "the game's detail page.",
    },
    "wizard.ifeo_pending": {
        "zh": "等待提权与注册表写入…",
        "en": "Waiting for elevation and the registry write…",
    },
    "wizard.ifeo_ok": {"zh": "✓ IFEO 已启用", "en": "✓ IFEO enabled"},
    "wizard.ifeo_fail": {
        "zh": "✗ 提权被取消或失败, 可稍后在游戏详情页重试",
        "en": "✗ Elevation was cancelled or failed — retry later on "
              "the game's detail page",
    },
    "wizard.pick_exe": {"zh": "选择游戏 exe", "en": "Choose game exe"},
    "wizard.name_invalid": {
        "zh": "仅限小写字母/数字/下划线",
        "en": "Lowercase letters, digits and underscores only",
    },
    "wizard.exe_missing": {
        "zh": "请选择游戏可执行文件",
        "en": "Please choose the game executable",
    },
    "wizard.name_taken": {
        "zh": "'{name}' 已被占用",
        "en": "'{name}' is already taken",
    },
    "wizard.config_exists_title": {
        "zh": "配置已存在", "en": "Config exists",
    },
    "wizard.config_exists_msg": {
        "zh": "redirect_config.toml 已存在, 覆盖?\n(选「否」保留现有配置)",
        "en": "redirect_config.toml already exists. Overwrite?\n"
              "(Choose \"No\" to keep the existing config)",
    },

    # 诊断页
    "diag.recent": {"zh": "最近注入", "en": "Recent injection"},
    "diag.fixed_log_note": {
        "zh": "此日志由注入器写入, 位置固定于 chain 目录",
        "en": "This log is written by the injector; its location is "
              "fixed in the chain directory",
    },
    "diag.no_records": {
        "zh": "暂无注入记录",
        "en": "No injection records yet",
    },

    # backend 校验消息(经 UI 显示)
    "validate.mode": {
        "zh": "playback.mode 必须是 {modes}, 当前: {mode!r}",
        "en": "playback.mode must be one of {modes}; current: {mode!r}",
    },
    "validate.period": {
        "zh": "target_period_hus 必须在 0–1000, 当前: {period!r}",
        "en": "target_period_hus must be within 0–1000; "
              "current: {period!r}",
    },
    # 占位符用 field 而非 key: tr() 首参名就是 key, 传 key= 会撞名 TypeError
    "validate.buffer": {
        "zh": "{field}.{rate} 必须是正整数帧数, 当前: {frames!r}",
        "en": "{field}.{rate} must be a positive integer frame count; "
              "current: {frames!r}",
    },
    # 硬约束: zh/en 都必须含字面量 log_level — config_card._SaveWorker
    # 按子串过滤该条目, 放行用户已在警告框知情确认的 Info
    "validate.log_level": {
        "zh": "log_level 必须为 Error — Info 在 overflow 时可写 GB 级日志"
              "(仅排障时临时使用)",
        "en": "log_level must be Error — Info can write GB-scale logs on "
              "overflow (use only temporarily for troubleshooting)",
    },

    # 反作弊显示名(backend 扫描命中, 经 UI 显示)
    "ac.eac": {"zh": "EasyAntiCheat (EAC)", "en": "EasyAntiCheat (EAC)"},
    "ac.battleye_service": {
        "zh": "BattlEye (BEService)", "en": "BattlEye (BEService)",
    },
    "ac.battleye": {"zh": "BattlEye", "en": "BattlEye"},
    "ac.hoyokprotect": {
        "zh": "HoYoKProtect (米哈游)", "en": "HoYoKProtect (miHoYo)",
    },
    "ac.mhyprot": {
        "zh": "HoYoKProtect (米哈游 mhyprot)",
        "en": "HoYoKProtect (miHoYo mhyprot)",
    },
    "ac.xigncode": {"zh": "XIGNCODE", "en": "XIGNCODE"},
    "ac.ace": {"zh": "腾讯 ACE", "en": "Tencent ACE"},
    "ac.ace_sentry": {
        "zh": "腾讯 ACE (Sentry)", "en": "Tencent ACE (Sentry)",
    },
    "ac.nprotect": {
        "zh": "nProtect GameGuard", "en": "nProtect GameGuard",
    },
}

_LANG = "zh"  # 模块级默认值;仅启动时由 set_language 覆盖一次

_VALID_LANGUAGES = ("zh", "en")


def tr(key: str, **params) -> str:
    """返回当前语言文案。

    回退链:当前语言缺失 → zh → 返回 key 本身(查找过程不抛异常)。
    params 非空时对结果做 .format(**params) 插值;占位符与参数不匹配
    属调用方错误,由 format 抛出的异常暴露(目录完整性由测试保证)。
    """
    entry = _MESSAGES.get(key) or {}
    text = entry.get(_LANG) or entry.get("zh") or key
    return text.format(**params) if params else text


def set_language(lang: str) -> None:
    """设置当前语言。只接受 "zh" / "en",其他值 raise ValueError。"""
    if lang not in _VALID_LANGUAGES:
        raise ValueError(f"不支持的语言: {lang!r}(只接受 zh / en)")
    global _LANG
    _LANG = lang


def current_language() -> str:
    """返回当前语言代码("zh" / "en")。"""
    return _LANG


def resolve_language(setting: str, system_locale: str) -> str:
    """把配置项解析为实际语言代码。

    setting ∈ "System" / "zh" / "en":
    - 显式 "zh" / "en" 原样返回
    - "System" 或未知值(手改配置):system_locale 以 "zh" 开头 → "zh",
      否则 → "en"

    system_locale 由调用方(QLocale.system().name())注入,
    保持本模块无 Qt 可单测。
    """
    if setting in _VALID_LANGUAGES:
        return setting
    return "zh" if system_locale.startswith("zh") else "en"
