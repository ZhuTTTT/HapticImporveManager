# HapticImproveManager

DualSense haptic 低延迟注入系统的可视化管理器。
包装 `C:\Users\ZhuTT\Workspace\specialk\` 下的 injector.py / haptic_launcher.py。

## 运行
    python -m pip install -r requirements.txt
    python app.py

## 功能
- 游戏列表: IFEO 状态灯 / 一键启停自动注入 / 启动游戏
- 添加游戏向导: exe 选择 → 反作弊检测 → 生成 redirect_config.toml → 开 IFEO
- 配置编辑: wasapi_relink 模式/缓冲可视化编辑(保留注释)
- 状态监控: 最近注入结果 + injector_debug.log / wasapi_relink.log 尾随

## 架构
薄 GUI + 子进程后端。GUI 普通权限运行; ifeo on/off 由 haptic_launcher 自行 UAC 提权。
游戏注册表: specialk/games.yaml(GUI 与 CLI 共用)。

## 测试
    python -m pytest tests/ -v
