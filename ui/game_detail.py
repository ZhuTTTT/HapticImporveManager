"""游戏详情页: 头部(启动/移除) + 状态卡(IFEO) + 配置卡容器。

所有 registry 调用显式传 paths.GAMES_YAML — 默认参数在定义时绑定,
显式传参才能让测试 monkeypatch 生效。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, FluentIcon,
                            InfoBar, InfoBarPosition, MessageBox,
                            PrimaryPushButton, PushButton, StrongBodyLabel,
                            SwitchButton, TitleLabel, themeColor)

from backend import ifeo, launcher, paths, registry
from backend.ifeo import IfeoState
from ui.config_card import ConfigCard


class GameDetailPage(QWidget):
    config_changed = Signal(str)

    def __init__(self, runner: launcher.ProcessRunner, parent=None):
        super().__init__(parent)
        self.runner = runner
        self.entry: registry.GameEntry | None = None
        self._ifeo_timer = QTimer(self)
        self._ifeo_timer.setInterval(1000)
        self._ifeo_timer.timeout.connect(self._poll_ifeo)
        self._poll_count = 0

        # 头部
        self.name_label = TitleLabel("", self)
        self.path_label = CaptionLabel("", self)
        self.btn_launch = PrimaryPushButton(FluentIcon.PLAY, "启动游戏", self)
        self.btn_launch.clicked.connect(self._launch)
        self.btn_remove = PushButton(FluentIcon.DELETE, "移除", self)
        self.btn_remove.clicked.connect(self._remove)
        head_btns = QHBoxLayout()
        head_btns.addStretch(1)
        head_btns.addWidget(self.btn_launch)
        head_btns.addWidget(self.btn_remove)
        head = QVBoxLayout()
        head.addWidget(self.name_label)
        head.addWidget(self.path_label)
        head.addLayout(head_btns)

        # 状态卡
        self.status_card = CardWidget(self)
        sc = QVBoxLayout(self.status_card)
        self.status_badge = BodyLabel("", self)
        self.anticheat_label = CaptionLabel(
            "⚠ 检测到反作弊特征, 注入有账号封禁风险", self)
        self.ifeo_switch = SwitchButton(self)
        self.ifeo_switch.setOnText("开")
        self.ifeo_switch.setOffText("关")
        self.ifeo_switch.checkedChanged.connect(self._on_ifeo_toggled)
        ifeo_row = QHBoxLayout()
        ifeo_row.addWidget(StrongBodyLabel("IFEO 自动注入", self))
        ifeo_row.addStretch(1)
        ifeo_row.addWidget(self.ifeo_switch)
        sc.addWidget(StrongBodyLabel("状态", self))
        sc.addWidget(self.status_badge)
        sc.addWidget(self.anticheat_label)
        sc.addLayout(ifeo_row)
        sc.addWidget(CaptionLabel(
            "开启后从 Steam/启动器正常启动游戏即自动注入(需 UAC 提权)。",
            self))

        # 配置卡
        self.config_card = ConfigCard(self)
        self.config_card.saved.connect(self.config_changed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(12)
        lay.addLayout(head)
        lay.addWidget(self.status_card)
        lay.addWidget(self.config_card)
        lay.addStretch(1)

    def set_game(self, entry: registry.GameEntry) -> bool:
        """切换游戏; 配置卡有未保存修改时先询问, 用户取消则返回 False。"""
        if self.config_card.is_dirty():
            box = MessageBox("未保存修改",
                             "当前配置有未保存修改, 放弃并切换?", self)
            if not box.exec():
                return False
        self._ifeo_timer.stop()  # 换游戏时停掉旧轮询
        self.entry = entry
        self.name_label.setText(entry.name)
        self.path_label.setText(entry.exe)
        self.path_label.setToolTip(entry.exe)
        self.anticheat_label.setVisible(entry.anticheat)
        self.refresh_status()
        self.config_card.set_game(entry)
        return True

    def refresh_status(self):
        e = self.entry
        if e is None:
            return
        state = ifeo.query_ifeo(os.path.basename(e.exe))
        if not e.exe_exists:
            text, tip = "● exe 丢失", "找不到游戏可执行文件, 请检查路径"
        elif e.config_exists and state == IfeoState.ON_OURS:
            text, tip = "● 就绪", "配置与 IFEO 均已就位"
        else:
            text, tip = "● 未完成", "配置或 IFEO 未就位"
        if state == IfeoState.ON_OTHER:
            text += "(IFEO 被其他调试器占用!)"
        self.status_badge.setText(text)
        self.status_badge.setToolTip(tip)
        self.ifeo_switch.blockSignals(True)
        self.ifeo_switch.setChecked(state == IfeoState.ON_OURS)
        self.ifeo_switch.blockSignals(False)
        self.btn_launch.setEnabled(e.exe_exists)

    def _on_ifeo_toggled(self, checked: bool):
        if self.entry is None:
            return
        launcher.set_ifeo(self.runner, self.entry.name, checked)
        self._poll_count = 0
        self._ifeo_timer.stop()  # 单实例: 重复切换先停旧轮询
        self._ifeo_timer.start()

    def _poll_ifeo(self):
        self._poll_count += 1
        state = ifeo.query_ifeo(os.path.basename(self.entry.exe))
        want = IfeoState.ON_OURS if self.ifeo_switch.isChecked() \
            else IfeoState.OFF
        if state == want or self._poll_count >= 10:
            self._ifeo_timer.stop()
            if state != want:
                InfoBar.warning("IFEO", "提权被取消或操作失败, 状态未变更",
                                parent=self, position=InfoBarPosition.TOP,
                                duration=4000)
            self.refresh_status()

    def _launch(self):
        if self.entry is not None:
            launcher.launch_game(self.runner, self.entry.name)

    def _remove(self):
        if self.entry is None:
            return
        box = MessageBox("移除游戏",
                         f"从列表移除 {self.entry.name}?\n"
                         "(不动游戏文件和 IFEO 设置)", self)
        if box.exec():
            registry.remove_game(self.entry.name, str(paths.GAMES_YAML))
            self.entry = None
            self.config_changed.emit("")  # 空串 = 当前游戏被移除, 请刷新
