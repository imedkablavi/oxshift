from __future__ import annotations

import platform
import tkinter as tk
from tkinter import messagebox, ttk

from .alpha_ui import OxShiftAlphaUI
from .app_prefs import AppPreferencesStore, VALID_PAGES
from .pro_ui import ACCENT, ACCENT_2, BG, BORDER, GOOD, MUTED, PANEL, PANEL_2, TEXT, WARN
from .voices import VOICE_PRESETS


VIRTUAL_OUTPUT_HINTS = (
    "oxshift",
    "voxshift",
    "cable input",
    "vb-audio",
    "voicemeeter",
    "blackhole",
    "virtual audio",
    "virtual sink",
)


def looks_like_virtual_output(name: str) -> bool:
    lowered = str(name or "").casefold()
    return any(hint in lowered for hint in VIRTUAL_OUTPUT_HINTS)


def route_readiness(input_name: str, output_name: str, running: bool) -> dict[str, bool]:
    return {
        "input": bool(str(input_name).strip()),
        "output": bool(str(output_name).strip()),
        "virtual": looks_like_virtual_output(output_name),
        "running": bool(running),
    }


class OxShiftProductUI(OxShiftAlphaUI):
    """User-facing Alpha shell focused on first-run success and daily usability.

    This layer only orchestrates UI state. Audio processing, model inference, file decoding and
    device recovery continue to live in their dedicated non-UI components.
    """

    def __init__(self, root: tk.Tk) -> None:
        self.ui_preferences = AppPreferencesStore()
        self._ui_ready = False
        self._autosave_after: str | None = None
        self._onboarding_window: tk.Toplevel | None = None
        self._onboarding_step = 0
        self._wizard_input = tk.StringVar(master=root, value="")
        self._wizard_output = tk.StringVar(master=root, value="")
        self._wizard_voice = tk.StringVar(master=root, value="Clean")
        self._wizard_cleanup = tk.StringVar(master=root, value="Balanced")
        super().__init__(root)

        self.root.title("OxShift Studio — Alpha")
        self.root.geometry(self.ui_preferences.state.window_geometry)
        self._bind_product_shortcuts()
        self._ui_ready = True

        target = self.ui_preferences.state.last_page
        if target in self.pages and self.ui_preferences.state.onboarding_complete:
            self._show(target)
        else:
            self._show("Home")
        self.root.after(450, self._maybe_show_onboarding)

    # ---------- Product home ----------

    def _home(self):
        page = self._page()
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(2, weight=1)

        hero = self._card(page)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        hero.grid_columnconfigure(1, weight=1)
        badge = tk.Frame(hero, bg=ACCENT, width=60, height=60)
        badge.grid(row=0, column=0, rowspan=3, padx=16, pady=16)
        badge.grid_propagate(False)
        tk.Label(badge, text="OX", bg=ACCENT, fg="white", font=("TkDefaultFont", 14, "bold")).place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(hero, text="Your voice route, in one place", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 18, "bold")).grid(row=0, column=1, sticky="sw", pady=(14, 0))
        self.home_voice = tk.Label(hero, text=self.voice.get(), bg=PANEL, fg=ACCENT_2, font=("TkDefaultFont", 11, "bold"))
        self.home_voice.grid(row=1, column=1, sticky="w", pady=(2, 0))
        self.home_desc = tk.Label(hero, text="Choose a microphone, route it to a virtual output, then start the engine.", bg=PANEL, fg=MUTED, wraplength=650, justify="left")
        self.home_desc.grid(row=2, column=1, sticky="nw", pady=(2, 14))
        self.home_start_button = self._button(hero, "Start engine", self._start, primary=True)
        self.home_start_button.grid(row=0, column=2, rowspan=3, padx=16, pady=16)

        readiness = self._card(page)
        readiness.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(0, 10))
        tk.Label(readiness, text="Setup checklist", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        tk.Label(readiness, text="These four checks are enough to get sound into Discord, OBS, games or calls.", bg=PANEL, fg=MUTED, wraplength=620, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        self.readiness_labels: dict[str, tk.Label] = {}
        for key, title in (("input", "Microphone selected"), ("output", "Output selected"), ("virtual", "Virtual microphone route"), ("running", "Audio engine running")):
            row = tk.Frame(readiness, bg=PANEL_2)
            row.pack(fill="x", padx=14, pady=3)
            marker = tk.Label(row, text="○", bg=PANEL_2, fg=MUTED, font=("TkDefaultFont", 12, "bold"), width=2)
            marker.pack(side="left", padx=(8, 2), pady=7)
            tk.Label(row, text=title, bg=PANEL_2, fg=TEXT).pack(side="left", pady=7)
            self.readiness_labels[key] = marker
        self.home_route_text = tk.Label(readiness, text="Open Audio setup to choose devices.", bg=PANEL, fg=MUTED, wraplength=620, justify="left")
        self.home_route_text.pack(anchor="w", padx=14, pady=(8, 4))
        actions = tk.Frame(readiness, bg=PANEL)
        actions.pack(fill="x", padx=10, pady=(4, 12))
        self._button(actions, "Audio setup", lambda: self._show("Audio"), primary=True).pack(side="left", padx=4)
        self._button(actions, "Setup guide", lambda: self._open_onboarding(force=True)).pack(side="left", padx=4)
        self._button(actions, "Choose voice", lambda: self._show("Voices")).pack(side="left", padx=4)
        self._button(actions, "Add sounds", lambda: self._show("Soundboard")).pack(side="left", padx=4)

        health = self._card(page)
        health.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=(0, 10))
        tk.Label(health, text="Live engine health", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        self.in_meter = self._meter(health, "MIC")
        self.board_meter = self._meter(health, "SOUNDBOARD")
        self.out_meter = self._meter(health, "OUTPUT")
        self.health_text = tk.Label(health, text="Engine stopped", bg=PANEL, fg=MUTED, justify="left", font=("TkDefaultFont", 8))
        self.health_text.pack(anchor="w", padx=14, pady=(10, 6))
        self.home_notice = tk.Label(health, text="Audio stays on this computer.", bg=PANEL, fg=GOOD, wraplength=420, justify="left")
        self.home_notice.pack(anchor="w", padx=14, pady=(0, 10))
        self.record_text = tk.Label(health, text="Recorder ready", bg=PANEL, fg=MUTED)
        self.record_text.pack(anchor="w", padx=14, pady=(0, 6))
        recorder_actions = tk.Frame(health, bg=PANEL)
        recorder_actions.pack(fill="x", padx=10, pady=(0, 12))
        self._button(recorder_actions, "Record output", self._record).pack(side="left", padx=4)
        self._button(recorder_actions, "Stop recording", self._stop_record).pack(side="left", padx=4)

        quick = self._card(page)
        quick.grid(row=2, column=0, columnspan=2, sticky="nsew")
        tk.Label(quick, text="Fast workflow", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(quick, text="1. Pick a voice  →  2. Tune Studio  →  3. Add Soundboard clips  →  4. Route to your app", bg=PANEL, fg=MUTED).pack(anchor="w", padx=14, pady=(0, 8))
        row = tk.Frame(quick, bg=PANEL)
        row.pack(fill="x", padx=10, pady=(0, 12))
        for text, page_name in (("Voices", "Voices"), ("Studio", "Studio"), ("Soundboard", "Soundboard"), ("Profiles", "Profiles"), ("AI models", "AI Models")):
            self._button(row, text, lambda p=page_name: self._show(p)).pack(side="left", padx=4)
        return page

    # ---------- Useful empty states ----------

    def _render_sounds(self):
        super()._render_sounds()
        if not hasattr(self, "sound_list"):
            return
        query = self.search_sound.get().strip()
        visible = [item for item in self.engine.soundboard.items if not query or query.casefold() in item.name.casefold() or query.casefold() in item.category.casefold()]
        if visible:
            return
        box = self._card(self.sound_list)
        box.pack(fill="x", pady=8)
        if self.engine.soundboard.items:
            title, detail = "No matching sounds", "Clear the search or try a different name/category."
            action_text, action = "Clear search", lambda: self.search_sound.set("")
        else:
            title, detail = "Your Soundboard is empty", "Import a clip or song. OxShift streams it from disk and mixes it into the virtual microphone."
            action_text, action = "Import sounds", self._import_sounds
        tk.Label(box, text=title, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 3))
        tk.Label(box, text=detail, bg=PANEL, fg=MUTED, wraplength=560, justify="left").pack(anchor="w", padx=14, pady=(0, 10))
        self._button(box, action_text, action, primary=True).pack(anchor="w", padx=14, pady=(0, 14))

    def _refresh_models(self):
        super()._refresh_models()
        if not hasattr(self, "ai_list"):
            return
        if self.ai_registry.scan():
            return
        box = self._card(self.ai_list)
        box.pack(fill="x", pady=8)
        tk.Label(box, text="No local AI models yet", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 3))
        tk.Label(box, text="Raw ONNX/PTH imports are quarantined. Only an OxShift manifest with a known schema and matching checksums can become executable.", bg=PANEL, fg=MUTED, wraplength=720, justify="left").pack(anchor="w", padx=14, pady=(0, 10))
        self._button(box, "Import model or manifest", self._import_models, primary=True).pack(anchor="w", padx=14, pady=(0, 14))

    # ---------- Audio page usability ----------

    def _audio(self):
        page = super()._audio()
        guide = self._card(page)
        guide.pack(fill="x", pady=(10, 0))
        tk.Label(guide, text="Route guide", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 3))
        self.audio_route_guide = tk.Label(guide, text="Select a physical microphone and a virtual output, then press Start.", bg=PANEL, fg=MUTED, wraplength=900, justify="left")
        self.audio_route_guide.pack(anchor="w", padx=14, pady=(0, 6))
        self.audio_virtual_status = tk.Label(guide, text="", bg=PANEL, fg=MUTED, wraplength=900, justify="left")
        self.audio_virtual_status.pack(anchor="w", padx=14, pady=(0, 12))
        return page

    def _start(self):
        if not hasattr(self, "input_combo"):
            self._show("Audio")
            return
        if not self._selected_input_name():
            self._show("Audio")
            messagebox.showinfo("Choose a microphone", "Select an input microphone before starting OxShift.", parent=self.root)
            return
        if not self._selected_output_name():
            self._show("Audio")
            messagebox.showinfo("Choose an output", "Select an output device or virtual microphone route before starting OxShift.", parent=self.root)
            return
        super()._start()
        if self.engine.last_status == "Running" and hasattr(self, "home_notice"):
            self.home_notice.configure(text="Engine is running. Select the virtual microphone in your target app.", fg=GOOD)

    # ---------- Onboarding ----------

    def _maybe_show_onboarding(self) -> None:
        if not self.ui_preferences.state.onboarding_complete:
            self._open_onboarding(force=False)

    def _open_onboarding(self, force: bool = False) -> None:
        if self._onboarding_window is not None and self._onboarding_window.winfo_exists():
            self._onboarding_window.lift()
            return
        if self.ui_preferences.state.onboarding_complete and not force:
            return
        self._onboarding_step = 0
        win = tk.Toplevel(self.root)
        self._onboarding_window = win
        win.title("Set up OxShift")
        win.geometry("680x500")
        win.minsize(620, 460)
        win.configure(bg=BG)
        win.transient(self.root)
        win.protocol("WM_DELETE_WINDOW", self._close_onboarding)

        header = tk.Frame(win, bg=PANEL)
        header.pack(fill="x")
        tk.Label(header, text="OxShift setup", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 16, "bold")).pack(side="left", padx=18, pady=14)
        self.wizard_progress = tk.Label(header, text="1 / 4", bg=PANEL, fg=ACCENT_2, font=("TkDefaultFont", 9, "bold"))
        self.wizard_progress.pack(side="right", padx=18)

        self.wizard_body = tk.Frame(win, bg=BG)
        self.wizard_body.pack(fill="both", expand=True, padx=18, pady=16)
        footer = tk.Frame(win, bg=BG)
        footer.pack(fill="x", padx=18, pady=(0, 18))
        self.wizard_back = self._button(footer, "Back", self._wizard_previous)
        self.wizard_back.pack(side="left")
        self._button(footer, "Skip for now", self._close_onboarding).pack(side="left", padx=8)
        self.wizard_next = self._button(footer, "Next", self._wizard_next, primary=True)
        self.wizard_next.pack(side="right")
        self._render_wizard_step()

    def _render_wizard_step(self) -> None:
        body = self.wizard_body
        for child in body.winfo_children():
            child.destroy()
        self.wizard_progress.configure(text=f"{self._onboarding_step + 1} / 4")
        self.wizard_back.configure(state="normal" if self._onboarding_step > 0 else "disabled")
        self.wizard_next.configure(text="Finish setup" if self._onboarding_step == 3 else "Next")

        if self._onboarding_step == 0:
            tk.Label(body, text="Welcome to OxShift", bg=BG, fg=TEXT, font=("TkDefaultFont", 20, "bold")).pack(anchor="w", pady=(18, 8))
            tk.Label(body, text="OxShift processes microphone audio locally. This setup chooses the route and safe defaults; it will not upload audio, install a kernel driver silently, or start the microphone without you pressing Start.", bg=BG, fg=MUTED, wraplength=610, justify="left", font=("TkDefaultFont", 10)).pack(anchor="w", pady=(0, 18))
            self._wizard_info_card(body, "1", "Pick your physical microphone", "The device you actually speak into.")
            self._wizard_info_card(body, "2", "Pick a virtual output", "Your target app will receive this as its microphone source.")
            self._wizard_info_card(body, "3", "Choose a voice and cleanup preset", "You can change every setting later in Studio.")
        elif self._onboarding_step == 1:
            tk.Label(body, text="Choose your audio route", bg=BG, fg=TEXT, font=("TkDefaultFont", 18, "bold")).pack(anchor="w", pady=(10, 4))
            tk.Label(body, text="If the virtual output is not installed yet, choose any output for testing and finish the driver setup later from Audio.", bg=BG, fg=MUTED, wraplength=610, justify="left").pack(anchor="w", pady=(0, 16))
            input_values = [f"{index}: {name}" for index, name in self._inputs]
            output_values = [f"{index}: {name}" for index, name in self._outputs]
            if not self._wizard_input.get() and input_values:
                self._wizard_input.set(input_values[0])
            if not self._wizard_output.get() and output_values:
                preferred = next((value for value in output_values if looks_like_virtual_output(value)), output_values[0])
                self._wizard_output.set(preferred)
            self._wizard_combo(body, "Microphone", self._wizard_input, input_values)
            self._wizard_combo(body, "Output / virtual route", self._wizard_output, output_values)
            if not input_values or not output_values:
                tk.Label(body, text="One or more device lists are empty. You can still continue; use Refresh devices on the Audio page after fixing the OS audio device.", bg=BG, fg=WARN, wraplength=610, justify="left").pack(anchor="w", pady=10)
        elif self._onboarding_step == 2:
            tk.Label(body, text="Pick a starting sound", bg=BG, fg=TEXT, font=("TkDefaultFont", 18, "bold")).pack(anchor="w", pady=(10, 4))
            tk.Label(body, text="These are only defaults. Studio exposes pitch, timbre, gain, cleanup and the reorderable effects chain.", bg=BG, fg=MUTED, wraplength=610, justify="left").pack(anchor="w", pady=(0, 16))
            voice_values = [preset.name for preset in VOICE_PRESETS]
            self._wizard_combo(body, "Voice preset", self._wizard_voice, voice_values)
            self._wizard_combo(body, "Microphone cleanup", self._wizard_cleanup, ["Balanced", "Noise-heavy room", "Natural / minimal"])
        else:
            input_name = self._wizard_input.get() or "Not selected"
            output_name = self._wizard_output.get() or "Not selected"
            tk.Label(body, text="Ready to use OxShift", bg=BG, fg=TEXT, font=("TkDefaultFont", 18, "bold")).pack(anchor="w", pady=(10, 4))
            tk.Label(body, text="Nothing starts automatically. Press Finish, then Start engine when you are ready.", bg=BG, fg=MUTED, wraplength=610, justify="left").pack(anchor="w", pady=(0, 16))
            self._summary_row(body, "Microphone", input_name)
            self._summary_row(body, "Output", output_name)
            self._summary_row(body, "Voice", self._wizard_voice.get())
            self._summary_row(body, "Cleanup", self._wizard_cleanup.get())
            if not looks_like_virtual_output(output_name):
                tk.Label(body, text="The selected output does not look like a known virtual microphone. OxShift can still run for testing, but Discord/OBS/games normally need a virtual cable/sink route.", bg=BG, fg=WARN, wraplength=610, justify="left").pack(anchor="w", pady=12)

    def _wizard_info_card(self, parent, number: str, title: str, detail: str) -> None:
        row = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        row.pack(fill="x", pady=4)
        tk.Label(row, text=number, bg=ACCENT, fg="white", width=3, pady=8, font=("TkDefaultFont", 10, "bold")).pack(side="left", padx=10, pady=10)
        text = tk.Frame(row, bg=PANEL)
        text.pack(side="left", fill="x", expand=True, pady=8)
        tk.Label(text, text=title, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        tk.Label(text, text=detail, bg=PANEL, fg=MUTED).pack(anchor="w", pady=(2, 0))

    def _wizard_combo(self, parent, label: str, variable: tk.StringVar, values: list[str]) -> None:
        box = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        box.pack(fill="x", pady=6)
        tk.Label(box, text=label, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        combo = ttk.Combobox(box, textvariable=variable, values=values, state="readonly" if values else "disabled", style="Ox.TCombobox")
        combo.pack(fill="x", padx=12, pady=(0, 12))
        if values and not variable.get():
            variable.set(values[0])

    def _summary_row(self, parent, label: str, value: str) -> None:
        row = tk.Frame(parent, bg=PANEL_2)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, bg=PANEL_2, fg=MUTED, width=16, anchor="w").pack(side="left", padx=10, pady=8)
        tk.Label(row, text=value, bg=PANEL_2, fg=TEXT, anchor="w").pack(side="left", fill="x", expand=True, padx=8, pady=8)

    def _wizard_next(self) -> None:
        if self._onboarding_step == 1:
            self._apply_wizard_route()
        elif self._onboarding_step == 2:
            self._apply_wizard_sound()
        elif self._onboarding_step == 3:
            self._apply_wizard_route()
            self._apply_wizard_sound()
            self._autosave_now()
            self.ui_preferences.complete_onboarding()
            self._close_onboarding()
            self._show("Home")
            return
        self._onboarding_step = min(3, self._onboarding_step + 1)
        self._render_wizard_step()

    def _wizard_previous(self) -> None:
        self._onboarding_step = max(0, self._onboarding_step - 1)
        self._render_wizard_step()

    def _apply_wizard_route(self) -> None:
        if hasattr(self, "input_combo"):
            values = list(self.input_combo["values"])
            if self._wizard_input.get() in values:
                self.input_combo.current(values.index(self._wizard_input.get()))
        if hasattr(self, "output_combo"):
            values = list(self.output_combo["values"])
            if self._wizard_output.get() in values:
                self.output_combo.current(values.index(self._wizard_output.get()))

    def _apply_wizard_sound(self) -> None:
        voice = self._wizard_voice.get()
        if voice:
            self._select_voice(voice)
        cleanup = self._wizard_cleanup.get()
        if cleanup == "Noise-heavy room":
            self.noise_suppression_var.set(75.0)
            self.agc_enabled_var.set(True)
            self.agc_target_var.set(-18.0)
        elif cleanup == "Natural / minimal":
            self.noise_suppression_var.set(15.0)
            self.agc_enabled_var.set(False)
        else:
            self.noise_suppression_var.set(45.0)
            self.agc_enabled_var.set(True)
            self.agc_target_var.set(-18.0)
        self._sync_cleanup()

    def _close_onboarding(self) -> None:
        win, self._onboarding_window = self._onboarding_window, None
        if win is not None and win.winfo_exists():
            win.destroy()

    # ---------- Autosave, navigation and keyboard UX ----------

    def _sync_dsp(self):
        super()._sync_dsp()
        self._schedule_autosave()

    def _sync_cleanup(self):
        super()._sync_cleanup()
        self._schedule_autosave()

    def _sync_board(self):
        super()._sync_board()
        self._schedule_autosave()

    def _schedule_autosave(self) -> None:
        if not self._ui_ready:
            return
        if self._autosave_after is not None:
            try:
                self.root.after_cancel(self._autosave_after)
            except tk.TclError:
                pass
        self._autosave_after = self.root.after(700, self._autosave_now)

    def _autosave_now(self) -> None:
        self._autosave_after = None
        if not self._ui_ready:
            return
        try:
            super()._save_profile()
        except (OSError, tk.TclError, ValueError):
            # Autosave must never interrupt audio or produce modal dialogs while dragging a slider.
            return

    def _show(self, page):
        if self._ui_ready and page in self.pages:
            self._autosave_now()
        super()._show(page)
        if self._ui_ready and page in VALID_PAGES:
            self.ui_preferences.state.last_page = page
            try:
                self.ui_preferences.save()
            except OSError:
                pass

    def _bind_product_shortcuts(self) -> None:
        for index, page in enumerate(VALID_PAGES, start=1):
            self.root.bind_all(f"<Control-Key-{index}>", lambda _event, p=page: self._shortcut_page(p))
        self.root.bind_all("<Control-s>", self._shortcut_save)
        self.root.bind_all("<F5>", self._shortcut_refresh)

    def _shortcut_page(self, page: str):
        self._show(page)
        return "break"

    def _shortcut_save(self, _event=None):
        self._autosave_now()
        if hasattr(self, "home_notice"):
            self.home_notice.configure(text=f"Profile '{self.profile_name.get()}' saved.", fg=GOOD)
        return "break"

    def _shortcut_refresh(self, _event=None):
        self._load_devices()
        if hasattr(self, "home_notice"):
            self.home_notice.configure(text="Audio devices refreshed.", fg=GOOD)
        return "break"

    # ---------- Live summaries ----------

    def _selected_input_name(self) -> str:
        if not hasattr(self, "input_combo"):
            return ""
        index = self.input_combo.current()
        return self._inputs[index][1] if 0 <= index < len(self._inputs) else ""

    def _selected_output_name(self) -> str:
        if not hasattr(self, "output_combo"):
            return ""
        index = self.output_combo.current()
        return self._outputs[index][1] if 0 <= index < len(self._outputs) else ""

    def _update_product_readiness(self) -> None:
        input_name = self._selected_input_name()
        output_name = self._selected_output_name()
        status = route_readiness(input_name, output_name, self.engine.last_status == "Running")
        if hasattr(self, "readiness_labels"):
            for key, ready in status.items():
                self.readiness_labels[key].configure(text="●" if ready else "○", fg=GOOD if ready else MUTED)
        if hasattr(self, "home_route_text"):
            if input_name or output_name:
                self.home_route_text.configure(text=f"Input: {input_name or 'not selected'}\nOutput: {output_name or 'not selected'}")
            else:
                self.home_route_text.configure(text="Open Audio setup to choose devices.")
        if hasattr(self, "home_start_button"):
            self.home_start_button.configure(text="Engine running" if status["running"] else "Start engine")
        if hasattr(self, "audio_route_guide"):
            self.audio_route_guide.configure(text=f"Input: {input_name or 'not selected'}\nOutput: {output_name or 'not selected'}")
        if hasattr(self, "audio_virtual_status"):
            if status["virtual"]:
                self.audio_virtual_status.configure(text="Virtual route detected. Select its microphone endpoint in Discord/OBS/the target app.", fg=GOOD)
            elif output_name:
                self.audio_virtual_status.configure(text=self._platform_virtual_mic_hint(), fg=WARN)
            else:
                self.audio_virtual_status.configure(text="Choose an output device. For app routing, use a virtual cable/sink.", fg=MUTED)

    def _platform_virtual_mic_hint(self) -> str:
        if platform.system() == "Windows":
            return "This output does not look like VB-CABLE/VoiceMeeter. Install a trusted signed virtual-audio driver, then refresh devices."
        if platform.system() == "Linux":
            return "This output does not look like the OxShift virtual sink. Create/enable the PipeWire/Pulse virtual microphone, then refresh devices."
        return "This output does not look like a virtual microphone route. A virtual audio device may be required by your target app."

    def _tick(self):
        self._update_product_readiness()
        super()._tick()

    def _close(self):
        try:
            if self._autosave_after is not None:
                self.root.after_cancel(self._autosave_after)
                self._autosave_after = None
            self._autosave_now()
            self.ui_preferences.state.window_geometry = self.root.winfo_geometry()
            self.ui_preferences.state.last_page = self.current_page if self.current_page in VALID_PAGES else "Home"
            self.ui_preferences.save()
        except (OSError, tk.TclError, ValueError):
            pass
        finally:
            super()._close()
