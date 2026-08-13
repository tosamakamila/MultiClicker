# -*- coding: utf-8 -*-
"""
MultiClicker - 多位置循环点击器
录制多个屏幕位置,依次循环定时点击。

热键:
  F8   录制当前鼠标位置
  F9   开始 / 停止(带倒计时)
  F10  清空位置列表
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

# ---------- 配色(浅色暖色调) ----------
BG          = "#f8f3ea"
CARD        = "#ffffff"
CARD2       = "#f3ecdf"
BORDER      = "#e6dac4"
ACCENT      = "#e8824f"
ACCENT_HOV  = "#d96f3d"
GREEN       = "#3f9d6e"
GREEN_DIM   = "#e6f3ec"
AMBER       = "#e0a03c"
AMBER_DIM   = "#f9efdb"
RED         = "#de5c5c"
TEXT        = "#433b30"
TEXT2       = "#857a6b"
TEXT3       = "#b3a793"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def beep(freq=880, ms=80):
    if winsound:
        try:
            winsound.Beep(freq, ms)
        except Exception:
            pass


class PositionCard(ctk.CTkFrame):
    """单个位置卡片,支持高亮当前点击项"""

    def __init__(self, master, index, pos, app):
        super().__init__(master, fg_color=CARD2, corner_radius=10, height=44)
        self.app = app
        self.index = index
        self.pos = pos
        self.pack_propagate(False)

        self.num = ctk.CTkLabel(self, text=f"{index + 1:02d}", width=34,
                                font=("Consolas", 14, "bold"), text_color=ACCENT)
        self.num.pack(side="left", padx=(12, 4))
        self.coord = ctk.CTkLabel(self, text=f"({pos[0]}, {pos[1]})",
                                  font=("Consolas", 13), text_color=TEXT)
        self.coord.pack(side="left", padx=4)

        for txt, cmd in (("▲", self.move_up), ("▼", self.move_down)):
            ctk.CTkButton(self, text=txt, width=26, height=26, corner_radius=6,
                          fg_color="transparent", hover_color=BORDER,
                          text_color=TEXT3, font=("Consolas", 11),
                          command=cmd).pack(side="right", padx=2)
        ctk.CTkButton(self, text="✕", width=26, height=26, corner_radius=6,
                      fg_color="transparent", hover_color=RED,
                      text_color=TEXT3, font=("Consolas", 12),
                      command=self.delete).pack(side="right", padx=(2, 8))

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
            self.configure(fg_color=GREEN_DIM, border_width=2, border_color=GREEN)
            self.num.configure(text_color=GREEN)
            self.coord.configure(text_color="#2f6b4f")
        else:
            self.configure(fg_color=CARD2, border_width=0)
            self.num.configure(text_color=ACCENT)
            self.coord.configure(text_color=TEXT)


class MultiClickerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MultiClicker · 多位置循环点击器")
        self.geometry("780x600")
        self.minsize(700, 520)
        self.configure(fg_color=BG)

        self.positions = []
        self.cards = []
        self.clicking = False
        self.countdown = None          # 剩余倒计时秒数,None 表示未倒计时
        self.total_clicks = 0
        self.topmost = ctk.BooleanVar(value=False)
        self.mouse_ctrl = mouse.Controller()

        self._load_settings()
        self._build_ui()
        self._start_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(60, self._tick_cursor)

    # ---------------- 设置持久化 ----------------
    def _load_settings(self):
        self.settings = {
            "interval": 2.0, "round_wait": 5.0, "start_delay": 3,
            "button": "左键", "click_type": "单击",
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
        # 顶部
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 6))

        ctk.CTkLabel(header, text="⚡ MultiClicker", font=("Segoe UI", 21, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(header, text="多位置循环点击", font=("Microsoft YaHei UI", 12),
                     text_color=TEXT3).pack(side="left", padx=(10, 0), pady=(8, 0))

        self.status_badge = ctk.CTkLabel(header, text="●  空闲", width=104, height=30,
                                         corner_radius=8, fg_color=CARD2,
                                         text_color=TEXT2, font=("Microsoft YaHei UI", 13, "bold"))
        self.status_badge.pack(side="right", padx=(0, 10))

        self.cursor_label = ctk.CTkLabel(header, text="(0, 0)", fg_color=CARD2, height=30,
                                         corner_radius=8, width=130,
                                         font=("Consolas", 12), text_color=TEXT2)
        self.cursor_label.pack(side="right", padx=6)

        # 主体
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(8, 4))

        # 左侧:位置列表
        left = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14)
        left.pack(side="left", fill="both", expand=True)

        lh = ctk.CTkFrame(left, fg_color="transparent")
        lh.pack(fill="x", padx=16, pady=(14, 6))
        self.count_title = ctk.CTkLabel(lh, text="点击位置 · 0", font=("Microsoft YaHei UI", 15, "bold"),
                                        text_color=TEXT)
        self.count_title.pack(side="left")
        ctk.CTkButton(lh, text="＋ 录制位置 (F8)", width=130, height=28, corner_radius=8,
                      fg_color=CARD2, hover_color=BORDER, text_color=TEXT,
                      font=("Microsoft YaHei UI", 12), command=self.record_position).pack(side="right")
        ctk.CTkButton(lh, text="清空 (F10)", width=86, height=28, corner_radius=8,
                      fg_color="transparent", hover_color=RED, text_color=TEXT3,
                      font=("Microsoft YaHei UI", 12), command=self.clear_positions).pack(side="right", padx=(8, 0))

        self.list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self._show_empty_hint()

        # 右侧:设置
        right = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14, width=250)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)

        ctk.CTkLabel(right, text="点击设置", font=("Microsoft YaHei UI", 15, "bold"),
                     text_color=TEXT).pack(padx=16, pady=(16, 10), anchor="w")

        def entry_block(parent, label, var, suffix="秒"):
            wrap = ctk.CTkFrame(parent, fg_color=CARD2, corner_radius=10)
            wrap.pack(fill="x", padx=16, pady=(4, 8))
            ctk.CTkLabel(wrap, text=label, font=("Microsoft YaHei UI", 12),
                         text_color=TEXT2).pack(side="left", padx=(12, 0))
            e = ctk.CTkEntry(wrap, textvariable=var, width=56, height=28, justify="center",
                             fg_color="transparent", border_width=0,
                             font=("Consolas", 13, "bold"), text_color=TEXT)
            e.pack(side="right", padx=(0, 8))
            ctk.CTkLabel(wrap, text=suffix, font=("Microsoft YaHei UI", 11),
                         text_color=TEXT3).pack(side="right")
            return e

        self.interval_var = ctk.StringVar(value=str(self.settings["interval"]))
        self.round_var = ctk.StringVar(value=str(self.settings["round_wait"]))
        self.delay_var = ctk.StringVar(value=str(self.settings["start_delay"]))
        entry_block(right, "位置间隔", self.interval_var)
        entry_block(right, "整轮等待", self.round_var)
        entry_block(right, "开始倒计时", self.delay_var)

        ctk.CTkLabel(right, text="鼠标按键", font=("Microsoft YaHei UI", 12),
                     text_color=TEXT2).pack(padx=16, pady=(8, 4), anchor="w")
        self.button_var = ctk.StringVar(value=self.settings["button"])
        ctk.CTkSegmentedButton(right, values=["左键", "右键"], variable=self.button_var,
                               height=32, font=("Microsoft YaHei UI", 12),
                               fg_color=CARD2, selected_color=ACCENT,
                               selected_hover_color=ACCENT_HOV,
                               unselected_color=CARD2, unselected_hover_color=BORDER,
                               text_color=TEXT2).pack(fill="x", padx=16)

        ctk.CTkLabel(right, text="点击类型", font=("Microsoft YaHei UI", 12),
                     text_color=TEXT2).pack(padx=16, pady=(12, 4), anchor="w")
        self.type_var = ctk.StringVar(value=self.settings["click_type"])
        ctk.CTkSegmentedButton(right, values=["单击", "双击"], variable=self.type_var,
                               height=32, font=("Microsoft YaHei UI", 12),
                               fg_color=CARD2, selected_color=ACCENT,
                               selected_hover_color=ACCENT_HOV,
                               unselected_color=CARD2, unselected_hover_color=BORDER,
                               text_color=TEXT2).pack(fill="x", padx=16)

        ctk.CTkCheckBox(right, text="窗口置顶", variable=self.topmost,
                        command=self._toggle_topmost, font=("Microsoft YaHei UI", 12),
                        text_color=TEXT2, checkbox_width=20, checkbox_height=20,
                        corner_radius=5, fg_color=ACCENT, hover_color=ACCENT_HOV,
                        border_color=BORDER, border_width=2).pack(padx=16, pady=(14, 0), anchor="w")

        # 开始按钮
        self.toggle_btn = ctk.CTkButton(right, text="▶  开始点击  (F9)", height=46,
                                        corner_radius=10, fg_color=ACCENT,
                                        hover_color=ACCENT_HOV, text_color="#ffffff",
                                        font=("Microsoft YaHei UI", 15, "bold"),
                                        command=self.toggle_clicking)
        self.toggle_btn.pack(fill="x", padx=16, pady=(18, 6))

        self.stats_label = ctk.CTkLabel(right, text="本轮 0 / 0  ·  总点击 0",
                                        font=("Microsoft YaHei UI", 11), text_color=TEXT3)
        self.stats_label.pack(pady=(0, 8))

        # 底部:日志
        logf = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14)
        logf.pack(fill="x", padx=20, pady=(4, 16))
        lh2 = ctk.CTkFrame(logf, fg_color="transparent")
        lh2.pack(fill="x", padx=16, pady=(8, 0))
        ctk.CTkLabel(lh2, text="日志", font=("Microsoft YaHei UI", 12, "bold"),
                     text_color=TEXT2).pack(side="left")
        ctk.CTkButton(lh2, text="清空", width=52, height=22, corner_radius=6,
                      fg_color="transparent", hover_color=BORDER, text_color=TEXT3,
                      font=("Microsoft YaHei UI", 11),
                      command=lambda: self.log_box.delete("1.0", "end")).pack(side="right")
        self.log_box = ctk.CTkTextbox(logf, height=74, fg_color=BG, corner_radius=8,
                                      font=("Consolas", 11), wrap="word")
        self.log_box.pack(fill="x", padx=12, pady=10)

        # 底部:热键说明栏(始终可见)
        hotbar = ctk.CTkFrame(self, fg_color="transparent")
        hotbar.pack(fill="x", padx=20, pady=(0, 14))
        ctk.CTkLabel(hotbar, text="操作键:", font=("Microsoft YaHei UI", 12, "bold"),
                     text_color=TEXT2).pack(side="left", padx=(2, 8))
        for key, desc in (("F8", "录制位置"), ("F9", "开始 / 停止"), ("F10", "清空列表"), ("ESC", "紧急停止")):
            cap = ctk.CTkFrame(hotbar, fg_color=CARD2, corner_radius=8)
            cap.pack(side="left", padx=4)
            ctk.CTkLabel(cap, text=key, font=("Consolas", 12, "bold"),
                         text_color=ACCENT, width=40).pack(side="left", padx=(6, 2), pady=3)
            ctk.CTkLabel(cap, text=desc, font=("Microsoft YaHei UI", 11),
                         text_color=TEXT2).pack(side="left", padx=(0, 8))

    def _show_empty_hint(self):
        hint = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        hint.pack(pady=52)
        ctk.CTkLabel(hint, text="◎", font=("Segoe UI", 42), text_color=ACCENT).pack()
        ctk.CTkLabel(hint, text="还没有点击位置", font=("Microsoft YaHei UI", 14, "bold"),
                     text_color=TEXT2).pack(pady=(6, 2))
        ctk.CTkLabel(hint, text="把鼠标移到目标处,按 F8 录制(可录多个)\n全部录好后,按 F9 开始循环点击",
                     font=("Microsoft YaHei UI", 12), text_color=TEXT3,
                     justify="center").pack()

    def _toggle_topmost(self):
        self.attributes("-topmost", self.topmost.get())

    # ---------------- 状态与日志 ----------------
    def log(self, msg, color=TEXT2):
        t = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{t}] {msg}\n", color)
        self.log_box.see("end")

    def set_status(self, text, color):
        self.status_badge.configure(text=text, text_color=color)

    def _tick_cursor(self):
        try:
            self.cursor_label.configure(text=f"鼠标 {self.mouse_ctrl.position}")
        except Exception:
            pass
        self.after(60, self._tick_cursor)

    # ---------------- 位置管理 ----------------
    def record_position(self):
        if self.clicking or self.countdown is not None:
            self.log("请先停止当前任务再录制", RED)
            return
        pos = self.mouse_ctrl.position
        self.positions.append(pos)
        self.refresh_list()
        self.log(f"录制 #{len(self.positions)}  位置 ({pos[0]}, {pos[1]})", GREEN)
        beep(990, 60)

    def clear_positions(self):
        if self.clicking or self.countdown is not None:
            self.log("请先停止当前任务再清空", RED)
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
            self._show_empty_hint()
        else:
            self.cards = []
            for i, p in enumerate(self.positions):
                card = PositionCard(self.list_frame, i, p, self)
                card.pack(fill="x", pady=3)
                self.cards.append(card)

    # ---------------- 设置解析 ----------------
    def _read_settings(self):
        try:
            interval = float(self.interval_var.get())
            round_wait = float(self.round_var.get())
            delay = int(float(self.delay_var.get()))
        except ValueError:
            self.log("间隔必须填写数字", RED)
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

    # ---------------- 开始 / 停止 ----------------
    def toggle_clicking(self):
        if self.clicking:
            self.stop_clicking("已手动停止")
            return
        if self.countdown is not None:
            self.cancel_countdown()
            return
        if not self.positions:
            self.log("请先录制至少一个位置", RED)
            return
        cfg = self._read_settings()
        if not cfg:
            return
        self._start_countdown(cfg)

    def _start_countdown(self, cfg):
        if cfg["start_delay"] == 0:
            self._launch(cfg)
            return
        self.countdown = cfg["start_delay"]
        self._set_countdown_ui(True)
        self.set_status(f"●  倒计时 {self.countdown}", AMBER)
        beep(700, 50)
        self._countdown_tick(cfg)

    def _countdown_tick(self, cfg):
        if self.countdown is None:
            return
        if self.countdown <= 0:
            self.countdown = None
            self._set_countdown_ui(False)
            self._launch(cfg)
            return
        self.toggle_btn.configure(text=f"⏳ {self.countdown} 秒后开始(点击取消)")
        self.countdown -= 1
        self.after(1000, lambda: self._countdown_tick(cfg))

    def cancel_countdown(self):
        self.countdown = None
        self._set_countdown_ui(False)
        self.set_status("●  空闲", TEXT2)
        self.log("已取消")

    def _set_countdown_ui(self, on):
        if on:
            self.toggle_btn.configure(fg_color=AMBER, hover_color=AMBER, text_color="#1a1a1a")
            self.record_btn_state(False)
        else:
            self.toggle_btn.configure(fg_color=ACCENT, hover_color=ACCENT_HOV,
                                      text_color="#ffffff", text="▶  开始点击  (F9)")
            self.record_btn_state(True)

    def record_btn_state(self, state):
        pass  # 录制按钮在刷新列表中重建,无需禁用

    def _launch(self, cfg):
        self.clicking = True
        self.total_clicks = 0
        self.set_status("●  运行中", GREEN)
        self.toggle_btn.configure(text="⏹  停止点击  (F9 / ESC)", fg_color=RED,
                                  hover_color="#e05a5a")
        self.log(f"开始循环 {len(self.positions)} 个位置 · 间隔 {cfg['interval']}s · "
                 f"整轮等待 {cfg['round_wait']}s", GREEN)
        self.stats_label.configure(text=f"本轮 0 / {len(self.positions)}  ·  总点击 0")
        threading.Thread(target=self._click_loop, args=(cfg,), daemon=True).start()

    def stop_clicking(self, reason=""):
        self.clicking = False
        self.set_status("●  空闲", TEXT2)
        self.toggle_btn.configure(text="▶  开始点击  (F9)", fg_color=ACCENT,
                                  hover_color=ACCENT_HOV, text_color="#ffffff")
        self._unhighlight_all()
        if reason:
            self.log(reason)
        self.log(f"本次共点击 {self.total_clicks} 次")

    def emergency_stop(self):
        if self.clicking:
            self.stop_clicking("ESC 紧急停止")
        elif self.countdown is not None:
            self.cancel_countdown()

    # ---------------- 点击循环 ----------------
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
        self.log(f"点击 #{idx + 1} ({x}, {y})", GREEN)
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

    def _do_click(self, left, double):
        btn = mouse.Button.left if left else mouse.Button.right
        self.mouse_ctrl.click(btn, 1)
        if double:
            time.sleep(0.05)
            self.mouse_ctrl.click(btn, 1)

    # ---------------- 热键 ----------------
    def _start_hotkeys(self):
        self.hotkeys = keyboard.GlobalHotKeys({
            "<f8>": lambda: self.after(0, self.record_position),
            "<f9>": lambda: self.after(0, self.toggle_clicking),
            "<f10>": lambda: self.after(0, self.clear_positions),
            "<esc>": lambda: self.after(0, self.emergency_stop),
        })
        self.hotkeys.start()

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
