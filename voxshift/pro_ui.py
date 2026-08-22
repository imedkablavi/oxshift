from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .ai_models import AIModelRegistry
from .audio_engine import AudioEngine
from .diagnostics import diagnostics_json
from .hotkeys import GlobalHotkeyManager
from .profiles import ProfileStore
from .voices import CATEGORIES, VOICE_PRESETS, get_preset


BG = "#090d16"
SIDEBAR = "#0c111d"
PANEL = "#111827"
PANEL_2 = "#182235"
BORDER = "#273449"
TEXT = "#f2f5fb"
MUTED = "#95a2b8"
ACCENT = "#6f7bf7"
ACCENT_2 = "#8993ff"
GOOD = "#38c991"
WARN = "#eab760"
DANGER = "#ef6c7d"


class OxShiftStudioUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("OxShift Studio")
        self.root.geometry("1320x820")
        self.root.minsize(1040, 680)
        self.root.configure(bg=BG)

        self.engine = AudioEngine()
        self.profiles = ProfileStore()
        self.ai_registry = AIModelRegistry()
        self.hotkeys = GlobalHotkeyManager()

        profile = self.profiles.active
        self.voice = tk.StringVar(value=profile.voice)
        self.gain = tk.DoubleVar(value=profile.gain_db)
        self.wet = tk.DoubleVar(value=profile.wet * 100.0)
        self.gate = tk.DoubleVar(value=profile.gate_db)
        self.pitch = tk.DoubleVar(value=profile.pitch_semitones)
        self.formant = tk.DoubleVar(value=profile.formant_color * 100.0)
        self.profile_name = tk.StringVar(value=profile.name)
        self.status = tk.StringVar(value="Stopped")
        self.search_voice = tk.StringVar(value="")
        self.search_sound = tk.StringVar(value="")
        self.category = tk.StringVar(value="All")
        self.sound_master = tk.DoubleVar(value=profile.soundboard_master * 100.0)
        self.duck = tk.DoubleVar(value=profile.soundboard_duck_db)
        self.overlap = tk.BooleanVar(value=profile.allow_overlap)
        self._inputs = []
        self._outputs = []
        self.current_page = "Home"

        self._configure_style()
        self._build_shell()
        self._load_devices()
        self._apply_profile(profile)
        self._refresh_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(100, self._tick)

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Ox.Horizontal.TProgressbar", troughcolor=PANEL_2, background=ACCENT, bordercolor=PANEL_2, lightcolor=ACCENT, darkcolor=ACCENT)
        style.configure("Ox.TCombobox", fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER)

    def _build_shell(self) -> None:
        sidebar = tk.Frame(self.root, bg=SIDEBAR, width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="OX", bg=ACCENT, fg="white", font=("TkDefaultFont", 12, "bold"), width=3, pady=7).pack(anchor="w", padx=18, pady=(20, 6))
        tk.Label(sidebar, text="OxShift Studio", bg=SIDEBAR, fg=TEXT, font=("TkDefaultFont", 16, "bold")).pack(anchor="w", padx=18)
        tk.Label(sidebar, text="VOICE + SOUND + AI", bg=SIDEBAR, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=18, pady=(2, 22))

        self.nav = {}
        for page, icon in (("Home", "⌂"), ("Voices", "◉"), ("Soundboard", "▶"), ("Studio", "≋"), ("Profiles", "▤"), ("AI Models", "◇"), ("Audio", "⌁")):
            btn = tk.Button(sidebar, text=f"  {icon}   {page}", anchor="w", bg=SIDEBAR, fg=MUTED, activebackground=PANEL_2, activeforeground=TEXT, relief="flat", bd=0, padx=14, pady=11, font=("TkDefaultFont", 10, "bold"), command=lambda p=page: self._show(p))
            btn.pack(fill="x", padx=10, pady=2)
            self.nav[page] = btn

        tk.Frame(sidebar, bg=SIDEBAR).pack(fill="both", expand=True)
        mode = self._card(sidebar)
        mode.pack(fill="x", padx=12, pady=14)
        tk.Label(mode, text="LOCAL ENGINE", bg=PANEL, fg=GOOD, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(mode, text="No cloud audio transport", bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8)).pack(anchor="w", padx=12, pady=(0, 10))

        main = tk.Frame(self.root, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=BG)
        top.pack(fill="x", padx=24, pady=(18, 8))
        self.title = tk.Label(top, text="Home", bg=BG, fg=TEXT, font=("TkDefaultFont", 20, "bold"))
        self.title.pack(side="left")
        self.profile_badge = tk.Label(top, textvariable=self.profile_name, bg=PANEL, fg=MUTED, padx=12, pady=6)
        self.profile_badge.pack(side="right", padx=(8, 0))
        self.status_badge = tk.Label(top, textvariable=self.status, bg=PANEL, fg=MUTED, padx=12, pady=6, font=("TkDefaultFont", 9, "bold"))
        self.status_badge.pack(side="right")

        self.content = tk.Frame(main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=(4, 18))
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.pages = {
            "Home": self._home(),
            "Voices": self._voices(),
            "Soundboard": self._soundboard(),
            "Studio": self._studio(),
            "Profiles": self._profiles(),
            "AI Models": self._ai_models(),
            "Audio": self._audio(),
        }
        self._show("Home")

    def _page(self):
        page = tk.Frame(self.content, bg=BG)
        page.grid(row=0, column=0, sticky="nsew")
        return page

    def _card(self, parent, **kwargs):
        return tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, **kwargs)

    def _button(self, parent, text, command, primary=False, danger=False):
        bg = ACCENT if primary else (DANGER if danger else PANEL_2)
        return tk.Button(parent, text=text, command=command, bg=bg, fg="white" if primary or danger else TEXT, activebackground=ACCENT_2 if primary else BORDER, activeforeground="white", relief="flat", bd=0, padx=13, pady=8, font=("TkDefaultFont", 9, "bold"))

    def _home(self):
        page = self._page()
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        hero = self._card(page)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        hero.grid_columnconfigure(1, weight=1)
        tk.Label(hero, text="◉", bg=ACCENT, fg="white", width=4, height=2, font=("TkDefaultFont", 18, "bold")).grid(row=0, column=0, rowspan=2, padx=16, pady=16)
        self.home_voice = tk.Label(hero, text=self.voice.get(), bg=PANEL, fg=TEXT, font=("TkDefaultFont", 18, "bold"))
        self.home_voice.grid(row=0, column=1, sticky="sw", pady=(14, 0))
        self.home_desc = tk.Label(hero, text=get_preset(self.voice.get()).description, bg=PANEL, fg=MUTED, wraplength=600, justify="left")
        self.home_desc.grid(row=1, column=1, sticky="nw", pady=(2, 14))
        self._button(hero, "Start engine", self._start, primary=True).grid(row=0, column=2, rowspan=2, padx=16)

        quick = self._card(page)
        quick.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(quick, text="Quick launch", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 8))
        grid = tk.Frame(quick, bg=PANEL)
        grid.pack(fill="x", padx=10)
        for c in range(3): grid.grid_columnconfigure(c, weight=1)
        for i, preset in enumerate(VOICE_PRESETS[:9]):
            self._button(grid, preset.name, lambda n=preset.name: self._select_voice(n), primary=preset.name == self.voice.get()).grid(row=i // 3, column=i % 3, sticky="ew", padx=4, pady=4)
        rec = tk.Frame(quick, bg=PANEL_2)
        rec.pack(fill="x", padx=14, pady=14)
        tk.Label(rec, text="OUTPUT RECORDER", bg=PANEL_2, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        self.record_text = tk.Label(rec, text="Ready", bg=PANEL_2, fg=TEXT, font=("TkDefaultFont", 10, "bold"))
        self.record_text.pack(anchor="w", padx=10, pady=(2, 8))
        self._button(rec, "Record", self._record, primary=True).pack(side="left", padx=(10, 4), pady=(0, 10))
        self._button(rec, "Stop recording", self._stop_record).pack(side="left", padx=4, pady=(0, 10))

        health = self._card(page)
        health.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        tk.Label(health, text="Engine health", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 6))
        self.in_meter = self._meter(health, "MIC")
        self.board_meter = self._meter(health, "SOUNDBOARD")
        self.out_meter = self._meter(health, "OUTPUT")
        self.health_text = tk.Label(health, text="Engine stopped", bg=PANEL, fg=MUTED, justify="left", font=("TkDefaultFont", 8))
        self.health_text.pack(anchor="w", padx=14, pady=12)
        self._button(health, "Export diagnostics", self._export_diagnostics).pack(fill="x", padx=14, pady=(0, 14))
        return page

    def _voices(self):
        page = self._page()
        filters = self._card(page)
        filters.pack(fill="x", pady=(0, 10))
        tk.Entry(filters, textvariable=self.search_voice, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0).pack(side="left", fill="x", expand=True, padx=12, pady=10)
        self.search_voice.trace_add("write", lambda *_: self._render_voices())
        for cat in CATEGORIES:
            self._button(filters, cat, lambda c=cat: self._set_category(c)).pack(side="left", padx=(0, 5), pady=7)
        self.voice_list = tk.Frame(page, bg=BG)
        self.voice_list.pack(fill="both", expand=True)
        self._render_voices()
        return page

    def _render_voices(self):
        if not hasattr(self, "voice_list"): return
        for child in self.voice_list.winfo_children(): child.destroy()
        query = self.search_voice.get().lower().strip()
        items = [p for p in VOICE_PRESETS if (self.category.get() == "All" or p.category == self.category.get()) and (not query or query in p.name.lower() or query in p.description.lower())]
        for c in range(3): self.voice_list.grid_columnconfigure(c, weight=1)
        for i, preset in enumerate(items):
            card = self._card(self.voice_list)
            card.grid(row=i // 3, column=i % 3, sticky="nsew", padx=5, pady=5)
            tk.Label(card, text=f"{preset.emoji}  {preset.name}", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 2))
            tk.Label(card, text=preset.category, bg=PANEL, fg=ACCENT_2, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=12)
            tk.Label(card, text=preset.description, bg=PANEL, fg=MUTED, wraplength=270, justify="left").pack(anchor="w", padx=12, pady=(5, 10))
            self._button(card, "Use voice", lambda n=preset.name: self._select_voice(n), primary=preset.name == self.voice.get()).pack(fill="x", padx=10, pady=(0, 10))

    def _soundboard(self):
        page = self._page()
        bar = self._card(page); bar.pack(fill="x", pady=(0, 10))
        tk.Entry(bar, textvariable=self.search_sound, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0).pack(side="left", fill="x", expand=True, padx=12, pady=10)
        self.search_sound.trace_add("write", lambda *_: self._render_sounds())
        self._button(bar, "Import", self._import_sounds, primary=True).pack(side="right", padx=6, pady=7)
        self._button(bar, "Stop all", self.engine.soundboard.stop_all, danger=True).pack(side="right", padx=6, pady=7)
        controls = self._card(page); controls.pack(fill="x", pady=(0, 10))
        self._slider(controls, "Master", self.sound_master, 0, 120, lambda: self._sync_board()).pack(side="left", fill="x", expand=True, padx=10, pady=8)
        self._slider(controls, "Mic duck", self.duck, 0, 24, lambda: self._sync_board()).pack(side="left", fill="x", expand=True, padx=10, pady=8)
        tk.Checkbutton(controls, text="Allow overlap", variable=self.overlap, command=self._sync_board, bg=PANEL, fg=TEXT, selectcolor=PANEL_2, activebackground=PANEL, activeforeground=TEXT).pack(side="left", padx=12)
        self.sound_list = tk.Frame(page, bg=BG); self.sound_list.pack(fill="both", expand=True)
        self._render_sounds()
        return page

    def _render_sounds(self):
        if not hasattr(self, "sound_list"): return
        for child in self.sound_list.winfo_children(): child.destroy()
        q = self.search_sound.get().lower().strip()
        items = [i for i in self.engine.soundboard.items if not q or q in i.name.lower() or q in i.category.lower()]
        for item in items:
            row = self._card(self.sound_list); row.pack(fill="x", pady=4)
            tk.Label(row, text=item.name, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(side="left", padx=12, pady=12)
            tk.Label(row, text=f"{Path(item.path).suffix.upper()[1:]} · {int(item.volume*100)}%", bg=PANEL, fg=MUTED).pack(side="left")
            self._button(row, "Remove", lambda i=item.id: self._remove_sound(i), danger=True).pack(side="right", padx=5, pady=7)
            self._button(row, "Stop", lambda i=item.id: self.engine.soundboard.stop(i)).pack(side="right", padx=5, pady=7)
            self._button(row, "Play", lambda i=item.id: self._play_sound(i), primary=True).pack(side="right", padx=5, pady=7)

    def _studio(self):
        page = self._page()
        left = self._card(page); left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = self._card(page); right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        tk.Label(left, text="Voice transformation", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        for label, var, lo, hi in (("Pitch (st)", self.pitch, -12, 12), ("Timbre / formant color", self.formant, -100, 100), ("Wet mix", self.wet, 0, 100)):
            self._slider(left, label, var, lo, hi, self._sync_dsp).pack(fill="x", padx=14, pady=8)
        tk.Label(right, text="Dynamics", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        for label, var, lo, hi in (("Gain (dB)", self.gain, -18, 18), ("Noise gate (dB)", self.gate, -80, -20)):
            self._slider(right, label, var, lo, hi, self._sync_dsp).pack(fill="x", padx=14, pady=8)
        tk.Label(right, text="Profiles save this complete studio state so gaming, streaming and calls can have different setups.", bg=PANEL, fg=MUTED, wraplength=420, justify="left").pack(anchor="w", padx=14, pady=16)
        return page

    def _profiles(self):
        page = self._page()
        top = self._card(page); top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text="Studio profiles", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 13, "bold")).pack(side="left", padx=14, pady=12)
        self._button(top, "Save current", self._save_profile, primary=True).pack(side="right", padx=6, pady=7)
        self._button(top, "New from current", self._new_profile).pack(side="right", padx=6, pady=7)
        self.profile_list = tk.Frame(page, bg=BG); self.profile_list.pack(fill="both", expand=True)
        self._render_profiles()
        return page

    def _render_profiles(self):
        if not hasattr(self, "profile_list"): return
        for child in self.profile_list.winfo_children(): child.destroy()
        for p in self.profiles.items:
            row = self._card(self.profile_list); row.pack(fill="x", pady=4)
            tk.Label(row, text=p.name, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(side="left", padx=12, pady=12)
            tk.Label(row, text=f"{p.voice} · {p.pitch_semitones:+.0f} st · {p.sample_rate//1000} kHz", bg=PANEL, fg=MUTED).pack(side="left")
            self._button(row, "Delete", lambda i=p.id: self._delete_profile(i), danger=True).pack(side="right", padx=5, pady=7)
            self._button(row, "Load", lambda i=p.id: self._load_profile(i), primary=p.id == self.profiles.active_id).pack(side="right", padx=5, pady=7)

    def _ai_models(self):
        page = self._page()
        top = self._card(page); top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text="Local AI voice models", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 13, "bold")).pack(side="left", padx=14, pady=12)
        self._button(top, "Import model", self._import_models, primary=True).pack(side="right", padx=8, pady=7)
        self.ai_status = tk.Label(page, text="", bg=BG, fg=MUTED, justify="left"); self.ai_status.pack(anchor="w", pady=(4, 10))
        self.ai_list = tk.Frame(page, bg=BG); self.ai_list.pack(fill="both", expand=True)
        self._refresh_models()
        return page

    def _audio(self):
        page = self._page()
        route = self._card(page); route.pack(fill="x", pady=(0, 10))
        tk.Label(route, text="Input microphone", bg=PANEL, fg=MUTED).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 3))
        tk.Label(route, text="Output / virtual sink", bg=PANEL, fg=MUTED).grid(row=0, column=1, sticky="w", padx=14, pady=(12, 3))
        self.input_combo = ttk.Combobox(route, state="readonly", style="Ox.TCombobox"); self.output_combo = ttk.Combobox(route, state="readonly", style="Ox.TCombobox")
        self.input_combo.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12)); self.output_combo.grid(row=1, column=1, sticky="ew", padx=14, pady=(0, 12))
        route.grid_columnconfigure(0, weight=1); route.grid_columnconfigure(1, weight=1)
        actions = self._card(page); actions.pack(fill="x")
        self._button(actions, "Start", self._start, primary=True).pack(side="left", padx=12, pady=12)
        self._button(actions, "Stop", self._stop).pack(side="left", padx=4, pady=12)
        self._button(actions, "Refresh devices", self._load_devices).pack(side="left", padx=4, pady=12)
        tk.Label(actions, text="Recommended: 48 kHz / 256 samples", bg=PANEL, fg=MUTED).pack(side="right", padx=12)
        return page

    def _slider(self, parent, label, variable, lo, hi, callback):
        box = tk.Frame(parent, bg=PANEL)
        tk.Label(box, text=label, bg=PANEL, fg=MUTED).pack(anchor="w")
        line = tk.Frame(box, bg=PANEL); line.pack(fill="x")
        ttk.Scale(line, from_=lo, to=hi, variable=variable, command=lambda _v: callback()).pack(side="left", fill="x", expand=True)
        value = tk.Label(line, bg=PANEL, fg=TEXT, width=7); value.pack(side="right", padx=(8, 0))
        def update(*_): value.configure(text=f"{variable.get():.0f}")
        variable.trace_add("write", update); update()
        return box

    def _meter(self, parent, label):
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=14, pady=(8, 2))
        bar = ttk.Progressbar(parent, maximum=1.0, style="Ox.Horizontal.TProgressbar")
        bar.pack(fill="x", padx=14)
        return bar

    def _select_voice(self, name):
        self.voice.set(name); preset = get_preset(name)
        self.pitch.set(preset.pitch_semitones); self.formant.set(preset.formant_color * 100.0)
        if hasattr(self, "home_voice"): self.home_voice.configure(text=name); self.home_desc.configure(text=preset.description)
        self._sync_dsp(); self._render_voices()

    def _set_category(self, category): self.category.set(category); self._render_voices()

    def _sync_dsp(self):
        self.engine.update_settings(preset=self.voice.get(), gain_db=float(self.gain.get()), wet=float(self.wet.get())/100.0, gate_db=float(self.gate.get()), pitch_semitones=float(self.pitch.get()), formant_color=float(self.formant.get())/100.0)

    def _sync_board(self):
        s = self.engine.soundboard.settings
        s.master_volume = max(0.0, min(1.2, float(self.sound_master.get())/100.0)); s.ducking_db = max(0.0, min(24.0, float(self.duck.get()))); s.allow_overlap = bool(self.overlap.get()); self.engine.soundboard.save()

    def _save_profile(self):
        p = self.profiles.update_active(name=self.profile_name.get(), voice=self.voice.get(), gain_db=self.gain.get(), wet=self.wet.get()/100.0, gate_db=self.gate.get(), pitch_semitones=self.pitch.get(), formant_color=self.formant.get()/100.0, soundboard_master=self.sound_master.get()/100.0, soundboard_duck_db=self.duck.get(), allow_overlap=self.overlap.get(), sample_rate=self.engine.sample_rate, blocksize=self.engine.blocksize)
        self.profile_name.set(p.name); self._render_profiles()

    def _new_profile(self):
        name = simpledialog.askstring("New profile", "Profile name:", parent=self.root)
        if name:
            self._save_profile(); p = self.profiles.create(name); self._apply_profile(p); self._render_profiles()

    def _load_profile(self, profile_id):
        p = self.profiles.select(profile_id)
        if p: self._apply_profile(p); self._render_profiles()

    def _delete_profile(self, profile_id):
        if not self.profiles.delete(profile_id): messagebox.showinfo("Profiles", "At least one profile must remain.")
        self._apply_profile(self.profiles.active); self._render_profiles()

    def _apply_profile(self, p):
        self.profile_name.set(p.name); self.voice.set(p.voice); self.gain.set(p.gain_db); self.wet.set(p.wet*100.0); self.gate.set(p.gate_db); self.pitch.set(p.pitch_semitones); self.formant.set(p.formant_color*100.0); self.sound_master.set(p.soundboard_master*100.0); self.duck.set(p.soundboard_duck_db); self.overlap.set(p.allow_overlap); self._sync_dsp(); self._sync_board()
        if hasattr(self, "home_voice"): self.home_voice.configure(text=p.voice); self.home_desc.configure(text=get_preset(p.voice).description)

    def _load_devices(self):
        try: devices = list(self.engine.devices())
        except Exception as exc: messagebox.showerror("Audio devices", str(exc)); devices = []
        self._devices = devices; self._inputs = [(i,d["name"]) for i,d in enumerate(devices) if d.get("max_input_channels",0)>0]; self._outputs=[(i,d["name"]) for i,d in enumerate(devices) if d.get("max_output_channels",0)>0]
        if hasattr(self, "input_combo"):
            self.input_combo["values"]=[f"{i}: {n}" for i,n in self._inputs]; self.output_combo["values"]=[f"{i}: {n}" for i,n in self._outputs]
            if self._inputs and self.input_combo.current()<0: self.input_combo.current(0)
            if self._outputs and self.output_combo.current()<0:
                preferred=next((j for j,(_,n) in enumerate(self._outputs) if "oxshift" in n.lower() or "voxshift" in n.lower()),0); self.output_combo.current(preferred)

    def _start(self):
        if not hasattr(self, "input_combo"): self._show("Audio"); return
        try:
            self._sync_dsp(); self._sync_board(); ii=self.input_combo.current(); oi=self.output_combo.current(); self.engine.start(self._inputs[ii][0] if 0<=ii<len(self._inputs) else None, self._outputs[oi][0] if 0<=oi<len(self._outputs) else None, sample_rate=self.profiles.active.sample_rate, blocksize=self.profiles.active.blocksize)
        except Exception as exc: messagebox.showerror("Could not start", str(exc))

    def _stop(self): self.engine.stop()

    def _record(self):
        if self.engine.last_status != "Running": self._start()
        if self.engine.last_status != "Running": return
        default=f"oxshift-{datetime.now().strftime('%Y%m%d-%H%M%S')}.wav"
        path=filedialog.asksaveasfilename(title="Record OxShift output", defaultextension=".wav", initialfile=default, filetypes=[("WAV audio","*.wav")])
        if path: self.engine.start_recording(path)

    def _stop_record(self): self.engine.stop_recording()

    def _import_sounds(self):
        paths=filedialog.askopenfilenames(title="Import sounds", filetypes=[("Audio","*.wav *.mp3 *.ogg *.flac *.aiff *.aif"),("All files","*")])
        if paths: self.engine.soundboard.add_files(list(paths)); self._render_sounds(); self._refresh_hotkeys()

    def _play_sound(self,item_id):
        if self.engine.last_status != "Running": self._start()
        if self.engine.last_status == "Running": self.engine.soundboard.play(item_id)

    def _remove_sound(self,item_id): self.engine.soundboard.remove(item_id); self._render_sounds(); self._refresh_hotkeys()

    def _refresh_hotkeys(self):
        bindings={i.hotkey.strip(): (lambda item_id=i.id: self.root.after(0,lambda:self._play_sound(item_id))) for i in self.engine.soundboard.items if i.hotkey.strip()}; self.hotkeys.start(bindings)

    def _import_models(self):
        paths=filedialog.askopenfilenames(title="Import local models", filetypes=[("Voice models","*.onnx *.pth *.index"),("All files","*")])
        if paths: self.ai_registry.import_files(list(paths)); self._refresh_models()

    def _refresh_models(self):
        if not hasattr(self,"ai_list"): return
        caps=self.ai_registry.capabilities(); self.ai_status.configure(text=f"ONNX Runtime: {'ready' if caps.onnxruntime else 'not installed'}\nProviders: {', '.join(caps.providers) if caps.providers else 'none'}")
        for c in self.ai_list.winfo_children(): c.destroy()
        for m in self.ai_registry.scan():
            row=self._card(self.ai_list); row.pack(fill="x",pady=4); tk.Label(row,text=m.name,bg=PANEL,fg=TEXT,font=("TkDefaultFont",10,"bold")).pack(side="left",padx=12,pady=12); tk.Label(row,text=f"{m.format.upper()} · {m.backend}",bg=PANEL,fg=GOOD if m.backend!="unavailable" else WARN).pack(side="right",padx=12)

    def _export_diagnostics(self):
        path=filedialog.asksaveasfilename(title="Export diagnostics", defaultextension=".json", initialfile="oxshift-diagnostics.json", filetypes=[("JSON","*.json")])
        if path: Path(path).write_text(diagnostics_json(self.engine,getattr(self,"_devices",[])),encoding="utf-8")

    def _show(self,page):
        self.current_page=page; self.pages[page].tkraise(); self.title.configure(text=page)
        for name,button in self.nav.items(): button.configure(bg=PANEL_2 if name==page else SIDEBAR,fg=TEXT if name==page else MUTED)
        if page=="Soundboard": self._render_sounds()
        elif page=="Profiles": self._render_profiles()
        elif page=="AI Models": self._refresh_models()

    def _tick(self):
        scale=lambda x:min(1.0,max(0.0,x*4.0))
        if hasattr(self,"in_meter"):
            self.in_meter["value"]=scale(self.engine.input_level); self.board_meter["value"]=scale(self.engine.soundboard_level); self.out_meter["value"]=scale(self.engine.output_level)
            if self.engine.last_status=="Running": self.health_text.configure(text=f"Buffer {self.engine.estimated_buffer_latency_ms:.2f} ms\nCallback {self.engine.callback_ms:.2f} ms · peak {self.engine.callback_peak_ms:.2f} ms\nXRuns {self.engine.xruns} · Pitch {self.engine.pitch_backend}")
            else: self.health_text.configure(text="Engine stopped")
            r=self.engine.recorder
            self.record_text.configure(text=f"Recording · {r.duration_seconds:.1f}s · dropped {r.state.dropped_blocks}" if r.state.recording else (f"Saved · {r.state.frames_written} frames" if r.state.path else "Ready"))
        self.status.set(self.engine.last_status); self.status_badge.configure(fg=GOOD if self.engine.last_status=="Running" else MUTED)
        self.root.after(100,self._tick)

    def _close(self):
        self.hotkeys.stop(); self.engine.stop(); self.root.destroy()
