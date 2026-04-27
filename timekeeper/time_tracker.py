"""
TimeKeeper — A cross-platform time-budget tracker
Works on Windows and macOS (Python 3.8+, uses only tkinter which is built-in)
Fully resizable: all UI elements scale with the window.
"""

import tkinter as tk
from tkinter import font as tkfont
import time
import math
import csv
import socket
import threading
import sys
import webbrowser
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────
BUDGET_SECONDS = 30 * 60   # 30-minute budget (change this value to adjust)
MIN_W, MIN_H   = 520, 560  # minimum window size

# CSV log — written to the user's home directory by default.
# Change this path to anywhere you prefer, e.g.:
#   Path("C:/Users/You/Documents/timekeeper_log.csv")  # Windows absolute
#   Path.home() / "Documents" / "timekeeper_log.csv"   # cross-platform Documents
CSV_PATH = Path.home() / "timekeeper_log.csv"

FLASK_PORT = 5000   # change if this port is already in use on your machine

# Resolve the app's base directory once at startup, before any threads launch.
# Inside a PyInstaller bundle this is the _MEIPASS extraction folder;
# when running from source it is the folder containing time_tracker.py.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent.resolve()

# ── Color Palette ──────────────────────────────────────────────────────────────
BG        = "#0f1117"
SURFACE   = "#1a1d27"
BORDER    = "#2a2d3a"
ACCENT    = "#4ade80"
ACCENT2   = "#facc15"
ACCENT3   = "#f87171"
TEXT_PRI  = "#f0f4ff"
TEXT_SEC  = "#8892aa"
TEXT_DIM  = "#4a5068"
BTN_START = "#22c55e"
BTN_STOP  = "#ef4444"


# ── Helpers ────────────────────────────────────────────────────────────────────

def fmt(seconds):
    if seconds is None:
        return "—"
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def fmt_hhmmss(seconds):
    """Format seconds as HH:MM:SS — unambiguous for Excel and Tableau."""
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ── Main App ───────────────────────────────────────────────────────────────────

class TimeKeeperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TimeKeeper")
        self.minsize(MIN_W, MIN_H)
        self.configure(bg=BG)

        # State
        self.budget          = BUDGET_SECONDS
        self.cumulative_secs = 0
        self.session_start   = None
        self.current_secs    = 0
        self.sessions        = []
        self.running         = False

        self._last_canvas_w  = 0
        self._last_canvas_h  = 0

        # Flask dashboard thread
        self._flask_thread   = None   # threading.Thread handle
        self._reload_event   = threading.Event()  # set on each _stop to trigger browser refresh

        self._build_ui()

        self.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"620x660+{(sw-620)//2}+{(sh-660)//2}")

        self._tick()

        # Shut Flask down cleanly when the window is closed
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=3)   # content row (gauge+data) expands most
        self.rowconfigure(5, weight=2)   # log row expands

        pad_x = 20

        # Title
        title_frame = tk.Frame(self, bg=BG)
        title_frame.grid(row=0, column=0, sticky="ew", padx=pad_x, pady=(16, 4))
        title_frame.columnconfigure(0, weight=1)

        self.title_label = tk.Label(title_frame, text="TIMEKEEPER", bg=BG,
                                    fg=TEXT_PRI, font=("Courier", 22, "bold"), anchor="w")
        self.title_label.grid(row=0, column=0, sticky="w")

        self.subtitle_label = tk.Label(title_frame, text="budget tracker", bg=BG,
                                       fg=TEXT_DIM, font=("Courier", 10), anchor="e")
        self.subtitle_label.grid(row=0, column=1, sticky="e", pady=(8, 0))

        tk.Frame(self, bg=BORDER, height=1).grid(row=1, column=0, sticky="ew",
                                                  padx=pad_x, pady=4)

        # Main content
        content = tk.Frame(self, bg=BG)
        content.grid(row=2, column=0, sticky="nsew", padx=pad_x, pady=8)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        self._build_gauge(content)
        self._build_data_column(content)

        tk.Frame(self, bg=BORDER, height=1).grid(row=3, column=0, sticky="ew",
                                                  padx=pad_x, pady=4)

        self._build_buttons(pad_x)
        self._build_log(pad_x)

    def _build_gauge(self, parent):
        gauge_frame = tk.Frame(parent, bg=BG)
        gauge_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        gauge_frame.rowconfigure(0, weight=1)
        gauge_frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(gauge_frame, bg=BG, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.status_label = tk.Label(gauge_frame, text="● IDLE", bg=BG,
                                     fg=TEXT_DIM, font=("Courier", 10, "bold"))
        self.status_label.grid(row=1, column=0, pady=(4, 4))

    def _build_data_column(self, parent):
        col = tk.Frame(parent, bg=SURFACE,
                       highlightbackground=BORDER, highlightthickness=1)
        col.grid(row=0, column=1, sticky="nsew", pady=4)
        col.columnconfigure(0, weight=1)

        tk.Label(col, text="TIME SUMMARY", bg=SURFACE, fg=TEXT_DIM,
                 font=("Courier", 9, "bold")).grid(row=0, column=0, sticky="w",
                                                    padx=14, pady=(12, 4))

        self.data_rows      = {}
        self._data_val_fonts = {}
        self._budget_entry  = None   # Entry widget when editing, else None
        self._budget_frame  = None   # parent frame for the starting row

        row_defs = [
            ("starting",   "Starting Budget",  fmt(self.budget)),
            ("current",    "Current Session",  "—"),
            ("instanced",  "Last Session",     "—"),
            ("cumulative", "Cumulative Used",  "—"),
            ("remaining",  "Remaining Budget", fmt(self.budget)),
        ]

        for grid_row, (key, label, value) in enumerate(row_defs, start=1):
            frame = tk.Frame(col, bg=SURFACE)
            frame.grid(row=grid_row*2-1, column=0, sticky="ew", padx=14, pady=(4, 0))
            frame.columnconfigure(0, weight=1)

            # Sub-label row: label text + edit hint for starting budget
            lbl_row = tk.Frame(frame, bg=SURFACE)
            lbl_row.pack(fill="x", anchor="w")

            tk.Label(lbl_row, text=label.upper(), bg=SURFACE, fg=TEXT_SEC,
                     font=("Courier", 8), anchor="w").pack(side="left")

            if key == "starting":
                self._edit_hint = tk.Label(lbl_row, text=" ✎ click to edit",
                                           bg=SURFACE, fg=TEXT_DIM,
                                           font=("Courier", 7), anchor="w")
                self._edit_hint.pack(side="left", padx=(4, 0))
                self._budget_frame = frame

            val_font = tkfont.Font(family="Courier", size=18, weight="bold")
            val_label = tk.Label(frame, text=value, bg=SURFACE, fg=TEXT_PRI,
                                 font=val_font, anchor="w", cursor="hand2" if key == "starting" else "")
            val_label.pack(anchor="w")
            self.data_rows[key] = val_label
            self._data_val_fonts[key] = val_font

            if key == "starting":
                val_label.bind("<Button-1>", self._begin_budget_edit)

            if key != "remaining":
                tk.Frame(col, bg=BORDER, height=1).grid(
                    row=grid_row*2, column=0, sticky="ew", padx=14, pady=(2, 0))

        self.data_rows["remaining"].config(fg=ACCENT)
        self._data_col = col

    # ── Budget inline editor ───────────────────────────────────────────────────

    def _begin_budget_edit(self, event=None):
        """Swap the Starting Budget label for an Entry widget."""
        if self.running or self._budget_entry is not None:
            return   # don't edit while a session is live

        lbl = self.data_rows["starting"]
        lbl.pack_forget()
        self._edit_hint.config(text=" ↩ enter to confirm")

        entry_font = self._data_val_fonts["starting"]
        self._budget_entry = tk.Entry(
            self._budget_frame,
            font=entry_font,
            bg=BORDER, fg=TEXT_PRI,
            insertbackground=TEXT_PRI,
            relief="flat", bd=4,
            width=6)
        self._budget_entry.insert(0, fmt(self.budget))
        self._budget_entry.select_range(0, "end")
        self._budget_entry.pack(anchor="w")
        self._budget_entry.focus_set()

        self._budget_entry.bind("<Return>",    self._commit_budget_edit)
        self._budget_entry.bind("<KP_Enter>",  self._commit_budget_edit)
        self._budget_entry.bind("<Escape>",    self._cancel_budget_edit)
        self._budget_entry.bind("<FocusOut>",  self._commit_budget_edit)

    def _commit_budget_edit(self, event=None):
        if self._budget_entry is None:
            return
        raw = self._budget_entry.get().strip()
        secs = self._parse_time_input(raw)

        if secs is not None and secs > 0:
            # Clamp budget so it can't be set below what's already been used
            secs = max(secs, self.cumulative_secs + 1)
            self.budget = secs
            self._update_data(live=self.current_secs)
            total_used = self.cumulative_secs + self.current_secs
            self._draw_gauge(total_used / self.budget if self.budget else 0)

        self._teardown_budget_entry()

    def _cancel_budget_edit(self, event=None):
        self._teardown_budget_entry()

    def _teardown_budget_entry(self):
        if self._budget_entry is None:
            return
        self._budget_entry.destroy()
        self._budget_entry = None
        self._edit_hint.config(text=" ✎ click to edit")
        # Restore the label
        lbl = self.data_rows["starting"]
        lbl.config(text=fmt(self.budget))
        lbl.pack(anchor="w")

    @staticmethod
    def _parse_time_input(raw):
        """Accept MM:SS or plain minutes (e.g. '30' → 1800s, '45:30' → 2730s)."""
        raw = raw.strip()
        if ":" in raw:
            parts = raw.split(":")
            try:
                m, s = int(parts[0]), int(parts[1])
                return m * 60 + s
            except (ValueError, IndexError):
                return None
        else:
            try:
                return int(raw) * 60
            except ValueError:
                return None

    def _build_buttons(self, pad_x):
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.grid(row=4, column=0, sticky="ew", padx=pad_x, pady=8)
        btn_frame.columnconfigure(0, weight=1)

        self.toggle_btn = tk.Button(
            btn_frame, text="▶  START SESSION",
            bg=BTN_START, fg="#000", activebackground="#16a34a",
            activeforeground="#000", font=("Courier", 13, "bold"),
            bd=0, padx=16, pady=10, cursor="hand2",
            command=self._toggle)
        self.toggle_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.reset_btn = tk.Button(
            btn_frame, text="↺  RESET",
            bg=SURFACE, fg=TEXT_SEC, activebackground=BORDER,
            activeforeground=TEXT_PRI, font=("Courier", 13, "bold"),
            bd=0, padx=16, pady=10, cursor="hand2",
            highlightbackground=BORDER, highlightthickness=1,
            command=self._reset)
        self.reset_btn.grid(row=0, column=1, sticky="e", padx=(0, 8))

        self.dash_btn = tk.Button(
            btn_frame, text="⧉  DASHBOARD",
            bg=SURFACE, fg=TEXT_SEC, activebackground=BORDER,
            activeforeground=TEXT_PRI, font=("Courier", 13, "bold"),
            bd=0, padx=16, pady=10, cursor="hand2",
            highlightbackground=BORDER, highlightthickness=1,
            command=self._open_dashboard)
        self.dash_btn.grid(row=0, column=2, sticky="e")

    def _build_log(self, pad_x):
        log_outer = tk.Frame(self, bg=SURFACE,
                             highlightbackground=BORDER, highlightthickness=1)
        log_outer.grid(row=5, column=0, sticky="nsew", padx=pad_x, pady=(0, 16))
        log_outer.columnconfigure(0, weight=1)
        log_outer.rowconfigure(1, weight=1)

        tk.Label(log_outer, text="SESSION LOG", bg=SURFACE, fg=TEXT_DIM,
                 font=("Courier", 9, "bold")).grid(row=0, column=0, sticky="w",
                                                    padx=12, pady=(8, 2))

        # Scroll area: content canvas + custom scrollbar side by side
        scroll_area = tk.Frame(log_outer, bg=SURFACE)
        scroll_area.grid(row=1, column=0, sticky="nsew")
        scroll_area.columnconfigure(0, weight=1)
        scroll_area.rowconfigure(0, weight=1)

        log_canvas = tk.Canvas(scroll_area, bg=SURFACE, highlightthickness=0, height=100)
        log_canvas.grid(row=0, column=0, sticky="nsew")

        # Custom scrollbar — a narrow Canvas we draw on ourselves
        sb_width = 6
        self._sb_canvas = tk.Canvas(scroll_area, bg=SURFACE, highlightthickness=0,
                                    width=sb_width + 6)
        self._sb_canvas.grid(row=0, column=1, sticky="ns", padx=(0, 6))
        self._sb_thumb  = None   # canvas item id for the thumb rectangle
        self._sb_track_h = 0
        self._sb_pos     = (0.0, 1.0)  # (top_frac, bottom_frac)

        # Wire scrolling
        log_canvas.configure(yscrollcommand=self._on_scroll_update)
        self._log_canvas = log_canvas

        # Drag state
        self._sb_drag_start_y   = None
        self._sb_drag_start_top = None

        self._sb_canvas.bind("<ButtonPress-1>",   self._sb_on_press)
        self._sb_canvas.bind("<B1-Motion>",        self._sb_on_drag)
        self._sb_canvas.bind("<ButtonRelease-1>",  self._sb_on_release)
        self._sb_canvas.bind("<Configure>",        self._sb_redraw)
        self._bind_wheel(log_canvas)

        self.log_inner = tk.Frame(log_canvas, bg=SURFACE)
        self._log_window = log_canvas.create_window((0, 0), window=self.log_inner, anchor="nw")

        self.log_inner.bind("<Configure>",
                            lambda e: log_canvas.configure(scrollregion=log_canvas.bbox("all")))
        log_canvas.bind("<Configure>",
                        lambda e: log_canvas.itemconfig(self._log_window, width=e.width))

        tk.Label(self.log_inner, text="No sessions recorded yet.",
                 bg=SURFACE, fg=TEXT_DIM, font=("Courier", 9)).pack(anchor="w", padx=12, pady=4)

    # ── Custom scrollbar helpers ───────────────────────────────────────────────

    def _on_scroll_update(self, top, bottom):
        """Called by the log canvas whenever scroll position changes."""
        self._sb_pos = (float(top), float(bottom))
        self._sb_redraw()

    def _sb_redraw(self, event=None):
        """Repaint the custom scrollbar thumb."""
        c   = self._sb_canvas
        top_frac, bot_frac = self._sb_pos
        track_h = c.winfo_height()
        cx      = c.winfo_width() / 2
        w       = 4          # thumb width
        radius  = 2          # corner radius

        c.delete("all")

        # Only draw thumb when content overflows (thumb doesn't fill the track)
        if bot_frac - top_frac >= 0.999:
            return

        # Track line (very subtle)
        c.create_line(cx, 6, cx, track_h - 6, fill=BORDER, width=2)

        # Thumb geometry
        usable  = track_h - 12
        thumb_t = 6 + top_frac * usable
        thumb_b = 6 + bot_frac * usable
        thumb_b = max(thumb_b, thumb_t + 16)   # minimum thumb height

        x0 = cx - w / 2
        x1 = cx + w / 2

        # Draw rounded-rectangle thumb
        r = radius
        # Main fill (two rects + four arcs make a rounded rect)
        c.create_rectangle(x0, thumb_t + r, x1, thumb_b - r,
                           fill=TEXT_DIM, outline="", width=0)
        c.create_rectangle(x0 + r, thumb_t, x1 - r, thumb_b,
                           fill=TEXT_DIM, outline="", width=0)
        c.create_oval(x0, thumb_t, x0 + r*2, thumb_t + r*2,
                      fill=TEXT_DIM, outline="")
        c.create_oval(x1 - r*2, thumb_t, x1, thumb_t + r*2,
                      fill=TEXT_DIM, outline="")
        c.create_oval(x0, thumb_b - r*2, x0 + r*2, thumb_b,
                      fill=TEXT_DIM, outline="")
        c.create_oval(x1 - r*2, thumb_b - r*2, x1, thumb_b,
                      fill=TEXT_DIM, outline="")

        self._sb_track_h = track_h

    def _sb_on_press(self, event):
        self._sb_drag_start_y   = event.y
        self._sb_drag_start_top = self._sb_pos[0]
        # Lighten thumb on press
        self._sb_canvas.config(cursor="hand2")

    def _sb_on_drag(self, event):
        if self._sb_drag_start_y is None:
            return
        track_h = self._sb_track_h or self._sb_canvas.winfo_height()
        usable  = track_h - 12
        if usable <= 0:
            return
        delta_frac = (event.y - self._sb_drag_start_y) / usable
        new_top    = clamp(self._sb_drag_start_top + delta_frac, 0.0, 1.0)
        self._log_canvas.yview_moveto(new_top)

    def _sb_on_release(self, event):
        self._sb_drag_start_y   = None
        self._sb_drag_start_top = None
        self._sb_canvas.config(cursor="")

    def _bind_wheel(self, widget):
        """Attach mousewheel bindings to widget and all its descendants."""
        widget.bind("<MouseWheel>", self._scroll_wheel)
        widget.bind("<Button-4>",   lambda e: self._log_canvas.yview_scroll(-1, "units"))
        widget.bind("<Button-5>",   lambda e: self._log_canvas.yview_scroll( 1, "units"))
        for child in widget.winfo_children():
            self._bind_wheel(child)

    def _scroll_wheel(self, event):
        # Windows gives delta in multiples of 120; macOS gives smaller values
        delta = -1 if event.delta > 0 else 1
        self._log_canvas.yview_scroll(delta, "units")

    # ── Resize Handling ────────────────────────────────────────────────────────

    def _on_resize(self, event):
        if event.widget is not self:
            return
        w = event.width

        title_size = clamp(int(w / 28), 12, 26)
        self.title_label.config(font=("Courier", title_size, "bold"))

        col_w = max(self._data_col.winfo_width(), 160)
        val_size = clamp(int(col_w / 9), 10, 22)
        for f in self._data_val_fonts.values():
            f.configure(size=val_size)

        btn_size = clamp(int(w / 48), 9, 14)
        self.toggle_btn.config(font=("Courier", btn_size, "bold"))
        self.reset_btn.config(font=("Courier", btn_size, "bold"))
        self.dash_btn.config(font=("Courier", btn_size, "bold"))

        status_size = clamp(int(w / 60), 8, 12)
        self.status_label.config(font=("Courier", status_size, "bold"))

    def _on_canvas_resize(self, event):
        w, h = event.width, event.height
        if w == self._last_canvas_w and h == self._last_canvas_h:
            return
        self._last_canvas_w = w
        self._last_canvas_h = h
        total_used = self.cumulative_secs + self.current_secs
        fraction   = total_used / self.budget if self.budget else 0
        self._draw_gauge(fraction)

    # ── Logic ──────────────────────────────────────────────────────────────────

    def _toggle(self):
        if not self.running:
            self._start()
        else:
            self._stop()

    def _start(self):
        if self.budget - self.cumulative_secs <= 0:
            return
        self.running = True
        self.session_start = time.time()
        self.current_secs = 0
        self.toggle_btn.config(text="■  STOP SESSION", bg=BTN_STOP,
                               activebackground="#b91c1c")
        self.status_label.config(text="● RUNNING", fg=ACCENT)

    def _stop(self):
        if not self.running:
            return
        duration = int(time.time() - self.session_start)
        duration = min(duration, self.budget - self.cumulative_secs)
        self.sessions.append(duration)
        self.cumulative_secs += duration
        self._append_csv(duration)
        self._reload_event.set()   # signal dashboard to refresh
        self.current_secs = 0
        self.session_start = None
        self.running = False
        self.toggle_btn.config(text="▶  START SESSION", bg=BTN_START,
                               activebackground="#16a34a")
        self.status_label.config(text="● STOPPED", fg=ACCENT2)
        self._update_log()
        self._update_data(live=0)
        self._draw_gauge(self.cumulative_secs / self.budget)

    def _reset(self):
        self.running = False
        self.session_start = None
        self.current_secs = 0
        self.cumulative_secs = 0
        self.sessions = []
        self.toggle_btn.config(text="▶  START SESSION", bg=BTN_START,
                               activebackground="#16a34a")
        self.status_label.config(text="● IDLE", fg=TEXT_DIM)
        self._update_log()
        self._update_data(live=0)
        self._draw_gauge(0)

    def _append_csv(self, duration):
        """Append one completed session row to the CSV log file.

        Time-duration columns are written as plain integers (seconds) so that
        Excel and Tableau can import them without ambiguity.  A companion
        *_HH:MM:SS column is included beside each one for human-readable display.
        Start Time and Stop Time are written as ISO 8601 strings (HH:MM:SS) which
        both apps recognise natively as time-of-day values.
        """
        now           = time.time()
        remaining     = max(0, self.budget - self.cumulative_secs)
        session_n     = len(self.sessions)
        date_str      = time.strftime("%Y-%m-%d")
        start_str     = time.strftime("%H:%M:%S", time.localtime(now - duration))
        stop_str      = time.strftime("%H:%M:%S")

        write_header = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0
        try:
            CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
            with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow([
                        "Date",
                        "Session #",
                        "Start Time",
                        "Stop Time",
                        "Duration (s)",
                        "Duration (HH:MM:SS)",
                        "Cumulative Used (s)",
                        "Cumulative Used (HH:MM:SS)",
                        "Remaining Budget (s)",
                        "Remaining Budget (HH:MM:SS)",
                        "Budget (s)",
                        "Budget (HH:MM:SS)",
                    ])
                writer.writerow([
                    date_str,
                    session_n,
                    start_str,
                    stop_str,
                    duration,
                    fmt_hhmmss(duration),
                    self.cumulative_secs,
                    fmt_hhmmss(self.cumulative_secs),
                    remaining,
                    fmt_hhmmss(remaining),
                    self.budget,
                    fmt_hhmmss(self.budget),
                ])
        except OSError as e:
            print(f"CSV write error: {e}")

    def _tick(self):
        if self.running and self.session_start:
            self.current_secs = int(time.time() - self.session_start)
            total_used = self.cumulative_secs + self.current_secs
            if total_used >= self.budget:
                self._stop()
            else:
                self._update_data(live=self.current_secs)
                self._draw_gauge(total_used / self.budget)
        self.after(500, self._tick)

    # ── Rendering ──────────────────────────────────────────────────────────────

    def _update_data(self, live=0):
        total_used = self.cumulative_secs + live
        remaining  = max(0, self.budget - total_used)
        last       = self.sessions[-1] if self.sessions else None

        self.data_rows["starting"].config(text=fmt(self.budget))
        self.data_rows["current"].config(
            text=fmt(live) if live else "—",
            fg=ACCENT if live else TEXT_PRI)
        self.data_rows["instanced"].config(
            text=fmt(last) if last is not None else "—")
        self.data_rows["cumulative"].config(
            text=fmt(total_used) if total_used else "—")

        rem_color = ACCENT3 if remaining == 0 else (ACCENT2 if remaining < 300 else ACCENT)
        self.data_rows["remaining"].config(text=fmt(remaining), fg=rem_color)

    def _draw_gauge(self, fraction):
        c  = self.canvas
        c.delete("all")

        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw < 10 or ch < 10:
            return

        cx, cy   = cw / 2, ch / 2
        margin   = 12
        r_outer  = max(min(cx, cy) - margin, 20)
        r_inner  = max(r_outer * 0.65, 10)

        start_angle = 225
        total_span  = 270

        base   = min(cw, ch)
        f_pct  = clamp(int(base / 9),  12, 36)
        f_lbl  = clamp(int(base / 28),  7, 13)
        f_time = clamp(int(base / 18),  9, 20)

        self._arc(c, cx, cy, r_outer, r_inner, start_angle, total_span, BORDER)

        if fraction > 0:
            fill_color = ACCENT3 if fraction >= 1 else (ACCENT2 if fraction >= 0.8 else ACCENT)
            self._arc(c, cx, cy, r_outer, r_inner, start_angle,
                      fraction * total_span, fill_color)

        total_used = self.cumulative_secs + self.current_secs
        remaining  = max(0, self.budget - total_used)
        pct        = int(fraction * 100)
        pct_color  = ACCENT3 if fraction >= 1 else (ACCENT2 if fraction >= 0.8 else TEXT_PRI)

        # Lay out text strictly inside the inner circle.
        # The usable vertical span is the inner-circle diameter minus a small
        # top/bottom margin, divided into four equal slots.
        safe      = r_inner * 0.82          # stay well clear of the arc wall
        total_txt = safe * 2                # full usable height
        slot      = total_txt / 4           # four rows: pct, "USED", time, "remaining"

        row_y = [cy - safe + slot * (i + 0.5) for i in range(4)]

        c.create_text(cx, row_y[0], text=f"{pct}%",
                      fill=pct_color, font=("Courier", f_pct, "bold"), anchor="center")
        c.create_text(cx, row_y[1], text="USED",
                      fill=TEXT_DIM, font=("Courier", f_lbl), anchor="center")
        c.create_text(cx, row_y[2], text=fmt(remaining),
                      fill=TEXT_SEC, font=("Courier", f_time, "bold"), anchor="center")
        c.create_text(cx, row_y[3], text="remaining",
                      fill=TEXT_DIM, font=("Courier", f_lbl), anchor="center")

    def _arc(self, canvas, cx, cy, r_outer, r_inner, start_deg, span_deg, color):
        steps  = max(3, int(abs(span_deg)))
        points = []
        for i in range(steps + 1):
            angle = math.radians(-(start_deg + i * span_deg / steps))
            points.append((cx + r_outer * math.cos(angle),
                           cy + r_outer * math.sin(angle)))
        for i in range(steps, -1, -1):
            angle = math.radians(-(start_deg + i * span_deg / steps))
            points.append((cx + r_inner * math.cos(angle),
                           cy + r_inner * math.sin(angle)))
        flat = [coord for pt in points for coord in pt]
        canvas.create_polygon(flat, fill=color, outline="", smooth=False)

    def _update_log(self):
        for w in self.log_inner.winfo_children():
            w.destroy()

        if not self.sessions:
            tk.Label(self.log_inner, text="No sessions recorded yet.",
                     bg=SURFACE, fg=TEXT_DIM, font=("Courier", 9)).pack(
                     anchor="w", padx=12, pady=4)
            return

        hdr = tk.Frame(self.log_inner, bg=SURFACE)
        hdr.pack(fill="x", padx=12, pady=(4, 2))
        for col_text, width in [("#", 4), ("Duration", 12), ("Cumulative", 13), ("Remaining", 12)]:
            tk.Label(hdr, text=col_text, bg=SURFACE, fg=TEXT_DIM,
                     font=("Courier", 8, "bold"), width=width, anchor="w").pack(side="left")

        cumul = 0
        for i, dur in enumerate(self.sessions, 1):
            cumul += dur
            rem = max(0, self.budget - cumul)
            row = tk.Frame(self.log_inner, bg=SURFACE)
            row.pack(fill="x", padx=12, pady=1)
            fg = ACCENT3 if rem == 0 else TEXT_PRI
            for val, width in [(str(i), 4), (fmt(dur), 12), (fmt(cumul), 13), (fmt(rem), 12)]:
                tk.Label(row, text=val, bg=SURFACE, fg=fg,
                         font=("Courier", 9), width=width, anchor="w").pack(side="left")

        # Re-bind wheel on all newly created child widgets
        self._bind_wheel(self.log_inner)

    # ── Flask dashboard management ────────────────────────────────────────

    def _port_free(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("127.0.0.1", port)) != 0

    def _flask_running(self):
        return self._flask_thread is not None and self._flask_thread.is_alive()

    def _start_flask(self):
        try:
            import pandas as pd
            from flask import Flask, render_template
        except ImportError as e:
            self.after(0, lambda: self._dash_error(
                f"Missing package: {e}\nInstall with:\n  pip install flask pandas"
            ))
            return

        import traceback as tb_mod

        def sec_to_hms(seconds):
            seconds = int(seconds)
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h:02d}:{m:02d}:{s:02d}"

        tmpl_dir = BASE_DIR / "templates"
        print(f"[TimeKeeper] templates folder: {tmpl_dir}")
        print(f"[TimeKeeper] templates exists: {tmpl_dir.exists()}")

        flask_app = Flask(__name__, template_folder=str(tmpl_dir))

        @flask_app.route("/")
        def dashboard():
            try:
                if not CSV_PATH.exists():
                    return (
                        "<html><body style='background:#282c34;font-family:Courier,"
                        "monospace;color:#f87171;padding:40px'>"
                        "<h2>No session data yet</h2>"
                        "<p style='color:#abb2bf'>Complete at least one session "
                        "in TimeKeeper first, then refresh this page.</p>"
                        "</body></html>", 200)
                df = pd.read_csv(CSV_PATH)
                if df.empty:
                    return (
                        "<html><body style='background:#282c34;font-family:Courier,"
                        "monospace;color:#f87171;padding:40px'>"
                        "<h2>Log file is empty</h2>"
                        "<p style='color:#abb2bf'>No session rows yet.</p>"
                        "</body></html>", 200)
                required = {"Duration (s)", "Cumulative Used (s)", "Date"}
                missing  = required - set(df.columns)
                if missing:
                    return (
                        f"<pre style='color:#f87171'>Missing columns: {missing}"
                        f"\nFound: {list(df.columns)}</pre>", 500)
                df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d")
                avg_cumulative = sec_to_hms(int(df["Cumulative Used (s)"].mean()))
                avg_break      = sec_to_hms(int(df["Duration (s)"].mean()))
                longest_dur    = sec_to_hms(df["Duration (s)"].max())
                longest_date   = df.loc[
                    df["Duration (s)"].idxmax(), "Date"].strftime("%m-%d-%Y")
                shortest_dur   = sec_to_hms(df["Duration (s)"].min())
                shortest_date  = df.loc[
                    df["Duration (s)"].idxmin(), "Date"].strftime("%m-%d-%Y")
                return render_template(
                    "index.html",
                    avg_cumulative=avg_cumulative,
                    avg_break=avg_break,
                    longest_break_date=longest_date,
                    longest_break=longest_dur,
                    shortest_break_date=shortest_date,
                    shortest_break=shortest_dur,
                )
            except Exception:
                tb = tb_mod.format_exc()
                return (
                    f"<pre style='color:#f87171;background:#282c34;"
                    f"padding:20px'>{tb}</pre>", 500)

        @flask_app.route("/events")
        def events():
            from flask import Response
            def stream():
                while True:
                    # Block until _stop sets the event (or 25 s timeout
                    # so the connection stays alive past proxy timeouts)
                    triggered = self._reload_event.wait(timeout=25)
                    if triggered:
                        self._reload_event.clear()
                        yield "data: reload\n\n"
                    else:
                        # Heartbeat keeps the connection open
                        yield ": heartbeat\n\n"
            return Response(stream(), mimetype="text/event-stream",
                            headers={"Cache-Control": "no-cache",
                                     "X-Accel-Buffering": "no"})

        flask_app.run(host="127.0.0.1", port=FLASK_PORT,
                      debug=False, use_reloader=False,
                      threaded=True)

    def _open_dashboard(self):
        if not self._flask_running():
            self._flask_thread = threading.Thread(
                target=self._start_flask, daemon=True)
            self._flask_thread.start()
            self.dash_btn.config(text="⧉  STARTING…", state="disabled")
            self._wait_for_flask()
        else:
            webbrowser.open(f"http://127.0.0.1:{FLASK_PORT}")

    def _wait_for_flask(self, attempts=0, max_attempts=20):
        if not self._port_free(FLASK_PORT):
            webbrowser.open(f"http://127.0.0.1:{FLASK_PORT}")
            self.dash_btn.config(text="⧉  DASHBOARD", state="normal")
            return
        if attempts >= max_attempts:
            self.dash_btn.config(text="⧉  DASHBOARD", state="normal")
            self._dash_error(
                "Flask did not start in time.\n"
                "Check that Flask and pandas are installed:\n"
                "  pip install flask pandas"
            )
            return
        self.after(250, lambda: self._wait_for_flask(attempts + 1, max_attempts))

    def _dash_error(self, message):
        win = tk.Toplevel(self)
        win.title("Dashboard Error")
        win.configure(bg=SURFACE)
        win.resizable(False, False)
        tk.Label(win, text=message, bg=SURFACE, fg=ACCENT3,
                 font=("Courier", 10), justify="left", padx=20, pady=20).pack()
        tk.Button(win, text="OK", bg=BORDER, fg=TEXT_PRI,
                  font=("Courier", 10), bd=0, padx=12, pady=6,
                  command=win.destroy).pack(pady=(0, 16))
        win.grab_set()

    def _on_close(self):
        # Flask thread is a daemon — it exits automatically with the process
        self.destroy()



# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = TimeKeeperApp()
    app.mainloop()
