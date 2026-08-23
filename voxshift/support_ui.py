from __future__ import annotations

import json
import tkinter as tk

from . import __version__
from .diagnostics import build_diagnostics
from .pro_ui import GOOD, MUTED, PANEL, TEXT, WARN


class SupportUI:
    def __init__(self, app) -> None:
        self.app = app
        top = app.title.master
        self.button = app._button(top, "Support", self.open)
        self.button.pack(side="right", padx=(0, 8))

    def open(self) -> None:
        existing = getattr(self, "window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            self._refresh_summary()
            return
        win = tk.Toplevel(self.app.root)
        self.window = win
        win.title("OxShift Support")
        win.geometry("620x470")
        win.configure(bg=self.app.root.cget("bg"))
        win.transient(self.app.root)

        tk.Label(win, text="Support & diagnostics", bg=win.cget("bg"), fg=TEXT, font=("TkDefaultFont", 18, "bold")).pack(anchor="w", padx=20, pady=(20, 4))
        tk.Label(
            win,
            text="Health exports intentionally omit device names, usernames, sound paths/names and model filenames.",
            bg=win.cget("bg"),
            fg=MUTED,
            wraplength=560,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        card = self.app._card(win)
        card.pack(fill="both", expand=True, padx=20, pady=6)
        self.summary = tk.Label(card, text="", bg=PANEL, fg=TEXT, justify="left", anchor="nw", font=("TkFixedFont", 9))
        self.summary.pack(fill="both", expand=True, padx=14, pady=14)

        actions = tk.Frame(win, bg=win.cget("bg"))
        actions.pack(fill="x", padx=20, pady=(8, 20))
        self.app._button(actions, "Export diagnostics JSON", self.app._export_diagnostics, primary=True).pack(side="left", padx=4)
        self.app._button(actions, "Copy health summary", self.copy_summary).pack(side="left", padx=4)
        self.app._button(actions, "Refresh", self._refresh_summary).pack(side="left", padx=4)
        self.app._button(actions, "Close", win.destroy).pack(side="right", padx=4)
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        if not hasattr(self, "summary"):
            return
        try:
            health = build_diagnostics(self.app.engine, getattr(self.app, "_devices", []))["audio"]
        except Exception as exc:
            self.summary.configure(text=f"Could not build diagnostics: {exc}", fg=WARN)
            return
        vc_state = "active" if health.get("vc_enabled") and health.get("vc_ready") else "off"
        text = "\n".join([
            f"OxShift             {__version__}",
            f"Engine              {health.get('status', 'unknown')}",
            f"Sample rate         {health.get('sample_rate', 0)} Hz",
            f"Block size          {health.get('blocksize', 0)} frames",
            f"Buffer estimate     {health.get('buffer_ms', 0.0):.2f} ms",
            f"Callback / peak     {health.get('callback_ms', 0.0):.2f} / {health.get('callback_peak_ms', 0.0):.2f} ms",
            f"XRuns               {health.get('xruns', 0)}",
            f"Callback errors     {health.get('callback_errors', 0)}",
            f"Recovery            {health.get('recovery_successes', 0)} / {health.get('recovery_attempts', 0)} successful",
            f"Cleanup             {health.get('cleanup_backend', 'unknown')}",
            f"Pitch               {health.get('pitch_backend', 'unknown')}",
            f"AI conversion       {vc_state}",
            f"VC underruns        {health.get('vc_underruns', 0)}",
            f"Recorder drops      {health.get('recorder_dropped_blocks', 0)}",
        ])
        self.summary.configure(text=text, fg=TEXT)

    def copy_summary(self) -> None:
        self._refresh_summary()
        text = self.summary.cget("text")
        try:
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(text)
            self.app.root.update_idletasks()
            if hasattr(self.app, "home_notice"):
                self.app.home_notice.configure(text="Privacy-safe health summary copied.", fg=GOOD)
        except tk.TclError:
            pass


def install_support_ui(app) -> SupportUI:
    support = SupportUI(app)
    app.support_ui = support
    return support
