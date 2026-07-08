# -*- coding: utf-8 -*-
"""
防熄屏 / 防锁屏 现代版 (Windows)，白色主题
- 圆角置顶悬浮卡片，可拖动；一键开关；键盘/鼠标/API/组合 四模式；间隔默认 60s
- 两个全局热键：显隐窗口(Ctrl+Alt+S)、开关防锁屏(Ctrl+Alt+D)，可自定义
- 标题栏「缩小」折叠成 mini 台灯（透明镂空，开=亮灯+光束，关=熄灯），单击开关/拖动/右键还原
- 最小化到托盘；配置自动持久化
- 附加：开机自启、启动即开启、间隔随机抖动(反检测)、鼠标模式不抢操作、切换提示、会话计时+上次时长
"""

import os
import sys
import json
import time
import queue
import random
import subprocess
import threading
import ctypes
from ctypes import wintypes
import winsound
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray
from pystray import Menu, MenuItem

# ================== 配色 / 常量 ==================
FONT = "Microsoft YaHei UI"
TRANSPARENT = "#0b0c10"
CARD_BG = "#ffffff"
BORDER = "#e6e8eb"
TEXT = "#1f2328"
MUTED = "#6b7280"
ACCENT = "#22c55e"
ACCENT_H = "#16a34a"
RED = "#ef4444"
RED_H = "#dc2626"
CHIP_FG = "#f1f3f5"
CHIP_SEL = "#e7f7ee"
CHIP_HOVER = "#e9ecef"
CHIP_ICON = "#4b5563"
HEADER_ICON = "#6b7280"
HOVER_CLOSE = "#fde2e2"
HOVER_SOFT = "#eef0f2"
DOT_OFF = "#c2c6cc"
HINT = "#9aa0a6"
ENTRY_BORDER = "#dcdfe3"
ENTRY_BG = "#f7f8fa"
SW_TRACK = "#cbd5e1"

FULL_W, FULL_H = 300, 520
MINI_W = MINI_H = 80

MODE_LABELS = {"keyboard": "键盘", "mouse": "鼠标", "api": "API", "hybrid": "键盘+API"}

# ================== Windows API ==================
PUL = ctypes.POINTER(wintypes.ULONG)
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_MOVE = 0x0001
VK_F15 = 0x7E
CREATE_NO_WINDOW = 0x08000000


class _KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", PUL)]


class _MouseInput(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", PUL)]


class _HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _InputUnion(ctypes.Union):
    _fields_ = [("ki", _KeyBdInput), ("mi", _MouseInput), ("hi", _HardwareInput)]


class _Input(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _InputUnion)]


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_Input), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetCursorPos.argtypes = (ctypes.POINTER(_Point),)
user32.GetCursorPos.restype = wintypes.BOOL

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
kernel32.SetThreadExecutionState.argtypes = (wintypes.DWORD,)
kernel32.SetThreadExecutionState.restype = wintypes.DWORD

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001


class _Msg(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD), ("pt", wintypes.POINT)]


user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = (ctypes.POINTER(_Msg), wintypes.HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT)
user32.PeekMessageW.restype = wintypes.BOOL

# 多显示器 / 工作区（排除任务栏），用于精确夹紧窗口位置
MONITOR_DEFAULTTONEAREST = 0x00000002


class _MonitorInfoEx(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
                ("szDevice", wintypes.WCHAR * 32)]


user32.MonitorFromPoint.argtypes = (wintypes.POINT, wintypes.DWORD)
user32.MonitorFromPoint.restype = wintypes.HANDLE
user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.POINTER(_MonitorInfoEx))
user32.GetMonitorInfoW.restype = wintypes.BOOL


def press_key(vk):
    extra = PUL(wintypes.ULONG(0))
    down = _Input()
    down.type = INPUT_KEYBOARD
    down.ki.wVk = vk
    down.ki.dwExtraInfo = extra
    up = _Input()
    up.type = INPUT_KEYBOARD
    up.ki.wVk = vk
    up.ki.dwFlags = KEYEVENTF_KEYUP
    up.ki.dwExtraInfo = extra
    arr = (_Input * 2)()
    arr[0] = down
    arr[1] = up
    user32.SendInput(2, arr, ctypes.sizeof(_Input))


def mouse_jiggle(dx=1, dy=1):
    extra = PUL(wintypes.ULONG(0))
    for mx, my in ((dx, dy), (-dx, -dy)):
        inp = _Input()
        inp.type = INPUT_MOUSE
        inp.mi.dx = mx
        inp.mi.dy = my
        inp.mi.dwFlags = MOUSEEVENTF_MOVE
        inp.mi.dwExtraInfo = extra
        user32.SendInput(1, (_Input * 1)(inp), ctypes.sizeof(_Input))
        time.sleep(0.02)


def get_cursor_pos():
    pt = _Point()
    user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


def api_set():
    kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)


def api_clear():
    kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def beep(on):
    try:
        winsound.Beep(880 if on else 620, 140)
    except Exception:
        pass


def fmt_dur(s):
    s = int(s)
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


# ================== 图标绘制 ==================
def make_icon(name, color):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if name == "power":
        d.arc([12, 10, 52, 50], start=135, end=360, fill=color, width=6)
        d.arc([12, 10, 52, 50], start=0, end=45, fill=color, width=6)
        d.line([32, 12, 32, 30], fill=color, width=6)
    elif name == "keyboard":
        d.rounded_rectangle([8, 20, 56, 48], radius=8, outline=color, width=4)
        for x in (16, 28, 40):
            d.rounded_rectangle([x, 26, x + 9, 31], radius=2, fill=color)
            d.rounded_rectangle([x, 35, x + 9, 40], radius=2, fill=color)
        d.rounded_rectangle([22, 44, 42, 47], radius=2, fill=color)
    elif name == "mouse":
        d.rounded_rectangle([22, 8, 42, 56], radius=12, outline=color, width=4)
        d.line([32, 15, 32, 27], fill=color, width=4)
    elif name == "cpu":
        d.rounded_rectangle([16, 16, 48, 48], radius=7, outline=color, width=4)
        d.rounded_rectangle([26, 26, 38, 38], radius=3, outline=color, width=3)
        for p in (22, 32, 42):
            d.line([p, 8, p, 16], fill=color, width=3)
            d.line([p, 48, p, 56], fill=color, width=3)
            d.line([8, p, 16, p], fill=color, width=3)
            d.line([48, p, 56, p], fill=color, width=3)
    elif name == "hybrid":
        d.rounded_rectangle([12, 12, 52, 52], radius=9, outline=color, width=4)
        d.line([24, 32, 40, 32], fill=color, width=5)
        d.line([32, 24, 32, 40], fill=color, width=5)
    elif name == "minimize":
        # 下箭头落入托盘 = 最小化到托盘
        d.line([32, 10, 32, 32], fill=color, width=4)
        d.polygon([(22, 24), (42, 24), (32, 36)], fill=color)
        d.line([12, 48, 52, 48], fill=color, width=4)
    elif name == "close":
        d.line([18, 18, 46, 46], fill=color, width=5)
        d.line([46, 18, 18, 46], fill=color, width=5)
    elif name == "shrink":
        # 四向内收箭头 = 收缩为迷你台灯
        w4 = 4
        d.line([32, 12, 32, 24], fill=color, width=w4)
        d.polygon([(25, 23), (39, 23), (32, 31)], fill=color)
        d.line([32, 40, 32, 52], fill=color, width=w4)
        d.polygon([(25, 41), (39, 41), (32, 33)], fill=color)
        d.line([12, 32, 24, 32], fill=color, width=w4)
        d.polygon([(23, 25), (23, 39), (31, 32)], fill=color)
        d.line([40, 32, 52, 32], fill=color, width=w4)
        d.polygon([(41, 25), (41, 39), (33, 32)], fill=color)
    elif name == "pin":
        # 图钉 = 置顶
        d.ellipse([22, 10, 42, 30], fill=color)
        d.polygon([(27, 26), (37, 26), (34, 54), (30, 54)], fill=color)
    return img


def make_app_icon(size=256):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([size * 0.05, size * 0.05, size * 0.95, size * 0.95],
                        radius=int(size * 0.22), fill=ACCENT)
    box = [size * 0.24, size * 0.22, size * 0.76, size * 0.76]
    w = max(2, int(size * 0.085))
    d.arc(box, 135, 360, fill="white", width=w)
    d.arc(box, 0, 45, fill="white", width=w)
    d.line([size / 2, size * 0.25, size / 2, size * 0.52], fill="white", width=w)
    return im


def make_lamp(on, size=200):
    """透明背景的台灯。on=True 叠加暖色光束；全部不透明像素，配合 transparentcolor 干净镂空。"""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    S = size
    if on:
        sh = (228, 178, 72); shhi = (252, 218, 128); rim = (150, 108, 36)
        bulb = (255, 247, 205); pole = (224, 219, 204); polehi = (246, 243, 234)
        joint = (150, 108, 36); base = (204, 198, 182); basesh = (138, 133, 118); basetop = (228, 223, 208)
        bo = (255, 192, 84); bm = (255, 214, 128); bc = (255, 238, 188)
    else:
        sh = (120, 124, 132); shhi = (170, 174, 182); rim = (70, 73, 80)
        bulb = (98, 101, 108); pole = (150, 153, 160); polehi = (180, 183, 190)
        joint = (74, 77, 84); base = (132, 135, 142); basesh = (84, 87, 94); basetop = (158, 161, 168)
    if on:
        d.polygon([(0.30 * S, 0.34 * S), (0.70 * S, 0.34 * S), (0.98 * S, 0.95 * S), (0.02 * S, 0.95 * S)], fill=bo)
        d.polygon([(0.355 * S, 0.34 * S), (0.645 * S, 0.34 * S), (0.85 * S, 0.93 * S), (0.15 * S, 0.93 * S)], fill=bm)
        d.polygon([(0.42 * S, 0.34 * S), (0.58 * S, 0.34 * S), (0.72 * S, 0.89 * S), (0.28 * S, 0.89 * S)], fill=bc)
    d.polygon([(0.30 * S, 0.13 * S), (0.70 * S, 0.13 * S), (0.80 * S, 0.33 * S), (0.20 * S, 0.33 * S)], fill=sh)
    d.polygon([(0.31 * S, 0.14 * S), (0.45 * S, 0.14 * S), (0.50 * S, 0.32 * S), (0.23 * S, 0.32 * S)], fill=shhi)
    d.ellipse([0.205 * S, 0.31 * S, 0.795 * S, 0.365 * S], fill=rim)
    d.ellipse([0.30 * S, 0.325 * S, 0.70 * S, 0.355 * S], fill=bulb)
    d.ellipse([0.455 * S, 0.33 * S, 0.545 * S, 0.395 * S], fill=joint)
    d.rounded_rectangle([0.475 * S, 0.375 * S, 0.525 * S, 0.71 * S], radius=int(0.025 * S), fill=pole)
    d.rounded_rectangle([0.478 * S, 0.38 * S, 0.492 * S, 0.70 * S], radius=int(0.01 * S), fill=polehi)
    d.rounded_rectangle([0.335 * S, 0.77 * S, 0.665 * S, 0.83 * S], radius=int(0.04 * S), fill=base)
    d.rounded_rectangle([0.365 * S, 0.775 * S, 0.635 * S, 0.79 * S], radius=int(0.02 * S), fill=basetop)
    d.ellipse([0.31 * S, 0.825 * S, 0.69 * S, 0.86 * S], fill=basesh)
    return im


def ctk_img(pil, size):
    return ctk.CTkImage(light_image=pil, dark_image=pil, size=size)


# ================== 全局热键监听（支持多个） ==================
class HotkeyListener:
    def __init__(self):
        self._entries = {}
        self._thread = None
        self._stop = False
        self.ok = {}

    def set_all(self, entries):
        self._entries = dict(entries)
        self._restart()

    def _restart(self):
        self.stop()
        self._stop = False
        if self._entries:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _run(self):
        self.ok = {}
        for hid, (mods, vk, _cb) in self._entries.items():
            self.ok[hid] = bool(user32.RegisterHotKey(None, hid, mods, vk))
        msg = _Msg()
        try:
            while not self._stop:
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    if msg.message == WM_HOTKEY:
                        e = self._entries.get(int(msg.wParam))
                        if e:
                            try:
                                e[2]()
                            except Exception:
                                pass
                time.sleep(0.05)
        finally:
            for hid in self._entries:
                try:
                    user32.UnregisterHotKey(None, hid)
                except Exception:
                    pass

    def stop(self):
        self._stop = True
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=1.0)
        self._thread = None


# ================== 工具函数 ==================
def keysym_to_vk(k):
    k = k.lower()
    if len(k) == 1 and k.isalpha():
        return 0x41 + (ord(k) - ord('a'))
    if len(k) == 1 and k.isdigit():
        return 0x30 + (ord(k) - ord('0'))
    if k.startswith("f") and k[1:].isdigit():
        n = int(k[1:])
        if 1 <= n <= 12:
            return 0x70 + n - 1
    return {"space": 0x20, "up": 0x26, "down": 0x28, "left": 0x25,
            "right": 0x27, "home": 0x24, "end": 0x23}.get(k)


def keysym_label(k):
    k = k.lower()
    if len(k) == 1 and k.isalpha():
        return k.upper()
    if k == "space":
        return "Space"
    return {"up": "↑", "down": "↓", "left": "←", "right": "→"}.get(k, k.capitalize())


def cfg_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "AntiLockScreen")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "config.json")


def load_cfg():
    try:
        with open(cfg_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(data):
    try:
        with open(cfg_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def _parse_hk(d, default_mods, default_vk, default_label):
    if isinstance(d, dict) and d.get("mods") and d.get("vk") and d.get("label"):
        return d["mods"], d["vk"], d["label"]
    return default_mods, default_vk, default_label


class ToolTip:
    """鼠标悬停显示文字提示。
    兼容 CTkButton：把 Enter/Leave 绑定到控件及其全部子控件，避免鼠标在按钮内部
    画布上移动时误触发 Leave 导致提示闪烁/不出现。text 可为字符串或返回字符串的可调用对象。"""

    def __init__(self, widget, text, show_delay=500, hide_grace=120):
        self.widget = widget
        self._text = text
        self.show_delay = show_delay
        self.hide_grace = hide_grace
        self._show_id = None
        self._hide_id = None
        self._top = None
        for seq, fn in (("<Enter>", self._on_enter), ("<Leave>", self._on_leave)):
            self._bind_tree(widget, seq, fn)

    def _bind_tree(self, w, seq, fn):
        try:
            w.bind(seq, fn, add="+")
        except Exception:
            pass
        for c in w.winfo_children():
            self._bind_tree(c, seq, fn)

    def _on_enter(self, _=None):
        self._cancel_hide()
        if self._top is None and self._show_id is None:
            self._show_id = self.widget.after(self.show_delay, self._show)

    def _on_leave(self, _=None):
        self._cancel_show()
        if self._top is not None:
            self._cancel_hide()
            self._hide_id = self.widget.after(self.hide_grace, self._destroy)

    def _cancel_show(self):
        if self._show_id is not None:
            try:
                self.widget.after_cancel(self._show_id)
            except Exception:
                pass
            self._show_id = None

    def _cancel_hide(self):
        if self._hide_id is not None:
            try:
                self.widget.after_cancel(self._hide_id)
            except Exception:
                pass
            self._hide_id = None

    def _show(self):
        self._show_id = None
        text = self._text() if callable(self._text) else self._text
        if not text or self._top is not None:
            return
        try:
            wx = self.widget.winfo_rootx()
            wy = self.widget.winfo_rooty()
            wh = self.widget.winfo_height()
        except Exception:
            return
        top = tk.Toplevel(self.widget)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg=BORDER)                       # 1px 描边的底色
        inner = tk.Frame(top, bg=CARD_BG)              # 白色内容区，与应用卡片一致
        inner.pack(padx=1, pady=1)
        tk.Label(inner, text=text, justify="left",
                 bg=CARD_BG, fg=CHIP_ICON, bd=0,
                 padx=8, pady=3, font=(FONT, 10)).pack()
        top.attributes("-alpha", 0.9)                  # 虚影：整体半透明，淡化不突兀
        top.update_idletasks()
        tw, th = top.winfo_reqwidth(), top.winfo_reqheight()
        sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
        x, y = wx, wy + wh + 6
        if x + tw > sw - 6:
            x = sw - tw - 6
        if y + th > sh - 6:
            y = wy - th - 6
        top.geometry(f"+{max(0, x)}+{max(0, y)}")
        self._top = top

    def _destroy(self):
        self._hide_id = None
        if self._top is not None:
            try:
                self._top.destroy()
            except Exception:
                pass
            self._top = None


# ================== 主界面 ==================
class AntiLockApp:
    def __init__(self, root):
        self.root = root
        self.running = threading.Event()
        self.cur_mode = "keyboard"
        self.cur_interval = 60
        self.last_tick = 0.0
        self._disp_iv = 60
        self.worker = None

        # 会话计时
        self.session_start = None
        self.last_session = None

        # 鼠标模式：上次光标位置（用于"不抢操作"）
        self._last_mouse = None

        # 附加功能开关
        self.cfg_autoon = True
        self.cfg_jitter = True
        self.cfg_notify = True

        # 两个热键默认
        self.hk_show_mods, self.hk_show_vk, self.hk_show_label = MOD_CONTROL | MOD_ALT, 0x53, "Ctrl + Alt + S"
        self.hk_run_mods, self.hk_run_vk, self.hk_run_label = MOD_CONTROL | MOD_ALT, 0x44, "Ctrl + Alt + D"

        self._visible = True
        self._mini = False
        self._capturing = False
        self._capture_target = None
        self._hotkey_q = queue.Queue()

        cfg = load_cfg()
        if cfg.get("mode") in MODE_LABELS:
            self.cur_mode = cfg["mode"]
        if isinstance(cfg.get("interval"), int) and cfg["interval"] >= 1:
            self.cur_interval = cfg["interval"]
        self.cfg_autoon = bool(cfg.get("autoon", True))
        self.cfg_jitter = bool(cfg.get("jitter", True))
        self.cfg_notify = bool(cfg.get("notify", True))
        # 完整卡片默认不置顶（像普通 Win10 窗口）；迷你台灯始终置顶。可由"图钉"按钮切换
        self._topmost = bool(cfg.get("topmost", False))
        if isinstance(cfg.get("last_session"), (int, float)) and cfg["last_session"] > 0:
            self.last_session = cfg["last_session"]
        hks = cfg.get("hotkeys") or {}
        self.hk_show_mods, self.hk_show_vk, self.hk_show_label = _parse_hk(
            hks.get("show"), self.hk_show_mods, self.hk_show_vk, self.hk_show_label)
        self.hk_run_mods, self.hk_run_vk, self.hk_run_label = _parse_hk(
            hks.get("run"), self.hk_run_mods, self.hk_run_vk, self.hk_run_label)

        self.interval_var = ctk.StringVar(value=str(self.cur_interval))
        self.interval_var.trace_add("write", self._on_interval_change)

        self.lamp_on_img = ctk_img(make_lamp(True, 200), (72, 72))
        self.lamp_off_img = ctk_img(make_lamp(False, 200), (72, 72))

        self._build_window()
        self._build_full_card()
        self._build_mini()
        # 按实际内容测量完整卡片高度，避免固定高度造成内容裁剪或大块留白
        self.root.update_idletasks()
        self.full_h = max(FULL_H, self.full_card.winfo_reqheight() + 6)
        self._place_full_initial()
        self.update_mini_style()

        self.hotkey = HotkeyListener()
        self.hotkey.set_all(self._entries())
        self._make_tray()

        self.root.after(300, self._tick)
        if self.cfg_autoon:
            self.root.after(400, self.start)   # 启动即开启

    def _entries(self):
        return {
            1: (self.hk_show_mods, self.hk_show_vk, lambda: self._hotkey_q.put("vis")),
            2: (self.hk_run_mods, self.hk_run_vk, lambda: self._hotkey_q.put("run")),
        }

    # ---------- 窗口 ----------
    def _build_window(self):
        r = self.root
        r.overrideredirect(True)
        r.wm_attributes("-transparentcolor", TRANSPARENT)
        r.configure(fg_color=TRANSPARENT)
        r.attributes("-topmost", self._topmost)
        self._drag_off = (0, 0)

    def _place_full_initial(self):
        """按测得的完整卡片高度，把窗口放到主屏工作区右上角（避开任务栏）。"""
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        wl, wt, wr, wb = self._work_area(sw // 2, sh // 2)
        self.root.geometry(f"{FULL_W}x{self.full_h}+{wr - FULL_W - 20}+{max(wt + 16, 60)}")

    def _build_full_card(self):
        self.full_card = ctk.CTkFrame(self.root, corner_radius=22, fg_color=CARD_BG,
                                      border_width=1, border_color=BORDER)
        self.full_card.pack(fill="both", expand=True)
        card = self.full_card

        # 标题栏
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 6))
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, image=ctk_img(make_app_icon(64), (22, 22)), text="").pack(side="left")
        ctk.CTkLabel(left, text="防熄屏", font=(FONT, 14, "bold"),
                     text_color=TEXT).pack(side="left", padx=6)
        # 右上角窗口控制（小图标）：置顶 / 缩小为台灯 / 最小化到托盘 / 关闭
        ctrl = ctk.CTkFrame(header, fg_color="transparent")
        ctrl.pack(side="right")
        b_close = ctk.CTkButton(ctrl, image=ctk_img(make_icon("close", HEADER_ICON), (16, 16)),
                                text="", width=28, height=28, corner_radius=8, fg_color="transparent",
                                hover_color=HOVER_CLOSE, command=self._quit)
        b_close.pack(side="right", padx=(2, 0))
        b_min = ctk.CTkButton(ctrl, image=ctk_img(make_icon("minimize", HEADER_ICON), (16, 16)),
                              text="", width=28, height=28, corner_radius=8, fg_color="transparent",
                              hover_color=HOVER_SOFT, command=self._hide_to_tray)
        b_min.pack(side="right", padx=(2, 0))
        b_shrink = ctk.CTkButton(ctrl, image=ctk_img(make_icon("shrink", HEADER_ICON), (16, 16)),
                                 text="", width=28, height=28, corner_radius=8, fg_color="transparent",
                                 hover_color=HOVER_SOFT, command=self.enter_mini)
        b_shrink.pack(side="right", padx=(2, 0))
        self.pin_btn = ctk.CTkButton(ctrl, text="", width=28, height=28, corner_radius=8,
                                     fg_color="transparent", hover_color=HOVER_SOFT,
                                     command=self.toggle_topmost)
        self.pin_btn.pack(side="right", padx=(2, 0))
        self._update_pin_style()
        # 悬停文字提示
        ToolTip(b_close, "关闭程序")
        ToolTip(b_min, "最小化")
        ToolTip(b_shrink, "台灯模式")
        ToolTip(self.pin_btn, lambda: "取消置顶" if self._topmost else "置顶窗口")
        # 标题栏分隔线
        ctk.CTkFrame(card, height=1, fg_color=BORDER).pack(fill="x", padx=14, pady=(0, 8))
        for w in (header, left, ctrl):
            self._bind_drag(w)

        # 开关
        self.toggle_btn = ctk.CTkButton(
            card, image=ctk_img(make_icon("power", "#ffffff"), (22, 22)),
            text="开启防锁屏", compound="left", font=(FONT, 15, "bold"), height=48,
            corner_radius=14, fg_color=ACCENT, hover_color=ACCENT_H, text_color="white",
            command=self.toggle)
        self.toggle_btn.pack(fill="x", padx=16, pady=(6, 10))

        # 模式
        ctk.CTkLabel(card, text="模式", anchor="w", font=(FONT, 11),
                     text_color=MUTED).pack(fill="x", padx=20)
        chips = ctk.CTkFrame(card, fg_color="transparent")
        chips.pack(fill="x", padx=12, pady=(2, 8))
        self.chips = {}
        for val, label, ic in [("keyboard", "键盘", "keyboard"), ("mouse", "鼠标", "mouse"),
                               ("api", "API", "cpu"), ("hybrid", "组合", "hybrid")]:
            b = ctk.CTkButton(
                chips, image=ctk_img(make_icon(ic, CHIP_ICON), (22, 22)), text=label,
                compound="top", width=58, height=64, corner_radius=12, fg_color=CHIP_FG,
                hover_color=CHIP_HOVER, border_width=2, border_color=CHIP_FG,
                text_color="#52606d", font=(FONT, 11),
                command=lambda m=val: self._select_mode(m))
            b.pack(side="left", padx=4, expand=True, fill="x")
            self.chips[val] = b

        # 间隔
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkLabel(row, text="间隔（秒）", font=(FONT, 11), text_color=MUTED).pack(side="left")
        ctk.CTkEntry(row, textvariable=self.interval_var, width=64, justify="center",
                     font=(FONT, 12), border_width=1, border_color=ENTRY_BORDER,
                     fg_color=ENTRY_BG, text_color=TEXT).pack(side="left", padx=10)
        ctk.CTkLabel(row, text="（运行中可改）", font=(FONT, 9), text_color=HINT).pack(side="left")

        # 热键 1：显隐窗口
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkLabel(row2, text="热键·显隐窗口", font=(FONT, 11), text_color=MUTED).pack(side="left")
        self.hk_show_btn = ctk.CTkButton(row2, text=self.hk_show_label, width=150, anchor="center",
                                         font=(FONT, 12), fg_color=CHIP_FG, hover_color=CHIP_HOVER,
                                         text_color=TEXT, command=lambda: self._enter_capture("show"))
        self.hk_show_btn.pack(side="right")

        # 热键 2：开关防锁屏
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkLabel(row3, text="热键·开关", font=(FONT, 11), text_color=MUTED).pack(side="left")
        self.hk_run_btn = ctk.CTkButton(row3, text=self.hk_run_label, width=150, anchor="center",
                                       font=(FONT, 12), fg_color=CHIP_FG, hover_color=CHIP_HOVER,
                                       text_color=TEXT, command=lambda: self._enter_capture("run"))
        self.hk_run_btn.pack(side="right")

        # 附加设置（开关）
        ctk.CTkLabel(card, text="设置", anchor="w", font=(FONT, 11),
                     text_color=MUTED).pack(fill="x", padx=20)
        setf = ctk.CTkFrame(card, fg_color="transparent")
        setf.pack(fill="x", padx=14, pady=(2, 6))
        sw_kw = dict(font=(FONT, 11), fg_color=SW_TRACK, progress_color=ACCENT,
                     button_color="#ffffff", button_hover_color="#eef0f2", text_color=TEXT)
        self.sw_autostart = ctk.CTkSwitch(setf, text="开机自启", command=self._on_autostart_switch, **sw_kw)
        self.sw_autostart.grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self.sw_autoon = ctk.CTkSwitch(setf, text="启动即开启",
                                       command=lambda: self._on_bool_switch("autoon"), **sw_kw)
        self.sw_autoon.grid(row=0, column=1, sticky="w", padx=6, pady=3)
        self.sw_jitter = ctk.CTkSwitch(setf, text="随机抖动",
                                       command=lambda: self._on_bool_switch("jitter"), **sw_kw)
        self.sw_jitter.grid(row=1, column=0, sticky="w", padx=6, pady=3)
        self.sw_notify = ctk.CTkSwitch(setf, text="切换提示",
                                       command=lambda: self._on_bool_switch("notify"), **sw_kw)
        self.sw_notify.grid(row=1, column=1, sticky="w", padx=6, pady=3)
        if self._is_autostart():
            self.sw_autostart.select()
        if self.cfg_autoon:
            self.sw_autoon.select()
        if self.cfg_jitter:
            self.sw_jitter.select()
        if self.cfg_notify:
            self.sw_notify.select()

        # 状态条
        st = ctk.CTkFrame(card, fg_color="transparent")
        st.pack(fill="x", padx=20, pady=(4, 6))
        self.dot = ctk.CTkFrame(st, width=10, height=10, corner_radius=5, fg_color=DOT_OFF)
        self.dot.pack(side="left")
        self.status_label = ctk.CTkLabel(st, text="已停止 · 等待开启", anchor="w",
                                         text_color=MUTED, font=(FONT, 11))
        self.status_label.pack(side="left", padx=8)

        # 恢复默认：独立置于卡片底部，描边 + 克制配色，强调"次要/谨慎"操作
        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 14))
        self.reset_btn = ctk.CTkButton(footer, text="↺  恢复默认设置", height=32,
                                       corner_radius=10, fg_color="transparent",
                                       hover_color=HOVER_CLOSE, border_width=1,
                                       border_color=ENTRY_BORDER, text_color=MUTED,
                                       font=(FONT, 11), command=self.reset_to_defaults)
        self.reset_btn.pack(fill="x")

        self._restyle_chips()

    def _build_mini(self):
        self.mini_btn = ctk.CTkFrame(self.root, width=MINI_W, height=MINI_H,
                                     corner_radius=MINI_W // 2, fg_color="transparent",
                                     border_width=0)
        self.mini_label = ctk.CTkLabel(self.mini_btn, image=self.lamp_off_img, text="")
        self.mini_label.pack(expand=True)
        for w in (self.mini_btn, self.mini_label):
            w.bind("<ButtonPress-1>", self._mini_press)
            w.bind("<B1-Motion>", self._mini_drag)
            w.bind("<ButtonRelease-1>", self._mini_release)
            w.bind("<Button-3>", lambda e: self.exit_mini())

    # ---------- 拖动 ----------
    def _bind_drag(self, widget):
        widget.bind("<ButtonPress-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._on_drag)

    def _start_drag(self, e):
        self._drag_off = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _on_drag(self, e):
        self.root.geometry(f"+{e.x_root - self._drag_off[0]}+{e.y_root - self._drag_off[1]}")

    # ---------- mini 台灯 ----------
    def _mini_press(self, e):
        self._mpress = (e.x_root, e.y_root)
        self._morigin = (self.root.winfo_x(), self.root.winfo_y())
        self._mini_moved = False

    def _mini_drag(self, e):
        dx, dy = e.x_root - self._mpress[0], e.y_root - self._mpress[1]
        if abs(dx) > 4 or abs(dy) > 4:
            self._mini_moved = True
        self.root.geometry(f"+{self._morigin[0] + dx}+{self._morigin[1] + dy}")

    def _mini_release(self, e):
        if not self._mini_moved:
            self.toggle()

    def update_mini_style(self):
        if not hasattr(self, "mini_label"):
            return
        self.mini_label.configure(
            image=self.lamp_on_img if self.running.is_set() else self.lamp_off_img)

    def enter_mini(self, *_):
        self.full_card.pack_forget()
        self.mini_btn.pack()
        self._mini = True
        self._visible = True
        self._apply_topmost()                       # 先确保台灯置顶
        self.root.update_idletasks()
        self._resize(MINI_W, MINI_H)                # 最后定位，避免后续切 topmost 被系统重定位
        self.update_mini_style()

    def exit_mini(self, *_):
        self.mini_btn.pack_forget()
        self.full_card.pack(fill="both", expand=True)
        self._mini = False
        self._visible = True
        self._apply_topmost()                       # 先切到目标置顶状态
        self.root.update_idletasks()
        self._resize(FULL_W, self.full_h)           # 最后定位，保证位置生效、不溢出
        # 兜底：切换 topmost 后系统偶发重定位，延迟再夹紧一次，彻底防溢出
        self.root.after(40, lambda: self._resize(FULL_W, self.full_h))

    def _work_area(self, x, y):
        """返回包含点 (x, y) 的显示器工作区 (left, top, right, bottom)。
        使用 Win32 多屏 API：正确处理多显示器，并排除任务栏区域；失败时回退到整屏。"""
        try:
            hmon = user32.MonitorFromPoint(wintypes.POINT(x, y), MONITOR_DEFAULTTONEAREST)
            mi = _MonitorInfoEx()
            mi.cbSize = ctypes.sizeof(mi)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcWork
                return (r.left, r.top, r.right, r.bottom)
        except Exception:
            pass
        return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def _resize(self, w, h):
        """切到 w×h：以"当前所在显示器的工作区"为边界自适应选择展开方向并夹紧，
        彻底避免贴边 / 跨屏 / 压住任务栏时展开后溢出屏幕。"""
        x, y = self.root.winfo_x(), self.root.winfo_y()
        cw, ch = max(1, self.root.winfo_width()), max(1, self.root.winfo_height())
        left, top, right, bottom = self._work_area(x, y)
        m = 8  # 离工作区边缘的安全距离
        # 向右/向下展开会超出当前工作区时，改为右/下边缘对齐（向反方向展开）
        if x + w > right - m:
            x = x + cw - w
        if y + h > bottom - m:
            y = y + ch - h
        # 夹到当前显示器工作区内，避免压到任务栏或越界到屏外
        x = min(max(left + m, x), max(left + m, right - w - m))
        y = min(max(top + m, y), max(top + m, bottom - h - m))
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ---------- 置顶 ----------
    def _apply_topmost(self):
        """迷你台灯始终悬浮；完整卡片遵循"置顶"开关（默认不置顶）。"""
        self.root.attributes("-topmost", True if self._mini else self._topmost)

    def toggle_topmost(self, *_):
        self._topmost = not self._topmost
        self._apply_topmost()
        self._update_pin_style()
        self._save_cfg()

    def _update_pin_style(self):
        if not hasattr(self, "pin_btn"):
            return
        if self._topmost:
            self.pin_btn.configure(fg_color=ACCENT, hover_color=ACCENT_H,
                                   image=ctk_img(make_icon("pin", "#ffffff"), (16, 16)))
        else:
            self.pin_btn.configure(fg_color="transparent", hover_color=HOVER_SOFT,
                                   image=ctk_img(make_icon("pin", HEADER_ICON), (16, 16)))

    # ---------- 模式 ----------
    def _select_mode(self, mode):
        self.cur_mode = mode
        self._restyle_chips()
        if self.running.is_set():
            api_clear()
            if mode in ("api", "hybrid"):
                api_set()
        self._save_cfg()

    def _restyle_chips(self):
        for m, b in self.chips.items():
            if m == self.cur_mode:
                b.configure(fg_color=CHIP_SEL, border_color=ACCENT, text_color="#0f7a3e")
            else:
                b.configure(fg_color=CHIP_FG, border_color=CHIP_FG, text_color="#52606d")

    # ---------- 间隔 ----------
    def _on_interval_change(self, *_):
        s = self.interval_var.get()
        if s.isdigit():
            v = int(s)
            if v >= 1:
                self.cur_interval = v
                self._save_cfg()

    # ---------- 设置开关 ----------
    def _on_bool_switch(self, key):
        sw = {"autoon": self.sw_autoon, "jitter": self.sw_jitter, "notify": self.sw_notify}[key]
        setattr(self, "cfg_" + key, bool(sw.get()))
        self._save_cfg()

    def _on_autostart_switch(self):
        self._set_autostart(bool(self.sw_autostart.get()))

    def _startup_lnk_path(self):
        base = os.environ.get("APPDATA")
        if not base:
            return None
        return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs",
                            "Startup", "防熄屏.lnk")

    def _is_autostart(self):
        p = self._startup_lnk_path()
        return bool(p and os.path.exists(p))

    def _set_autostart(self, on):
        p = self._startup_lnk_path()
        if not p:
            return
        if on:
            self._create_lnk(p)
        else:
            try:
                os.remove(p)
            except OSError:
                pass

    def _create_lnk(self, lnk_path):
        if getattr(sys, "frozen", False):
            target, args, workdir = sys.executable, "", os.path.dirname(sys.executable)
        else:
            py = sys.executable
            pythonw = os.path.join(os.path.dirname(py), "pythonw.exe")
            target = pythonw if os.path.exists(pythonw) else py
            args = '"' + os.path.abspath(__file__) + '"'
            workdir = os.path.dirname(os.path.abspath(__file__))

        def q(s):
            return "'" + str(s).replace("'", "''") + "'"

        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" + q(lnk_path) + ");"
              "$s.TargetPath=" + q(target) + ";"
              "$s.Arguments=" + q(args) + ";"
              "$s.WorkingDirectory=" + q(workdir) + ";"
              "$s.WindowStyle=7;"
              "$s.Description='防熄屏';"
              "$s.Save()")
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           creationflags=CREATE_NO_WINDOW, check=False)
        except Exception:
            pass

    # ---------- 开关 ----------
    def toggle(self, *_):
        if self.running.is_set():
            self.stop()
        else:
            self.start()

    def start(self, *_):
        s = self.interval_var.get()
        if not s.isdigit() or int(s) < 1:
            self.interval_var.set("60")
            self.cur_interval = 60
        if self.cur_mode in ("api", "hybrid"):
            api_set()
        self.running.set()
        self.last_tick = time.time()
        self._disp_iv = self.cur_interval
        self.session_start = time.time()
        self._last_mouse = None
        if self.worker is None or not self.worker.is_alive():
            self.worker = threading.Thread(target=self._loop, daemon=True)
            self.worker.start()
        self.toggle_btn.configure(text="停止防锁屏", fg_color=RED, hover_color=RED_H)
        self.update_mini_style()
        self._notify(True)

    def stop(self, *_):
        if self.session_start:
            self.last_session = time.time() - self.session_start
            self.session_start = None
            self._save_cfg()
        self.running.clear()
        api_clear()
        self.toggle_btn.configure(text="开启防锁屏", fg_color=ACCENT, hover_color=ACCENT_H)
        self.update_mini_style()
        self._notify(False)

    def _notify(self, running):
        if not self.cfg_notify:
            return
        try:
            if running:
                self.tray.notify("防熄屏", f"已开启 · {MODE_LABELS[self.cur_mode]}")
            else:
                self.tray.notify("防熄屏", "已停止")
        except Exception:
            pass
        beep(running)

    def reset_to_defaults(self, *_):
        """清除全部配置并恢复默认（含删除配置文件与开机自启快捷方式）。"""
        if not messagebox.askyesno(
                "恢复默认", "将清除全部配置（模式/间隔/热键/开关/历史）并恢复默认，确定？"):
            return
        try:
            os.remove(cfg_path())
        except OSError:
            pass
        self._set_autostart(False)              # 删除开机自启快捷方式
        if self.running.is_set():
            api_clear()
        # 恢复内存默认值
        self.cur_mode = "keyboard"
        self.cur_interval = 60
        self.cfg_autoon = True
        self.cfg_jitter = True
        self.cfg_notify = True
        self._topmost = False
        self.last_session = None
        self.hk_show_mods, self.hk_show_vk, self.hk_show_label = MOD_CONTROL | MOD_ALT, 0x53, "Ctrl + Alt + S"
        self.hk_run_mods, self.hk_run_vk, self.hk_run_label = MOD_CONTROL | MOD_ALT, 0x44, "Ctrl + Alt + D"
        # 同步 UI
        self.interval_var.set("60")
        self.hk_show_btn.configure(text=self.hk_show_label, fg_color=CHIP_FG, text_color=TEXT)
        self.hk_run_btn.configure(text=self.hk_run_label, fg_color=CHIP_FG, text_color=TEXT)
        self.sw_autoon.select(); self.sw_jitter.select(); self.sw_notify.select(); self.sw_autostart.deselect()
        self._apply_topmost()
        self._update_pin_style()
        self._restyle_chips()
        self.update_mini_style()
        self.hotkey.set_all(self._entries())     # 用默认热键重新注册
        self._save_cfg()
        try:
            self.tray.notify("防熄屏", "已恢复默认设置")
        except Exception:
            pass

    def _tray_reset(self, icon=None, item=None):
        self.root.after(0, self.reset_to_defaults)

    # ---------- 后台：定期发送输入 ----------
    def _loop(self):
        while self.running.is_set():
            try:
                m = self.cur_mode
                if m in ("keyboard", "hybrid"):
                    press_key(VK_F15)
                elif m == "mouse":
                    pos = get_cursor_pos()
                    # 你正在动鼠标就不抖，避免抢操作
                    if self._last_mouse is None or pos == self._last_mouse:
                        mouse_jiggle(1, 1)
                    self._last_mouse = pos
            except Exception:
                pass
            self.last_tick = time.time()
            iv = self.cur_interval
            if self.cfg_jitter:
                iv = max(5, int(iv * random.uniform(0.8, 1.2)))   # 随机抖动，反检测
            self._disp_iv = iv
            slept = 0.0
            while slept < iv and self.running.is_set():
                time.sleep(0.2)
                slept += 0.2

    # ---------- 主循环刷新 ----------
    def _tick(self):
        try:
            while True:
                k = self._hotkey_q.get_nowait()
                if k == "vis":
                    self._toggle_vis()
                elif k == "run":
                    self.toggle()
        except queue.Empty:
            pass
        if self.running.is_set():
            remain = max(0, self._disp_iv - (time.time() - self.last_tick))
            elapsed = time.time() - (self.session_start or time.time())
            self.status_label.configure(
                text=f"⏱ 已运行 {fmt_dur(elapsed)} · 下次 {remain:.0f}s")
            self.dot.configure(fg_color=ACCENT)
        else:
            if self.last_session:
                self.status_label.configure(
                    text=f"已停止 · 上次 {fmt_dur(self.last_session)} · {self.hk_run_label} 开启")
            else:
                self.status_label.configure(text=f"已停止 · {self.hk_run_label} 开启")
            self.dot.configure(fg_color=DOT_OFF)
        self.root.after(250, self._tick)

    # ---------- 热键自定义（捕获） ----------
    def _enter_capture(self, target):
        self.hotkey.stop()
        self._capturing = True
        self._capture_target = target
        btn = self.hk_show_btn if target == "show" else self.hk_run_btn
        self._capture_btn = btn
        btn.configure(text="按下组合键…  Esc 取消", fg_color=ACCENT_H, text_color="white")
        self.root.bind_all("<KeyPress>", self._capture_key)
        self.root.bind_all("<Escape>", lambda e: self._exit_capture(cancel=True))
        self.root.focus_set()

    def _capture_key(self, event):
        if not self._capturing:
            return
        k = event.keysym
        if k in ("Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R",
                 "Super_L", "Super_R", "Win_L", "Win_R", "ISO_Level3_Shift", "Caps_Lock"):
            return
        mods, parts = 0, []
        if event.state & 0x4:
            mods |= MOD_CONTROL; parts.append("Ctrl")
        if event.state & 0x8:
            mods |= MOD_ALT; parts.append("Alt")
        if event.state & 0x1:
            mods |= MOD_SHIFT; parts.append("Shift")
        if event.state & 0x40:
            mods |= MOD_WIN; parts.append("Win")
        vk = keysym_to_vk(k)
        if vk is None:
            self._exit_capture(cancel=True)
            return
        if not (mods & (MOD_CONTROL | MOD_ALT | MOD_WIN)):
            return
        label = " + ".join(parts + [keysym_label(k)])
        self._apply_hotkey(mods, vk, label)

    def _apply_hotkey(self, mods, vk, label):
        t = self._capture_target
        if t == "show":
            self.hk_show_mods, self.hk_show_vk, self.hk_show_label = mods, vk, label
            check_id = 1
        else:
            self.hk_run_mods, self.hk_run_vk, self.hk_run_label = mods, vk, label
            check_id = 2
        self._capture_btn.configure(text=label, fg_color=CHIP_FG, text_color=TEXT)
        self._save_cfg()
        self.hotkey.set_all(self._entries())
        btn = self._capture_btn
        self.root.after(250, lambda: btn.configure(
            text=f"{label}（可能被占用）", text_color="#b07a00") if not self.hotkey.ok.get(check_id) else None)
        self._capturing = False
        try:
            self.root.unbind_all("<KeyPress>")
            self.root.unbind_all("<Escape>")
        except Exception:
            pass

    def _exit_capture(self, cancel=False):
        self._capturing = False
        try:
            self.root.unbind_all("<KeyPress>")
            self.root.unbind_all("<Escape>")
        except Exception:
            pass
        if cancel and self._capture_target:
            lbl = self.hk_show_label if self._capture_target == "show" else self.hk_run_label
            self._capture_btn.configure(text=lbl, fg_color=CHIP_FG, text_color=TEXT)
        self.hotkey.set_all(self._entries())

    # ---------- 托盘 ----------
    def _make_tray(self):
        menu = Menu(
            MenuItem("显示 / 隐藏窗口", self._tray_toggle_vis, default=True),
            Menu.SEPARATOR,
            MenuItem(lambda i: "停止防锁屏" if self.running.is_set() else "开启防锁屏",
                     self._tray_toggle_run),
            Menu.SEPARATOR,
            MenuItem("恢复默认设置", self._tray_reset),
            Menu.SEPARATOR,
            MenuItem("退出", self._tray_quit),
        )
        self.tray = pystray.Icon("antilock", make_app_icon(64), "防熄屏", menu)
        self.tray.run_detached()

    def _tray_toggle_vis(self, icon=None, item=None):
        self.root.after(0, self._toggle_vis)

    def _tray_toggle_run(self, icon=None, item=None):
        self.root.after(0, self.toggle)

    def _tray_quit(self, icon=None, item=None):
        self.root.after(0, self._quit)

    # ---------- 显隐 ----------
    def _toggle_vis(self):
        if self._visible:
            self._hide_to_tray()
        else:
            self._restore()

    def _hide_to_tray(self):
        self.root.withdraw()
        self._visible = False

    def _restore(self):
        self.root.deiconify()
        self.root.lift()
        self._apply_topmost()
        self._visible = True

    # ---------- 配置持久化 / 退出 ----------
    def _save_cfg(self):
        save_cfg({
            "mode": self.cur_mode, "interval": self.cur_interval,
            "autoon": self.cfg_autoon, "jitter": self.cfg_jitter, "notify": self.cfg_notify,
            "topmost": self._topmost,
            "last_session": self.last_session,
            "hotkeys": {
                "show": {"mods": self.hk_show_mods, "vk": self.hk_show_vk, "label": self.hk_show_label},
                "run": {"mods": self.hk_run_mods, "vk": self.hk_run_vk, "label": self.hk_run_label},
            },
        })

    def _quit(self, *_):
        if self.session_start:
            self.last_session = time.time() - self.session_start
            self.session_start = None
        self.running.clear()
        api_clear()
        try:
            self.hotkey.stop()
        except Exception:
            pass
        self._save_cfg()
        try:
            if getattr(self, "tray", None):
                self.tray.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass


def main():
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    AntiLockApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
