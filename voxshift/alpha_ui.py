from __future__ import annotations

from pathlib import Path
from threading import Thread
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .dsp import DEFAULT_EFFECT_ORDER
from .playlists import PlaylistController
from .pro_ui import (
    ACCENT,
    ACCENT_2,
    BG,
    BORDER,
    GOOD,
    MUTED,
    PANEL,
    PANEL_2,
    TEXT,
    WARN,
    OxShiftStudioUI,
)
from .waveform import WaveformEnvelope, load_waveform


class OxShiftAlphaUI(OxShiftStudioUI):
    """Alpha product shell layered on the proven Studio UI.

    Legacy UI modules remain importable for rollback/debugging, but the package entry point
    targets this class. Disk-heavy waveform/model work stays on UI/background threads; the
    PortAudio callback remains owned by AudioEngine.
    """

    def __init__(self, root: tk.Tk) -> None:
        self.effect_order = list(DEFAULT_EFFECT_ORDER)
        self.disabled_effects: set[str] = set()
        self.cleanup_backend_var = tk.StringVar(master=root, value="auto")
        self.noise_suppression_var = tk.DoubleVar(master=root, value=45.0)
        self.agc_enabled_var = tk.BooleanVar(master=root, value=True)
        self.agc_target_var = tk.DoubleVar(master=root, value=-18.0)
        self.agc_max_var = tk.DoubleVar(master=root, value=12.0)
        self.echo_cancel_var = tk.BooleanVar(master=root, value=False)
        self.playlist_name_var = tk.StringVar(master=root, value="")
        self._waveform_token = 0
        super().__init__(root)

    # ---------- Studio / microphone conditioning / reorderable FX ----------

    def _studio(self):
        page = self._page()
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(1, weight=1)

        voice = self._card(page)
        voice.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 10))
        tk.Label(voice, text="Voice transformation", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        for label, var, lo, hi in (
            ("Pitch (st)", self.pitch, -12, 12),
            ("Timbre / formant color", self.formant, -100, 100),
            ("Wet mix", self.wet, 0, 100),
            ("Gain (dB)", self.gain, -18, 18),
            ("Noise gate (dB)", self.gate, -80, -20),
        ):
            self._slider(voice, label, var, lo, hi, self._sync_dsp).pack(fill="x", padx=14, pady=5)

        cleanup = self._card(page)
        cleanup.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 10))
        tk.Label(cleanup, text="Microphone conditioning", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 6))
        row = tk.Frame(cleanup, bg=PANEL)
        row.pack(fill="x", padx=14, pady=5)
        tk.Label(row, text="Backend", bg=PANEL, fg=MUTED).pack(side="left")
        backend = ttk.Combobox(row, textvariable=self.cleanup_backend_var, values=("auto", "builtin", "webrtc"), state="readonly", width=12, style="Ox.TCombobox")
        backend.pack(side="right")
        backend.bind("<<ComboboxSelected>>", lambda _e: self._sync_cleanup())
        self._slider(cleanup, "Noise suppression", self.noise_suppression_var, 0, 100, self._sync_cleanup).pack(fill="x", padx=14, pady=5)
        self._slider(cleanup, "AGC target (dBFS)", self.agc_target_var, -30, -8, self._sync_cleanup).pack(fill="x", padx=14, pady=5)
        self._slider(cleanup, "AGC max gain (dB)", self.agc_max_var, 0, 24, self._sync_cleanup).pack(fill="x", padx=14, pady=5)
        tk.Checkbutton(cleanup, text="Automatic gain control", variable=self.agc_enabled_var, command=self._sync_cleanup, bg=PANEL, fg=TEXT, selectcolor=PANEL_2, activebackground=PANEL, activeforeground=TEXT).pack(anchor="w", padx=14, pady=3)
        tk.Checkbutton(cleanup, text="Echo cancellation (requires true far-end reference)", variable=self.echo_cancel_var, command=self._sync_cleanup, bg=PANEL, fg=TEXT, selectcolor=PANEL_2, activebackground=PANEL, activeforeground=TEXT).pack(anchor="w", padx=14, pady=(3, 12))

        chain = self._card(page)
        chain.grid(row=1, column=0, columnspan=2, sticky="nsew")
        header = tk.Frame(chain, bg=PANEL)
        header.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(header, text="Custom effects chain", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(side="left")
        tk.Label(header, text="Reorder or bypass stages; changes are profile-persistent", bg=PANEL, fg=MUTED).pack(side="right")
        self.effect_chain_frame = tk.Frame(chain, bg=PANEL)
        self.effect_chain_frame.pack(fill="both", expand=True, padx=10, pady=(2, 12))
        self._render_effect_chain()
        return page

    def _render_effect_chain(self):
        if not hasattr(self, "effect_chain_frame"):
            return
        for child in self.effect_chain_frame.winfo_children():
            child.destroy()
        for index, effect in enumerate(self.effect_order):
            row = tk.Frame(self.effect_chain_frame, bg=PANEL_2, highlightbackground=BORDER, highlightthickness=1)
            row.pack(fill="x", pady=3)
            enabled = effect not in self.disabled_effects
            tk.Label(row, text=f"{index + 1:02d}  {effect.replace('_', ' ').title()}", bg=PANEL_2, fg=TEXT if enabled else MUTED, font=("TkDefaultFont", 9, "bold")).pack(side="left", padx=10, pady=8)
            self._button(row, "↓", lambda e=effect: self._move_effect(e, 1)).pack(side="right", padx=2, pady=5)
            self._button(row, "↑", lambda e=effect: self._move_effect(e, -1)).pack(side="right", padx=2, pady=5)
            self._button(row, "Bypass" if enabled else "Enable", lambda e=effect: self._toggle_effect(e), primary=not enabled).pack(side="right", padx=5, pady=5)

    def _move_effect(self, effect: str, delta: int) -> None:
        if effect not in self.effect_order:
            return
        old = self.effect_order.index(effect)
        new = max(0, min(len(self.effect_order) - 1, old + delta))
        if old != new:
            self.effect_order.pop(old)
            self.effect_order.insert(new, effect)
            self._sync_dsp()
            self._render_effect_chain()

    def _toggle_effect(self, effect: str) -> None:
        if effect in self.disabled_effects:
            self.disabled_effects.remove(effect)
        else:
            self.disabled_effects.add(effect)
        self._sync_dsp()
        self._render_effect_chain()

    def _sync_dsp(self):
        self.engine.update_settings(
            preset=self.voice.get(),
            gain_db=float(self.gain.get()),
            wet=float(self.wet.get()) / 100.0,
            gate_db=float(self.gate.get()),
            pitch_semitones=float(self.pitch.get()),
            formant_color=float(self.formant.get()) / 100.0,
            effect_order=tuple(self.effect_order),
            disabled_effects=tuple(sorted(self.disabled_effects)),
        )

    def _sync_cleanup(self):
        self.engine.update_cleanup(
            backend=self.cleanup_backend_var.get(),
            noise_suppression=float(self.noise_suppression_var.get()) / 100.0,
            agc_enabled=bool(self.agc_enabled_var.get()),
            agc_target_dbfs=float(self.agc_target_var.get()),
            agc_max_gain_db=float(self.agc_max_var.get()),
            echo_cancellation=bool(self.echo_cancel_var.get()),
        )

    # ---------- Soundboard editor / waveform / playlists ----------

    def _soundboard(self):
        page = self._page()
        self.playlists = PlaylistController(self.engine.soundboard)
        self.playlist_name_var.set(self.playlists.active_name)

        bar = self._card(page)
        bar.pack(fill="x", pady=(0, 8))
        tk.Entry(bar, textvariable=self.search_sound, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0).pack(side="left", fill="x", expand=True, padx=12, pady=10)
        self.search_sound.trace_add("write", lambda *_: self._render_sounds())
        self._button(bar, "Import", self._import_sounds, primary=True).pack(side="right", padx=6, pady=7)
        self._button(bar, "Stop all", self.engine.soundboard.stop_all, danger=True).pack(side="right", padx=6, pady=7)

        controls = self._card(page)
        controls.pack(fill="x", pady=(0, 8))
        self._slider(controls, "Master", self.sound_master, 0, 120, self._sync_board).pack(side="left", fill="x", expand=True, padx=10, pady=7)
        self._slider(controls, "Mic duck", self.duck, 0, 24, self._sync_board).pack(side="left", fill="x", expand=True, padx=10, pady=7)
        tk.Checkbutton(controls, text="Allow overlap", variable=self.overlap, command=self._sync_board, bg=PANEL, fg=TEXT, selectcolor=PANEL_2, activebackground=PANEL, activeforeground=TEXT).pack(side="left", padx=12)

        playlist_bar = self._card(page)
        playlist_bar.pack(fill="x", pady=(0, 8))
        tk.Label(playlist_bar, text="Playlist", bg=PANEL, fg=MUTED).pack(side="left", padx=(12, 6))
        self.playlist_combo = ttk.Combobox(playlist_bar, textvariable=self.playlist_name_var, values=self.playlists.names(), state="readonly", width=22, style="Ox.TCombobox")
        self.playlist_combo.pack(side="left", pady=8)
        self.playlist_combo.bind("<<ComboboxSelected>>", lambda _e: self._playlist_select())
        self._button(playlist_bar, "New", self._new_playlist).pack(side="left", padx=4, pady=6)
        self._button(playlist_bar, "Delete", self._delete_playlist, danger=True).pack(side="left", padx=4, pady=6)
        self._button(playlist_bar, "Play", self._play_playlist, primary=True).pack(side="right", padx=4, pady=6)
        self._button(playlist_bar, "Next", self._next_playlist).pack(side="right", padx=4, pady=6)
        self._button(playlist_bar, "Stop", self.playlists.stop).pack(side="right", padx=4, pady=6)

        body = tk.Frame(page, bg=BG)
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        right = self._card(body)
        right.pack(side="left", fill="both", expand=True, padx=(5, 0))
        self.sound_list = tk.Frame(left, bg=BG)
        self.sound_list.pack(fill="both", expand=True)
        self.sound_editor = right
        self._render_sounds()
        self._render_sound_editor(None)
        return page

    def _render_sounds(self):
        if not hasattr(self, "sound_list"):
            return
        for child in self.sound_list.winfo_children():
            child.destroy()
        query = self.search_sound.get().lower().strip()
        items = [item for item in self.engine.soundboard.items if not query or query in item.name.lower() or query in item.category.lower()]
        for item in items:
            row = self._card(self.sound_list)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=item.name, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(side="left", padx=10, pady=10)
            tk.Label(row, text=f"{Path(item.path).suffix.upper()[1:]} · {int(item.volume * 100)}%", bg=PANEL, fg=MUTED).pack(side="left")
            self._button(row, "Remove", lambda i=item.id: self._remove_sound_alpha(i), danger=True).pack(side="right", padx=3, pady=6)
            self._button(row, "Edit", lambda i=item.id: self._render_sound_editor(i)).pack(side="right", padx=3, pady=6)
            self._button(row, "+ Playlist", lambda i=item.id: self._add_to_playlist(i)).pack(side="right", padx=3, pady=6)
            self._button(row, "Play", lambda i=item.id: self._play_sound(i), primary=True).pack(side="right", padx=3, pady=6)

    def _remove_sound_alpha(self, item_id: str) -> None:
        self.engine.soundboard.remove(item_id)
        self.playlists.prune_missing()
        self._render_sounds()
        self._render_sound_editor(None)
        self._refresh_hotkeys()

    def _render_sound_editor(self, item_id: str | None) -> None:
        if not hasattr(self, "sound_editor"):
            return
        for child in self.sound_editor.winfo_children():
            child.destroy()
        item = self.engine.soundboard.get(item_id) if item_id else None
        if item is None:
            tk.Label(self.sound_editor, text="Waveform editor", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
            tk.Label(self.sound_editor, text="Select Edit on a sound to set trim, fades, loop and volume non-destructively.", bg=PANEL, fg=MUTED, wraplength=440, justify="left").pack(anchor="w", padx=14, pady=6)
            return

        self._editing_sound_id = item.id
        tk.Label(self.sound_editor, text=item.name, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        self.wave_canvas = tk.Canvas(self.sound_editor, height=150, bg=PANEL_2, highlightbackground=BORDER, highlightthickness=1)
        self.wave_canvas.pack(fill="x", padx=14, pady=8)
        self.wave_canvas.create_text(12, 12, anchor="nw", text="Loading waveform…", fill=MUTED)

        self.edit_volume = tk.DoubleVar(master=self.root, value=item.volume * 100.0)
        self.edit_trim_start = tk.DoubleVar(master=self.root, value=item.trim_start)
        self.edit_trim_end = tk.DoubleVar(master=self.root, value=item.trim_end)
        self.edit_fade_in = tk.DoubleVar(master=self.root, value=item.fade_in)
        self.edit_fade_out = tk.DoubleVar(master=self.root, value=item.fade_out)
        self.edit_loop = tk.BooleanVar(master=self.root, value=item.loop)

        fields = tk.Frame(self.sound_editor, bg=PANEL)
        fields.pack(fill="x", padx=14, pady=4)
        for row, (label, variable) in enumerate((
            ("Volume %", self.edit_volume),
            ("Trim start (s)", self.edit_trim_start),
            ("Trim end (s, 0 = end)", self.edit_trim_end),
            ("Fade in (s)", self.edit_fade_in),
            ("Fade out (s)", self.edit_fade_out),
        )):
            tk.Label(fields, text=label, bg=PANEL, fg=MUTED).grid(row=row, column=0, sticky="w", pady=3)
            tk.Entry(fields, textvariable=variable, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", width=14).grid(row=row, column=1, sticky="e", padx=(12, 0), pady=3)
        fields.grid_columnconfigure(0, weight=1)
        tk.Checkbutton(self.sound_editor, text="Loop", variable=self.edit_loop, bg=PANEL, fg=TEXT, selectcolor=PANEL_2, activebackground=PANEL, activeforeground=TEXT).pack(anchor="w", padx=14, pady=5)
        self._button(self.sound_editor, "Save edit", self._save_sound_edit, primary=True).pack(fill="x", padx=14, pady=(6, 14))

        self._waveform_token += 1
        token = self._waveform_token
        path = item.path

        def worker():
            try:
                envelope = load_waveform(path, points=700, target_rate=self.engine.sample_rate)
                self.root.after(0, lambda: self._draw_waveform(envelope) if token == self._waveform_token else None)
            except Exception as exc:
                self.root.after(0, lambda: self._waveform_error(str(exc)) if token == self._waveform_token else None)

        Thread(target=worker, name="OxShiftWaveform", daemon=True).start()

    def _draw_waveform(self, envelope: WaveformEnvelope) -> None:
        canvas = getattr(self, "wave_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        canvas.update_idletasks()
        width = max(200, canvas.winfo_width())
        height = max(80, canvas.winfo_height())
        mid = height / 2.0
        points = max(1, envelope.points)
        step = max(1, points // max(1, width))
        for i in range(0, points, step):
            x = (i / max(1, points - 1)) * width
            top = mid - float(envelope.maximum[i]) * mid * 0.9
            bottom = mid - float(envelope.minimum[i]) * mid * 0.9
            canvas.create_line(x, top, x, bottom, fill=ACCENT_2)
        canvas.create_text(8, 8, anchor="nw", text=f"{envelope.duration_seconds:.2f}s", fill=MUTED)

    def _waveform_error(self, text: str) -> None:
        canvas = getattr(self, "wave_canvas", None)
        if canvas is not None and canvas.winfo_exists():
            canvas.delete("all")
            canvas.create_text(10, 10, anchor="nw", text=f"Preview unavailable: {text}", fill=WARN, width=420)

    def _save_sound_edit(self) -> None:
        item_id = getattr(self, "_editing_sound_id", "")
        try:
            start = max(0.0, float(self.edit_trim_start.get()))
            end = max(0.0, float(self.edit_trim_end.get()))
            if end and end < start:
                raise ValueError("trim end must be after trim start")
            self.engine.soundboard.update_item(
                item_id,
                volume=float(self.edit_volume.get()) / 100.0,
                trim_start=start,
                trim_end=end,
                fade_in=max(0.0, float(self.edit_fade_in.get())),
                fade_out=max(0.0, float(self.edit_fade_out.get())),
                loop=bool(self.edit_loop.get()),
            )
            self._render_sounds()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Sound edit", str(exc))

    def _playlist_select(self) -> None:
        self.playlists.select(self.playlist_name_var.get())

    def _new_playlist(self) -> None:
        name = simpledialog.askstring("New playlist", "Playlist name:", parent=self.root)
        if not name:
            return
        try:
            playlist = self.playlists.create(name)
            self.playlist_name_var.set(playlist.name)
            self.playlist_combo["values"] = self.playlists.names()
        except ValueError as exc:
            messagebox.showerror("Playlist", str(exc))

    def _delete_playlist(self) -> None:
        if not self.playlists.delete_active():
            messagebox.showinfo("Playlist", "At least one playlist must remain.")
        self.playlist_name_var.set(self.playlists.active_name)
        self.playlist_combo["values"] = self.playlists.names()

    def _add_to_playlist(self, item_id: str) -> None:
        self.playlists.select(self.playlist_name_var.get())
        if not self.playlists.add(item_id):
            messagebox.showinfo("Playlist", "Sound is already in this playlist or no longer exists.")

    def _play_playlist(self) -> None:
        if self.engine.last_status != "Running":
            self._start()
        if self.engine.last_status == "Running":
            self.playlists.select(self.playlist_name_var.get())
            self.playlists.play()

    def _next_playlist(self) -> None:
        if self.engine.last_status == "Running":
            self.playlists.next()

    # ---------- Models ----------

    def _import_models(self):
        paths = filedialog.askopenfilenames(
            title="Import local model or validated bundle",
            filetypes=[("OxShift bundle / model", "*.json *.onnx *.pth *.index"), ("All files", "*")],
        )
        errors: list[str] = []
        for raw in paths:
            path = Path(raw)
            try:
                if path.name == "oxshift-model.json":
                    self.ai_registry.import_validated_bundle(path)
                else:
                    self.ai_registry.import_files([str(path)])
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
        self._refresh_models()
        if errors:
            messagebox.showwarning("Model import", "Some items were rejected:\n\n" + "\n".join(errors[:8]))

    def _refresh_models(self):
        if not hasattr(self, "ai_list"):
            return
        caps = self.ai_registry.capabilities()
        models = self.ai_registry.scan()
        executable = sum(1 for model in models if model.executable)
        self.ai_status.configure(
            text=(
                f"ONNX Runtime: {'ready' if caps.onnxruntime else 'not installed'}\n"
                f"Providers: {', '.join(caps.providers) if caps.providers else 'none'}\n"
                f"Validated executable bundles: {executable} · Raw imports are quarantined"
            )
        )
        for child in self.ai_list.winfo_children():
            child.destroy()
        for model in models:
            row = self._card(self.ai_list)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=model.name, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(side="left", padx=12, pady=12)
            status_color = GOOD if model.executable else (WARN if model.backend in {"quarantined", "validation-pending-runtime"} else "#ef6c7d")
            tk.Label(row, text=f"{model.format.upper()} · {model.backend}", bg=PANEL, fg=status_color).pack(side="right", padx=12)
            if model.validation_error:
                tk.Label(row, text=model.validation_error, bg=PANEL, fg=MUTED, wraplength=500, justify="left").pack(side="right", padx=8)

    # ---------- Audio route recovery / profile persistence ----------

    def _audio(self):
        page = self._page()
        route = self._card(page)
        route.pack(fill="x", pady=(0, 10))
        tk.Label(route, text="Input microphone", bg=PANEL, fg=MUTED).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 3))
        tk.Label(route, text="Output / virtual sink", bg=PANEL, fg=MUTED).grid(row=0, column=1, sticky="w", padx=14, pady=(12, 3))
        self.input_combo = ttk.Combobox(route, state="readonly", style="Ox.TCombobox")
        self.output_combo = ttk.Combobox(route, state="readonly", style="Ox.TCombobox")
        self.input_combo.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        self.output_combo.grid(row=1, column=1, sticky="ew", padx=14, pady=(0, 12))
        route.grid_columnconfigure(0, weight=1)
        route.grid_columnconfigure(1, weight=1)

        actions = self._card(page)
        actions.pack(fill="x", pady=(0, 10))
        self._button(actions, "Start", self._start, primary=True).pack(side="left", padx=12, pady=12)
        self._button(actions, "Stop", self._stop).pack(side="left", padx=4, pady=12)
        self._button(actions, "Refresh devices", self._load_devices).pack(side="left", padx=4, pady=12)
        self._button(actions, "Recover now", self.engine.request_recovery).pack(side="left", padx=4, pady=12)
        tk.Label(actions, text="Recommended: 48 kHz / 256 samples", bg=PANEL, fg=MUTED).pack(side="right", padx=12)

        health = self._card(page)
        health.pack(fill="x")
        tk.Label(health, text="Device recovery", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        self.recovery_text = tk.Label(health, text="No recovery attempts", bg=PANEL, fg=MUTED, justify="left")
        self.recovery_text.pack(anchor="w", padx=14, pady=(0, 12))
        tk.Label(health, text="Windows Alpha uses a user-installed signed virtual-audio driver (for example VB-CABLE/VoiceMeeter); OxShift does not silently install kernel drivers.", bg=PANEL, fg=MUTED, wraplength=900, justify="left").pack(anchor="w", padx=14, pady=(0, 12))
        return page

    def _load_devices(self):
        previous_input = ""
        previous_output = ""
        if hasattr(self, "input_combo") and self.input_combo.current() >= 0 and getattr(self, "_inputs", None):
            previous_input = self._inputs[self.input_combo.current()][1]
        if hasattr(self, "output_combo") and self.output_combo.current() >= 0 and getattr(self, "_outputs", None):
            previous_output = self._outputs[self.output_combo.current()][1]
        if not previous_input:
            previous_input = getattr(self.profiles.active, "input_device_name", "")
        if not previous_output:
            previous_output = getattr(self.profiles.active, "output_device_name", "")

        try:
            devices = list(self.engine.devices())
        except Exception as exc:
            if hasattr(self, "input_combo"):
                messagebox.showerror("Audio devices", str(exc))
            devices = []
        self._devices = devices
        self._inputs = [(i, d["name"]) for i, d in enumerate(devices) if d.get("max_input_channels", 0) > 0]
        self._outputs = [(i, d["name"]) for i, d in enumerate(devices) if d.get("max_output_channels", 0) > 0]
        if hasattr(self, "input_combo"):
            self.input_combo["values"] = [f"{i}: {name}" for i, name in self._inputs]
            self.output_combo["values"] = [f"{i}: {name}" for i, name in self._outputs]
            if self._inputs:
                pick = next((j for j, (_, name) in enumerate(self._inputs) if name == previous_input), 0)
                self.input_combo.current(pick)
            if self._outputs:
                preferred = next((j for j, (_, name) in enumerate(self._outputs) if name == previous_output), None)
                if preferred is None:
                    preferred = next((j for j, (_, name) in enumerate(self._outputs) if "oxshift" in name.lower() or "voxshift" in name.lower() or "cable input" in name.lower()), 0)
                self.output_combo.current(preferred)

    def _start(self):
        if not hasattr(self, "input_combo"):
            self._show("Audio")
            return
        try:
            self._sync_dsp()
            self._sync_cleanup()
            self._sync_board()
            ii = self.input_combo.current()
            oi = self.output_combo.current()
            self.engine.start(
                self._inputs[ii][0] if 0 <= ii < len(self._inputs) else None,
                self._outputs[oi][0] if 0 <= oi < len(self._outputs) else None,
                sample_rate=self.profiles.active.sample_rate,
                blocksize=self.profiles.active.blocksize,
            )
        except Exception as exc:
            messagebox.showerror("Could not start", str(exc))

    def _save_profile(self):
        input_name = self._inputs[self.input_combo.current()][1] if hasattr(self, "input_combo") and 0 <= self.input_combo.current() < len(self._inputs) else ""
        output_name = self._outputs[self.output_combo.current()][1] if hasattr(self, "output_combo") and 0 <= self.output_combo.current() < len(self._outputs) else ""
        profile = self.profiles.update_active(
            name=self.profile_name.get(),
            voice=self.voice.get(),
            gain_db=self.gain.get(),
            wet=self.wet.get() / 100.0,
            gate_db=self.gate.get(),
            pitch_semitones=self.pitch.get(),
            formant_color=self.formant.get() / 100.0,
            noise_suppression=self.noise_suppression_var.get() / 100.0,
            agc_enabled=self.agc_enabled_var.get(),
            agc_target_dbfs=self.agc_target_var.get(),
            agc_max_gain_db=self.agc_max_var.get(),
            cleanup_backend=self.cleanup_backend_var.get(),
            echo_cancellation=self.echo_cancel_var.get(),
            effect_order=list(self.effect_order),
            disabled_effects=sorted(self.disabled_effects),
            soundboard_master=self.sound_master.get() / 100.0,
            soundboard_duck_db=self.duck.get(),
            allow_overlap=self.overlap.get(),
            sample_rate=self.engine.sample_rate,
            blocksize=self.engine.blocksize,
            input_device_name=input_name,
            output_device_name=output_name,
        )
        self.profile_name.set(profile.name)
        self._render_profiles()

    def _apply_profile(self, profile):
        super()._apply_profile(profile)
        self.cleanup_backend_var.set(profile.cleanup_backend)
        self.noise_suppression_var.set(profile.noise_suppression * 100.0)
        self.agc_enabled_var.set(profile.agc_enabled)
        self.agc_target_var.set(profile.agc_target_dbfs)
        self.agc_max_var.set(profile.agc_max_gain_db)
        self.echo_cancel_var.set(profile.echo_cancellation)
        self.effect_order = list(profile.effect_order)
        self.disabled_effects = set(profile.disabled_effects)
        self._sync_cleanup()
        self._sync_dsp()
        self._render_effect_chain()
        if hasattr(self, "input_combo"):
            self._load_devices()

    def _tick(self):
        if hasattr(self, "playlists"):
            self.playlists.tick()
        if hasattr(self, "recovery_text"):
            error = f"\nLast error: {self.engine.last_recovery_error}" if self.engine.last_recovery_error else ""
            self.recovery_text.configure(text=f"Attempts {self.engine.recovery_attempts} · recovered {self.engine.recovery_successes} · callback errors {self.engine.callback_errors}{error}")
        super()._tick()
