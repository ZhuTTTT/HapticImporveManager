"""注入配置卡: 模式四选一卡片 + 白话解释 + 缓冲实时毫秒换算 + 脏状态。

模式文案集中在 i18n 目录(mode.<Mode>.* 键); 本文件只做呈现与交互。

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

from backend import config, launcher, paths, registry
from backend.registry import GameEntry
from i18n import tr
from ui import theme
from ui.app_config import APP_CFG
from ui.config_model import (FormState, apply_form, frames_to_ms,
                             hus_to_ms, load_form)

_MODE_ICONS = {  # 模式卡的语义图标
    "Normal": FluentIcon.SPEED_HIGH,     # 低延迟 = 速度
    "Ringbuf": FluentIcon.SYNC,          # 环形缓冲
    "Compat": FluentIcon.DEVELOPER_TOOLS,
    "Bypass": FluentIcon.SPEED_OFF,      # 处理关闭 = 不干预(与 Normal 同族呼应)
}


class _ModeCard(CardWidget):
    """单个模式选择卡: 图标 + 标题 + 一句话简介; 点击选中。"""
    clicked = Signal(str)

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        icon = IconWidget(_MODE_ICONS[mode], self)
        icon.setFixedSize(20, 20)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(icon)
        head.addWidget(StrongBodyLabel(tr(f"mode.{mode}.title"), self))
        head.addStretch(1)
        lay = QVBoxLayout(self)
        lay.addLayout(head)
        brief = CaptionLabel(tr(f"mode.{mode}.brief"), self)
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
        self._pending_state: FormState | None = None  # _save 时捕获, 成功后回写 hint
        self._save_tip: StateToolTip | None = None
        self._save_thread: QThread | None = None
        self._save_worker: _SaveWorker | None = None

        lay = QVBoxLayout(self)
        lay.addWidget(StrongBodyLabel(tr("config.title"), self))
        lay.addWidget(CaptionLabel(tr("config.caption"), self))

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
        self.buf_normal_label = BodyLabel(tr("config.buffer"), self)
        self.buf_normal_hint = CaptionLabel(tr("config.buffer_hint"), self)
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
        self.buf_ring_label = BodyLabel(tr("config.ring_buffer"), self)
        self.buf_ring_hint = CaptionLabel(tr("config.ring_buffer_hint"), self)
        self._buf_ring_widgets = (self.buf_ring_label, br_host,
                                  self.buf_ring_hint)

        self.raw_switch = SwitchButton(self)
        self.raw_switch.setOnText(tr("common.on"))
        self.raw_switch.setOffText(tr("common.off"))
        self.raw_switch.checkedChanged.connect(self._mark_dirty)
        self.force_switch = SwitchButton(self)
        self.force_switch.setOnText(tr("common.on"))
        self.force_switch.setOffText(tr("common.off"))
        self.force_switch.checkedChanged.connect(self._mark_dirty)

        self.log_box = ComboBox(self)
        self.log_box.addItems(["Error", "Info"])
        self.log_box.currentTextChanged.connect(self._on_log_level)

        form = QFormLayout()
        form.addRow(tr("config.period"), period_row)
        form.addRow("", CaptionLabel(tr("config.period_hint"), self))
        form.addRow(self.buf_normal_label, bn_host)
        form.addRow("", self.buf_normal_hint)
        form.addRow(self.buf_ring_label, br_host)
        form.addRow("", self.buf_ring_hint)
        form.addRow(tr("config.raw"), self.raw_switch)
        form.addRow("", CaptionLabel(tr("config.raw_hint"), self))
        form.addRow(tr("config.force_period"), self.force_switch)
        form.addRow("", CaptionLabel(tr("config.force_period_hint"), self))
        form.addRow(tr("config.log_level"), self.log_box)
        lay.addLayout(form)

        # 按钮
        self.btn_save = PrimaryPushButton(tr("config.save"), self)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save)
        self.btn_default = PushButton(tr("config.reset"), self)
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
            box = MessageBox(tr("config.missing_title"),
                             tr("config.missing_msg", name=entry.name), self)
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
                self.error_view.setPlainText(
                    tr("config.parse_failed", err=e) + "\n\n" + f.read())
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
            tr("config.period_native") if st.period_hus == 0
            else f"{hus_to_ms(st.period_hus):.1f} ms")
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
        # 意外模式值(手改 toml)无文案, 详情区留空而不露出消息键
        self.mode_detail.setText(
            tr(f"mode.{mode}.detail") if mode in config.MODES else "")
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
            tr("config.period_native") if v == 0 else f"{hus_to_ms(v):.1f} ms")
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
            box = MessageBox(tr("config.log_level"),
                             tr("config.log_info_warn"), self)
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
        self._save_tip = StateToolTip(tr("config.saving_title"),
                                      tr("config.saving_msg"), self)
        self._save_tip.show()

        state = self._current_state()
        self._pending_state = state  # 保存成功后回写注册表 hint 用
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
            self._save_tip.setContent(tr("config.saved_title") if not problems
                                      else tr("config.invalid_title"))
            self._save_tip.setState(True)  # 打勾并自动淡出
            self._save_tip = None

        if problems:
            self.btn_save.setEnabled(True)  # 仍然脏, 允许改了再存
            InfoBar.warning(tr("config.invalid_title"), "\n".join(problems),
                            parent=self, position=InfoBarPosition.TOP,
                            duration=6000)
            return
        self._dirty = False
        # 回写列表 hint(模式相关缓冲: Ringbuf 取虚拟缓冲, 其余取普通缓冲),
        # 否则游戏中心列表永远显示注册时的旧值
        st = self._pending_state
        registry.update_hints(
            name, st.mode,
            st.buf_ring if st.mode == "Ringbuf" else st.buf_normal,
            str(paths.GAMES_YAML))
        msg = tr("config.saved_msg")
        if running:
            msg += tr("config.saved_running_suffix")
        InfoBar.success(tr("config.save"), msg, parent=self,
                        position=InfoBarPosition.TOP, duration=3000)
        # 保存期间用户可能已切换游戏, 仅当仍是同一游戏时才发 saved
        if self.entry is not None and self.entry.name == name:
            self.saved.emit(name)

    def _reset_default(self):
        box = MessageBox(tr("config.reset"), tr("config.reset_msg"), self)
        if box.exec():
            self.doc = config.default_config(APP_CFG.log_dir.value)
            self.error_view.hide()
            self._set_form_enabled(True)
            self._fill(load_form(self.doc))
            self._mark_dirty()
