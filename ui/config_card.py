"""注入配置卡: 模式四选一卡片 + 白话解释 + 缓冲实时毫秒换算 + 脏状态。

文案集中在 config_model.MODE_INFO; 本文件只做呈现与交互。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFormLayout, QGridLayout, QHBoxLayout,
                               QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, ComboBox,
                            InfoBar, InfoBarPosition, MessageBox,
                            PlainTextEdit, PrimaryPushButton, PushButton,
                            Slider, SpinBox, StrongBodyLabel, SwitchButton,
                            themeColor)

from backend import config, launcher
from backend.registry import GameEntry
from ui.app_config import APP_CFG
from ui.config_model import (MODE_INFO, FormState, apply_form, frames_to_ms,
                             hus_to_ms, load_form)


class _ModeCard(CardWidget):
    """单个模式选择卡: 标题 + 一句话简介; 点击选中。"""
    clicked = Signal(str)

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        info = MODE_INFO[mode]
        lay = QVBoxLayout(self)
        lay.addWidget(StrongBodyLabel(info["title"], self))
        brief = CaptionLabel(info["brief"], self)
        brief.setWordWrap(True)
        lay.addWidget(brief)

    def mouseReleaseEvent(self, e):
        self.clicked.emit(self.mode)
        super().mouseReleaseEvent(e)

    def set_selected(self, on: bool):
        # 用主题色描边表达选中, 不写死颜色(深色适配)
        c = themeColor().name()
        self.setStyleSheet(
            f"_ModeCard {{ border: 2px solid {c}; }}" if on else "")


class ConfigCard(CardWidget):
    saved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entry: GameEntry | None = None
        self.doc = None
        self._dirty = False
        self._loading = False

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
        self.period_slider.valueChanged.connect(self._on_period)
        period_row = QHBoxLayout()
        period_row.addWidget(self.period_slider, 1)
        period_row.addWidget(self.period_label)

        self.buf_normal = SpinBox(self)
        self.buf_normal.setRange(1, 65536)
        self.buf_normal_ms = CaptionLabel("", self)
        self.buf_normal.valueChanged.connect(self._on_buf_normal)
        bn_row = QHBoxLayout()
        bn_row.addWidget(self.buf_normal, 1)
        bn_row.addWidget(self.buf_normal_ms)

        self.buf_ring = SpinBox(self)
        self.buf_ring.setRange(1, 65536)
        self.buf_ring_ms = CaptionLabel("", self)
        self.buf_ring.valueChanged.connect(self._on_buf_ring)
        br_row = QHBoxLayout()
        br_row.addWidget(self.buf_ring, 1)
        br_row.addWidget(self.buf_ring_ms)

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
        form.addRow("缓冲大小", bn_row)
        form.addRow("", CaptionLabel(
            "普通模式用: 游戏能囤多少音频。小了破音, 大了拖延迟。", self))
        form.addRow("虚拟缓冲", br_row)
        form.addRow("", CaptionLabel(
            "虚拟缓冲模式用: 幕后接住游戏爆发写入的通道长度。", self))
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
        self.buf_normal.setEnabled(mode == "Normal")
        self.buf_ring.setEnabled(mode == "Ringbuf")

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
        if self.doc is None or self.entry is None:
            return
        state = self._current_state()
        apply_form(self.doc, state)
        problems = config.validate(self.doc)
        # backend validate 硬性要求 log_level=Error, 作为兜底防手改配置;
        # UI 层用户选 Info 时已在警告对话框知情确认, 故过滤该条目放行。
        problems = [p for p in problems if "log_level" not in p]
        if problems:
            InfoBar.warning("校验失败", "\n".join(problems),
                            parent=self, position=InfoBarPosition.TOP,
                            duration=6000)
            return
        config.save_config(self.entry.game_dir, self.doc)
        self._dirty = False
        self.btn_save.setEnabled(False)
        msg = "配置已保存"
        if launcher.is_game_running(os.path.basename(self.entry.exe)):
            msg += "; 游戏正在运行, 重启后生效"
        InfoBar.success("保存", msg, parent=self,
                        position=InfoBarPosition.TOP, duration=3000)
        self.saved.emit(self.entry.name)

    def _reset_default(self):
        box = MessageBox("恢复默认", "用默认配置覆盖当前表单?(未保存前不影响文件)",
                         self)
        if box.exec():
            self.doc = config.default_config(APP_CFG.log_dir.value)
            self.error_view.hide()
            self._set_form_enabled(True)
            self._fill(load_form(self.doc))
            self._mark_dirty()
