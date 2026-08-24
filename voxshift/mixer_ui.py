from __future__ import annotations

import tkinter as tk

from .pro_ui import ACCENT, BG, GOOD, MUTED, PANEL, PANEL_2, SIDEBAR, TEXT, WARN


EQ_PRESETS: dict[str, tuple[float, float, float, float, float]] = {
    "Flat": (0.0, 0.0, 0.0, 0.0, 0.0),
    "Broadcast": (1.5, -1.0, 0.0, 2.5, 1.0),
    "Deep": (5.0, 3.0, -1.0, -2.0, -1.0),
    "Warm": (3.0, 1.5, 0.0, -1.0, 0.5),
    "Bright": (-1.0, -1.0, 0.5, 3.0, 4.0),
    "Telephone": (-12.0, -5.0, 3.0, 4.0, -12.0),
}


class MixerUI:
    """Dedicated realtime mixer/EQ page.

    The five-band EQ is real DSP. Voice gain/pitch and Soundboard level reuse the existing
    controls so the mixer does not create a second source of truth.
    """

    def __init__(self, app) -> None:
        self.app = app
        root = app.root
        profile = app.profiles.active
        self.enabled = tk.BooleanVar(master=root, value=bool(profile.eq_enabled))
        self.eq_vars = [
            tk.DoubleVar(master=root, value=profile.eq_80_db),
            tk.DoubleVar(master=root, value=profile.eq_250_db),
            tk.DoubleVar(master=root, value=profile.eq_1000_db),
            tk.DoubleVar(master=root, value=profile.eq_4000_db),
            tk.DoubleVar(master=root, value=profile.eq_12000_db),
        ]
        self._save_after: str | None = None
        self._original_apply_profile = app._apply_profile
        self._install_profile_hook()
        self._build_page()
        self._install_navigation()
        self._sync_eq(save=False)

    def _install_profile_hook(self) -> None:
        def apply_profile(profile):
            result = self._original_apply_profile(profile)
            self.load_profile(profile)
            return result

        self.app._apply_profile = apply_profile

    @staticmethod
    def _value_text(value: float, suffix: str = " dB") -> str:
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.1f}{suffix}"

    def _vertical_fader(
        self,
        parent,
        title: str,
        variable: tk.Variable,
        lo: float,
        hi: float,
        command,
        *,
        suffix: str = "",
    ):
        strip = tk.Frame(parent, bg=PANEL_2, padx=8, pady=8)
        tk.Label(strip, text=title, bg=PANEL_2, fg=TEXT, font=("TkDefaultFont", 9, "bold")).pack(pady=(0, 4))
        value_label = tk.Label(strip, bg=PANEL_2, fg=ACCENT, width=9, font=("TkDefaultFont", 8, "bold"))
        value_label.pack(pady=(0, 3))

        def changed(_raw=None):
            value = float(variable.get())
            value_label.configure(text=self._value_text(value, suffix) if suffix else f"{value:.0f}")
            command()

        scale = tk.Scale(
            strip,
            variable=variable,
            from_=hi,
            to=lo,
            orient="vertical",
            showvalue=False,
            resolution=0.5,
            length=190,
            width=15,
            sliderlength=26,
            command=changed,
            bg=PANEL_2,
            fg=TEXT,
            troughcolor=PANEL,
            activebackground=ACCENT,
            highlightthickness=0,
            bd=0,
        )
        scale.pack(fill="y", expand=True)
        changed()
        return strip

    def _build_page(self) -> None:
        page = tk.Frame(self.app.content, bg=BG)
        page.grid(row=0, column=0, sticky="nsew")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        self.app.pages["Mixer"] = page

        header = tk.Frame(page, bg=BG)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        tk.Label(header, text="Realtime mixer", bg=BG, fg=TEXT, font=("TkDefaultFont", 15, "bold")).pack(side="left")
        tk.Label(
            header,
            text="Voice bus  ·  5-band EQ  ·  Soundboard bus",
            bg=BG,
            fg=MUTED,
            font=("TkDefaultFont", 9),
        ).pack(side="left", padx=12)
        tk.Checkbutton(
            header,
            text="EQ enabled",
            variable=self.enabled,
            command=self._sync_eq,
            bg=BG,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=BG,
            activeforeground=TEXT,
        ).pack(side="right")

        console = self.app._card(page)
        console.grid(row=1, column=0, sticky="nsew")
        console.grid_columnconfigure(1, weight=1)
        console.grid_rowconfigure(1, weight=1)

        preset_row = tk.Frame(console, bg=PANEL)
        preset_row.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 4))
        tk.Label(preset_row, text="TONE", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(side="left", padx=(0, 8))
        for name in EQ_PRESETS:
            self.app._button(preset_row, name, lambda n=name: self.apply_preset(n), primary=name == "Flat").pack(side="left", padx=3)
        self.eq_status = tk.Label(preset_row, text="", bg=PANEL, fg=GOOD, font=("TkDefaultFont", 8, "bold"))
        self.eq_status.pack(side="right")

        voice_bus = tk.Frame(console, bg=PANEL_2, padx=10, pady=10)
        voice_bus.grid(row=1, column=0, sticky="ns", padx=(12, 6), pady=(6, 10))
        tk.Label(voice_bus, text="VOICE BUS", bg=PANEL_2, fg=GOOD, font=("TkDefaultFont", 8, "bold")).pack(pady=(0, 8))
        self._vertical_fader(voice_bus, "Level", self.app.gain, -18, 18, self.app._sync_dsp, suffix=" dB").pack(side="left", fill="y", padx=3)
        self._vertical_fader(voice_bus, "Pitch", self.app.pitch, -12, 12, self.app._sync_dsp, suffix=" st").pack(side="left", fill="y", padx=3)

        eq = tk.Frame(console, bg=PANEL_2, padx=10, pady=10)
        eq.grid(row=1, column=1, sticky="nsew", padx=6, pady=(6, 10))
        tk.Label(eq, text="5-BAND VOICE EQ", bg=PANEL_2, fg=GOOD, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", pady=(0, 8))
        strips = tk.Frame(eq, bg=PANEL_2)
        strips.pack(fill="both", expand=True)
        labels = ("Bass\n80 Hz", "Low-mid\n250 Hz", "Mid\n1 kHz", "Presence\n4 kHz", "Air\n12 kHz")
        for label, variable in zip(labels, self.eq_vars):
            self._vertical_fader(strips, label, variable, -12, 12, self._sync_eq, suffix=" dB").pack(
                side="left", fill="both", expand=True, padx=3
            )

        board_bus = tk.Frame(console, bg=PANEL_2, padx=10, pady=10)
        board_bus.grid(row=1, column=2, sticky="ns", padx=(6, 12), pady=(6, 10))
        tk.Label(board_bus, text="SOUNDBOARD", bg=PANEL_2, fg=WARN, font=("TkDefaultFont", 8, "bold")).pack(pady=(0, 8))
        self._vertical_fader(board_bus, "Level", self.app.sound_master, 0, 120, self.app._sync_board, suffix=" %").pack(side="left", fill="y", padx=3)
        self._vertical_fader(board_bus, "Duck", self.app.duck, 0, 24, self.app._sync_board, suffix=" dB").pack(side="left", fill="y", padx=3)

        footer = tk.Frame(console, bg=PANEL)
        footer.grid(row=2, column=0, columnspan=3, sticky="ew", padx=14, pady=(0, 12))
        tk.Label(
            footer,
            text="Deep voice: start with Deep, then lower Pitch by 1–3 st in small steps. EQ changes tone; Pitch changes actual perceived pitch.",
            bg=PANEL,
            fg=MUTED,
            justify="left",
        ).pack(side="left")
        self.reset_note = tk.Label(footer, text="", bg=PANEL, fg=GOOD)
        self.reset_note.pack(side="right")

        # Adding a new grid child can raise it; preserve the page the user was already viewing.
        current = self.app.pages.get(self.app.current_page)
        if current is not None:
            current.tkraise()

    def _install_navigation(self) -> None:
        anchor = self.app.nav.get("Voices")
        if anchor is None:
            return
        sidebar = anchor.master
        button = tk.Button(
            sidebar,
            text="  ≋   Mixer / EQ",
            anchor="w",
            bg=SIDEBAR,
            fg=MUTED,
            activebackground=PANEL_2,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=14,
            pady=11,
            font=("TkDefaultFont", 10, "bold"),
            command=lambda: self.app._show("Mixer"),
        )
        button.pack(fill="x", padx=10, pady=2, after=anchor)
        self.app.nav["Mixer"] = button

    def values(self) -> tuple[float, float, float, float, float]:
        values = [float(max(-12.0, min(12.0, var.get()))) for var in self.eq_vars]
        return values[0], values[1], values[2], values[3], values[4]

    def _sync_eq(self, save: bool = True) -> None:
        gains = self.values()
        self.app.engine.update_settings(eq_enabled=bool(self.enabled.get()), eq_bands_db=gains)
        if hasattr(self, "eq_status"):
            state = "ACTIVE" if self.enabled.get() else "BYPASSED"
            self.eq_status.configure(text=f"EQ {state}", fg=GOOD if self.enabled.get() else MUTED)
        if save:
            self._schedule_save()

    def _schedule_save(self) -> None:
        if self._save_after is not None:
            try:
                self.app.root.after_cancel(self._save_after)
            except tk.TclError:
                pass
        self._save_after = self.app.root.after(650, self._save_profile_eq)

    def _save_profile_eq(self) -> None:
        self._save_after = None
        gains = self.values()
        try:
            self.app.profiles.update_active(
                eq_enabled=bool(self.enabled.get()),
                eq_80_db=gains[0],
                eq_250_db=gains[1],
                eq_1000_db=gains[2],
                eq_4000_db=gains[3],
                eq_12000_db=gains[4],
            )
        except OSError:
            return

    def load_profile(self, profile) -> None:
        self.enabled.set(bool(profile.eq_enabled))
        values = (profile.eq_80_db, profile.eq_250_db, profile.eq_1000_db, profile.eq_4000_db, profile.eq_12000_db)
        for variable, value in zip(self.eq_vars, values):
            variable.set(float(value))
        self._sync_eq(save=False)

    def apply_preset(self, name: str) -> None:
        values = EQ_PRESETS.get(name)
        if values is None:
            return
        for variable, value in zip(self.eq_vars, values):
            variable.set(value)
        self.enabled.set(True)
        self._sync_eq()
        if hasattr(self, "reset_note"):
            self.reset_note.configure(text=f"{name} loaded")


def install_mixer_ui(app) -> MixerUI:
    extension = MixerUI(app)
    app.mixer_ui = extension
    return extension
