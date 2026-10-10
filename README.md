# HapticImproveManager

DualSense haptic 低延迟注入系统的可视化管理器。
包装 `C:\Users\ZhuTT\Workspace\specialk\` 下的 injector.py / haptic_launcher.py。

## 运行
    python -m pip install -r requirements.txt
    python app.py

## 功能
- 游戏中心: 左侧游戏列表, 右侧详情(状态/IFEO 开关/启动/配置编辑), 选中即上下文
- 注入配置通俗化: 模式四选一卡片(Normal/Ringbuf/Compat/Bypass)带白话说明,
  缓冲帧数实时换算毫秒
- 添加游戏向导: exe 选择 → 反作弊检测 → 生成 redirect_config.toml → 开 IFEO
- 诊断: 最近注入结果 + injector_debug.log / wasapi_relink.log 尾随,
  一键在资源管理器打开
- 设置: 浅色/深色/跟随系统主题, Mica 云母背景, 日志目录可改并批量同步到所有游戏

## 架构
薄 GUI(PySide6 + qfluentwidgets)+ 子进程后端。
GUI 普通权限运行; ifeo on/off 由 haptic_launcher 自行 UAC 提权。
游戏注册表: specialk/games.yaml(GUI 与 CLI 共用)。
ui/config_model.py 为表单↔TOML 纯函数映射(可单测);
GUI 设置(主题/日志目录)存 %APPDATA%/HapticImproveManager/gui_config.json。

## 测试
    python -m pytest tests/ -v

## 打包 exe
    packaging\build_exe.bat

产出 `dist\HapticImproveManager\`, 双击其中 `HapticImproveManager.exe` 即可运行
(onedir 模式, 整目录拷走才可用, 勿只拷 exe)。

注意: 冻结态下「启动游戏 / IFEO 开关」依赖系统装有 Python 且 PATH 可见
(backend 会优先找 pythonw, 再找 python)——injector 链仍在外部 specialk 项目,
exe 只打包 GUI 自身。系统找不到 Python 时仍可浏览配置, 仅启动/IFEO 子进程失败
(日志可见报错)。
