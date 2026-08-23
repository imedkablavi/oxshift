from __future__ import annotations

from threading import Thread
import tkinter as tk
from tkinter import messagebox

from .audio_probe import MicrophoneProbeResult, probe_microphone
from .hotkey_syntax import normalize_hotkey
from .pro_ui import GOOD, MUTED, PANEL, PANEL_2, TEXT, WARN


class ProductExtras:
    """Small UX services installed after the main product shell is constructed."""

    def __init__(self, app) -> None:
        self.app = app
        self.root = app.root
        self._original_schedule_autosave = app._schedule_autosave
        self._original_refresh_hotkeys = app._refresh_hotkeys
        self._original_render_sound_editor = app._render_sound_editor
        self._probe_running = False
        self._install_guards()
        self._install_header_actions()
        self._install_audio_probe()
        self._apply_saved_preferences()
        self.root.bind_all("<Control-comma>", self._shortcut_preferences)

    def _install_guards(self) -> None:
        # Instance-level wrappers keep the underlying Alpha implementation intact while
        # allowing user-facing preferences/extensions to control optional behavior.
        self.app._schedule_autosave = self._guarded_autosave
        self.app._refresh_hotkeys = self._guarded_refresh_hotkeys
        self.app._render_sound_editor = self._render_sound_editor_with_metadata

        if hasattr(self.app, "input_combo"):
            self.app.input_combo.bind("<<ComboboxSelected>>", lambda _e: self.app._schedule_autosave(), add="+")
        if hasattr(self.app, "output_combo"):
            self.app.output_combo.bind("<<ComboboxSelected>>", lambda _e: self.app._schedule_autosave(), add="+")

    def _guarded_autosave(self) -> None:
        if self.app.ui_preferences.state.autosave_profile:
            self._original_schedule_autosave()

    def _guarded_refresh_hotkeys(self) -> None:
        if self.app.ui_preferences.state.global_hotkeys_enabled:
            self._original_refresh_hotkeys()
        else:
            self.app.hotkeys.stop()

    def _install_header_actions(self) -> None:
        top = self.app.title.master
        self.preferences_button = self.app._button(top, "Preferences", self.open_preferences)
        self.preferences_button.pack(side="right", padx=(0, 8))

    def _install_audio_probe(self) -> None:
        page = self.app.pages.get("Audio")
        if page is None:
            return
        card = self.app._card(page)
        card.pack(fill="x", pady=(10, 0))
        tk.Label(card, text="Microphone test", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 3))
        tk.Label(
            card,
            text="Measures microphone level for 1.5 seconds. Audio is not saved, routed to speakers, or sent through AI.",
            bg=PANEL,
            fg=MUTED,
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 6))
        line = tk.Frame(card, bg=PANEL)
        line.pack(fill="x", padx=10, pady=(0, 12))
        self.probe_button = self.app._button(line, "Test microphone", self.start_microphone_test, primary=True)
        self.probe_button.pack(side="left", padx=4)
        self.probe_status = tk.Label(line, text="Ready", bg=PANEL, fg=MUTED)
        self.probe_status.pack(side="left", padx=10)

    def _apply_saved_preferences(self) -> None:
        if not self.app.ui_preferences.state.global_hotkeys_enabled:
            self.app.hotkeys.stop()

    # ---------- Soundboard metadata / hotkey editor ----------

    def _render_sound_editor_with_metadata(self, item_id: str | None) -> None:
        self._original_render_sound_editor(item_id)
        if not item_id or not hasattr(self.app, "sound_editor"):
            return
        item = self.app.engine.soundboard.get(item_id)
        if item is None:
            return

        self._metadata_item_id = item.id
        self.sound_name_var = tk.StringVar(master=self.root, value=item.name)
        self.sound_category_var = tk.StringVar(master=self.root, value=item.category)
        self.sound_hotkey_var = tk.StringVar(master=self.root, value=item.hotkey)

        card = tk.Frame(self.app.sound_editor, bg=PANEL_2)
        card.pack(fill="x", padx=14, pady=(0, 14))
        tk.Label(card, text="Sound details", bg=PANEL_2, fg=TEXT, font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 5))
        for row, (label, variable) in enumerate((
            ("Display name", self.sound_name_var),
            ("Category", self.sound_category_var),
            ("Global hotkey", self.sound_hotkey_var),
        ), start=1):
            tk.Label(card, text=label, bg=PANEL_2, fg=MUTED).grid(row=row, column=0, sticky="w", padx=10, pady=4)
            tk.Entry(card, textvariable=variable, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat").grid(row=row, column=1, sticky="ew", padx=10, pady=4)
        card.grid_columnconfigure(1, weight=1)
        tk.Label(card, text="Hotkey examples: <f8> or <ctrl>+<alt>+1. Leave empty to disable.", bg=PANEL_2, fg=MUTED, justify="left").grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=(3, 7))
        self.sound_details_status = tk.Label(card, text="", bg=PANEL_2, fg=MUTED, justify="left")
        self.sound_details_status.grid(row=5, column=0, sticky="w", padx=10, pady=(0, 10))
        self.app._button(card, "Save details", self._save_sound_details, primary=True).grid(row=5, column=1, sticky="e", padx=10, pady=(0, 10))

    def _save_sound_details(self) -> None:
        item = self.app.engine.soundboard.get(getattr(self, "_metadata_item_id", ""))
        if item is None:
            return
        name = self.sound_name_var.get().strip()[:80]
        category = self.sound_category_var.get().strip()[:40] or "General"
        if not name:
            self.sound_details_status.configure(text="Name cannot be empty.", fg=WARN)
            return
        try:
            hotkey = normalize_hotkey(self.sound_hotkey_var.get())
        except ValueError as exc:
            self.sound_details_status.configure(text=str(exc), fg=WARN)
            return

        duplicate = next(
            (
                other
                for other in self.app.engine.soundboard.items
                if other.id != item.id and hotkey and str(other.hotkey).casefold() == hotkey.casefold()
            ),
            None,
        )
        if duplicate is not None:
            self.sound_details_status.configure(text=f"Hotkey already belongs to '{duplicate.name}'.", fg=WARN)
            return

        self.app.engine.soundboard.update_item(item.id, name=name, category=category, hotkey=hotkey)
        self.sound_hotkey_var.set(hotkey)
        self.app._refresh_hotkeys()
        self.app._render_sounds()
        if hotkey and self.app.hotkeys.last_error:
            self.sound_details_status.configure(text=f"Saved. Global listener unavailable: {self.app.hotkeys.last_error}", fg=WARN)
        else:
            self.sound_details_status.configure(text="Sound details saved.", fg=GOOD)

    # ---------- Preferences ----------

    def open_preferences(self) -> None:
        existing = getattr(self, "preferences_window", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return

        win = tk.Toplevel(self.root)
        self.preferences_window = win
        win.title("OxShift Preferences")
        win.geometry("560x430")
        win.resizable(False, False)
        win.configure(bg=self.app.root.cget("bg"))
        win.transient(self.root)

        autosave = tk.BooleanVar(master=win, value=self.app.ui_preferences.state.autosave_profile)
        hotkeys = tk.BooleanVar(master=win, value=self.app.ui_preferences.state.global_hotkeys_enabled)

        tk.Label(win, text="Preferences", bg=win.cget("bg"), fg=TEXT, font=("TkDefaultFont", 18, "bold")).pack(anchor="w", padx=20, pady=(20, 4))
        tk.Label(win, text="Product behavior only. Audio/voice settings remain inside Profiles and Studio.", bg=win.cget("bg"), fg=MUTED, wraplength=500, justify="left").pack(anchor="w", padx=20, pady=(0, 14))

        card = self.app._card(win)
        card.pack(fill="x", padx=20, pady=6)
        tk.Checkbutton(
            card,
            text="Autosave Studio and profile changes",
            variable=autosave,
            bg=PANEL,
            fg=TEXT,
            selectcolor=self.app.root.cget("bg"),
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 5))
        tk.Label(card, text="Manual save with Ctrl+S remains available when autosave is off.", bg=PANEL, fg=MUTED).pack(anchor="w", padx=34, pady=(0, 8))
        tk.Checkbutton(
            card,
            text="Enable global Soundboard hotkeys",
            variable=hotkeys,
            bg=PANEL,
            fg=TEXT,
            selectcolor=self.app.root.cget("bg"),
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(anchor="w", padx=14, pady=(4, 5))
        tk.Label(card, text="Wayland security policy may prevent global hotkeys; OxShift remains usable without them.", bg=PANEL, fg=MUTED, wraplength=470, justify="left").pack(anchor="w", padx=34, pady=(0, 12))

        maintenance = self.app._card(win)
        maintenance.pack(fill="x", padx=20, pady=6)
        tk.Label(maintenance, text="Setup & interface", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=14, pady=(12, 6))
        actions = tk.Frame(maintenance, bg=PANEL)
        actions.pack(fill="x", padx=10, pady=(0, 12))
        self.app._button(actions, "Run setup guide", lambda: self._reopen_setup(win)).pack(side="left", padx=4)
        self.app._button(actions, "Reset window size", self._reset_window_size).pack(side="left", padx=4)
        self.app._button(actions, "Refresh audio devices", self._refresh_devices).pack(side="left", padx=4)

        footer = tk.Frame(win, bg=win.cget("bg"))
        footer.pack(fill="x", padx=20, pady=(14, 20))
        self.app._button(footer, "Cancel", win.destroy).pack(side="right", padx=4)

        def save() -> None:
            prefs = self.app.ui_preferences.state
            prefs.autosave_profile = bool(autosave.get())
            prefs.global_hotkeys_enabled = bool(hotkeys.get())
            try:
                self.app.ui_preferences.save()
            except OSError as exc:
                messagebox.showerror("Preferences", f"Could not save preferences.\n\n{exc}", parent=win)
                return
            self._guarded_refresh_hotkeys()
            win.destroy()
            if hasattr(self.app, "home_notice"):
                self.app.home_notice.configure(text="Preferences saved.", fg=GOOD)

        self.app._button(footer, "Save", save, primary=True).pack(side="right", padx=4)

    def _shortcut_preferences(self, _event=None):
        self.open_preferences()
        return "break"

    def _reopen_setup(self, preferences_window: tk.Toplevel) -> None:
        preferences_window.destroy()
        self.app._open_onboarding(force=True)

    def _reset_window_size(self) -> None:
        self.root.geometry("1320x820")
        self.app.ui_preferences.state.window_geometry = "1320x820"
        try:
            self.app.ui_preferences.save()
        except OSError:
            pass

    def _refresh_devices(self) -> None:
        self.app._load_devices()
        if hasattr(self.app, "home_notice"):
            self.app.home_notice.configure(text="Audio devices refreshed.", fg=GOOD)

    # ---------- Microphone test ----------

    def start_microphone_test(self) -> None:
        if self._probe_running:
            return
        if self.app.engine.last_status == "Running":
            messagebox.showinfo(
                "Microphone test",
                "Stop the OxShift engine before running the isolated microphone test.",
                parent=self.root,
            )
            return
        index = self.app.input_combo.current() if hasattr(self.app, "input_combo") else -1
        if not (0 <= index < len(self.app._inputs)):
            messagebox.showinfo("Microphone test", "Choose an input microphone first.", parent=self.root)
            return

        device_index = self.app._inputs[index][0]
        self._probe_running = True
        self.probe_button.configure(state="disabled", text="Listening…")
        self.probe_status.configure(text="Speak normally for 1.5 seconds", fg=MUTED)

        def worker() -> None:
            try:
                result = probe_microphone(device_index, duration_seconds=1.5, sample_rate=self.app.profiles.active.sample_rate)
                self.root.after(0, lambda: self._finish_probe(result, None))
            except Exception as exc:
                self.root.after(0, lambda: self._finish_probe(None, str(exc)))

        Thread(target=worker, name="OxShiftMicProbe", daemon=True).start()

    def _finish_probe(self, result: MicrophoneProbeResult | None, error: str | None) -> None:
        self._probe_running = False
        try:
            if not self.probe_button.winfo_exists():
                return
        except tk.TclError:
            return
        self.probe_button.configure(state="normal", text="Test microphone")
        if error:
            self.probe_status.configure(text=f"Test failed: {error}", fg=WARN)
            return
        assert result is not None
        db = result.peak_dbfs
        if db > -5.0:
            text, color = f"Signal detected: {db:.1f} dBFS — very hot / may clip", WARN
        elif db > -35.0:
            text, color = f"Signal detected: {db:.1f} dBFS — good level", GOOD
        elif db > -55.0:
            text, color = f"Signal detected: {db:.1f} dBFS — quiet", WARN
        else:
            text, color = f"Very little signal: {db:.1f} dBFS — check mic/mute/gain", WARN
        self.probe_status.configure(text=text, fg=color)


def install_product_extras(app) -> ProductExtras:
    extras = ProductExtras(app)
    app.product_extras = extras
    return extras
