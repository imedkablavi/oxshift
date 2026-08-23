from __future__ import annotations

from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .enhanced_ui import (
    ACCENT_2,
    BG,
    GOOD,
    MUTED,
    PANEL,
    PANEL_2,
    TEXT,
    OxShiftEnhancedUI,
)
from .waveform import WaveformEnvelope, load_waveform


class WaveformEditor:
    """Non-destructive Soundboard clip editor.

    The editor only writes trim/fade metadata. Source audio files are never modified.
    Waveform decoding runs in a worker thread so opening a long song does not freeze Tk.
    """

    def __init__(self, owner: "OxShiftAdvancedUI", item_id: str) -> None:
        self.owner = owner
        self.item = owner.engine.soundboard.get(item_id)
        if self.item is None:
            return
        self.window = tk.Toplevel(owner.root)
        self.window.title(f"Sound editor — {self.item.name}")
        self.window.geometry("920x520")
        self.window.minsize(760, 460)
        self.window.configure(bg=BG)

        self.trim_start = tk.DoubleVar(master=self.window, value=float(self.item.trim_start))
        self.trim_end = tk.DoubleVar(master=self.window, value=float(self.item.trim_end))
        self.fade_in = tk.DoubleVar(master=self.window, value=float(self.item.fade_in))
        self.fade_out = tk.DoubleVar(master=self.window, value=float(self.item.fade_out))
        self.volume = tk.DoubleVar(master=self.window, value=float(self.item.volume) * 100.0)
        self.loop = tk.BooleanVar(master=self.window, value=bool(self.item.loop))
        self.duration = 0.0
        self.envelope: WaveformEnvelope | None = None
        self.drag_handle: str | None = None

        top = owner._card(self.window)
        top.pack(fill="x", padx=14, pady=(14, 8))
        tk.Label(top, text=self.item.name, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 13, "bold")).pack(side="left", padx=12, pady=10)
        self.status = tk.Label(top, text="Loading waveform…", bg=PANEL, fg=MUTED)
        self.status.pack(side="right", padx=12)

        self.canvas = tk.Canvas(self.window, bg=PANEL_2, highlightthickness=1, highlightbackground="#273449", height=220)
        self.canvas.pack(fill="x", padx=14, pady=8)
        self.canvas.bind("<Configure>", lambda _e: self._draw())
        self.canvas.bind("<Button-1>", self._begin_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", lambda _e: setattr(self, "drag_handle", None))

        controls = owner._card(self.window)
        controls.pack(fill="both", expand=True, padx=14, pady=8)
        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=1)
        controls.grid_columnconfigure(2, weight=1)
        controls.grid_columnconfigure(3, weight=1)

        self._scale(controls, "Trim start (s)", self.trim_start, 0, 1, 0, 0)
        self._scale(controls, "Trim end (s, 0 = end)", self.trim_end, 0, 1, 0, 1)
        self._scale(controls, "Fade in (s)", self.fade_in, 0, 10, 1, 0)
        self._scale(controls, "Fade out (s)", self.fade_out, 0, 10, 1, 1)
        self._scale(controls, "Clip volume (%)", self.volume, 0, 200, 2, 0, colspan=2)
        tk.Checkbutton(
            controls,
            text="Loop clip",
            variable=self.loop,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).grid(row=2, column=2, sticky="w", padx=14, pady=14)

        actions = tk.Frame(self.window, bg=BG)
        actions.pack(fill="x", padx=14, pady=(4, 14))
        owner._button(actions, "Preview", self._preview, primary=True).pack(side="left")
        owner._button(actions, "Stop", lambda: owner.engine.soundboard.stop(self.item.id)).pack(side="left", padx=6)
        owner._button(actions, "Save changes", self._save, primary=True).pack(side="right")
        owner._button(actions, "Close", self.window.destroy).pack(side="right", padx=6)

        threading.Thread(target=self._load_worker, name="OxShiftWaveform", daemon=True).start()

    def _scale(self, parent, label, var, lo, hi, row, col, colspan=1) -> None:
        frame = tk.Frame(parent, bg=PANEL)
        frame.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=14, pady=8)
        tk.Label(frame, text=label, bg=PANEL, fg=MUTED).pack(anchor="w")
        line = tk.Frame(frame, bg=PANEL)
        line.pack(fill="x")
        scale = ttk.Scale(line, from_=lo, to=hi, variable=var, command=lambda _v: self._draw())
        scale.pack(side="left", fill="x", expand=True)
        value = tk.Label(line, bg=PANEL, fg=TEXT, width=8)
        value.pack(side="right", padx=(8, 0))
        def refresh(*_):
            value.configure(text=f"{var.get():.2f}")
            self._draw()
        var.trace_add("write", refresh)
        if label.startswith("Trim"):
            setattr(self, f"_{label.split()[1]}_scale", scale)
        refresh()

    def _load_worker(self) -> None:
        try:
            env = load_waveform(self.item.path, points=1400)
            self.owner.root.after(0, lambda: self._waveform_ready(env))
        except Exception as exc:
            self.owner.root.after(0, lambda: self.status.configure(text=f"Waveform unavailable: {exc}"))

    def _waveform_ready(self, env: WaveformEnvelope) -> None:
        if not self.window.winfo_exists():
            return
        self.envelope = env
        self.duration = max(0.0, float(env.duration_seconds))
        for attr in ("_start_scale", "_end_scale"):
            scale = getattr(self, attr, None)
            if scale is not None:
                scale.configure(to=max(self.duration, 0.01))
        if self.trim_end.get() > self.duration:
            self.trim_end.set(self.duration)
        self.status.configure(text=f"{self.duration:.2f}s · {env.points} preview points")
        self._draw()

    def _clip_bounds(self) -> tuple[float, float]:
        duration = max(self.duration, 0.001)
        start = max(0.0, min(float(self.trim_start.get()), duration))
        raw_end = float(self.trim_end.get())
        end = duration if raw_end <= 0.0 else max(start, min(raw_end, duration))
        return start, end

    def _draw(self) -> None:
        if not hasattr(self, "canvas") or not self.canvas.winfo_exists():
            return
        self.canvas.delete("all")
        width = max(20, self.canvas.winfo_width())
        height = max(20, self.canvas.winfo_height())
        mid = height / 2
        self.canvas.create_line(0, mid, width, mid, fill="#3b4961")
        env = self.envelope
        if env is not None and env.points:
            step = width / max(env.points - 1, 1)
            amp = height * 0.44
            for i in range(env.points):
                x = i * step
                y1 = mid - float(env.maximum[i]) * amp
                y2 = mid - float(env.minimum[i]) * amp
                self.canvas.create_line(x, y1, x, y2, fill=ACCENT_2)
        if self.duration <= 0:
            return
        start, end = self._clip_bounds()
        x1 = width * start / self.duration
        x2 = width * end / self.duration
        self.canvas.create_rectangle(0, 0, x1, height, fill="#111827", stipple="gray50", outline="")
        self.canvas.create_rectangle(x2, 0, width, height, fill="#111827", stipple="gray50", outline="")
        self.canvas.create_line(x1, 0, x1, height, fill=GOOD, width=3, tags="trim-start")
        self.canvas.create_line(x2, 0, x2, height, fill="#eab760", width=3, tags="trim-end")
        self.canvas.create_text(x1 + 5, 12, text=f"{start:.2f}s", anchor="nw", fill=GOOD)
        self.canvas.create_text(x2 - 5, 12, text=f"{end:.2f}s", anchor="ne", fill="#eab760")

    def _begin_drag(self, event) -> None:
        if self.duration <= 0:
            return
        width = max(1, self.canvas.winfo_width())
        start, end = self._clip_bounds()
        sx = width * start / self.duration
        ex = width * end / self.duration
        self.drag_handle = "start" if abs(event.x - sx) <= abs(event.x - ex) else "end"
        self._drag(event)

    def _drag(self, event) -> None:
        if not self.drag_handle or self.duration <= 0:
            return
        width = max(1, self.canvas.winfo_width())
        seconds = max(0.0, min(self.duration, event.x / width * self.duration))
        if self.drag_handle == "start":
            end = self._clip_bounds()[1]
            self.trim_start.set(min(seconds, end))
        else:
            start = self._clip_bounds()[0]
            self.trim_end.set(max(seconds, start))

    def _save(self) -> None:
        start, end = self._clip_bounds()
        raw_end = 0.0 if self.duration and abs(end - self.duration) < 0.02 else end
        clip_duration = max(0.0, end - start)
        fade_in = min(max(0.0, float(self.fade_in.get())), clip_duration)
        fade_out = min(max(0.0, float(self.fade_out.get())), clip_duration)
        self.owner.engine.soundboard.update_item(
            self.item.id,
            trim_start=start,
            trim_end=raw_end,
            fade_in=fade_in,
            fade_out=fade_out,
            volume=float(self.volume.get()) / 100.0,
            loop=bool(self.loop.get()),
        )
        self.owner._render_sounds()
        self.status.configure(text="Saved · source file unchanged")

    def _preview(self) -> None:
        self._save()
        self.owner._play_sound(self.item.id)


class OxShiftAdvancedUI(OxShiftEnhancedUI):
    """Current product UI: VoiceLab + speech backend selection + waveform Soundboard editor."""

    def __init__(self, root: tk.Tk) -> None:
        self.cleanup_backend_choice = tk.StringVar(master=root, value="auto")
        self.echo_cancellation = tk.BooleanVar(master=root, value=False)
        super().__init__(root)
        self.root.title("OxShift Studio — Advanced Preview")

    def _studio(self):
        page = super()._studio()
        backend = self._card(page)
        backend.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        tk.Label(backend, text="Speech processing backend", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(
            backend,
            text="Auto prefers WebRTC when installed; Built-in is dependency-free. AEC only activates when a true far-end speaker reference is supplied.",
            bg=PANEL,
            fg=MUTED,
            wraplength=850,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 8))
        line = tk.Frame(backend, bg=PANEL)
        line.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(line, text="Backend", bg=PANEL, fg=MUTED).pack(side="left")
        combo = ttk.Combobox(line, state="readonly", width=16, values=("auto", "builtin", "webrtc"), textvariable=self.cleanup_backend_choice)
        combo.pack(side="left", padx=(8, 18))
        combo.bind("<<ComboboxSelected>>", lambda _e: self._sync_cleanup())
        tk.Checkbutton(
            line,
            text="AEC (requires far-end reference)",
            variable=self.echo_cancellation,
            command=self._sync_cleanup,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).pack(side="left")
        self.backend_status = tk.Label(line, text="", bg=PANEL, fg=GOOD)
        self.backend_status.pack(side="right")
        return page

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
            trim = f" · trim {item.trim_start:.1f}s→{item.trim_end:.1f}s" if item.trim_start or item.trim_end else ""
            tk.Label(row, text=f"{item.category} · {Path(item.path).suffix.upper()[1:]} · {int(item.volume*100)}%{trim}", bg=PANEL, fg=MUTED).pack(side="left")
            self._button(row, "Remove", lambda i=item.id: self._remove_sound(i), danger=True).pack(side="right", padx=4, pady=7)
            self._button(row, "Edit", lambda i=item.id: self._edit_sound(i)).pack(side="right", padx=4, pady=7)
            self._button(row, "Stop", lambda i=item.id: self.engine.soundboard.stop(i)).pack(side="right", padx=4, pady=7)
            self._button(row, "Play", lambda i=item.id: self._play_sound(i), primary=True).pack(side="right", padx=4, pady=7)
            self._button(row, star, lambda i=item.id, v=not item.favorite: self._favorite_sound(i, v)).pack(side="right", padx=4, pady=7)

    def _edit_sound(self, item_id: str) -> None:
        try:
            WaveformEditor(self, item_id)
        except Exception as exc:
            messagebox.showerror("Sound editor", str(exc), parent=self.root)

    def _sync_cleanup(self) -> None:
        self.engine.update_cleanup(
            backend=self.cleanup_backend_choice.get(),
            noise_suppression=float(self.noise_suppression.get()) / 100.0,
            agc_enabled=bool(self.agc_enabled.get()),
            agc_target_dbfs=float(self.agc_target.get()),
            agc_max_gain_db=float(self.agc_max_gain.get()),
            echo_cancellation=bool(self.echo_cancellation.get()),
        )

    def _save_profile(self):
        super()._save_profile()
        self.profiles.update_active(
            cleanup_backend=self.cleanup_backend_choice.get(),
            echo_cancellation=bool(self.echo_cancellation.get()),
        )

    def _apply_profile(self, profile):
        self.cleanup_backend_choice.set(getattr(profile, "cleanup_backend", "auto"))
        self.echo_cancellation.set(bool(getattr(profile, "echo_cancellation", False)))
        super()._apply_profile(profile)
        self._sync_cleanup()

    def _tick(self):
        super()._tick()
        if hasattr(self, "backend_status"):
            text = f"Active: {self.engine.cleanup_backend}"
            if self.engine.speech_probability > 0:
                text += f" · speech {self.engine.speech_probability:.0%}"
            if self.engine.cleanup_error:
                text += " · fallback"
                self.backend_status.configure(fg="#eab760")
            else:
                self.backend_status.configure(fg=GOOD)
            self.backend_status.configure(text=text)
