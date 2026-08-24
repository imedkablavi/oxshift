from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .audio_performance import PERFORMANCE_PRESETS, VALID_BLOCK_SIZES, VALID_SAMPLE_RATES, latency_ms, validate_audio_format
from .pro_ui import GOOD, MUTED, PANEL, TEXT


class AudioPerformanceUI:
    def __init__(self, app) -> None:
        self.app = app
        active = app.profiles.active
        # ProductUI applies the active profile before this extension is installed. Mirror its
        # persisted format into the idle engine immediately so later autosave cannot overwrite
        # a 44.1/96 kHz or non-default block-size profile with stale 48k/256 engine fields.
        app.engine.sample_rate = int(active.sample_rate)
        app.engine.blocksize = int(active.blocksize)
        self.sample_rate_var = tk.StringVar(master=app.root, value=str(active.sample_rate))
        self.blocksize_var = tk.StringVar(master=app.root, value=str(active.blocksize))
        self._original_apply_profile = app._apply_profile
        app._apply_profile = self._apply_profile_with_format
        self._install()

    def _install(self) -> None:
        page = self.app.pages.get("Audio")
        if page is None:
            return
        card = self.app._card(page)
        card.pack(fill="x", pady=(10, 0))
        tk.Label(card, text="Audio performance", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 3))
        tk.Label(card, text="Change format only while the engine is stopped. Lower buffers reduce nominal buffering latency but give the CPU less time per callback.", bg=PANEL, fg=MUTED, wraplength=900, justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        presets = tk.Frame(card, bg=PANEL)
        presets.pack(fill="x", padx=10, pady=(0, 8))
        for name in PERFORMANCE_PRESETS:
            self.app._button(presets, name, lambda n=name: self.apply_preset(n), primary=name == "Balanced").pack(side="left", padx=4)

        row = tk.Frame(card, bg=PANEL)
        row.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(row, text="Sample rate", bg=PANEL, fg=MUTED).pack(side="left")
        rate = ttk.Combobox(row, textvariable=self.sample_rate_var, values=[str(v) for v in VALID_SAMPLE_RATES], state="readonly", width=10, style="Ox.TCombobox")
        rate.pack(side="left", padx=(8, 18))
        tk.Label(row, text="Buffer", bg=PANEL, fg=MUTED).pack(side="left")
        block = ttk.Combobox(row, textvariable=self.blocksize_var, values=[str(v) for v in VALID_BLOCK_SIZES], state="readonly", width=8, style="Ox.TCombobox")
        block.pack(side="left", padx=(8, 18))
        self.app._button(row, "Apply", self.apply_custom, primary=True).pack(side="left")
        self.status = tk.Label(card, text="", bg=PANEL, fg=MUTED)
        self.status.pack(anchor="w", padx=14, pady=(0, 12))
        self._refresh_status()

    def _can_change(self) -> bool:
        if self.app.engine.last_status == "Running":
            messagebox.showinfo("Audio performance", "Stop the engine before changing sample rate or buffer size.", parent=self.app.root)
            return False
        return True

    def apply_preset(self, name: str) -> None:
        if not self._can_change():
            return
        rate, block = PERFORMANCE_PRESETS[name]
        self.sample_rate_var.set(str(rate))
        self.blocksize_var.set(str(block))
        self._commit(rate, block, f"{name} preset applied")

    def apply_custom(self) -> None:
        if not self._can_change():
            return
        try:
            rate, block = validate_audio_format(int(self.sample_rate_var.get()), int(self.blocksize_var.get()))
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Audio performance", str(exc), parent=self.app.root)
            return
        self._commit(rate, block, "Custom audio format applied")

    def _commit(self, rate: int, block: int, message: str) -> None:
        profile = self.app.profiles.update_active(sample_rate=rate, blocksize=block)
        self.app.engine.sample_rate = profile.sample_rate
        self.app.engine.blocksize = profile.blocksize
        self._refresh_status(message)
        if hasattr(self.app, "home_notice"):
            self.app.home_notice.configure(text=f"{message}. Start the engine to use it.", fg=GOOD)
        self.app._render_profiles()

    def _refresh_status(self, prefix: str = "") -> None:
        rate = int(self.sample_rate_var.get())
        block = int(self.blocksize_var.get())
        text = f"{rate / 1000:.1f} kHz · {block} frames · nominal one-buffer time {latency_ms(rate, block):.2f} ms"
        if prefix:
            text = f"{prefix} · {text}"
        self.status.configure(text=text)

    def _apply_profile_with_format(self, profile) -> None:
        # Sync the idle engine first because AlphaUI's profile application may trigger UI
        # synchronization/autosave paths that read engine.sample_rate/blocksize.
        self.app.engine.sample_rate = int(profile.sample_rate)
        self.app.engine.blocksize = int(profile.blocksize)
        self._original_apply_profile(profile)
        self.sample_rate_var.set(str(profile.sample_rate))
        self.blocksize_var.set(str(profile.blocksize))
        if hasattr(self, "status"):
            self._refresh_status()


def install_audio_performance_ui(app) -> AudioPerformanceUI:
    extension = AudioPerformanceUI(app)
    app.audio_performance_ui = extension
    return extension
