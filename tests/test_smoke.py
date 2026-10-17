import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture(autouse=True)
def _pin_zh(monkeypatch):
    """pin 住语言解析: MainWindow 构造时重新 resolve_language, 光 set_language
    会被覆盖; 钉死解析函数后, 标题断言不随系统语言/用户 gui_config 漂移。"""
    import i18n
    monkeypatch.setattr(i18n, "resolve_language", lambda *a: "zh")
    old = i18n.current_language()
    i18n.set_language("zh")
    yield
    i18n.set_language(old)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _isolate_backend_paths(tmp_path, monkeypatch):
    """把注册表/注入器日志指向 tmp_path, 避免读真实文件。

    不隔离时: 首个游戏缺 redirect_config.toml 会在 offscreen 下弹模态框,
    pytest 无超时挂死; games.yaml 缺失还会读写真实 chain/ 目录的注册表;
    冷启同步会扫真实 IFEO 注册表(开发机有 5 条)并建骨架条目 — 骨架
    无配置同样触发模态框, 一并隔离。
    """
    from backend import ifeo, paths
    games_yaml = tmp_path / "games.yaml"
    games_yaml.write_text("games: {}\n", encoding="utf-8")
    monkeypatch.setattr(paths, "GAMES_YAML", str(games_yaml))
    monkeypatch.setattr(paths, "INJECTOR_RESULT",
                        str(tmp_path / "injector_result.txt"))
    monkeypatch.setattr(paths, "INJECTOR_DEBUG_LOG",
                        str(tmp_path / "injector_debug.log"))
    monkeypatch.setattr(ifeo, "scan_ours_exe_names", lambda: [])


def test_main_window_instantiates(qapp, tmp_path, monkeypatch):
    _isolate_backend_paths(tmp_path, monkeypatch)
    from ui.app_config import load_app_config
    from ui.main_window import MainWindow
    cfg = load_app_config(str(tmp_path / "gui.json"))
    win = MainWindow(cfg)
    assert win.windowTitle() == "Haptic 低延迟管理器"
    assert win.settings_page.theme_box.count() == 3
    win.close()
    win.deleteLater()


def test_games_page_instantiates(qapp, tmp_path, monkeypatch):
    from backend import ifeo, paths
    # 造一个临时 games.yaml, 避免读真实注册表
    games_yaml = tmp_path / "games.yaml"
    games_yaml.write_text("games: {}\n", encoding="utf-8")
    monkeypatch.setattr(paths, "GAMES_YAML", str(games_yaml))
    # 冷启同步会扫真实 IFEO 注册表(开发机有 5 条) — 测试隔离为空
    monkeypatch.setattr(ifeo, "scan_ours_exe_names", lambda: [])

    from ui.games_page import GamesPage
    page = GamesPage()
    assert page.game_list.count() == 0
    assert page.stack.currentIndex() == 0  # 空状态
    page.deleteLater()


def test_add_game_dialog_instantiates(qapp):
    from ui.add_game_dialog import AddGameDialog
    # MessageBoxBase(MaskDialogBase) 要求 parent 非空: __init__ 用 parent 定几何
    host = QWidget()
    dlg = AddGameDialog(host)
    assert dlg.stack.count() == 4
    dlg.deleteLater()
    host.deleteLater()


def test_config_card_dirty_flow(qapp, tmp_path):
    from backend.config import default_config, save_config, load_config
    from backend.registry import GameEntry
    from ui.config_card import ConfigCard

    d = tmp_path / "g"
    d.mkdir()
    exe = d / "g.exe"
    exe.write_text("", encoding="utf-8")
    save_config(str(d), default_config())
    entry = GameEntry(name="g", exe=str(exe))

    card = ConfigCard()
    card.set_game(entry)
    assert not card.is_dirty()
    assert not card.btn_save.isEnabled()

    card.buf_normal.setValue(512)  # 模拟用户修改
    assert card.is_dirty()
    assert card.btn_save.isEnabled()

    from PySide6.QtTest import QSignalSpy
    spy = QSignalSpy(card.saved)  # 保存已异步化, 等待完成信号
    card.btn_save.click()
    assert spy.wait(5000)
    assert not card.is_dirty()
    assert load_config(str(d))["playback"]["target_buffer_len"]["48000"] == 512
    card.deleteLater()


def test_diagnostics_page(qapp, tmp_path, monkeypatch):
    from backend import paths, monitor
    result = tmp_path / "injector_result.txt"
    result.write_text("injected OK: test", encoding="utf-8")
    dbg = tmp_path / "injector_debug.log"
    dbg.write_text("line1\nline2\n", encoding="utf-8")
    monkeypatch.setattr(paths, "INJECTOR_RESULT", str(result))
    monkeypatch.setattr(paths, "INJECTOR_DEBUG_LOG", str(dbg))

    from ui.diagnostics_page import DiagnosticsPage
    page = DiagnosticsPage()
    assert "injected OK" in page.result_label.text()
    assert "line2" in page.log_views["injector_debug"].toPlainText()
    page.deleteLater()


def test_diag_tabs_switch_both_ways(qapp, tmp_path, monkeypatch):
    """日志选项卡双向切换: Pivot.itemClicked 是 Signal(bool), 曾让
    addItem 的 lambda 默认参数被信号 bool 顶掉(恒切同一页) —
    表现为只有第一次点击能切, 回不来。"""
    from backend import paths
    result = tmp_path / "injector_result.txt"
    result.write_text("x", encoding="utf-8")
    dbg = tmp_path / "injector_debug.log"
    dbg.write_text("y", encoding="utf-8")
    monkeypatch.setattr(paths, "INJECTOR_RESULT", str(result))
    monkeypatch.setattr(paths, "INJECTOR_DEBUG_LOG", str(dbg))

    from ui.diagnostics_page import DiagnosticsPage
    page = DiagnosticsPage()
    assert page.stack.currentIndex() == 0
    page.tabs.items["wasapi_relink"].click()
    assert page.stack.currentIndex() == 1
    page.tabs.items["injector_debug"].click()  # 修复前: 停在 1 回不来
    assert page.stack.currentIndex() == 0
    page.tabs.items["wasapi_relink"].click()
    assert page.stack.currentIndex() == 1
    page.deleteLater()


# --- Task 9 收尾断言: 新入口接线 ---


def test_create_main_window_factory(qapp, tmp_path, monkeypatch):
    """app.py 消费的工厂接口: create_main_window() 返回可用主窗口。"""
    _isolate_backend_paths(tmp_path, monkeypatch)  # 同 I5: 防读真实 games.yaml
    from ui.main_window import MainWindow, create_main_window
    win = create_main_window()
    assert isinstance(win, MainWindow)
    assert win.windowTitle() == "Haptic 低延迟管理器"
    win.close()
    win.deleteLater()


def test_app_entrypoint_importable():
    """app.py 作为入口可导入且暴露 main() (不在测试中执行事件循环)。"""
    import importlib
    m = importlib.import_module("app")
    assert callable(m.main)


# --- 终审修复回归测试(2026-10-10 final-review I1–I4) ---


class _AcceptBox:
    """自动确认的 MessageBox 替身(qfluentwidgets.MessageBox 签名: title, content, parent)。"""
    def __init__(self, *args, **kwargs):
        self.yesButton = _DummyButton()
        self.cancelButton = _DummyButton()

    def exec(self):
        return True


class _DummyButton:
    def setText(self, _text):
        pass


def _make_game(tmp_path, name):
    """造 exe + redirect_config 齐全的游戏, 避免 ConfigCard 弹「无配置」模态框。"""
    from backend.config import default_config, save_config
    from backend.registry import GameEntry
    d = tmp_path / name
    d.mkdir()
    exe = d / f"{name}.exe"
    exe.write_text("", encoding="utf-8")
    save_config(str(d), default_config())
    return GameEntry(name=name, exe=str(exe))


def test_game_detail_remove_stops_ifeo_poll(qapp, tmp_path, monkeypatch):
    """I1: UAC pending 轮询期间移除游戏 — 定时器停, _poll_ifeo 不再炸。"""
    from backend import launcher, paths, registry
    import ui.game_detail as gd
    monkeypatch.setattr(gd, "MessageBox", _AcceptBox)
    entry = _make_game(tmp_path, "g")
    games_yaml = tmp_path / "games.yaml"
    registry.save_games({"g": entry}, str(games_yaml))
    monkeypatch.setattr(paths, "GAMES_YAML", str(games_yaml))

    page = gd.GameDetailPage(launcher.ProcessRunner())
    assert page.set_game(entry)
    page._ifeo_timer.start()  # 模拟拨 IFEO 开关后 UAC 框 pending, 轮询进行中
    page._remove()
    assert page.entry is None
    assert not page._ifeo_timer.isActive()
    assert registry.load_games(str(games_yaml)) == {}
    page._poll_ifeo()  # entry=None 时守卫直接返回, 不得抛 AttributeError
    page.deleteLater()


def test_remove_with_ifeo_on_waits_for_off(qapp, tmp_path, monkeypatch):
    """移除自动注入开启的游戏: 先关 IFEO, 落定(OFF)后才删注册表项;
    UAC 取消(超时仍 ON)则中止移除、游戏保留。"""
    from backend import ifeo, launcher, paths, registry
    from backend.ifeo import IfeoState
    import ui.game_detail as gd
    monkeypatch.setattr(gd, "MessageBox", _AcceptBox)
    entry = _make_game(tmp_path, "g")
    games_yaml = tmp_path / "games.yaml"
    registry.save_games({"g": entry}, str(games_yaml))
    monkeypatch.setattr(paths, "GAMES_YAML", str(games_yaml))

    calls = []
    monkeypatch.setattr(launcher, "set_ifeo",
                        lambda r, name, on: calls.append((name, on)))
    state = {"cur": IfeoState.ON_OURS}
    monkeypatch.setattr(ifeo, "query_ifeo", lambda _n: state["cur"])

    page = gd.GameDetailPage(launcher.ProcessRunner())
    page.set_game(entry)
    page._remove()
    # IFEO 开着: 不移除, 先发起 off 并进入待移除轮询(顺序反了 launcher
    # 按名字反查 games.yaml 会 unknown game)
    assert calls == [("g", False)]
    assert page.entry is not None and page._pending_remove
    assert set(registry.load_games(str(games_yaml))) == {"g"}

    # 模拟 UAC 取消: 状态一直 ON_OURS, 轮询超时 → 中止移除, 游戏保留
    page._poll_count = 9
    page._poll_ifeo()
    assert not page._pending_remove
    assert page.entry is not None
    assert set(registry.load_games(str(games_yaml))) == {"g"}

    # 重试: 这次 off 落定(OFF) → 真正移除
    page._remove()
    state["cur"] = IfeoState.OFF
    page._poll_ifeo()
    assert registry.load_games(str(games_yaml)) == {}
    assert page.entry is None
    page.deleteLater()


def test_config_card_save_info_log_level(qapp, tmp_path, monkeypatch):
    """I2: 选 Info 经警告对话框确认后, 保存放行 log_level 校验条目。"""
    from backend.config import load_config
    import ui.config_card as cc
    monkeypatch.setattr(cc, "MessageBox", _AcceptBox)  # 挡掉 Info 警告对话框
    entry = _make_game(tmp_path, "g")

    card = cc.ConfigCard()
    card.set_game(entry)
    card.log_box.setCurrentText("Info")  # 触发警告(替身自动确认)
    assert card.is_dirty()
    from PySide6.QtTest import QSignalSpy
    spy = QSignalSpy(card.saved)  # 保存异步, 等完成信号
    card.btn_save.click()
    assert spy.wait(5000)
    assert not card.is_dirty()  # 校验不再因 log_level 拒存
    assert load_config(str(tmp_path / "g"))["log_level"] == "Info"
    card.deleteLater()


def test_games_page_refresh_keeps_selection(qapp, tmp_path, monkeypatch):
    """I3: 保存配置触发 refresh 后仍选中原游戏, 不跳回列表第一款。"""
    from backend import paths, registry
    g1 = _make_game(tmp_path, "g1")
    g2 = _make_game(tmp_path, "g2")
    games_yaml = tmp_path / "games.yaml"
    registry.save_games({"g1": g1, "g2": g2}, str(games_yaml))
    monkeypatch.setattr(paths, "GAMES_YAML", str(games_yaml))

    from ui.games_page import GamesPage
    page = GamesPage()
    page.game_list.setCurrentRow(1)  # 选中第二款
    assert page.detail.entry.name == "g2"
    page.refresh()  # 模拟 saved → config_changed → refresh
    assert page.game_list.currentRow() == 1
    assert page.detail.entry.name == "g2"
    page.deleteLater()


def test_settings_page_change_dir_emit_on_no_sync(qapp, tmp_path, monkeypatch):
    """I4: 选「仅以后生效」(不同步游戏)也要发 log_dir_changed。"""
    from backend import paths
    import ui.settings_page as sp
    games_yaml = tmp_path / "games.yaml"
    games_yaml.write_text("games: {}\n", encoding="utf-8")
    monkeypatch.setattr(paths, "GAMES_YAML", str(games_yaml))
    new_dir = str(tmp_path / "new_logs")
    monkeypatch.setattr(sp.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: new_dir))

    class _DeclineBox(_AcceptBox):
        def exec(self):
            return False  # 用户选「仅以后生效」
    monkeypatch.setattr(sp, "MessageBox", _DeclineBox)

    from ui.app_config import load_app_config
    cfg = load_app_config(str(tmp_path / "gui.json"))
    page = sp.SettingsPage(cfg)
    seen = []
    page.log_dir_changed.connect(seen.append)
    page._change_dir()
    assert cfg.log_dir.value == new_dir
    assert seen == [new_dir]  # 修复前: 此分支不发信号, 诊断页 watcher 停在旧路径
    page.deleteLater()


def test_settings_language_change_restart_flow(qapp, tmp_path, monkeypatch):
    """语言切换: 弹重启确认框 — 确认则写盘并调 restart_app, 取消只写盘。"""
    import ui.settings_page as sp
    from ui.app_config import load_app_config
    cfg = load_app_config(str(tmp_path / "gui.json"))
    page = sp.SettingsPage(cfg)
    calls = []
    monkeypatch.setattr(sp, "restart_app", lambda: calls.append(1))
    monkeypatch.setattr(sp, "MessageBox", _AcceptBox)  # 确认 → 立即重启
    # ConfigItem 是类级共享描述符, "新"cfg 的初值其实是真实用户配置;
    # 下拉只在索引变化时发信号 — 先归位到 0, 保证后续 setCurrentIndex 必触发
    old_lang = cfg.language.value
    monkeypatch.setattr(cfg, "save", lambda: None)  # 不写盘, 防污染真实配置
    page.lang_box.setCurrentIndex(0)
    calls.clear()

    page.lang_box.setCurrentIndex(2)  # English
    assert cfg.language.value == "en"
    assert calls == [1]

    class _DeclineBox(_AcceptBox):
        def exec(self):
            return False  # 稍后自行重启
    monkeypatch.setattr(sp, "MessageBox", _DeclineBox)
    page.lang_box.setCurrentIndex(1)  # 中文
    assert cfg.language.value == "zh"
    assert calls == [1]  # 取消不再触发重启

    cfg.language.value = old_lang  # 恢复共享描述符, 不污染后续测试
    page.deleteLater()


def test_config_card_missing_config_defers_prompt(qapp, tmp_path, monkeypatch):
    """配置缺失时 set_game 不同步弹模态框(推迟到事件循环) — 启动期主窗口
    未 show 时同步模态 exec 会阻塞在不可见父窗口上: 进程活着但没界面,
    用户只能看到"打不开"(v0.4.3 骨架条目触发此陷阱的真实事故)。"""
    import ui.config_card as cc
    from backend.registry import GameEntry

    def _boom(*a, **k):
        raise AssertionError("synchronous MessageBox during set_game")

    monkeypatch.setattr(cc, "MessageBox", _boom)
    d = tmp_path / "g"
    d.mkdir()
    exe = d / "g.exe"
    exe.write_text("", encoding="utf-8")  # 故意不放 redirect_config.toml
    card = cc.ConfigCard()
    card.set_game(GameEntry(name="g", exe=str(exe)))  # 不抛不阻塞
    assert card.doc is None
    assert not card.btn_save.isEnabled()  # 表单禁用, 等延迟弹窗的结果
    card.deleteLater()


def test_config_card_buffer_visibility_follows_mode(qapp, tmp_path):
    """缓冲项与模式联动: 不适用当前模式的整组(标签+输入+说明)直接隐藏。"""
    from ui.config_card import ConfigCard
    entry = _make_game(tmp_path, "g")  # 默认配置 mode=Normal
    card = ConfigCard()
    card.set_game(entry)
    assert not card.buf_normal_label.isHidden()   # Normal → 显示缓冲大小
    assert card.buf_ring_label.isHidden()         #        隐藏虚拟缓冲

    card._on_mode_card("Ringbuf")
    assert card.buf_normal_label.isHidden()
    assert not card.buf_ring_label.isHidden()

    card._on_mode_card("Bypass")                  # 不干预 → 两者都藏
    assert card.buf_normal_label.isHidden()
    assert card.buf_ring_label.isHidden()
    card.deleteLater()


def test_config_card_save_does_not_block_ui(qapp, tmp_path, monkeypatch):
    """保存异步化: tasklist/磁盘慢也不冻结 UI; 保存中出现 StateToolTip。"""
    import time
    from backend import launcher
    monkeypatch.setattr(launcher, "is_game_running",
                        lambda _name: time.sleep(1) or False)  # 模拟慢查询
    from ui.config_card import ConfigCard
    entry = _make_game(tmp_path, "g")
    card = ConfigCard()
    card.set_game(entry)
    card.buf_normal.setValue(513)

    from PySide6.QtTest import QSignalSpy
    spy = QSignalSpy(card.saved)
    t = time.perf_counter()
    card.btn_save.click()
    elapsed = time.perf_counter() - t
    assert elapsed < 0.9          # UI 线程立即返回, 不等 tasklist
    assert card._save_tip is not None  # loading 指示出现
    assert spy.wait(5000)         # 后台完成后发 saved
    assert not card.is_dirty()
    card.deleteLater()


def test_config_save_updates_registry_hints(qapp, tmp_path, monkeypatch):
    """保存配置回写 games.yaml 的 mode_hint/buffer_hint(列表不再显示旧值)。"""
    from backend import paths, registry
    entry = _make_game(tmp_path, "g")
    games_yaml = tmp_path / "games.yaml"
    registry.save_games({"g": entry}, str(games_yaml))
    monkeypatch.setattr(paths, "GAMES_YAML", str(games_yaml))

    from ui.config_card import ConfigCard
    card = ConfigCard()
    card.set_game(entry)
    card.buf_normal.setValue(512)

    from PySide6.QtTest import QSignalSpy
    spy = QSignalSpy(card.saved)
    card.btn_save.click()
    assert spy.wait(5000)
    e = registry.load_games(str(games_yaml))["g"]
    assert e.mode_hint == "Normal"
    assert e.buffer_hint == 512  # 修复前: 仍为注册时的 960
    card.deleteLater()


def test_game_detail_fills_available_width(qapp, tmp_path):
    """详情页填满右侧空间(移除 760 限宽的布局回归)。"""
    from backend import launcher
    from ui.game_detail import GameDetailPage
    entry = _make_game(tmp_path, "g")
    page = GameDetailPage(launcher.ProcessRunner())
    page.resize(1200, 700)
    page.set_game(entry)
    page.show()
    container = page.layout().itemAt(0).widget()  # 填满后 container 是 HBox 唯一项
    assert container.width() > 1000  # 修复前: 被 760 上限居中
    page.deleteLater()


def test_list_dot_updates_after_ifeo_toggle(qapp, tmp_path, monkeypatch):
    """IFEO 轮询落定后左侧列表状态点同步变绿(修复前只刷新详情徽章)。"""
    from backend import ifeo, launcher, paths, registry
    from backend.ifeo import IfeoState
    entry = _make_game(tmp_path, "g")
    games_yaml = tmp_path / "games.yaml"
    registry.save_games({"g": entry}, str(games_yaml))
    monkeypatch.setattr(paths, "GAMES_YAML", str(games_yaml))
    monkeypatch.setattr(launcher, "set_ifeo", lambda *a, **k: None)

    from ui.games_page import GamesPage
    page = GamesPage()
    item = page.game_list.item(0)
    old_widget = page.game_list.itemWidget(item)

    monkeypatch.setattr(ifeo, "query_ifeo",
                        lambda _name: IfeoState.ON_OURS)
    page.detail.ifeo_switch.setChecked(True)  # 触发 _on_ifeo_toggled → 轮询
    page.detail._poll_ifeo()                  # 立即落定(不等定时器)

    from ui.games_page import _status_level
    assert _status_level(entry) == "ok"
    # refresh() 会 clear() 列表, 旧 item 已析构 — 重新取 item 比较部件身份
    new_widget = page.game_list.itemWidget(page.game_list.item(0))
    assert new_widget is not old_widget  # 列表已刷新重建, 状态点变绿
    page.deleteLater()


def test_list_hover_follows_item_widgets(qapp, tmp_path, monkeypatch):
    """内嵌列表项自行上报 hover: delegate.hoverRow 跟随 enter/leave,
    不再停在首次悬停行(qfluentwidgets 视图 entered 信号被内嵌部件遮蔽)。"""
    from backend import paths, registry
    g1 = _make_game(tmp_path, "g1")
    g2 = _make_game(tmp_path, "g2")
    games_yaml = tmp_path / "games.yaml"
    registry.save_games({"g1": g1, "g2": g2}, str(games_yaml))
    monkeypatch.setattr(paths, "GAMES_YAML", str(games_yaml))

    # QTest.mouseMove 在 offscreen 下不合成 enter/leave, 直接投事件
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QEnterEvent
    from ui.games_page import GamesPage
    page = GamesPage()
    lw = page.game_list
    w0 = lw.itemWidget(lw.item(0))
    w1 = lw.itemWidget(lw.item(1))

    def enter(w):
        QApplication.sendEvent(
            w, QEnterEvent(QPointF(1, 1), QPointF(1, 1), QPointF(1, 1)))

    def leave(w):
        QApplication.sendEvent(w, QEvent(QEvent.Leave))

    enter(w0)
    assert lw.delegate.hoverRow == 0
    leave(w0)
    enter(w1)
    assert lw.delegate.hoverRow == 1  # 修复前: 停在 -1/旧行不更新
    leave(w1)
    assert lw.delegate.hoverRow == -1
    page.deleteLater()
