"""注入配置卡: 模式四选一卡片 + 白话解释 + 缓冲实时毫秒换算 + 脏状态。

文案集中在 config_model.MODE_INFO; 本文件只做呈现与交互。

保存走后台线程(_SaveWorker): tasklist 查进程 + 杀软扫描磁盘写入
在真实机器上可耗时数秒, 同步执行会冻结 UI。
"""
from __future__ import annotations

import os

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (QFormLayout, QGridLayout, QHBoxLayout,
                               QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, ComboBox,
                            FluentIcon, IconWidget, InfoBar, InfoBarPosition,
                            MessageBox, PlainTextEdit, PrimaryPushButton,
                            PushButton, Slider, SpinBox, StateToolTip,
                            StrongBodyLabel, SwitchButton)

from backend import config, launcher
from backend.registry import GameEntry
from ui import theme
from ui.app_config import APP_CFG
from ui.config_model import (MODE_INFO, FormState, apply_form, frames_to_ms,
                             hus_to_ms, load_form)

_MODE_ICONS = {  # 模式卡的语义图标
    "Normal": FluentIcon.SPEED_HIGH,     # 低延迟 = 速度
    "Ringbuf": FluentIcon.SYNC,          # 环形缓冲
    "Compat": FluentIcon.DEVELOPER_TOOLS,
    "Bypass": FluentIcon.SKIP_FORWARD,   # 直通不干预
}


class _ModeCard(CardWidget):
    """单个模式选择卡: 图标 + 标题 + 一句话简介; 点击选中。"""
    clicked = Signal(str)

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        info = MODE_INFO[mode]
        icon = IconWidget(_MODE_ICONS[mode], self)
        icon.setFixedSize(20, 20)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(icon)
        head.addWidget(StrongBodyLabel(info["title"], self))
        head.addStretch(1)
        lay = QVBoxLayout(self)
        lay.addLayout(head)
        brief = CaptionLabel(info["brief"], self)
        brief.setWordWrap(True)
        lay.addWidget(brief)

    def mouseReleaseEvent(self, e):
        self.clicked.emit(self.mode)
        super().mouseReleaseEvent(e)

    def set_selected(self, on: bool):
        # 选中 = 主题色描边 + 淡底, 用主题令牌不写死颜色(深色适配)
        if on:
            c = theme.ACCENT
            self.setStyleSheet(
                f"_ModeCard {{ border: 1px solid {c};"
                f" background: {theme.accent_tint(0.10)}; }}")
        else:
            self.setStyleSheet("")


class _SaveWorker(QObject):
    """后台线程: 应用表单 → 校验 → 落盘 → tasklist 查游戏进程。

    完成后发 finished(problems, game_running, name)。
    注意: worker 持有 doc 期间 UI 线程不得再读写该 doc
    (保存中 _save 有 _saving 重入守卫, 表单控件只读值不改 doc)。
    """
    finished = Signal(list, bool, str)

    def __init__(self, doc, state: FormState, game_dir: str,
                 exe_name: str, name: str):
        super().__init__()
        self._doc = doc
        self._state = state
        self._game_dir = game_dir
        self._exe_name = exe_name
        self._name = name

    def run(self):
        apply_form(self._doc, self._state)
        # backend validate 硬性要求 log_level=Error, 作为兜底防手改配置;
        # UI 层用户选 Info 时已在警告对话框知情确认, 故过滤该条目放行。
        problems = [p for p in config.validate(self._doc)
                    if "log_level" not in p]
        if not problems:
            config.save_config(self._game_dir, self._doc)
        running = launcher.is_game_running(self._exe_name)
        self.finished.emit(problems, running, self._name)


class ConfigCard(CardWidget):
    saved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entry: GameEntry | None = None
        self.doc = None
        self._dirty = False
        self._loading = False
        self._saving = False
        self._save_tip: StateToolTip | None = None
        self._save_thread: QThread | None = None
        self._save_worker: _SaveWorker | None = None

        lay = QVBoxLayout(self)
        lay.addWidget(StrongBodyLabel("注入配置", self))
        lay.addWidget(CaptionLabel(
            "修改后点「保存」生效; 游戏运行中保存需重启游戏。", self))

        # 模式四卡
        self.mode_cards: dict[str, _ModeCard] = {}
        grid = QGridLayout()
        from backend.config import MODES
        for i, m in enumerate(MODES):
            card = _ModeCard(m, self)
            card.clicked.connect(self._on_mode_card)
            self.mode_cards[m] = card
            grid.addWidget(card, i // 2, i % 2)
        lay.addLayout(grid)
        self.mode_detail = CaptionLabel("", self)
        self.mode_detail.setWordWrap(True)
        lay.addWidget(self.mode_detail)

        # 表单
        self.period_slider = Slider(Qt.Orientation.Horizontal, self)
        self.period_slider.setRange(0, 1000)
        self.period_label = BodyLabel("", self)
        self.period_label.setFont(theme.mono_font())  # 测量数字用等宽
        self.period_slider.valueChanged.connect(self._on_period)
        period_row = QHBoxLayout()
        period_row.addWidget(self.period_slider, 1)
        period_row.addWidget(self.period_label)

        self.buf_normal = SpinBox(self)
        self.buf_normal.setRange(1, 65536)
        self.buf_normal_ms = CaptionLabel("", self)
        self.buf_normal_ms.setFont(theme.mono_font(9))
        self.buf_normal.valueChanged.connect(self._on_buf_normal)
        bn_host = QWidget(self)
        bn_row = QHBoxLayout(bn_host)
        bn_row.setContentsMargins(0, 0, 0, 0)
        bn_row.addWidget(self.buf_normal, 1)
        bn_row.addWidget(self.buf_normal_ms)
        self.buf_normal_label = BodyLabel("缓冲大小", self)
        self.buf_normal_hint = CaptionLabel(
            "普通模式用: 游戏能囤多少音频。小了破音, 大了拖延迟。", self)
        # 同一组的三个件随模式一起显示/隐藏
        self._buf_normal_widgets = (self.buf_normal_label, bn_host,
                                    self.buf_normal_hint)

        self.buf_ring = SpinBox(self)
        self.buf_ring.setRange(1, 65536)
        self.buf_ring_ms = CaptionLabel("", self)
        self.buf_ring_ms.setFont(theme.mono_font(9))
        self.buf_ring.valueChanged.connect(self._on_buf_ring)
        br_host = QWidget(self)
        br_row = QHBoxLayout(br_host)
        br_row.setContentsMargins(0, 0, 0, 0)
        br_row.addWidget(self.buf_ring, 1)
        br_row.addWidget(self.buf_ring_ms)
        self.buf_ring_label = BodyLabel("虚拟缓冲", self)
        self.buf_ring_hint = CaptionLabel(
            "虚拟缓冲模式用: 幕后接住游戏爆发写入的通道长度。", self)
        self._buf_ring_widgets = (self.buf_ring_label, br_host,
                                  self.buf_ring_hint)

        self.raw_switch = SwitchButton(self)
        self.raw_switch.setOnText("开")
        self.raw_switch.setOffText("关")
        self.raw_switch.checkedChanged.connect(self._mark_dirty)
        self.force_switch = SwitchButton(self)
        self.force_switch.setOnText("开")
        self.force_switch.setOffText("关")
        self.force_switch.checkedChanged.connect(self._mark_dirty)

        self.log_box = ComboBox(self)
        self.log_box.addItems(["Error", "Info"])
        self.log_box.currentTextChanged.connect(self._on_log_level)

        form = QFormLayout()
        form.addRow("推送节奏", period_row)
        form.addRow("", CaptionLabel(
            "手柄多久收到一次音频。越小越跟手, 太小会破音; 最左 = 不干预(原生)。",
            self))
        form.addRow(self.buf_normal_label, bn_host)
        form.addRow("", self.buf_normal_hint)
        form.addRow(self.buf_ring_label, br_host)
        form.addRow("", self.buf_ring_hint)
        form.addRow("原始模式(raw)", self.raw_switch)
        form.addRow("", CaptionLabel("保持默认(开)即可, 出问题再动。", self))
        form.addRow("强制周期", self.force_switch)
        form.addRow("", CaptionLabel("强制按推送节奏发送。保持默认(开)即可。",
                                     self))
        form.addRow("日志级别", self.log_box)
        lay.addLayout(form)

        # 按钮
        self.btn_save = PrimaryPushButton("保存", self)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save)
        self.btn_default = PushButton("恢复默认", self)
        self.btn_default.clicked.connect(self._reset_default)
        btns = QHBoxLayout()
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_default)
        btns.addStretch(1)
        lay.addLayout(btns)

        self.error_view = PlainTextEdit(self)
        self.error_view.setReadOnly(True)
        self.error_view.hide()
        lay.addWidget(self.error_view)

    # ---- 数据装载 ----

    def set_game(self, entry: GameEntry):
        self.entry = entry
        self.error_view.hide()
        try:
            self.doc = config.load_config(entry.game_dir)
        except FileNotFoundError:
            self.doc = None
            box = MessageBox("无配置",
                             f"{entry.name} 还没有 redirect_config.toml,\n"
                             "生成默认配置?", self)
            if box.exec():
                self.doc = config.default_config(APP_CFG.log_dir.value)
                config.save_config(entry.game_dir, self.doc)
            else:
                self._set_form_enabled(False)
                return
        except Exception as e:  # tomlkit 解析失败: 显示原文, 禁表单
            self.doc = None
            self._set_form_enabled(False)
            self.error_view.show()
            with open(entry.config_path, encoding="utf-8") as f:
                self.error_view.setPlainText(f"配置解析失败: {e}\n\n"
                                             + f.read())
            return
        self._set_form_enabled(True)
        self._fill(load_form(self.doc))

    def _set_form_enabled(self, on: bool):
        for w in (*self.mode_cards.values(), self.period_slider,
                  self.buf_normal, self.buf_ring, self.raw_switch,
                  self.force_switch, self.log_box, self.btn_default):
            w.setEnabled(on)
        if not on:
            self.btn_save.setEnabled(False)

    def _fill(self, st: FormState):
        self._loading = True
        self._select_mode(st.mode)
        self.period_slider.setValue(st.period_hus)
        self.period_label.setText(
            "原生" if st.period_hus == 0 else f"{hus_to_ms(st.period_hus):.1f} ms")
        self.buf_normal.setValue(st.buf_normal)
        self.buf_ring.setValue(st.buf_ring)
        self.raw_switch.setChecked(st.raw)
        self.force_switch.setChecked(st.force_period)
        self.log_box.setCurrentText(st.log_level)
        self._loading = False
        self._dirty = False
        self.btn_save.setEnabled(False)

    # ---- 交互 ----

    def _select_mode(self, mode: str):
        for m, c in self.mode_cards.items():
            c.set_selected(m == mode)
        info = MODE_INFO.get(mode)
        self.mode_detail.setText(info["detail"] if info else "")
        # 缓冲项与模式联动: 不适用当前模式的整组隐藏(标签+输入+说明)
        for w in self._buf_normal_widgets:
            w.setVisible(mode == "Normal")
        for w in self._buf_ring_widgets:
            w.setVisible(mode == "Ringbuf")

    def _on_mode_card(self, mode: str):
        self._select_mode(mode)
        self._mark_dirty()

    def _on_period(self, v: int):
        self.period_label.setText(
            "原生" if v == 0 else f"{hus_to_ms(v):.1f} ms")
        self._mark_dirty()

    def _on_buf_normal(self, v: int):
        self.buf_normal_ms.setText(f"≈ {frames_to_ms(v):.1f} ms")
        self._mark_dirty()

    def _on_buf_ring(self, v: int):
        self.buf_ring_ms.setText(f"≈ {frames_to_ms(v):.1f} ms")
        self._mark_dirty()

    def _on_log_level(self, level: str):
        if self._loading:
            return
        if level != "Error":
            box = MessageBox(
                "日志级别",
                "Info 在 overflow 时可写 GB 级日志(实测一次会话 2.9GB)。\n"
                "仅排障临时使用, 确定切换?", self)
            if not box.exec():
                self._loading = True
                self.log_box.setCurrentText("Error")
                self._loading = False
                return
        self._mark_dirty()

    def _mark_dirty(self, *_args):
        if self._loading or self.doc is None:
            return
        self._dirty = True
        self.btn_save.setEnabled(True)

    def is_dirty(self) -> bool:
        return self._dirty

    # ---- 保存 ----

    def _current_state(self) -> FormState:
        return FormState(
            mode=self._selected_mode(),
            period_hus=self.period_slider.value(),
            buf_normal=self.buf_normal.value(),
            buf_ring=self.buf_ring.value(),
            raw=self.raw_switch.isChecked(),
            force_period=self.force_switch.isChecked(),
            log_level=self.log_box.currentText(),
        )

    def _selected_mode(self) -> str:
        for m, c in self.mode_cards.items():
            if c.styleSheet():
                return m
        return "Normal"

    def _save(self):
        if self.doc is None or self.entry is None or self._saving:
            return
        self._saving = True
        self.btn_save.setEnabled(False)
        self._save_tip = StateToolTip("保存中", "正在写入配置…", self)
        self._save_tip.show()

        state = self._current_state()
        worker = _SaveWorker(self.doc, state, self.entry.game_dir,
                             os.path.basename(self.entry.exe),
                             self.entry.name)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(self._on_save_finished)
        # PySide6 信号连接不持有接收者强引用, 局部变量被 GC 后槽函数静默失效,
        # 必须存实例属性(_on_save_finished 里释放)
        self._save_worker = worker
        self._save_thread = thread
        thread.start()

    def _on_save_finished(self, problems: list, running: bool, name: str):
        self._save_thread.wait()
        self._save_thread = None
        self._save_worker = None  # 释放引用, deleteLater 回收 C++ 侧
        self._saving = False
        if self._save_tip is not None:
            self._save_tip.setContent("保存完成" if not problems
                                      else "校验失败")
            self._save_tip.setState(True)  # 打勾并自动淡出
            self._save_tip = None

        if problems:
            self.btn_save.setEnabled(True)  # 仍然脏, 允许改了再存
            InfoBar.warning("校验失败", "\n".join(problems),
                            parent=self, position=InfoBarPosition.TOP,
                            duration=6000)
            return
        self._dirty = False
        msg = "配置已保存"
        if running:
            msg += "; 游戏正在运行, 重启后生效"
        InfoBar.success("保存", msg, parent=self,
                        position=InfoBarPosition.TOP, duration=3000)
        # 保存期间用户可能已切换游戏, 仅当仍是同一游戏时才发 saved
        if self.entry is not None and self.entry.name == name:
            self.saved.emit(name)

    def _reset_default(self):
        box = MessageBox("恢复默认", "用默认配置覆盖当前表单?(未保存前不影响文件)",
                         self)
        if box.exec():
            self.doc = config.default_config(APP_CFG.log_dir.value)
            self.error_view.hide()
            self._set_form_enabled(True)
            self._fill(load_form(self.doc))
            self._mark_dirty()
