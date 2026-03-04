#!/usr/bin/env python3
"""Canvas Calendar – Desktop App"""

import tkinter as tk
from tkinter import ttk, messagebox
import calendar
import threading
from datetime import datetime, timedelta
import requests
import json
import webbrowser
import os

# ── Config persistence ──
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".canvas_config.json")

DEFAULT_TOKEN = "11224~vCk8JMH4hB8P83UBEXn9JQrPvfLwwn6XhvfYMAJatmT9uacT6VnwhCMvf-PWYx8aG"

def load_config():
    defaults = {
        "canvas_url": "https://canvas.ubc.ca",
        "token": DEFAULT_TOKEN,
        "user_name": "",
    }
    try:
        with open(CONFIG_PATH, "r") as f:
            defaults.update(json.load(f))
    except Exception:
        pass
    return defaults

def save_config(data):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# ── Canvas API ──
class CanvasAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def get(self, endpoint, params=None):
        url = f"{self.base_url}/api/v1{endpoint}"
        results = []
        while url:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            results.extend(resp.json())
            url = None
            params = None
            links = resp.headers.get("Link", "")
            for part in links.split(","):
                if 'rel="next"' in part:
                    url = part.split("<")[1].split(">")[0]
        return results

    def get_single(self, endpoint):
        resp = self.session.get(f"{self.base_url}/api/v1{endpoint}", timeout=15)
        resp.raise_for_status()
        return resp.json()


# ── Colors ──
C = {
    "bg": "#f5f6fa",
    "card": "#ffffff",
    "text": "#1e293b",
    "muted": "#94a3b8",
    "border": "#e2e8f0",
    "today_bg": "#dbeafe",
    "selected_bg": "#bfdbfe",
    "hover": "#f0f4ff",
    "btn_bg": "#1e1e1e",
    "btn_fg": "#ffffff",
    "btn_hover": "#333333",
    "primary": "#3b82f6",
    "red": "#ef4444",
    "orange": "#f59e0b",
    "purple": "#8b5cf6",
    "green": "#22c55e",
    "assignment": "#ef4444",
    "event": "#3b82f6",
    "quiz": "#f59e0b",
    "discussion": "#8b5cf6",
    "sidebar_bg": "#111111",
    "sidebar_fg": "#ffffff",
    "sidebar_muted": "#888888",
    "sidebar_sel": "#3b82f6",
}

MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]
MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class CanvasCalendarApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Canvas Calendar")
        self.root.geometry("1150x750")
        self.root.minsize(950, 600)
        self.root.configure(bg=C["bg"])

        self.today = datetime.now()
        self.year = self.today.year
        self.month = self.today.month
        self.selected_date = None

        self.api = None
        self.courses = []
        self.events = []
        self.selected_course_id = None

        self.config = load_config()
        self.url_var = tk.StringVar(value=self.config["canvas_url"])
        self.name_var = tk.StringVar(value=self.config["user_name"])
        self.token_var = tk.StringVar(value=self.config["token"])
        self.status_var = tk.StringVar()

        self._build_ui()
        self._render_calendar()
        self._update_sidebar_selection()

    # ═══════════════════ UI BUILD ═══════════════════
    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg=C["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ── Left sidebar: Year + Month picker ──
        self.sidebar = tk.Frame(main_frame, bg=C["sidebar_bg"], width=90)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Year section — clickable to pick year
        year_frame = tk.Frame(self.sidebar, bg=C["sidebar_bg"])
        year_frame.pack(fill=tk.X, pady=(16, 4))

        self.year_label = tk.Label(year_frame, text=str(self.year),
                                    font=("Helvetica Neue", 18, "bold"),
                                    bg=C["sidebar_bg"], fg=C["sidebar_fg"],
                                    cursor="hand2")
        self.year_label.pack()
        self.year_label.bind("<Button-1>", lambda e: self._show_year_picker())

        sep = tk.Frame(self.sidebar, bg="#333333", height=1)
        sep.pack(fill=tk.X, padx=12, pady=(8, 8))

        # Month list
        self.month_frame = tk.Frame(self.sidebar, bg=C["sidebar_bg"])
        self.month_frame.pack(fill=tk.BOTH, expand=True)

        self.month_labels = []
        for i, name in enumerate(MONTH_SHORT):
            lbl = tk.Label(self.month_frame, text=name,
                           font=("Helvetica Neue", 13),
                           bg=C["sidebar_bg"], fg=C["sidebar_muted"],
                           cursor="hand2", pady=4)
            lbl.pack(fill=tk.X)
            lbl.bind("<Button-1>", lambda e, m=i+1: self._pick_month(m))
            self.month_labels.append(lbl)

        # ── Right area ──
        right = tk.Frame(main_frame, bg=C["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── Top toolbar ──
        toolbar = tk.Frame(right, bg=C["bg"])
        toolbar.pack(fill=tk.X, padx=24, pady=(16, 10))

        # Left: nav arrows + month title
        nav = tk.Frame(toolbar, bg=C["bg"])
        nav.pack(side=tk.LEFT)

        self._make_btn(nav, "<", self._prev_month, width=3, font_size=16).pack(side=tk.LEFT, padx=(0, 4))
        self.month_title = tk.Label(nav, text="", font=("Helvetica Neue", 22, "bold"),
                                     bg=C["bg"], fg=C["text"], width=18, anchor="center")
        self.month_title.pack(side=tk.LEFT, padx=4)
        self._make_btn(nav, ">", self._next_month, width=3, font_size=16).pack(side=tk.LEFT, padx=(4, 0))

        # Right: Today + Settings
        right_btns = tk.Frame(toolbar, bg=C["bg"])
        right_btns.pack(side=tk.RIGHT)

        self._make_btn(right_btns, "Settings", self._open_settings, padx=14).pack(side=tk.RIGHT, padx=(8, 0))
        self._make_btn(right_btns, "Today", self._go_today, padx=14).pack(side=tk.RIGHT)

        # ── Legend ──
        legend = tk.Frame(right, bg=C["bg"])
        legend.pack(fill=tk.X, padx=28, pady=(0, 8))
        for label, color in [("Assignment", C["assignment"]), ("Event", C["event"]),
                              ("Quiz", C["quiz"]), ("Discussion", C["discussion"])]:
            f = tk.Frame(legend, bg=C["bg"])
            f.pack(side=tk.LEFT, padx=(0, 16))
            dot = tk.Canvas(f, width=10, height=10, bg=C["bg"], highlightthickness=0)
            dot.create_oval(1, 1, 9, 9, fill=color, outline="")
            dot.pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(f, text=label, font=("Helvetica Neue", 11), bg=C["bg"],
                     fg=C["muted"]).pack(side=tk.LEFT)

        # ── Calendar grid container ──
        cal_outer = tk.Frame(right, bg=C["bg"])
        cal_outer.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 4))

        self.cal_frame = tk.Frame(cal_outer, bg=C["card"], highlightbackground=C["border"],
                                   highlightthickness=1)
        self.cal_frame.pack(fill=tk.BOTH, expand=True)

        # Weekday header
        header_frame = tk.Frame(self.cal_frame, bg="#f8fafc")
        header_frame.pack(fill=tk.X)
        header_frame.columnconfigure(tuple(range(7)), weight=1)
        for i, day in enumerate(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]):
            tk.Label(header_frame, text=day, font=("Helvetica Neue", 11, "bold"),
                     bg="#f8fafc", fg=C["muted"], pady=8).grid(row=0, column=i, sticky="ew")

        self.grid_frame = tk.Frame(self.cal_frame, bg=C["border"])
        self.grid_frame.pack(fill=tk.BOTH, expand=True)

        # ── Event detail panel (bottom) ──
        self.detail_frame = tk.Frame(right, bg=C["card"], highlightbackground=C["border"],
                                      highlightthickness=1)
        self.detail_visible = False

    def _make_btn(self, parent, text, command, width=None, padx=8, font_size=12):
        """Create a black button using a Frame+Label to ensure black bg on macOS."""
        frame = tk.Frame(parent, bg=C["btn_bg"], padx=padx, pady=5, cursor="hand2")
        lbl = tk.Label(frame, text=text, font=("Helvetica Neue", font_size, "bold"),
                       bg=C["btn_bg"], fg=C["btn_fg"])
        lbl.pack()
        if width:
            lbl.config(width=width)
        for w in (frame, lbl):
            w.bind("<Button-1>", lambda e: command())
            w.bind("<Enter>", lambda e: [frame.config(bg=C["btn_hover"]), lbl.config(bg=C["btn_hover"])])
            w.bind("<Leave>", lambda e: [frame.config(bg=C["btn_bg"]), lbl.config(bg=C["btn_bg"])])
        return frame

    # ═══════════════════ SIDEBAR ═══════════════════
    def _update_sidebar_selection(self):
        self.year_label.config(text=str(self.year))
        for i, lbl in enumerate(self.month_labels):
            if i + 1 == self.month:
                lbl.config(bg=C["sidebar_sel"], fg=C["sidebar_fg"],
                           font=("Helvetica Neue", 13, "bold"))
            else:
                lbl.config(bg=C["sidebar_bg"], fg=C["sidebar_muted"],
                           font=("Helvetica Neue", 13))

    def _show_year_picker(self):
        """Show a small popup below the year label to pick a year."""
        # Close existing picker if any
        if hasattr(self, '_year_popup') and self._year_popup and self._year_popup.winfo_exists():
            self._year_popup.destroy()
            self._year_popup = None
            return

        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.configure(bg=C["sidebar_bg"])
        self._year_popup = popup

        # Position below year label
        x = self.year_label.winfo_rootx()
        y = self.year_label.winfo_rooty() + self.year_label.winfo_height() + 4
        popup.geometry(f"+{x}+{y}")

        # Year range: current - 5 to current + 5
        for yr in range(self.year - 5, self.year + 6):
            is_current = (yr == self.year)
            lbl = tk.Label(popup, text=str(yr),
                           font=("Helvetica Neue", 13, "bold" if is_current else "normal"),
                           bg=C["sidebar_sel"] if is_current else C["sidebar_bg"],
                           fg=C["sidebar_fg"],
                           padx=16, pady=3, cursor="hand2")
            lbl.pack(fill=tk.X)
            lbl.bind("<Button-1>", lambda e, y=yr, p=popup: self._pick_year(y, p))
            if not is_current:
                lbl.bind("<Enter>", lambda e, l=lbl: l.config(bg="#333333"))
                lbl.bind("<Leave>", lambda e, l=lbl: l.config(bg=C["sidebar_bg"]))

        # Close popup when clicking anywhere else in the main window
        def _close_popup(event):
            if popup.winfo_exists():
                popup.destroy()
            self._year_popup = None
            self.root.unbind("<Button-1>")

        self.root.after(100, lambda: self.root.bind("<Button-1>", _close_popup))

    def _pick_year(self, year, popup):
        popup.destroy()
        self.year = year
        self._update_sidebar_selection()
        self._on_month_change()

    def _pick_month(self, month):
        self.month = month
        self._update_sidebar_selection()
        self._on_month_change()

    # ═══════════════════ SETTINGS DIALOG ═══════════════════
    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("480x560")
        win.configure(bg=C["card"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        # Center on parent
        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 480) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 560) // 2
        win.geometry(f"+{x}+{y}")

        container = tk.Frame(win, bg=C["card"], padx=28, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(container, text="Settings", font=("Helvetica Neue", 20, "bold"),
                 bg=C["card"], fg=C["text"]).pack(anchor="w", pady=(0, 16))

        # Canvas URL
        self._settings_field(container, "CANVAS URL", self.url_var)

        # Name
        self._settings_field(container, "YOUR NAME", self.name_var, placeholder="Auto-detected")

        # Token
        self._settings_field(container, "ACCESS TOKEN", self.token_var, mono=True)

        # Connect button (Frame+Label for macOS black bg)
        self.settings_connect_frame = tk.Frame(container, bg=C["btn_bg"], pady=8, cursor="hand2")
        self.settings_connect_label = tk.Label(self.settings_connect_frame, text="Connect",
                                                font=("Helvetica Neue", 13, "bold"),
                                                bg=C["btn_bg"], fg=C["btn_fg"])
        self.settings_connect_label.pack()
        for w in (self.settings_connect_frame, self.settings_connect_label):
            w.bind("<Button-1>", lambda e: self._on_connect(win))
            w.bind("<Enter>", lambda e: [self.settings_connect_frame.config(bg=C["btn_hover"]),
                                          self.settings_connect_label.config(bg=C["btn_hover"])])
            w.bind("<Leave>", lambda e: [self.settings_connect_frame.config(bg=C["btn_bg"]),
                                          self.settings_connect_label.config(bg=C["btn_bg"])])
        self.settings_connect_frame.pack(fill=tk.X, pady=(8, 4))

        # Status
        self.settings_status = tk.Label(container, textvariable=self.status_var,
                                         font=("Helvetica Neue", 11), bg=C["card"],
                                         fg=C["muted"], wraplength=400, justify="left")
        self.settings_status.pack(anchor="w", pady=(4, 8))

        # Courses section
        sep = tk.Frame(container, bg=C["border"], height=1)
        sep.pack(fill=tk.X, pady=(4, 8))

        tk.Label(container, text="COURSES", font=("Helvetica Neue", 10),
                 bg=C["card"], fg=C["muted"]).pack(anchor="w", pady=(0, 4))

        course_frame = tk.Frame(container, bg=C["card"])
        course_frame.pack(fill=tk.BOTH, expand=True)

        self.course_listbox = tk.Listbox(course_frame, font=("Helvetica Neue", 12),
                                          relief="solid", bd=1, highlightthickness=0,
                                          selectmode=tk.SINGLE, activestyle="none",
                                          selectbackground=C["btn_bg"],
                                          selectforeground=C["btn_fg"])
        sb = tk.Scrollbar(course_frame, command=self.course_listbox.yview)
        self.course_listbox.config(yscrollcommand=sb.set)
        self.course_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.course_listbox.insert(0, "  All Courses")
        if self.courses:
            for c in self.courses:
                self.course_listbox.insert(tk.END, f"  {c['name']}")
        sel_idx = 0
        if self.selected_course_id:
            for i, c in enumerate(self.courses):
                if c["id"] == self.selected_course_id:
                    sel_idx = i + 1
                    break
        self.course_listbox.selection_set(sel_idx)
        self.course_listbox.bind("<<ListboxSelect>>", self._on_course_select)

        self._settings_win = win

    def _settings_field(self, parent, label, var, placeholder=None, mono=False):
        tk.Label(parent, text=label, font=("Helvetica Neue", 10),
                 bg=C["card"], fg=C["muted"]).pack(anchor="w", pady=(8, 2))
        font = ("Menlo", 10) if mono else ("Helvetica Neue", 13)
        entry = tk.Entry(parent, textvariable=var, font=font,
                         relief="solid", bd=1, highlightthickness=0)
        entry.pack(fill=tk.X, pady=(0, 4))

    # ═══════════════════ CALENDAR RENDERING ═══════════════════
    def _render_calendar(self):
        self.month_title.config(text=f"{MONTH_NAMES[self.month - 1]} {self.year}")

        for w in self.grid_frame.winfo_children():
            w.destroy()

        self.grid_frame.columnconfigure(tuple(range(7)), weight=1, uniform="col")

        cal = calendar.Calendar(firstweekday=6)  # Sunday first
        weeks = cal.monthdayscalendar(self.year, self.month)

        # Pad to always 6 rows for consistent height
        while len(weeks) < 6:
            weeks.append([0] * 7)

        # Build event map
        filtered = self._get_filtered_events()
        ev_map = {}
        for ev in filtered:
            d = self._event_date(ev)
            if d:
                ev_map.setdefault(d, []).append(ev)

        today_str = self.today.strftime("%Y-%m-%d")

        self.grid_frame.rowconfigure(tuple(range(len(weeks))), weight=1, uniform="row")

        for r, week in enumerate(weeks):
            for col, day in enumerate(week):
                is_outside = (day == 0)

                cell = tk.Frame(self.grid_frame, bg=C["card"], highlightbackground=C["border"],
                                highlightthickness=0)
                cell.grid(row=r, column=col, sticky="nsew", padx=(0, 1), pady=(0, 1))

                if is_outside:
                    cell.config(bg="#fafbfc")
                    continue

                date_str = f"{self.year}-{self.month:02d}-{day:02d}"
                is_today = (date_str == today_str)
                is_selected = (date_str == self.selected_date)

                bg = C["card"]
                if is_today:
                    bg = C["today_bg"]
                if is_selected:
                    bg = C["selected_bg"]
                cell.config(bg=bg)

                # All children clickable
                cell.bind("<Button-1>", lambda e, d=date_str: self._select_date(d))

                # Day number
                if is_today:
                    num_c = tk.Canvas(cell, width=28, height=28, bg=bg, highlightthickness=0)
                    num_c.create_oval(2, 2, 26, 26, fill=C["primary"], outline="")
                    num_c.create_text(14, 14, text=str(day), fill="white",
                                       font=("Helvetica Neue", 12, "bold"))
                    num_c.pack(anchor="w", padx=6, pady=(4, 0))
                    num_c.bind("<Button-1>", lambda e, d=date_str: self._select_date(d))
                else:
                    lbl = tk.Label(cell, text=str(day), font=("Helvetica Neue", 12, "bold"),
                                   bg=bg, fg=C["text"])
                    lbl.pack(anchor="w", padx=8, pady=(4, 0))
                    lbl.bind("<Button-1>", lambda e, d=date_str: self._select_date(d))

                # Event dots
                day_events = ev_map.get(date_str, [])
                if day_events:
                    dots_c = tk.Canvas(cell, bg=bg, height=12, highlightthickness=0)
                    dots_c.pack(anchor="w", padx=6, pady=(2, 0))
                    dots_c.bind("<Button-1>", lambda e, d=date_str: self._select_date(d))

                    for i, ev in enumerate(day_events[:5]):
                        etype = self._event_type(ev)
                        color = C.get(etype, C["event"])
                        x = 4 + i * 12
                        dots_c.create_oval(x, 1, x + 9, 10, fill=color, outline="")

                    if len(day_events) > 5:
                        ml = tk.Label(cell, text=f"+{len(day_events)-5}", bg=bg,
                                      fg=C["muted"], font=("Helvetica Neue", 9))
                        ml.pack(anchor="w", padx=8)
                        ml.bind("<Button-1>", lambda e, d=date_str: self._select_date(d))

    # ═══════════════════ EVENT DETAIL PANEL ═══════════════════
    def _select_date(self, date_str):
        self.selected_date = date_str
        self._render_calendar()
        self._show_detail(date_str)

    def _show_detail(self, date_str):
        if self.detail_visible:
            self.detail_frame.pack_forget()
        for w in self.detail_frame.winfo_children():
            w.destroy()

        d = datetime.strptime(date_str, "%Y-%m-%d")

        # Header
        hdr = tk.Frame(self.detail_frame, bg="#f8fafc")
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=d.strftime("%A, %B %d, %Y"),
                 font=("Helvetica Neue", 14, "bold"), bg="#f8fafc",
                 fg=C["text"]).pack(side=tk.LEFT, padx=16, pady=10)
        tk.Button(hdr, text="X", font=("Helvetica Neue", 12, "bold"),
                  bg="#f8fafc", fg=C["muted"], relief="flat", cursor="hand2",
                  command=self._hide_detail, bd=0).pack(side=tk.RIGHT, padx=12)

        tk.Frame(self.detail_frame, bg=C["border"], height=1).pack(fill=tk.X)

        # Scrollable list
        canvas_w = tk.Canvas(self.detail_frame, bg=C["card"], highlightthickness=0, height=170)
        sb = tk.Scrollbar(self.detail_frame, orient="vertical", command=canvas_w.yview)
        inner = tk.Frame(canvas_w, bg=C["card"])
        inner.bind("<Configure>", lambda e: canvas_w.configure(scrollregion=canvas_w.bbox("all")))
        canvas_w.create_window((0, 0), window=inner, anchor="nw")
        canvas_w.configure(yscrollcommand=sb.set)

        filtered = self._get_filtered_events()
        day_events = [ev for ev in filtered if self._event_date(ev) == date_str]
        day_events.sort(key=lambda e: e.get("start_at") or e.get("all_day_date") or "")

        if not day_events:
            tk.Label(inner, text="No events on this day", font=("Helvetica Neue", 12),
                     bg=C["card"], fg=C["muted"], pady=30).pack()
        else:
            for ev in day_events:
                self._render_event_card(inner, ev)

        canvas_w.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _mw(event):
            canvas_w.yview_scroll(-1 if event.delta > 0 else 1, "units")
        canvas_w.bind("<MouseWheel>", _mw)
        inner.bind("<MouseWheel>", _mw)

        self.detail_frame.pack(fill=tk.X, padx=24, pady=(4, 12))
        self.detail_visible = True

    def _render_event_card(self, parent, ev):
        etype = self._event_type(ev)
        border_color = C.get(etype, C["event"])
        badge_styles = {
            "assignment": ("#fef2f2", C["red"]),
            "event": ("#eff6ff", C["primary"]),
            "quiz": ("#fffbeb", "#d97706"),
            "discussion": ("#faf5ff", C["purple"]),
        }

        card = tk.Frame(parent, bg=C["card"], padx=12, pady=8)
        card.pack(fill=tk.X, padx=12, pady=4)

        bar = tk.Frame(card, bg=border_color, width=4)
        bar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        content = tk.Frame(card, bg=C["card"])
        content.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(content, text=ev.get("title", "Untitled"), font=("Helvetica Neue", 13, "bold"),
                 bg=C["card"], fg=C["text"], anchor="w", wraplength=500,
                 justify="left").pack(anchor="w")

        meta = tk.Frame(content, bg=C["card"])
        meta.pack(anchor="w", pady=(2, 0))

        bg_c, fg_c = badge_styles.get(etype, ("#f1f5f9", C["muted"]))
        tk.Label(meta, text=etype.upper(), font=("Helvetica Neue", 9, "bold"),
                 bg=bg_c, fg=fg_c, padx=6, pady=1).pack(side=tk.LEFT, padx=(0, 8))

        course = self._get_course_name(ev)
        if course:
            tk.Label(meta, text=course, font=("Helvetica Neue", 11),
                     bg=C["card"], fg=C["muted"]).pack(side=tk.LEFT, padx=(0, 8))

        start = ev.get("start_at")
        if start:
            try:
                t = datetime.fromisoformat(start.replace("Z", "+00:00"))
                tk.Label(meta, text=t.strftime("%I:%M %p"), font=("Helvetica Neue", 11),
                         bg=C["card"], fg=C["muted"]).pack(side=tk.LEFT, padx=(0, 8))
            except Exception:
                pass

        assignment = ev.get("assignment") or {}
        due = assignment.get("due_at")
        if due:
            try:
                dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
                tk.Label(meta, text=f"Due {dt.strftime('%I:%M %p')}",
                         font=("Helvetica Neue", 11, "bold"), bg=C["card"],
                         fg=C["red"]).pack(side=tk.LEFT, padx=(0, 8))
            except Exception:
                pass

        html_url = ev.get("html_url")
        if html_url:
            link = tk.Label(content, text="Open in Canvas →", font=("Helvetica Neue", 11),
                            bg=C["card"], fg=C["primary"], cursor="hand2")
            link.pack(anchor="w", pady=(2, 0))
            link.bind("<Button-1>", lambda e, u=html_url: webbrowser.open(u))

    def _hide_detail(self):
        self.detail_frame.pack_forget()
        self.detail_visible = False
        self.selected_date = None
        self._render_calendar()

    # ═══════════════════ API ═══════════════════
    def _on_connect(self, settings_win=None):
        self.settings_connect_label.config(text="Connecting...")
        self.status_var.set("Connecting...")
        threading.Thread(target=lambda: self._connect_thread(settings_win), daemon=True).start()

    def _connect_thread(self, settings_win=None):
        try:
            url = self.url_var.get().strip().rstrip("/")
            token = self.token_var.get().strip()
            self.api = CanvasAPI(url, token)

            try:
                user = self.api.get_single("/users/self")
                if user.get("name") and not self.name_var.get():
                    self.root.after(0, lambda: self.name_var.set(user["name"]))
            except Exception:
                pass

            courses = self.api.get("/courses?enrollment_state=active&per_page=50")
            self.courses = sorted([c for c in courses if c.get("name")], key=lambda c: c["name"])

            self.root.after(0, self._update_course_list)

            save_config({
                "canvas_url": url,
                "token": token,
                "user_name": self.name_var.get(),
            })

            self._load_events()

        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))
        finally:
            self.root.after(0, lambda: self.settings_connect_label.config(text="Connect"))

    def _update_course_list(self):
        try:
            self.course_listbox.delete(0, tk.END)
            self.course_listbox.insert(0, "  All Courses")
            for c in self.courses:
                self.course_listbox.insert(tk.END, f"  {c['name']}")
            self.course_listbox.selection_set(0)
        except Exception:
            pass
        self.status_var.set(f"Connected! {len(self.courses)} courses.")

    def _load_events(self):
        if not self.api or not self.courses:
            return
        try:
            start = datetime(self.year, self.month, 1) - timedelta(days=7)
            end_m = self.month + 1
            end_y = self.year
            if end_m > 12:
                end_m = 1
                end_y += 1
            end = datetime(end_y, end_m, 1) + timedelta(days=7)

            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")
            ctx = "&".join(f"context_codes[]=course_{c['id']}" for c in self.courses)

            events = []
            try:
                ev = self.api.get(f"/calendar_events?type=event&start_date={start_str}&end_date={end_str}&per_page=100&{ctx}")
                events.extend([{**e, "_type": "event"} for e in ev])
            except Exception:
                pass
            try:
                assign = self.api.get(f"/calendar_events?type=assignment&start_date={start_str}&end_date={end_str}&per_page=100&{ctx}")
                events.extend([{**e, "_type": "assignment"} for e in assign])
            except Exception:
                pass

            self.events = events
            self.root.after(0, self._render_calendar)
            self.root.after(0, lambda: self.status_var.set(f"Loaded {len(self.events)} events."))
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"Event error: {e}"))

    # ═══════════════════ HELPERS ═══════════════════
    def _event_date(self, ev):
        s = ev.get("start_at") or ev.get("end_at") or ev.get("all_day_date")
        if not s:
            return None
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return d.strftime("%Y-%m-%d")
        except Exception:
            return None

    def _event_type(self, ev):
        assignment = ev.get("assignment")
        if assignment:
            st = assignment.get("submission_types", [])
            if "online_quiz" in st or "quiz" in st:
                return "quiz"
            if "discussion_topic" in st:
                return "discussion"
            return "assignment"
        return "event" if ev.get("_type") != "assignment" else "assignment"

    def _get_course_name(self, ev):
        ctx = ev.get("context_code", "")
        if ctx.startswith("course_"):
            try:
                cid = int(ctx.split("_")[1])
                for c in self.courses:
                    if c["id"] == cid:
                        return c["name"]
            except Exception:
                pass
        return ""

    def _get_filtered_events(self):
        if not self.selected_course_id:
            return self.events
        return [e for e in self.events
                if e.get("context_code") == f"course_{self.selected_course_id}"]

    def _on_course_select(self, event):
        sel = self.course_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == 0:
            self.selected_course_id = None
        else:
            self.selected_course_id = self.courses[idx - 1]["id"]
        self._render_calendar()
        if self.selected_date:
            self._show_detail(self.selected_date)

    # ═══════════════════ NAVIGATION ═══════════════════
    def _prev_month(self):
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        self._on_month_change()

    def _next_month(self):
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self._on_month_change()

    def _go_today(self):
        self.year = self.today.year
        self.month = self.today.month
        self._on_month_change()

    def _on_month_change(self):
        self._update_sidebar_selection()
        self._hide_detail() if self.detail_visible else None
        self.selected_date = None
        self._render_calendar()
        if self.api:
            threading.Thread(target=self._load_events, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = CanvasCalendarApp(root)
    root.mainloop()
