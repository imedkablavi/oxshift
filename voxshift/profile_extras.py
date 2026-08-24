from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from .dsp import DEFAULT_EFFECT_ORDER
from .profile_templates import PROFILE_TEMPLATES, template_settings, unique_profile_name
from .pro_ui import GOOD, MUTED, PANEL, TEXT


class ProfileTemplateUI:
    def __init__(self, app) -> None:
        self.app = app
        self._install_templates_card()

    def _install_templates_card(self) -> None:
        page = self.app.pages.get("Profiles")
        if page is None or not hasattr(self.app, "profile_list"):
            return
        card = self.app._card(page)
        card.pack(fill="x", pady=(0, 10), before=self.app.profile_list)
        tk.Label(card, text="Starter profiles", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 3))
        tk.Label(
            card,
            text="Create a new profile with practical defaults. Your current profile is not overwritten.",
            bg=PANEL,
            fg=MUTED,
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 7))
        row = tk.Frame(card, bg=PANEL)
        row.pack(fill="x", padx=10, pady=(0, 12))
        for name in PROFILE_TEMPLATES:
            self.app._button(row, f"New {name}", lambda n=name: self.create_from_template(n)).pack(side="left", padx=4)
        self.app._button(row, "Reset active to Clean", self.reset_active).pack(side="right", padx=4)

    def create_from_template(self, template_name: str) -> None:
        existing = [profile.name for profile in self.app.profiles.items]
        name = unique_profile_name(existing, template_name)
        self.app.profiles.create(name, clone=self.app.profiles.active)
        settings = template_settings(template_name)
        profile = self.app.profiles.update_active(name=name, **settings)
        self.app._apply_profile(profile)
        self.app._render_profiles()
        if hasattr(self.app, "home_notice"):
            self.app.home_notice.configure(text=f"Created profile '{name}'.", fg=GOOD)

    def reset_active(self) -> None:
        profile = self.app.profiles.active
        if not messagebox.askyesno(
            "Reset active profile",
            f"Reset '{profile.name}' to clean/default voice settings? Device routing and the profile name will be kept.",
            parent=self.app.root,
        ):
            return
        input_name = profile.input_device_name
        output_name = profile.output_device_name
        updated = self.app.profiles.update_active(
            voice="Clean",
            gain_db=0.0,
            wet=1.0,
            gate_db=-55.0,
            pitch_semitones=0.0,
            formant_color=0.0,
            eq_enabled=True,
            eq_80_db=0.0,
            eq_250_db=0.0,
            eq_1000_db=0.0,
            eq_4000_db=0.0,
            eq_12000_db=0.0,
            noise_suppression=0.45,
            agc_enabled=True,
            agc_target_dbfs=-18.0,
            agc_max_gain_db=12.0,
            cleanup_backend="auto",
            echo_cancellation=False,
            effect_order=list(DEFAULT_EFFECT_ORDER),
            disabled_effects=[],
            soundboard_master=0.85,
            soundboard_duck_db=0.0,
            allow_overlap=True,
            sample_rate=48000,
            blocksize=256,
            input_device_name=input_name,
            output_device_name=output_name,
        )
        self.app._apply_profile(updated)
        self.app._render_profiles()


def install_profile_templates(app) -> ProfileTemplateUI:
    extension = ProfileTemplateUI(app)
    app.profile_template_ui = extension
    return extension
