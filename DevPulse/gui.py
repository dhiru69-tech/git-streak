"""
DevPulse — Desktop GUI
Professional dark monitoring dashboard
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading, datetime, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import devpulse as core

# ─── Color Palette ────────────────────────────────────
BG       = "#0D1117"   # GitHub dark
BG2      = "#161B22"   # Card bg
BG3      = "#21262D"   # Input bg
BORDER   = "#30363D"   # Borders
GREEN    = "#3FB950"   # Success / active
GREEN2   = "#238636"   # Button green
BLUE     = "#58A6FF"   # Accent
YELLOW   = "#D29922"   # Warning
RED      = "#F85149"   # Error
TEXT     = "#E6EDF3"   # Primary text
TEXT2    = "#8B949E"   # Secondary text
TEXT3    = "#484F58"   # Muted

FONT_MONO = ("Consolas", 10) if sys.platform == "win32" else ("Menlo", 10)
FONT_SM   = ("Segoe UI", 9)  if sys.platform == "win32" else ("SF Pro Text", 9)
FONT_MD   = ("Segoe UI", 10) if sys.platform == "win32" else ("SF Pro Text", 10)
FONT_LG   = ("Segoe UI", 12) if sys.platform == "win32" else ("SF Pro Text", 12)
FONT_XL   = ("Segoe UI", 18) if sys.platform == "win32" else ("SF Pro Text", 18)
FONT_BOLD = ("Segoe UI Semibold", 10) if sys.platform == "win32" else ("SF Pro Text", 10)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class Card(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG2, relief="flat",
                         highlightbackground=BORDER, highlightthickness=1,
                         **kwargs)


class StatCard(tk.Frame):
    def __init__(self, parent, label: str, value: str = "—",
                 accent: str = TEXT, **kwargs):
        super().__init__(parent, bg=BG2, relief="flat",
                         highlightbackground=BORDER, highlightthickness=1,
                         padx=20, pady=14, **kwargs)
        tk.Label(self, text=label, bg=BG2, fg=TEXT2,
                 font=FONT_SM).pack(anchor="w")
        self._val = tk.StringVar(value=value)
        self._lbl = tk.Label(self, textvariable=self._val, bg=BG2, fg=accent,
                             font=(FONT_XL[0], 26, "bold"))
        self._lbl.pack(anchor="w", pady=(2, 0))

    def set(self, v: str):
        self._val.set(v)

    def set_color(self, color: str):
        self._lbl.config(fg=color)


class LogPanel(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG2,
                         highlightbackground=BORDER, highlightthickness=1,
                         **kwargs)
        header = tk.Frame(self, bg=BG3, pady=6, padx=12)
        header.pack(fill="x")
        tk.Label(header, text="Activity Log", bg=BG3, fg=TEXT2,
                 font=FONT_SM).pack(side="left")
        self._clear_btn = tk.Button(
            header, text="Clear", bg=BG3, fg=TEXT3, relief="flat",
            font=FONT_SM, cursor="hand2",
            command=self._clear, bd=0, padx=6
        )
        self._clear_btn.pack(side="right")
        self._text = tk.Text(
            self, bg=BG, fg=TEXT2, font=FONT_MONO,
            relief="flat", bd=0, wrap="word",
            selectbackground=BG3, insertbackground=TEXT,
            state="disabled", pady=8, padx=10,
        )
        sb = ttk.Scrollbar(self, orient="vertical", command=self._text.yview)
        self._text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._text.pack(fill="both", expand=True)

        # Tag colors
        self._text.tag_configure("time",   foreground=TEXT3)
        self._text.tag_configure("ok",     foreground=GREEN)
        self._text.tag_configure("warn",   foreground=YELLOW)
        self._text.tag_configure("err",    foreground=RED)
        self._text.tag_configure("info",   foreground=BLUE)
        self._text.tag_configure("normal", foreground=TEXT2)

    def _classify(self, msg: str) -> str:
        m = msg.lower()
        if any(w in m for w in ("error", "fail", "❌")):   return "err"
        if any(w in m for w in ("warn", "skip")):          return "warn"
        if any(w in m for w in ("ok", "success", "push", "commit", "✅", "done")):
            return "ok"
        if any(w in m for w in ("started", "active", "engine", "running")):
            return "info"
        return "normal"

    def append(self, msg: str):
        ts  = datetime.datetime.now().strftime("%H:%M:%S")
        tag = self._classify(msg)
        self._text.configure(state="normal")
        self._text.insert("end", f"[{ts}] ", "time")
        self._text.insert("end", msg + "\n", tag)
        self._text.see("end")
        self._text.configure(state="disabled")

    def _clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")

    def load_file(self, n: int = 60):
        for line in core.get_log_lines(n):
            if "] " in line:
                _, rest = line.split("] ", 1)
                tag = self._classify(rest)
                self._text.configure(state="normal")
                self._text.insert("end", line + "\n", tag)
                self._text.configure(state="disabled")
        self._text.see("end")


class DevPulseApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DevPulse")
        self.configure(bg=BG)
        self.geometry("1000x680")
        self.minsize(800, 560)
        self._setup_style()
        self._build_layout()
        self._refresh_stats()
        self._check_scheduler_state()
        self.after(5000, self._tick)

    # ── Style ──────────────────────────────────────────
    def _setup_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TScrollbar", background=BG3, troughcolor=BG2,
                    borderwidth=0, arrowcolor=TEXT3)
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG2, foreground=TEXT2,
                    padding=[16, 6], font=FONT_SM)
        s.map("TNotebook.Tab",
              background=[("selected", BG)],
              foreground=[("selected", TEXT)])
        s.configure("Treeview", background=BG2, foreground=TEXT,
                    fieldbackground=BG2, borderwidth=0, rowheight=28,
                    font=FONT_SM)
        s.configure("Treeview.Heading", background=BG3, foreground=TEXT2,
                    borderwidth=0, font=FONT_SM)
        s.map("Treeview", background=[("selected", BG3)])

    # ── Layout ─────────────────────────────────────────
    def _build_layout(self):
        # ── Header bar ──
        hdr = tk.Frame(self, bg=BG2, height=52,
                       highlightbackground=BORDER, highlightthickness=1)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="⚡", bg=BG2, fg=GREEN,
                 font=(FONT_XL[0], 18)).pack(side="left", padx=(14, 4), pady=12)
        tk.Label(hdr, text="DevPulse", bg=BG2, fg=TEXT,
                 font=(FONT_XL[0], 14, "bold")).pack(side="left", pady=12)
        tk.Label(hdr, text=f"v{core.VERSION}", bg=BG2, fg=TEXT3,
                 font=FONT_SM).pack(side="left", padx=(6, 0), pady=16)

        self._status_dot  = tk.Label(hdr, text="●", bg=BG2, fg=TEXT3,
                                     font=(FONT_XL[0], 12))
        self._status_dot.pack(side="right", padx=(0, 8))
        self._status_label = tk.Label(hdr, text="Stopped", bg=BG2, fg=TEXT3,
                                      font=FONT_SM)
        self._status_label.pack(side="right", pady=12)

        # ── Notebook ──
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=0, pady=0)

        self._tab_dashboard = tk.Frame(nb, bg=BG)
        self._tab_repos     = tk.Frame(nb, bg=BG)
        self._tab_intel     = tk.Frame(nb, bg=BG)
        self._tab_settings  = tk.Frame(nb, bg=BG)

        nb.add(self._tab_dashboard, text="  Dashboard  ")
        nb.add(self._tab_repos,     text="  Repositories  ")
        nb.add(self._tab_intel,     text="  Intelligence  ")
        nb.add(self._tab_settings,  text="  Settings  ")

        self._build_dashboard()
        self._build_repos()
        self._build_intel()
        self._build_settings()

        # ── Footer bar ──
        ftr = tk.Frame(self, bg=BG2, height=40,
                       highlightbackground=BORDER, highlightthickness=1)
        ftr.pack(fill="x", side="bottom")
        ftr.pack_propagate(False)

        self._start_btn = self._mkbtn(ftr, "▶  Start",   GREEN2, self._on_start)
        self._stop_btn  = self._mkbtn(ftr, "■  Stop",    "#6E7681", self._on_stop)
        self._run_btn   = self._mkbtn(ftr, "↯  Run Now", BLUE,   self._on_run_now)
        self._su_btn    = self._mkbtn(ftr, "⊞  Startup", BG3,    self._on_startup)

        self._start_btn.pack(side="left", padx=(8, 2), pady=6)
        self._stop_btn.pack(side="left",  padx=2,      pady=6)
        self._run_btn.pack(side="left",   padx=2,      pady=6)
        self._su_btn.pack(side="right",   padx=(2, 8), pady=6)

        self._footer_lbl = tk.Label(ftr, text="", bg=BG2, fg=TEXT3, font=FONT_SM)
        self._footer_lbl.pack(side="right", padx=8)

    def _mkbtn(self, parent, text, bg, cmd):
        return tk.Button(
            parent, text=text, bg=bg, fg=TEXT, relief="flat",
            font=FONT_SM, cursor="hand2", command=cmd,
            padx=14, pady=4, bd=0, activebackground=BG3, activeforeground=TEXT
        )

    # ── Dashboard Tab ──────────────────────────────────
    def _build_dashboard(self):
        pad = dict(padx=14, pady=10)

        # Stat cards row
        cards_row = tk.Frame(self._tab_dashboard, bg=BG)
        cards_row.pack(fill="x", **pad)

        self._card_commits = StatCard(cards_row, "Total Commits",
                                      str(core.total_commits()), GREEN)
        self._card_repos   = StatCard(cards_row, "Repos",    "0", BLUE)
        self._card_today   = StatCard(cards_row, "Today",    "—", TEXT2)
        self._card_status  = StatCard(cards_row, "Status",   "OFF", RED)

        for c in (self._card_commits, self._card_repos,
                  self._card_today, self._card_status):
            c.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._card_commits.pack(side="left", fill="both", expand=True, padx=0)

        # Log panel
        self._log = LogPanel(self._tab_dashboard)
        self._log.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self._log.load_file(80)

    # ── Repos Tab ──────────────────────────────────────
    def _build_repos(self):
        pad = dict(padx=14, pady=10)

        toolbar = tk.Frame(self._tab_repos, bg=BG)
        toolbar.pack(fill="x", **pad)
        self._mkbtn(toolbar, "+ Add Repo",    GREEN2, self._add_repo).pack(side="left", padx=(0, 6))
        self._mkbtn(toolbar, "− Remove",      RED,    self._remove_repo).pack(side="left")
        self._mkbtn(toolbar, "↺ Refresh",     BG3,    self._refresh_repos).pack(side="right")

        card = Card(self._tab_repos)
        card.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        cols = ("path", "status", "last_commit", "remote")
        self._repo_tree = ttk.Treeview(card, columns=cols, show="headings",
                                       selectmode="browse")
        self._repo_tree.heading("path",        text="Repository Path")
        self._repo_tree.heading("status",      text="Status")
        self._repo_tree.heading("last_commit", text="Last Commit")
        self._repo_tree.heading("remote",      text="Remote")
        self._repo_tree.column("path",        width=360)
        self._repo_tree.column("status",      width=90,  anchor="center")
        self._repo_tree.column("last_commit", width=140, anchor="center")
        self._repo_tree.column("remote",      width=80,  anchor="center")
        self._repo_tree.pack(fill="both", expand=True)
        self._refresh_repos()

    def _add_repo(self):
        path = filedialog.askdirectory(title="Select Repository Folder")
        if not path:
            return
        cfg = core.load_config()
        if path not in cfg["repos"]:
            cfg["repos"].append(path)
            core.save_config(cfg)
            core.init_repo(path)
            self._log.append(f"Repo added: {path}")
        self._refresh_repos()
        self._refresh_stats()

    def _remove_repo(self):
        sel = self._repo_tree.selection()
        if not sel:
            return
        item  = self._repo_tree.item(sel[0])
        path  = item["values"][0]
        cfg   = core.load_config()
        if path in cfg["repos"]:
            cfg["repos"].remove(path)
            core.save_config(cfg)
            self._log.append(f"Repo removed: {path}")
        self._refresh_repos()
        self._refresh_stats()

    def _refresh_repos(self):
        for row in self._repo_tree.get_children():
            self._repo_tree.delete(row)
        cfg   = core.load_config()
        state = core.load_state()
        for rp in cfg.get("repos", []):
            exists = "OK" if Path(rp).exists() else "Missing"
            last   = state.get(f"last_{rp}", "Never")
            remote = "Yes" if core.has_remote(rp) else "No"
            self._repo_tree.insert("", "end", values=(rp, exists, last, remote))

    # ── Intelligence Tab ───────────────────────────────
    def _build_intel(self):
        pad = dict(padx=14, pady=10)

        top = tk.Frame(self._tab_intel, bg=BG)
        top.pack(fill="x", **pad)
        tk.Label(top, text="AI Content Engine", bg=BG, fg=TEXT,
                 font=(FONT_LG[0], 13, "bold")).pack(side="left")

        form = Card(self._tab_intel)
        form.pack(fill="x", padx=14, pady=(0, 10))

        # AI toggle
        row1 = tk.Frame(form, bg=BG2)
        row1.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(row1, text="Enable AI Content Generation", bg=BG2, fg=TEXT,
                 font=FONT_MD).pack(side="left")
        self._ai_var = tk.BooleanVar(value=core.load_config().get("ai_enabled", False))
        cb = tk.Checkbutton(row1, variable=self._ai_var, bg=BG2,
                            fg=GREEN, selectcolor=BG3, activebackground=BG2,
                            command=self._save_intel)
        cb.pack(side="right")

        # API key
        row2 = tk.Frame(form, bg=BG2)
        row2.pack(fill="x", padx=16, pady=4)
        tk.Label(row2, text="Anthropic API Key", bg=BG2, fg=TEXT2,
                 font=FONT_SM, width=22, anchor="w").pack(side="left")
        self._api_entry = tk.Entry(row2, bg=BG3, fg=TEXT, relief="flat",
                                   font=FONT_MONO, show="●", bd=4,
                                   insertbackground=TEXT)
        self._api_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        cfg = core.load_config()
        if cfg.get("anthropic_api_key"):
            self._api_entry.insert(0, cfg["anthropic_api_key"])
        tk.Button(row2, text="Save", bg=GREEN2, fg=TEXT, relief="flat",
                  font=FONT_SM, cursor="hand2", padx=12, bd=0,
                  command=self._save_intel).pack(side="right", padx=(6, 0))

        # Status row
        row3 = tk.Frame(form, bg=BG2)
        row3.pack(fill="x", padx=16, pady=(4, 14))
        self._ai_status = tk.Label(row3, bg=BG2, fg=TEXT3, font=FONT_SM,
                                   text="AI disabled — using built-in content library")
        self._ai_status.pack(side="left")
        self._update_ai_status()

        # Info box
        info = Card(self._tab_intel)
        info.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        tk.Label(info, text="What AI generates:", bg=BG2, fg=TEXT2,
                 font=FONT_SM, pady=8, padx=14).pack(anchor="w")
        items = [
            ("Working utility scripts",          "Real Python/Bash tools, not placeholder code"),
            ("Technical documentation",          "Context-aware notes based on your repo content"),
            ("Smart commit messages",            "Concise, imperative, no AI-sounding phrases"),
            ("Contextual content",               "Analyzes your repo languages and history first"),
        ]
        for title, desc in items:
            row = tk.Frame(info, bg=BG2)
            row.pack(fill="x", padx=14, pady=3)
            tk.Label(row, text="→", bg=BG2, fg=GREEN, font=FONT_SM).pack(side="left", padx=(0, 8))
            tk.Label(row, text=title, bg=BG2, fg=TEXT, font=FONT_BOLD).pack(side="left")
            tk.Label(row, text=f" — {desc}", bg=BG2, fg=TEXT2, font=FONT_SM).pack(side="left")

    def _save_intel(self):
        cfg = core.load_config()
        cfg["ai_enabled"]        = self._ai_var.get()
        cfg["anthropic_api_key"] = self._api_entry.get().strip()
        core.save_config(cfg)
        self._update_ai_status()
        self._log.append("Intelligence settings saved")

    def _update_ai_status(self):
        cfg = core.load_config()
        if cfg.get("ai_enabled") and cfg.get("anthropic_api_key"):
            self._ai_status.config(text="AI engine enabled — Claude generates content",
                                   fg=GREEN)
        elif cfg.get("ai_enabled"):
            self._ai_status.config(text="AI enabled but no API key provided", fg=YELLOW)
        else:
            self._ai_status.config(text="AI disabled — using built-in content library", fg=TEXT3)

    # ── Settings Tab ───────────────────────────────────
    def _build_settings(self):
        pad = dict(padx=14, pady=10)

        form = Card(self._tab_settings)
        form.pack(fill="x", padx=14, pady=14)

        rows = [
            ("GitHub Username",   "github_username", False),
            ("Commit Start Hour", "commit_hour_min", False),
            ("Commit End Hour",   "commit_hour_max", False),
        ]
        self._setting_vars: dict[str, tk.StringVar] = {}
        cfg = core.load_config()

        for label, key, secret in rows:
            row = tk.Frame(form, bg=BG2)
            row.pack(fill="x", padx=16, pady=6)
            tk.Label(row, text=label, bg=BG2, fg=TEXT, font=FONT_SM,
                     width=22, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(cfg.get(key, "")))
            self._setting_vars[key] = var
            entry = tk.Entry(row, textvariable=var, bg=BG3, fg=TEXT,
                             relief="flat", font=FONT_MD, bd=4,
                             show="●" if secret else "",
                             insertbackground=TEXT)
            entry.pack(side="left", fill="x", expand=True, padx=(8, 0))

        # Skip probability slider
        row_skip = tk.Frame(form, bg=BG2)
        row_skip.pack(fill="x", padx=16, pady=6)
        tk.Label(row_skip, text="Skip-day Probability", bg=BG2, fg=TEXT,
                 font=FONT_SM, width=22, anchor="w").pack(side="left")
        self._skip_var = tk.DoubleVar(value=cfg.get("skip_days_probability", 0.08))
        skip_lbl = tk.Label(row_skip, text=f"{self._skip_var.get():.0%}",
                            bg=BG2, fg=TEXT2, font=FONT_SM, width=5)
        skip_lbl.pack(side="right")
        def on_skip(v):
            skip_lbl.config(text=f"{float(v):.0%}")
        sl = ttk.Scale(row_skip, from_=0.0, to=0.3, variable=self._skip_var,
                       orient="horizontal", command=on_skip)
        sl.pack(side="left", fill="x", expand=True, padx=(8, 8))

        # Enabled toggle
        row_en = tk.Frame(form, bg=BG2)
        row_en.pack(fill="x", padx=16, pady=(6, 14))
        tk.Label(row_en, text="Automation Enabled", bg=BG2, fg=TEXT,
                 font=FONT_SM, width=22, anchor="w").pack(side="left")
        self._enabled_var = tk.BooleanVar(value=cfg.get("enabled", True))
        tk.Checkbutton(row_en, variable=self._enabled_var, bg=BG2,
                       fg=GREEN, selectcolor=BG3,
                       activebackground=BG2).pack(side="left", padx=(8, 0))

        btn_row = tk.Frame(self._tab_settings, bg=BG)
        btn_row.pack(pady=8)
        self._mkbtn(btn_row, "Save Settings", GREEN2, self._save_settings).pack(side="left", padx=4)
        self._mkbtn(btn_row, "Reset Defaults", BG3, self._reset_settings).pack(side="left", padx=4)

    def _save_settings(self):
        cfg = core.load_config()
        cfg["github_username"] = self._setting_vars["github_username"].get().strip()
        try:
            cfg["commit_hour_min"] = int(self._setting_vars["commit_hour_min"].get())
            cfg["commit_hour_max"] = int(self._setting_vars["commit_hour_max"].get())
        except ValueError:
            messagebox.showerror("Invalid", "Hours must be integers (0–23)")
            return
        cfg["skip_days_probability"] = round(self._skip_var.get(), 2)
        cfg["enabled"]               = self._enabled_var.get()
        core.save_config(cfg)
        self._log.append("Settings saved")
        self._refresh_stats()

    def _reset_settings(self):
        core.save_config(core.DEFAULT_CONFIG.copy())
        messagebox.showinfo("Reset", "Settings reset to defaults")

    # ── Stats & Ticker ──────────────────────────────────
    def _refresh_stats(self):
        cfg   = core.load_config()
        state = core.load_state()
        today = datetime.date.today().isoformat()
        repos = cfg.get("repos", [])

        self._card_repos.set(str(len(repos)))
        self._card_commits.set(str(core.total_commits()))

        done_any = any(state.get(f"last_{r}") == today for r in repos)
        self._card_today.set("Done ✓" if done_any else "Pending")
        self._card_today._val  # already set

        running = core.is_running()
        self._card_status.set("RUNNING" if running else "STOPPED")

        if running:
            self._card_status.set_color(GREEN)
            self._status_dot.config(fg=GREEN)
            self._status_label.config(text="Running", fg=GREEN)
        else:
            self._card_status.set_color(RED)
            self._status_dot.config(fg=TEXT3)
            self._status_label.config(text="Stopped", fg=TEXT3)

        self._footer_lbl.config(
            text=f"Last run: {state.get('last_run_time', '—')}"
        )

    def _check_scheduler_state(self):
        """Reflect persisted scheduler state on launch."""
        self._refresh_stats()

    def _tick(self):
        self._refresh_stats()
        self.after(5000, self._tick)

    # ── Button Handlers ────────────────────────────────
    def _on_start(self):
        def cb(msg): self.after(0, self._log.append, msg)
        core.start_scheduler(status_cb=cb)
        self._log.append("Scheduler started — auto-commit active")
        self._refresh_stats()

    def _on_stop(self):
        core.stop_scheduler()
        self._log.append("Scheduler stopped")
        self._refresh_stats()

    def _on_run_now(self):
        self._log.append("Manual run triggered...")
        def _bg():
            def cb(msg): self.after(0, self._log.append, msg)
            results = core.run_automation(status_cb=cb, force=True)
            ok = sum(1 for r in results if r[0])
            self.after(0, self._log.append,
                       f"Run complete — {ok}/{len(results)} commits succeeded")
            # update last_run_time
            state = core.load_state()
            state["last_run_time"] = datetime.datetime.now().strftime("%b %d %H:%M")
            core.save_state(state)
            self.after(0, self._refresh_stats)
        threading.Thread(target=_bg, daemon=True).start()

    def _on_startup(self):
        ok, msg = core.register_startup()
        if ok:
            self._log.append(f"Startup registered: {msg}")
            messagebox.showinfo("Startup", msg)
        else:
            self._log.append(f"Startup failed: {msg}")
            messagebox.showerror("Startup Failed", msg +
                                 "\n\nWindows: Run as Administrator")


def launch():
    app = DevPulseApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
