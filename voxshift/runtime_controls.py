from __future__ import annotations

import tkinter as tk

from .pro_ui import GOOD, MUTED


class RuntimeControls:
    """Small daily-use controls shared by Home and keyboard navigation."""

    def __init__(self, app) -> None:
        self.app = app
        if hasattr(app, "home_start_button"):
            app.home_start_button.configure(command=self.toggle_engine)
        app.root.bind_all("<Control-space>", self._shortcut_toggle)

    def toggle_engine(self) -> None:
        if self.app.engine.last_status == "Running":
            self.app._stop()
            if hasattr(self.app, "home_notice"):
                self.app.home_notice.configure(text="Engine stopped. Your profile and route remain saved.", fg=MUTED)
        else:
            self.app._start()

    def _shortcut_toggle(self, _event=None):
        try:
            focused = self.app.root.focus_get()
            top = focused.winfo_toplevel() if focused is not None else self.app.root
            if top is not self.app.root:
                return None
        except tk.TclError:
            return None
        self.toggle_engine()
        return "break"

    def update_button(self) -> None:
        if not hasattr(self.app, "home_start_button"):
            return
        running = self.app.engine.last_status == "Running"
        self.app.home_start_button.configure(text="Stop engine" if running else "Start engine")


def install_runtime_controls(app) -> RuntimeControls:
    controls = RuntimeControls(app)
    app.runtime_controls = controls
    original_readiness = app._update_product_readiness

    def readiness_with_runtime_button() -> None:
        original_readiness()
        controls.update_button()

    app._update_product_readiness = readiness_with_runtime_button
    return controls
