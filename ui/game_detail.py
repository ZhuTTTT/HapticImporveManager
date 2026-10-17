"""游戏详情页: 头部(启动/移除) + 状态卡(IFEO) + 配置卡容器。

所有 registry 调用显式传 paths.GAMES_YAML — 默认参数在定义时绑定,
显式传参才能让测试 monkeypatch 生效。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, FluentIcon,
                            InfoBar, InfoBarPosition, MessageBox,
                            PrimaryPushButton, PushButton, StrongBodyLabel,
                            SwitchButton, TitleLabel)

from backend import ifeo, launcher, paths, registry
from backend.ifeo import IfeoState
from i18n import tr
from ui import theme
from ui.config_card import ConfigCard


class GameDetailPage(QWidget):
    config_changed = Signal(str)
    ifeo_settled = Signal(str)  # IFEO 轮询落定(开关状态已稳定), 列表需同步状态点

    def __init__(self, runner: launcher.ProcessRunner, parent=None):
        super().__init__(parent)
        self.runner = runner
        self.entry: registry.GameEntry | None = None
        self._pending_remove = False  # 移除流程: 已发起 IFEO off, 等轮询落定
        self._ifeo_timer = QTimer(self)
        self._ifeo_timer.setInterval(1000)
        self._ifeo_timer.timeout.connect(self._poll_ifeo)
        self._poll_count = 0

        # 头部: 左侧游戏名+路径, 右侧操作按钮
        self.name_label = TitleLabel("", self)
        self.path_label = CaptionLabel("", self)
        self.btn_launch = PrimaryPushButton(FluentIcon.PLAY,
                                            tr("detail.launch"), self)
        self.btn_launch.clicked.connect(self._launch)
        self.btn_locate = PushButton(FluentIcon.FOLDER,
                                     tr("detail.locate_exe"), self)
        self.btn_locate.setToolTip(tr("detail.locate_exe_tip"))
        self.btn_locate.clicked.connect(self._locate_exe)
        self.btn_remove = PushButton(FluentIcon.DELETE, tr("detail.remove"),
                                     self)
        self.btn_remove.clicked.connect(self._remove)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.addWidget(self.name_label)
        title_col.addWidget(self.path_label)
        head = QHBoxLayout()
        head.addLayout(title_col, 1)
        head.addWidget(self.btn_locate, 0, Qt.AlignmentFlag.AlignTop)
        head.addWidget(self.btn_launch, 0, Qt.AlignmentFlag.AlignTop)
        head.addWidget(self.btn_remove, 0, Qt.AlignmentFlag.AlignTop)

        # 状态卡
        self.status_card = CardWidget(self)
        sc = QVBoxLayout(self.status_card)
        self.status_badge = BodyLabel("", self)
        self.status_badge.setAutoFillBackground(False)
        self.anticheat_label = CaptionLabel(tr("detail.anticheat_warn"), self)
        self.ifeo_switch = SwitchButton(self)
        self.ifeo_switch.setOnText(tr("common.on"))
        self.ifeo_switch.setOffText(tr("common.off"))
        self.ifeo_switch.checkedChanged.connect(self._on_ifeo_toggled)
        ifeo_row = QHBoxLayout()
        ifeo_row.addWidget(StrongBodyLabel(tr("detail.ifeo_label"), self))
        ifeo_row.addStretch(1)
        ifeo_row.addWidget(self.ifeo_switch)
        sc.addWidget(StrongBodyLabel(tr("detail.status"), self))
        badge_row = QHBoxLayout()  # 徽章是胶囊, 不拉伸
        badge_row.addWidget(self.status_badge, 0)
        badge_row.addStretch(1)
        sc.addLayout(badge_row)
        sc.addWidget(self.anticheat_label)
        sc.addLayout(ifeo_row)
        sc.addWidget(CaptionLabel(tr("detail.ifeo_caption"), self))

        # 配置卡
        self.config_card = ConfigCard(self)
        self.config_card.saved.connect(self.config_changed)

        # 内容列: 填满右侧(与诊断/设置页一致; 居中限宽会让导航切换时宽度跳变)
        container = QWidget(self)
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(12)
        cl.addLayout(head)
        cl.addWidget(self.status_card)
        cl.addWidget(self.config_card)
        cl.addStretch(1)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.addWidget(container)

    def set_game(self, entry: registry.GameEntry) -> bool:
        """切换游戏; 配置卡有未保存修改时先询问, 用户取消则返回 False。"""
        if self.config_card.is_dirty():
            box = MessageBox(tr("detail.unsaved_title"),
                             tr("detail.unsaved_msg"), self)
            if not box.exec():
                return False
        self._ifeo_timer.stop()  # 换游戏时停掉旧轮询
        self._pending_remove = False  # 挂起的移除流程随旧游戏作废
        self.btn_remove.setEnabled(True)
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
            level = "err"
            text = tr("detail.badge_exe_missing")
            tip = tr("detail.badge_exe_missing_tip")
        elif e.config_exists and state == IfeoState.ON_OURS:
            level = "ok"
            text = tr("detail.badge_ready")
            tip = tr("detail.badge_ready_tip")
        else:
            level = "warn"
            text = tr("detail.badge_incomplete")
            tip = tr("detail.badge_incomplete_tip")
        if state == IfeoState.ON_OTHER:
            level, text = "err", text + tr("detail.badge_ifeo_occupied")
        self.status_badge.setText(text)
        self.status_badge.setToolTip(tip)
        self.status_badge.setStyleSheet(theme.pill_style(level))
        self.ifeo_switch.blockSignals(True)
        self.ifeo_switch.setChecked(state == IfeoState.ON_OURS)
        self.ifeo_switch.blockSignals(False)
        self.btn_launch.setEnabled(e.exe_exists)
        # 「定位 exe」仅 exe 丢失时显示(典型: 注册表同步重建的骨架条目)
        self.btn_locate.setVisible(not e.exe_exists)

    def _locate_exe(self):
        if self.entry is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, tr("detail.locate_exe_title"), "",
            tr("detail.locate_exe_filter"))
        if not path:
            return
        registry.update_exe(self.entry.name, path, str(paths.GAMES_YAML))
        self.entry.exe = path
        self.set_game(self.entry)  # 重载: 状态徽章/按钮可见性/配置卡刷新
        self.config_changed.emit(self.entry.name)  # 列表状态点同步

    def _on_ifeo_toggled(self, checked: bool):
        if self.entry is None:
            return
        launcher.set_ifeo(self.runner, self.entry.name, checked)
        self._poll_count = 0
        self._ifeo_timer.stop()  # 单实例: 重复切换先停旧轮询
        self._ifeo_timer.start()

    def _poll_ifeo(self):
        # 移除游戏后定时器可能仍在跑: 先守卫, 避免解引用 None 刷异常
        if self.entry is None:
            self._ifeo_timer.stop()
            return
        self._poll_count += 1
        state = ifeo.query_ifeo(os.path.basename(self.entry.exe))
        if self._pending_remove:
            # 移除流程: 等 IFEO off 落定后才能真正删注册表项(launcher 的
            # ifeo 子命令要按名字反查 games.yaml, 先删会 unknown game)
            if state == IfeoState.OFF:
                self._ifeo_timer.stop()
                self._do_remove()
            elif self._poll_count >= 10:
                # UAC 被取消或关闭失败: 中止移除, 游戏保留, 不留注册表残留
                self._ifeo_timer.stop()
                self._pending_remove = False
                self.btn_remove.setEnabled(True)
                InfoBar.warning(tr("detail.remove_title"),
                                tr("detail.remove_ifeo_failed"),
                                parent=self, position=InfoBarPosition.TOP,
                                duration=4000)
                self.refresh_status()
            return
        want = IfeoState.ON_OURS if self.ifeo_switch.isChecked() \
            else IfeoState.OFF
        if state == want or self._poll_count >= 10:
            self._ifeo_timer.stop()
            if state != want:
                InfoBar.warning("IFEO", tr("detail.ifeo_failed_msg"),
                                parent=self, position=InfoBarPosition.TOP,
                                duration=4000)
            self.refresh_status()
            # 轮询落定: 通知游戏中心刷新列表状态点(否则详情绿了列表仍黄)
            self.ifeo_settled.emit(self.entry.name)

    def _launch(self):
        if self.entry is not None:
            launcher.launch_game(self.runner, self.entry.name)

    def _remove(self):
        if self.entry is None or self._pending_remove:
            return
        box = MessageBox(tr("detail.remove_title"),
                         tr("detail.remove_confirm", name=self.entry.name),
                         self)
        if not box.exec():
            return
        self._ifeo_timer.stop()  # 移除即停轮询, entry 置 None 后不再触发
        state = ifeo.query_ifeo(os.path.basename(self.entry.exe))
        if state == IfeoState.ON_OURS:
            # 自动注入开着: 先关 IFEO(launcher 内部 UAC 提权), 轮询落定后
            # 才移除 — 顺序反了 launcher 按名字反查 games.yaml 会 unknown game。
            # ON_OTHER 是别人的调试器, 不动; OFF 无需提权, 直接移除。
            self._pending_remove = True
            self.btn_remove.setEnabled(False)
            launcher.set_ifeo(self.runner, self.entry.name, False)
            self._poll_count = 0
            self._ifeo_timer.start()
            return
        self._do_remove()

    def _do_remove(self):
        self._pending_remove = False
        self.btn_remove.setEnabled(True)
        registry.remove_game(self.entry.name, str(paths.GAMES_YAML))
        self.entry = None
        self.config_changed.emit("")  # 空串 = 当前游戏被移除, 请刷新
