# -*- coding: utf-8 -*-
"""
MultiClicker - 循环点击 + 连点器
多位置循环定时点击 / 单点快速连击。白天/黑夜主题无缝切换。

热键:
  F8   录制位置(循环模式:加入列表;连点模式:设定固定点)
  F9   开始 / 停止
  F10  清空(循环模式:清空列表;连点模式:清除固定点)
  ESC  紧急停止 / 取消倒计时
"""

import json
import os
import time
import threading
import customtkinter as ctk
from pynput import mouse, keyboard

try:
    import winsound
except ImportError:
    winsound = None

APP_NAME = "MultiClicker"
CONFIG_PATH = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                           APP_NAME, "config.json")

# ---------- 两套主题 ----------
THEMES = {
    "light": {
        "BG": "#f5f5f7", "CARD": "#ffffff", "CARD2": "#ececf0",
        "BORDER": "#e0e0e6", "ACCENT": "#e8824f", "ACCENT_HOV": "#d96f3d",
        "GREEN": "#3f9d6e", "GREEN_DIM": "#e6f3ec", "AMBER": "#e0a03c",
        "RED": "#de5c5c", "TEXT": "#3a3a40", "TEXT2": "#7a7a85",
        "TEXT3": "#b0b0b8", "HL_TEXT": "#2f6b4f", "MODE": "light",
    },
    "dark": {
        "BG": "#0e1018", "CARD": "#161a26", "CARD2": "#1e2334",
        "BORDER": "#2a3045", "ACCENT": "#6366f1", "ACCENT_HOV": "#7c7ff5",
        "GREEN": "#34d399", "GREEN_DIM": "#1c2b26", "AMBER": "#fbbf24",
        "RED": "#f87171", "TEXT": "#e2e8f0", "TEXT2": "#94a3b8",
        "TEXT3": "#64748b", "HL_TEXT": "#d1fae5", "MODE": "dark",
    },
}


def beep(freq=880, ms=80):
    if winsound:
        try:
            winsound.Beep(freq, ms)
        except Exception:
            pass


class PositionCard(ctk.CTkFrame):
    """循环模式:单个位置卡片,支持高亮当前点击项"""

    def __init__(self, master, index, pos, app):
        super().__init__(master, fg_color=app.c("CARD2"), corner_radius=10, height=44)
        self.app = app
        self.index = index
        self.pos = pos
        self.pack_propagate(False)

        app.reg(self, fg="CARD2")
        self.num = ctk.CTkLabel(self, text=f"{index + 1:02d}", width=34,
                                font=("Consolas", 14, "bold"))
        app.reg(self.num, text="ACCENT")
        self.num.pack(side="left", padx=(12, 4))
        self.coord = ctk.CTkLabel(self, text=f"({pos[0]}, {pos[1]})",
                                  font=("Consolas", 13))
        app.reg(self.coord, text="TEXT")
        self.coord.pack(side="left", padx=4)

        for txt, cmd in (("▲", self.move_up), ("▼", self.move_down)):
            b = ctk.CTkButton(self, text=txt, width=26, height=26, corner_radius=6,
                              fg_color="transparent", font=("Consolas", 11),
                              command=cmd)
            app.reg(b, hover="BORDER", text="TEXT3")
            b.pack(side="right", padx=2)
        b = ctk.CTkButton(self, text="✕", width=26, height=26, corner_radius=6,
                          fg_color="transparent", font=("Consolas", 12),
                          command=self.delete)
        app.reg(b, hover="RED", text="TEXT3")
        b.pack(side="right", padx=(2, 8))

    def move_up(self):
        i = self.app.positions.index(self.pos)
        if i > 0:
            self.app.positions[i], self.app.positions[i - 1] = \
                self.app.positions[i - 1], self.app.positions[i]
            self.app.refresh_list()

    def move_down(self):
        i = self.app.positions.index(self.pos)
        if i < len(self.app.positions) - 1:
            self.app.positions[i], self.app.positions[i + 1] = \
                self.app.positions[i + 1], self.app.positions[i]
            self.app.refresh_list()

    def delete(self):
        self.app.positions.remove(self.pos)
        self.app.refresh_list()
        self.app.log("已删除一个位置")

    def highlight(self, on):
        if on:
            self.configure(fg_color=self.app.c("GREEN_DIM"), border_width=2,
                           border_color=self.app.c("GREEN"))
            self.num.configure(text_color=self.app.c("GREEN"))
            self.coord.configure(text_color=self.app.c("HL_TEXT"))
        else:
            self.configure(fg_color=self.app.c("CARD2"), border_width=0)
            self.num.configure(text_color=self.app.c("ACCENT"))
            self.coord.configure(text_color=self.app.c("TEXT"))


class MultiClickerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MultiClicker · 循环点击 / 连点器")
        self.geometry("780x640")
        self.minsize(720, 560)

        self.positions = []
        self.cards = []
        self.fixed_pos = None
        self.clicking = False
        self.countdown = None
        self.total_clicks = 0
        self.spam_start_time = 0.0
        self.topmost = ctk.BooleanVar(value=False)
        self.mouse_ctrl = mouse.Controller()
        self._theme_registry = []

        self._load_settings()
        self.colors = dict(THEMES[self.settings["theme"]])
        ctk.set_appearance_mode(self.colors["MODE"])
        self._build_ui()
        self._start_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(60, self._tick_cursor)

    # ---------------- 主题系统 ----------------
    def c(self, key):
        return self.colors[key]

    def _theme_is_light(self):
        return self.colors["MODE"] == "light"

    def reg(self, widget, fg=None, text=None, hover=None, border=None,
            selected=None, sel_hover=None, unselected=None, unsel_hover=None):
        """设置控件颜色并注册,主题切换时统一刷新"""
        roles = {"fg": fg, "text": text, "hover": hover, "border": border,
                 "selected": selected, "sel_hover": sel_hover,
                 "unselected": unselected, "unsel_hover": unsel_hover}
        self._apply_color(widget, roles)
        self._theme_registry.append((widget, roles))
        return widget

    def _apply_color(self, widget, roles):
        kw = {}
        if roles["fg"]:
            kw["fg_color"] = self.c(roles["fg"])
        if roles["text"]:
            kw["text_color"] = self.c(roles["text"])
        if roles["hover"]:
            kw["hover_color"] = self.c(roles["hover"])
        if roles["border"]:
            kw["border_color"] = self.c(roles["border"])
        if roles["selected"]:
            kw["selected_color"] = self.c(roles["selected"])
        if roles["sel_hover"]:
            kw["selected_hover_color"] = self.c(roles["sel_hover"])
        if roles["unselected"]:
            kw["unselected_color"] = self.c(roles["unselected"])
        if roles["unsel_hover"]:
            kw["unselected_hover_color"] = self.c(roles["unsel_hover"])
        if kw:
            try:
                widget.configure(**kw)
            except Exception:
                pass

    def switch_theme(self):
        light = self.theme_switch.get() == 1
        self.settings["theme"] = "light" if light else "dark"
        self._save_settings()
        self.colors = dict(THEMES[self.settings["theme"]])
        ctk.set_appearance_mode(self.colors["MODE"])

        self.configure(fg_color=self.c("BG"))
        for w, roles in self._theme_registry:
            self._apply_color(w, roles)

        # 页签按钮配色
        try:
            self.tabs.configure(
                segmented_button_selected_color=self.c("ACCENT"),
                segmented_button_selected_hover_color=self.c("ACCENT_HOV"),
                segmented_button_unselected_color=self.c("CARD2"),
                segmented_button_unselected_hover_color=self.c("BORDER"),
                text_color=self.c("TEXT2"))
        except Exception:
            pass

        # 日志 tag 颜色同步
        self.log_box._textbox.tag_configure("ok", foreground=self.c("GREEN"))
        self.log_box._textbox.tag_configure("info", foreground=self.c("TEXT2"))
        self.log_box._textbox.tag_configure("err", foreground=self.c("RED"))

        # 运行态颜色重应用
        self._refresh_state_colors()
        self.log(f"已切换为{'白天' if light else '黑夜'}主题")

    def _refresh_state_colors(self):
        """按当前运行状态重设动态颜色"""
        if self.clicking:
            self._set_running_ui(True)
            self._unhighlight_all()
        else:
            self._set_running_ui(False)
        if self.countdown is not None:
            self._set_loop_btn_countdown(True)
            self.set_status("AMBER")
        else:
            self.set_status(self._status_role)

    # ---------------- 设置持久化 ----------------
    def _load_settings(self):
        self.settings = {
            "interval": 2.0, "round_wait": 5.0, "start_delay": 3,
            "button": "左键", "click_type": "单击",
            "spam_interval_ms": 50, "spam_max": 0,
            "spam_pos_mode": "跟随鼠标", "spam_button": "左键",
            "theme": "light",
        }
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.settings.update(json.load(f))
        except Exception:
            pass

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------------- UI ----------------
    def _build_ui(self):
        self._theme_registry = []

        # 顶部
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 6))

        # 左上角:主题切换 ☀️ switch 🌙
        theme_box = ctk.CTkFrame(header, fg_color="transparent")
        theme_box.pack(side="left", pady=(4, 0))
        ctk.CTkLabel(theme_box, text="☀️", font=("Segoe UI Emoji", 15)).pack(side="left")
        self.theme_switch = ctk.CTkSwitch(
            theme_box, text="", width=44, command=self.switch_theme,
            button_color="#ffffff", button_hover_color="#d8d8e0")
        self.reg(self.theme_switch, fg="ACCENT")
        self.theme_switch.pack(side="left", padx=5)
        if self._theme_is_light():
            self.theme_switch.select()
        else:
            self.theme_switch.deselect()
        ctk.CTkLabel(theme_box, text="🌙", font=("Segoe UI Emoji", 15)).pack(side="left")

        ctk.CTkLabel(header, text="⚡ MultiClicker", font=("Segoe UI", 20, "bold"),
                     text_color=self.c("TEXT")).pack(side="left", padx=(14, 0))
        ctk.CTkLabel(header, text="循环点击 / 连点器", font=("Microsoft YaHei UI", 12),
                     text_color=self.c("TEXT3")).pack(side="left", padx=(8, 0), pady=(7, 0))

        self._status_role = "TEXT2"
        self.status_badge = ctk.CTkLabel(header, text="●  空闲", width=104, height=30,
                                         corner_radius=8,
                                         font=("Microsoft YaHei UI", 13, "bold"))
        self.reg(self.status_badge, fg="CARD2", text="TEXT2")
        self.status_badge.pack(side="right", padx=(0, 10))

        self.cursor_label = ctk.CTkLabel(header, text="(0, 0)", height=30,
                                         corner_radius=8, width=130,
                                         font=("Consolas", 12))
        self.reg(self.cursor_label, fg="CARD2", text="TEXT2")
        self.cursor_label.pack(side="right", padx=6)

        # 模式切换
        self.tabs = ctk.CTkTabview(self, fg_color="transparent", corner_radius=14,
                                   segmented_button_selected_color=self.c("ACCENT"),
                                   segmented_button_selected_hover_color=self.c("ACCENT_HOV"),
                                   segmented_button_unselected_color=self.c("CARD2"),
                                   segmented_button_unselected_hover_color=self.c("BORDER"),
                                   text_color=self.c("TEXT2"))
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(8, 4))
        self.tab_loop = self.tabs.add("🔄  循环点击")
        self.tab_spam = self.tabs.add("⚡  连点器")
        self._build_loop_tab(self.tab_loop)
        self._build_spam_tab(self.tab_spam)

        # 底部:统计 + 日志
        bottom = ctk.CTkFrame(self, corner_radius=14)
        self.reg(bottom, fg="CARD")
        bottom.pack(fill="x", padx=20, pady=(4, 4))

        lh2 = ctk.CTkFrame(bottom, fg_color="transparent")
        lh2.pack(fill="x", padx=16, pady=(8, 0))
        ctk.CTkLabel(lh2, text="日志", font=("Microsoft YaHei UI", 12, "bold"),
                     text_color=self.c("TEXT2")).pack(side="left")
        self.stats_label = ctk.CTkLabel(lh2, text="", font=("Microsoft YaHei UI", 11))
        self.reg(self.stats_label, text="TEXT3")
        self.stats_label.pack(side="right")
        self.log_box = ctk.CTkTextbox(bottom, height=64, corner_radius=8,
                                      font=("Consolas", 11), wrap="word")
        self.reg(self.log_box, fg="BG")
        self.log_box.pack(fill="x", padx=12, pady=(4, 10))
        self.log_box._textbox.tag_configure("ok", foreground=self.c("GREEN"))
        self.log_box._textbox.tag_configure("info", foreground=self.c("TEXT2"))
        self.log_box._textbox.tag_configure("err", foreground=self.c("RED"))

        # 底部:热键说明栏
        hotbar = ctk.CTkFrame(self, fg_color="transparent")
        hotbar.pack(fill="x", padx=20, pady=(0, 14))
        ctk.CTkLabel(hotbar, text="操作键:", font=("Microsoft YaHei UI", 12, "bold"),
                     text_color=self.c("TEXT2")).pack(side="left", padx=(2, 8))
        for key, desc in (("F8", "录制位置"), ("F9", "开始 / 停止"), ("F10", "清空"), ("ESC", "紧急停止")):
            cap = ctk.CTkFrame(hotbar, corner_radius=8)
            self.reg(cap, fg="CARD2")
            cap.pack(side="left", padx=4)
            ctk.CTkLabel(cap, text=key, font=("Consolas", 12, "bold"),
                         text_color=self.c("ACCENT"), width=40).pack(side="left", padx=(6, 2), pady=3)
            ctk.CTkLabel(cap, text=desc, font=("Microsoft YaHei UI", 11),
                         text_color=self.c("TEXT2")).pack(side="left", padx=(0, 8))

    def _row_box(self, parent, label_text, widget_factory, padx=16, pady=(4, 8)):
        """带背景的行容器:左侧说明文字 + 右侧控件,与分段按钮同高"""
        wrap = ctk.CTkFrame(parent, corner_radius=10)
        self.reg(wrap, fg="CARD2")
        wrap.pack(fill="x", padx=padx, pady=pady)
        ctk.CTkLabel(wrap, text=label_text, font=("Microsoft YaHei UI", 12),
                     text_color=self.c("TEXT2")).pack(side="left", padx=(12, 0), pady=8)
        widget_factory(wrap).pack(side="right", padx=(0, 6), pady=3)
        return wrap

    # ---------- 循环点击页 ----------
    def _build_loop_tab(self, tab):
        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True, pady=6)

        left = ctk.CTkFrame(body, corner_radius=14)
        self.reg(left, fg="CARD")
        left.pack(side="left", fill="both", expand=True)

        lh = ctk.CTkFrame(left, fg_color="transparent")
        lh.pack(fill="x", padx=16, pady=(14, 6))
        self.count_title = ctk.CTkLabel(lh, text=f"点击位置 · {len(self.positions)}",
                                        font=("Microsoft YaHei UI", 15, "bold"),
                                        text_color=self.c("TEXT"))
        self.count_title.pack(side="left")
        ctk.CTkButton(lh, text="＋ 录制位置 (F8)", width=130, height=28, corner_radius=8,
                      fg_color=self.c("CARD2"), hover_color=self.c("BORDER"),
                      text_color=self.c("TEXT"), font=("Microsoft YaHei UI", 12),
                      command=self.record_position).pack(side="right")
        ctk.CTkButton(lh, text="清空 (F10)", width=86, height=28, corner_radius=8,
                      fg_color="transparent", hover_color=self.c("RED"),
                      text_color=self.c("TEXT3"), font=("Microsoft YaHei UI", 12),
                      command=self.clear_positions).pack(side="right", padx=(8, 0))

        self.list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.refresh_list()

        right = ctk.CTkFrame(body, corner_radius=14, width=250)
        self.reg(right, fg="CARD")
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        ctk.CTkLabel(right, text="点击设置", font=("Microsoft YaHei UI", 15, "bold"),
                     text_color=self.c("TEXT")).pack(padx=16, pady=(16, 10), anchor="w")

        def entry_block(parent, label, var, suffix="秒"):
            wrap = ctk.CTkFrame(parent, corner_radius=10)
            self.reg(wrap, fg="CARD2")
            wrap.pack(fill="x", padx=16, pady=(4, 8))
            ctk.CTkLabel(wrap, text=label, font=("Microsoft YaHei UI", 12),
                         text_color=self.c("TEXT2")).pack(side="left", padx=(12, 0))
            e = ctk.CTkEntry(wrap, textvariable=var, width=56, height=28, justify="center",
                             fg_color="transparent", border_width=0,
                             font=("Consolas", 13, "bold"))
            self.reg(e, text="TEXT")
            e.pack(side="right", padx=(0, 8))
            ctk.CTkLabel(wrap, text=suffix, font=("Microsoft YaHei UI", 11),
                         text_color=self.c("TEXT3")).pack(side="right")
            return e

        self.interval_var = ctk.StringVar(value=str(self.settings["interval"]))
        self.round_var = ctk.StringVar(value=str(self.settings["round_wait"]))
        self.delay_var = ctk.StringVar(value=str(self.settings["start_delay"]))
        entry_block(right, "位置间隔", self.interval_var)
        entry_block(right, "整轮等待", self.round_var)
        entry_block(right, "开始倒计时", self.delay_var)

        ctk.CTkLabel(right, text="鼠标按键", font=("Microsoft YaHei UI", 12),
                     text_color=self.c("TEXT2")).pack(padx=16, pady=(8, 4), anchor="w")
        self.button_var = ctk.StringVar(value=self.settings["button"])
        self._seg(right, ["左键", "右键"], self.button_var).pack(fill="x", padx=16)

        ctk.CTkLabel(right, text="点击类型", font=("Microsoft YaHei UI", 12),
                     text_color=self.c("TEXT2")).pack(padx=16, pady=(10, 4), anchor="w")
        self.type_var = ctk.StringVar(value=self.settings["click_type"])
        self._seg(right, ["单击", "双击"], self.type_var).pack(fill="x", padx=16)

        # 窗口置顶:与分段按钮同高的行样式
        self._row_box(right, "窗口置顶",
                      lambda p: ctk.CTkSwitch(p, text="", variable=self.topmost,
                                              command=self._toggle_topmost,
                                              progress_color=self.c("ACCENT"),
                                              button_color="#ffffff",
                                              button_hover_color="#d8d8e0"),
                      pady=(10, 0))

        self.loop_toggle_btn = ctk.CTkButton(right, text="▶  开始点击  (F9)", height=46,
                                             corner_radius=10, text_color="#ffffff",
                                             font=("Microsoft YaHei UI", 15, "bold"),
                                             command=self.toggle_clicking)
        self.reg(self.loop_toggle_btn, fg="ACCENT", hover="ACCENT_HOV")
        self.loop_toggle_btn.pack(fill="x", padx=16, pady=(18, 14))

    def _seg(self, parent, values, var):
        seg = ctk.CTkSegmentedButton(parent, values=values, variable=var, height=32,
                                     font=("Microsoft YaHei UI", 12))
        self.reg(seg, fg="CARD2", selected="ACCENT", sel_hover="ACCENT_HOV",
                 unselected="CARD2", unsel_hover="BORDER", text="TEXT2")
        return seg

    # ---------- 连点器页 ----------
    def _build_spam_tab(self, tab):
        card = ctk.CTkFrame(tab, corner_radius=14)
        self.reg(card, fg="CARD")
        card.pack(fill="both", expand=True, pady=6)

        ctk.CTkLabel(card, text="连点设置", font=("Microsoft YaHei UI", 16, "bold"),
                     text_color=self.c("TEXT")).pack(padx=24, pady=(20, 12), anchor="w")

        ctk.CTkLabel(card, text="点击位置", font=("Microsoft YaHei UI", 13),
                     text_color=self.c("TEXT2")).pack(padx=24, anchor="w")
        self.spam_pos_var = ctk.StringVar(value=self.settings["spam_pos_mode"])
        self._seg(card, ["跟随鼠标", "固定位置"], self.spam_pos_var).pack(
            padx=24, pady=(4, 8), anchor="w")

        self.fixed_row = ctk.CTkFrame(card, corner_radius=10)
        self.reg(self.fixed_row, fg="CARD2")
        self.fixed_row.pack(fill="x", padx=24, pady=(0, 8))
        self.fixed_label = ctk.CTkLabel(
            self.fixed_row,
            text=(f"固定位置: ({self.fixed_pos[0]}, {self.fixed_pos[1]})"
                  if self.fixed_pos else "未设置固定位置"),
            font=("Microsoft YaHei UI", 12))
        self.reg(self.fixed_label,
                 text="TEXT" if self.fixed_pos else "TEXT3")
        self.fixed_label.pack(side="left", padx=12, pady=8)
        ctk.CTkButton(self.fixed_row, text="设定 (F8)", width=92, height=26, corner_radius=8,
                      text_color="#ffffff", font=("Microsoft YaHei UI", 12),
                      command=self.record_fixed_pos).pack(side="right", padx=6)

        def field_row(parent, label, hint, var):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=6)
            ctk.CTkLabel(row, text=label, font=("Microsoft YaHei UI", 13),
                         text_color=self.c("TEXT2")).pack(side="left")
            if hint:
                ctk.CTkLabel(row, text=hint, font=("Microsoft YaHei UI", 11),
                             text_color=self.c("TEXT3")).pack(side="right", padx=(0, 8))
            e = ctk.CTkEntry(row, textvariable=var, width=80, height=32,
                             justify="center", border_width=1,
                             font=("Consolas", 13, "bold"))
            self.reg(e, fg="CARD2", border="BORDER", text="TEXT")
            e.pack(side="right")
            return e

        self.spam_interval_var = ctk.StringVar(value=str(self.settings["spam_interval_ms"]))
        field_row(card, "点击间隔(毫秒)", "ms(10=每秒约100次)", self.spam_interval_var)
        self.spam_max_var = ctk.StringVar(value=str(self.settings["spam_max"]))
        field_row(card, "点击次数(0=无限)", None, self.spam_max_var)

        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", padx=24, pady=6)
        ctk.CTkLabel(row3, text="鼠标按键", font=("Microsoft YaHei UI", 13),
                     text_color=self.c("TEXT2")).pack(side="left")
        self.spam_button_var = ctk.StringVar(value=self.settings["spam_button"])
        self._seg(row3, ["左键", "右键"], self.spam_button_var).pack(side="right")

        self._row_box(card, "窗口置顶",
                      lambda p: ctk.CTkSwitch(p, text="", variable=self.topmost,
                                              command=self._toggle_topmost,
                                              progress_color=self.c("ACCENT"),
                                              button_color="#ffffff",
                                              button_hover_color="#d8d8e0"),
                      padx=24, pady=(10, 0))

        self.spam_toggle_btn = ctk.CTkButton(card, text="▶  开始连点  (F9)", height=50,
                                             corner_radius=10, text_color="#ffffff",
                                             font=("Microsoft YaHei UI", 15, "bold"),
                                             command=self.toggle_clicking)
        self.reg(self.spam_toggle_btn, fg="ACCENT", hover="ACCENT_HOV")
        self.spam_toggle_btn.pack(fill="x", padx=24, pady=(18, 10))

        ctk.CTkLabel(card, text="提示:连点器立即开始,无倒计时;运行中按 ESC 或 F9 停止",
                     font=("Microsoft YaHei UI", 11), text_color=self.c("TEXT3")).pack(pady=(0, 16))

    def _toggle_topmost(self):
        self.attributes("-topmost", self.topmost.get())

    # ---------------- 状态与日志 ----------------
    def log(self, msg, level="info"):
        t = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{t}] {msg}\n", level)
        self.log_box.see("end")

    def set_status(self, role):
        """role: 'TEXT2'(空闲) / 'GREEN'(运行) / 'AMBER'(倒计时)"""
        self._status_role = role
        self.status_badge.configure(text={
            "TEXT2": "●  空闲", "GREEN": "●  运行中", "AMBER": "●  倒计时",
        }.get(role, "●  空闲"), text_color=self.c(role))

    def _tick_cursor(self):
        try:
            self.cursor_label.configure(text=f"鼠标 {self.mouse_ctrl.position}")
        except Exception:
            pass
        self.after(60, self._tick_cursor)

    def _current_tab(self):
        return self.tabs.get()

    # ---------------- 位置管理 ----------------
    def record_position(self):
        if self.clicking or self.countdown is not None:
            self.log("请先停止当前任务再录制", "err")
            return
        pos = self.mouse_ctrl.position
        self.positions.append(pos)
        self.refresh_list()
        self.log(f"录制 #{len(self.positions)}  位置 ({pos[0]}, {pos[1]})", "ok")
        beep(990, 60)

    def clear_positions(self):
        if self.clicking or self.countdown is not None:
            self.log("请先停止当前任务再清空", "err")
            return
        self.positions.clear()
        self.refresh_list()
        self.log("位置列表已清空")

    def refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.list_frame._parent_canvas.yview_moveto(0)
        self.count_title.configure(text=f"点击位置 · {len(self.positions)}")

        if not self.positions:
            hint = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            hint.pack(pady=52)
            ctk.CTkLabel(hint, text="◎", font=("Segoe UI", 42),
                         text_color=self.c("ACCENT")).pack()
            ctk.CTkLabel(hint, text="还没有点击位置", font=("Microsoft YaHei UI", 14, "bold"),
                         text_color=self.c("TEXT2")).pack(pady=(6, 2))
            ctk.CTkLabel(hint, text="把鼠标移到目标处,按 F8 录制(可录多个)\n全部录好后,按 F9 开始循环点击",
                         font=("Microsoft YaHei UI", 12), text_color=self.c("TEXT3"),
                         justify="center").pack()
        else:
            self.cards = []
            for i, p in enumerate(self.positions):
                card = PositionCard(self.list_frame, i, p, self)
                card.pack(fill="x", pady=3)
                self.cards.append(card)

    def record_fixed_pos(self):
        if self.clicking or self.countdown is not None:
            self.log("请先停止当前任务再设定", "err")
            return
        self.fixed_pos = self.mouse_ctrl.position
        self.fixed_label.configure(text=f"固定位置: ({self.fixed_pos[0]}, {self.fixed_pos[1]})",
                                   text_color=self.c("TEXT"))
        self.log(f"已设定固定位置 ({self.fixed_pos[0]}, {self.fixed_pos[1]})", "ok")
        beep(990, 60)

    def clear_fixed_pos(self):
        self.fixed_pos = None
        self.fixed_label.configure(text="未设置固定位置", text_color=self.c("TEXT3"))
        self.log("已清除固定位置")

    # ---------------- 读取设置 ----------------
    def _read_loop_settings(self):
        try:
            interval = float(self.interval_var.get())
            round_wait = float(self.round_var.get())
            delay = int(float(self.delay_var.get()))
        except ValueError:
            self.log("间隔必须填写数字", "err")
            return None
        cfg = {
            "interval": max(0.1, interval),
            "round_wait": max(0.0, round_wait),
            "start_delay": max(0, min(60, delay)),
            "left": self.button_var.get() == "左键",
            "double": self.type_var.get() == "双击",
        }
        self.settings.update({
            "interval": cfg["interval"], "round_wait": cfg["round_wait"],
            "start_delay": cfg["start_delay"],
            "button": self.button_var.get(), "click_type": self.type_var.get(),
        })
        self._save_settings()
        return cfg

    def _read_spam_settings(self):
        try:
            ms = float(self.spam_interval_var.get())
            maxn = int(float(self.spam_max_var.get()))
        except ValueError:
            self.log("间隔/次数必须填写数字", "err")
            return None
        if self.spam_pos_var.get() == "固定位置" and self.fixed_pos is None:
            self.log("请先设定固定位置(F8)", "err")
            return None
        cfg = {
            "interval": max(0.005, ms / 1000.0),
            "max_clicks": max(0, maxn),
            "fixed": self.fixed_pos if self.spam_pos_var.get() == "固定位置" else None,
            "left": self.spam_button_var.get() == "左键",
        }
        self.settings.update({
            "spam_interval_ms": ms, "spam_max": maxn,
            "spam_pos_mode": self.spam_pos_var.get(),
            "spam_button": self.spam_button_var.get(),
        })
        self._save_settings()
        return cfg

    # ---------------- 开始 / 停止 ----------------
    def toggle_clicking(self):
        if self.clicking:
            self.stop_clicking("已手动停止")
            return
        if self.countdown is not None:
            self.cancel_countdown()
            return
        if self._current_tab() == "🔄  循环点击":
            if not self.positions:
                self.log("请先录制至少一个位置", "err")
                return
            cfg = self._read_loop_settings()
            if not cfg:
                return
            self._start_countdown(cfg)
        else:
            cfg = self._read_spam_settings()
            if not cfg:
                return
            self._launch_spam(cfg)

    def _start_countdown(self, cfg):
        if cfg["start_delay"] == 0:
            self._launch_loop(cfg)
            return
        self.countdown = cfg["start_delay"]
        self._set_loop_btn_countdown(True)
        self.set_status("AMBER")
        beep(700, 50)
        self._countdown_tick(cfg)

    def _countdown_tick(self, cfg):
        if self.countdown is None:
            return
        if self.countdown <= 0:
            self.countdown = None
            self._set_loop_btn_countdown(False)
            self._launch_loop(cfg)
            return
        self.loop_toggle_btn.configure(text=f"⏳ {self.countdown} 秒后开始(点击取消)")
        self.set_status("AMBER")
        self.countdown -= 1
        self.after(1000, lambda: self._countdown_tick(cfg))

    def cancel_countdown(self):
        self.countdown = None
        self._set_loop_btn_countdown(False)
        self.set_status("TEXT2")
        self.log("已取消")

    def _set_loop_btn_countdown(self, on):
        if on:
            self.loop_toggle_btn.configure(fg_color=self.c("AMBER"),
                                           hover_color=self.c("AMBER"),
                                           text_color="#ffffff")
        else:
            self.loop_toggle_btn.configure(fg_color=self.c("ACCENT"),
                                           hover_color=self.c("ACCENT_HOV"),
                                           text_color="#ffffff",
                                           text="▶  开始点击  (F9)")

    def _set_running_ui(self, running):
        btn_text = "⏹  停止点击  (F9 / ESC)" if running else "▶  开始点击  (F9)"
        fg, hov = (self.c("RED"), "#e05a5a") if running else \
                  (self.c("ACCENT"), self.c("ACCENT_HOV"))
        self.loop_toggle_btn.configure(text=btn_text, fg_color=fg, hover_color=hov)
        self.spam_toggle_btn.configure(
            text="⏹  停止连点  (F9 / ESC)" if running else "▶  开始连点  (F9)",
            fg_color=fg, hover_color=hov)

    def _launch_loop(self, cfg):
        self.clicking = True
        self.total_clicks = 0
        self.set_status("GREEN")
        self._set_running_ui(True)
        self.log(f"开始循环 {len(self.positions)} 个位置 · 间隔 {cfg['interval']}s · "
                 f"整轮等待 {cfg['round_wait']}s", "ok")
        self.stats_label.configure(text=f"本轮 0 / {len(self.positions)}  ·  总点击 0")
        threading.Thread(target=self._click_loop, args=(cfg,), daemon=True).start()

    def _launch_spam(self, cfg):
        self.clicking = True
        self.total_clicks = 0
        self.spam_start_time = time.time()
        self.set_status("GREEN")
        self._set_running_ui(True)
        pos_desc = "跟随鼠标" if cfg["fixed"] is None else f"({cfg['fixed'][0]}, {cfg['fixed'][1]})"
        self.log(f"开始连点 · 位置: {pos_desc} · 间隔 {cfg['interval'] * 1000:.0f}ms", "ok")
        self.stats_label.configure(text="CPS 0.0 · 总点击 0")
        threading.Thread(target=self._spam_loop, args=(cfg,), daemon=True).start()

    def stop_clicking(self, reason=""):
        self.clicking = False
        self.set_status("TEXT2")
        self._set_running_ui(False)
        self._unhighlight_all()
        if reason:
            self.log(reason)
        self.log(f"本次共点击 {self.total_clicks} 次")
        self.stats_label.configure(text=f"总点击 {self.total_clicks}")

    def emergency_stop(self):
        if self.clicking:
            self.stop_clicking("ESC 紧急停止")
        elif self.countdown is not None:
            self.cancel_countdown()

    # ---------------- 循环点击线程 ----------------
    def _click_loop(self, cfg):
        idx = 0
        while self.clicking:
            x, y = self.positions[idx]
            self.mouse_ctrl.position = (x, y)
            time.sleep(0.08)
            self._do_click(cfg["left"], cfg["double"])
            self.total_clicks += 1
            self.after(0, self._on_click_done, idx, x, y)
            idx = (idx + 1) % len(self.positions)
            time.sleep(cfg["interval"])
            if idx == 0:
                time.sleep(cfg["round_wait"])

    def _on_click_done(self, idx, x, y):
        self.log(f"点击 #{idx + 1} ({x}, {y})", "ok")
        self.stats_label.configure(text=f"本轮 {idx + 1} / {len(self.positions)}  ·  "
                                        f"总点击 {self.total_clicks}")
        self._highlight(idx)

    def _highlight(self, idx):
        self._unhighlight_all()
        if idx < len(self.cards):
            self.cards[idx].highlight(True)

    def _unhighlight_all(self):
        for c in self.cards:
            c.highlight(False)

    # ---------------- 连点线程 ----------------
    def _spam_loop(self, cfg):
        while self.clicking:
            if cfg["fixed"] is not None:
                self.mouse_ctrl.position = cfg["fixed"]
            self._do_click(cfg["left"], False)
            self.total_clicks += 1
            if self.total_clicks % 5 == 0:
                self.after(0, self._on_spam_done)
            if cfg["max_clicks"] and self.total_clicks >= cfg["max_clicks"]:
                self.after(0, lambda: self.stop_clicking("已完成设定次数"))
                return
            time.sleep(cfg["interval"])

    def _on_spam_done(self):
        dt = max(0.001, time.time() - self.spam_start_time)
        cps = self.total_clicks / dt
        self.stats_label.configure(text=f"CPS {cps:.1f} · 总点击 {self.total_clicks}")

    def _do_click(self, left, double):
        btn = mouse.Button.left if left else mouse.Button.right
        self.mouse_ctrl.click(btn, 1)
        if double:
            time.sleep(0.05)
            self.mouse_ctrl.click(btn, 1)

    # ---------------- 热键 ----------------
    def _start_hotkeys(self):
        self.hotkeys = keyboard.GlobalHotKeys({
            "<f8>": lambda: self.after(0, self._hotkey_f8),
            "<f9>": lambda: self.after(0, self.toggle_clicking),
            "<f10>": lambda: self.after(0, self._hotkey_f10),
            "<esc>": lambda: self.after(0, self.emergency_stop),
        })
        self.hotkeys.start()

    def _hotkey_f8(self):
        if self._current_tab() == "🔄  循环点击":
            self.record_position()
        else:
            self.record_fixed_pos()

    def _hotkey_f10(self):
        if self._current_tab() == "🔄  循环点击":
            self.clear_positions()
        else:
            self.clear_fixed_pos()

    def on_closing(self):
        self.clicking = False
        self.countdown = None
        self.hotkeys.stop()
        self.destroy()


def main():
    app = MultiClickerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
