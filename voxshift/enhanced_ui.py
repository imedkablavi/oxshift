from __future__ import annotations

from pathlib import Path
import tkinter as tk

from .device_routing import resolve_device
from .pro_ui import (
    ACCENT_2,
    BG,
    GOOD,
    MUTED,
    PANEL,
    PANEL_2,
    TEXT,
    OxShiftStudioUI,
)


class OxShiftEnhancedUI(OxShiftStudioUI):
    """Product-focused Studio layer with mic cleanup and resilient routing controls."""

    def __init__(self, root: tk.Tk) -> None:
        self.noise_suppression = tk.DoubleVar(master=root, value=45.0)
        self.agc_enabled = tk.BooleanVar(master=root, value=True)
        self.agc_target = tk.DoubleVar(master=root, value=-18.0)
        self.agc_max_gain = tk.DoubleVar(master=root, value=12.0)
        self.sound_filter = tk.StringVar(master=root, value="All")
        super().__init__(root)
        self.root.title("OxShift Studio — Pro Audio")

    def _studio(self):
        page = self._page()
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)

        transform = self._card(page)
        transform.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        cleanup = self._card(page)
        cleanup.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        tk.Label(transform, text="VoiceLab", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        tk.Label(transform, text="Transformation chain", bg=PANEL, fg=ACCENT_2, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=14, pady=(0, 8))
        for label, var, lo, hi in (
            ("Pitch (st)", self.pitch, -12, 12),
            ("Timbre / formant color", self.formant, -100, 100),
            ("Wet mix", self.wet, 0, 100),
            ("Output gain (dB)", self.gain, -18, 18),
            ("Noise gate (dB)", self.gate, -80, -20),
        ):
            self._slider(transform, label, var, lo, hi, self._sync_dsp).pack(fill="x", padx=14, pady=6)

        tk.Label(cleanup, text="Mic Cleanup", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        tk.Label(cleanup, text="Runs before AI + VoiceLab", bg=PANEL, fg=GOOD, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=14, pady=(0, 8))
        self._slider(cleanup, "Noise suppression", self.noise_suppression, 0, 100, self._sync_cleanup).pack(fill="x", padx=14, pady=6)
        tk.Checkbutton(
            cleanup,
            text="Automatic gain control",
            variable=self.agc_enabled,
            command=self._sync_cleanup,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w", padx=14, pady=8)
        self._slider(cleanup, "AGC target (dBFS)", self.agc_target, -30, -8, self._sync_cleanup).pack(fill="x", padx=14, pady=6)
        self._slider(cleanup, "AGC max gain (dB)", self.agc_max_gain, 0, 24, self._sync_cleanup).pack(fill="x", padx=14, pady=6)
        self.cleanup_status = tk.Label(cleanup, text="Noise floor learning…", bg=PANEL, fg=MUTED, justify="left")
        self.cleanup_status.pack(anchor="w", padx=14, pady=14)
        return page

    def _soundboard(self):
        page = self._page()
        bar = self._card(page)
        bar.pack(fill="x", pady=(0, 10))
        tk.Entry(bar, textvariable=self.search_sound, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0).pack(side="left", fill="x", expand=True, padx=12, pady=10)
        self.search_sound.trace_add("write", lambda *_: self._render_sounds())
        for label in ("All", "Favorites", "Music", "Effects", "General"):
            self._button(bar, label, lambda value=label: self._set_sound_filter(value), primary=self.sound_filter.get() == label).pack(side="left", padx=3, pady=7)
        self._button(bar, "Import", self._import_sounds, primary=True).pack(side="right", padx=6, pady=7)

        controls = self._card(page)
        controls.pack(fill="x", pady=(0, 10))
        self._slider(controls, "Master", self.sound_master, 0, 120, lambda: self._sync_board()).pack(side="left", fill="x", expand=True, padx=10, pady=8)
        self._slider(controls, "Mic duck", self.duck, 0, 24, lambda: self._sync_board()).pack(side="left", fill="x", expand=True, padx=10, pady=8)
        tk.Checkbutton(controls, text="Allow overlap", variable=self.overlap, command=self._sync_board, bg=PANEL, fg=TEXT, selectcolor=PANEL_2, activebackground=PANEL, activeforeground=TEXT).pack(side="left", padx=12)
        self._button(controls, "Stop all", self.engine.soundboard.stop_all, danger=True).pack(side="right", padx=8)

        self.sound_list = tk.Frame(page, bg=BG)
        self.sound_list.pack(fill="both", expand=True)
        self._render_sounds()
        return page

    def _set_sound_filter(self, value: str) -> None:
        self.sound_filter.set(value)
        self._render_sounds()

    def _render_sounds(self):
        if not hasattr(self, "sound_list"):
            return
        for child in self.sound_list.winfo_children():
            child.destroy()
        query = self.search_sound.get().lower().strip()
        selected = self.sound_filter.get()
        items = []
        for item in self.engine.soundboard.items:
            if query and query not in item.name.lower() and query not in item.category.lower():
                continue
            if selected == "Favorites" and not item.favorite:
                continue
            if selected not in {"All", "Favorites"} and item.category.lower() != selected.lower():
                continue
            items.append(item)

        if not items:
            tk.Label(self.sound_list, text="No sounds in this deck.", bg=BG, fg=MUTED).pack(pady=30)
            return

        for item in items:
            row = self._card(self.sound_list)
            row.pack(fill="x", pady=4)
            star = "★" if item.favorite else "☆"
            tk.Label(row, text=f"{star}  {item.name}", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(side="left", padx=12, pady=12)
            tk.Label(row, text=f"{item.category} · {Path(item.path).suffix.upper()[1:]} · {int(item.volume*100)}%", bg=PANEL, fg=MUTED).pack(side="left")
            self._button(row, "Remove", lambda i=item.id: self._remove_sound(i), danger=True).pack(side="right", padx=4, pady=7)
            self._button(row, "Stop", lambda i=item.id: self.engine.soundboard.stop(i)).pack(side="right", padx=4, pady=7)
            self._button(row, "Play", lambda i=item.id: self._play_sound(i), primary=True).pack(side="right", padx=4, pady=7)
            self._button(row, star, lambda i=item.id, v=not item.favorite: self._favorite_sound(i, v)).pack(side="right", padx=4, pady=7)
            for category in ("Music", "Effects", "General"):
                self._button(row, category, lambda i=item.id, c=category: self._categorize_sound(i, c)).pack(side="right", padx=2, pady=7)

    def _favorite_sound(self, item_id: str, value: bool) -> None:
        self.engine.soundboard.update_item(item_id, favorite=value)
        self._render_sounds()

    def _categorize_sound(self, item_id: str, category: str) -> None:
        self.engine.soundboard.update_item(item_id, category=category)
        self._render_sounds()

    def _sync_cleanup(self) -> None:
        self.engine.update_cleanup(
            noise_suppression=float(self.noise_suppression.get()) / 100.0,
            agc_enabled=bool(self.agc_enabled.get()),
            agc_target_dbfs=float(self.agc_target.get()),
            agc_max_gain_db=float(self.agc_max_gain.get()),
        )

    def _save_profile(self):
        input_name = ""
        output_name = ""
        if hasattr(self, "input_combo") and 0 <= self.input_combo.current() < len(self._inputs):
            input_name = self._inputs[self.input_combo.current()][1]
        if hasattr(self, "output_combo") and 0 <= self.output_combo.current() < len(self._outputs):
            output_name = self._outputs[self.output_combo.current()][1]
        p = self.profiles.update_active(
            name=self.profile_name.get(), voice=self.voice.get(), gain_db=self.gain.get(), wet=self.wet.get()/100.0,
            gate_db=self.gate.get(), pitch_semitones=self.pitch.get(), formant_color=self.formant.get()/100.0,
            noise_suppression=self.noise_suppression.get()/100.0, agc_enabled=self.agc_enabled.get(),
            agc_target_dbfs=self.agc_target.get(), agc_max_gain_db=self.agc_max_gain.get(),
            soundboard_master=self.sound_master.get()/100.0, soundboard_duck_db=self.duck.get(), allow_overlap=self.overlap.get(),
            sample_rate=self.engine.sample_rate, blocksize=self.engine.blocksize,
            input_device_name=input_name, output_device_name=output_name,
        )
        self.profile_name.set(p.name)
        self._render_profiles()

    def _apply_profile(self, p):
        super()._apply_profile(p)
        self.noise_suppression.set(p.noise_suppression * 100.0)
        self.agc_enabled.set(p.agc_enabled)
        self.agc_target.set(p.agc_target_dbfs)
        self.agc_max_gain.set(p.agc_max_gain_db)
        self._sync_cleanup()
        if hasattr(self, "input_combo"):
            self._restore_profile_devices()

    def _load_devices(self):
        super()._load_devices()
        if hasattr(self, "input_combo"):
            self._restore_profile_devices()

    def _restore_profile_devices(self) -> None:
        profile = self.profiles.active
        in_result = resolve_device(self._inputs, profile.input_device_name)
        out_result = resolve_device(self._outputs, profile.output_device_name, virtual_output=True)
        if in_result.index is not None:
            pos = next((i for i, (idx, _) in enumerate(self._inputs) if idx == in_result.index), -1)
            if pos >= 0:
                self.input_combo.current(pos)
        if out_result.index is not None:
            pos = next((i for i, (idx, _) in enumerate(self._outputs) if idx == out_result.index), -1)
            if pos >= 0:
                self.output_combo.current(pos)

    def _tick(self):
        super()._tick()
        if hasattr(self, "cleanup_status"):
            self.cleanup_status.configure(
                text=f"Noise floor {self.engine.noise_floor:.5f}\nAGC gain {self.engine.cleanup_gain_db:+.1f} dB · cleaned level {self.engine.cleaned_level:.4f}"
            )
