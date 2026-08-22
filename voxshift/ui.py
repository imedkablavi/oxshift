from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .audio_engine import AudioEngine
from .voices import CATEGORIES, VOICE_PRESETS, VoicePreset, get_preset


BG = "#0b1020"
PANEL = "#121a2d"
PANEL_2 = "#182239"
TEXT = "#eef3ff"
MUTED = "#8e9ab4"
ACCENT = "#6d7cff"
ACCENT_ACTIVE = "#8591ff"
BORDER = "#25314d"
GOOD = "#35c98a"


class VoxShiftUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("OxShift — Real-time Voice Changer")
        self.root.geometry("1120x720")
        self.root.minsize(920, 620)
        self.root.configure(bg=BG)
        self.engine = AudioEngine()

        self.selected_voice = tk.StringVar(value="Clean")
        self.selected_category = tk.StringVar(value="All")
        self.search = tk.StringVar(value="")
        self.gain = tk.DoubleVar(value=0.0)
        self.wet = tk.DoubleVar(value=100.0)
        self.gate = tk.DoubleVar(value=-55.0)
        self.status = tk.StringVar(value="Stopped")
        self.voice_description = tk.StringVar(value=get_preset("Clean").description)
        self.current_page = "Dashboard"

        self._configure_styles()
        self._build_shell()
        self._load_devices()
        self._select_voice("Clean")
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(60, self._tick)

    def _configure_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Ox.Horizontal.TProgressbar", troughcolor=PANEL_2, background=ACCENT, bordercolor=PANEL_2, lightcolor=ACCENT, darkcolor=ACCENT)
        style.configure("Ox.TCombobox", fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER)

    def _build_shell(self) -> None:
        self.sidebar = tk.Frame(self.root, bg="#080d19", width=190)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg="#080d19")
        brand.pack(fill="x", padx=18, pady=(20, 24))
        tk.Label(brand, text="OX", fg=TEXT, bg=ACCENT, font=("TkDefaultFont", 11, "bold"), width=3, pady=5).pack(side="left")
        tk.Label(brand, text="  OxShift", fg=TEXT, bg="#080d19", font=("TkDefaultFont", 15, "bold")).pack(side="left")

        self.nav_buttons: dict[str, tk.Button] = {}
        for name, symbol in (("Dashboard", "⌂"), ("Voices", "◉"), ("Studio", "≋"), ("Audio", "⌁")):
            btn = tk.Button(
                self.sidebar,
                text=f"  {symbol}   {name}",
                anchor="w",
                relief="flat",
                bd=0,
                padx=15,
                pady=11,
                bg="#080d19",
                fg=MUTED,
                activebackground=PANEL_2,
                activeforeground=TEXT,
                font=("TkDefaultFont", 10, "bold"),
                command=lambda page=name: self._show_page(page),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[name] = btn

        tk.Frame(self.sidebar, bg="#080d19").pack(fill="both", expand=True)
        privacy = tk.Frame(self.sidebar, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        privacy.pack(fill="x", padx=12, pady=14)
        tk.Label(privacy, text="LOCAL MODE", fg=GOOD, bg=PANEL, font=("TkDefaultFont", 9, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(privacy, text="Audio stays on this device", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8), wraplength=145, justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        right = tk.Frame(self.root, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        self.topbar = tk.Frame(right, bg=BG)
        self.topbar.pack(fill="x", padx=24, pady=(18, 8))
        self.page_title = tk.Label(self.topbar, text="Dashboard", fg=TEXT, bg=BG, font=("TkDefaultFont", 19, "bold"))
        self.page_title.pack(side="left")
        self.status_pill = tk.Label(self.topbar, textvariable=self.status, fg=MUTED, bg=PANEL, padx=12, pady=6, font=("TkDefaultFont", 9, "bold"))
        self.status_pill.pack(side="right")

        self.content = tk.Frame(right, bg=BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=(4, 18))

        self.pages: dict[str, tk.Frame] = {}
        self.pages["Dashboard"] = self._build_dashboard(self.content)
        self.pages["Voices"] = self._build_voices(self.content)
        self.pages["Studio"] = self._build_studio(self.content)
        self.pages["Audio"] = self._build_audio(self.content)

        self._show_page("Dashboard")

    def _page(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=0, column=0, sticky="nsew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        return frame

    def _card(self, parent: tk.Widget, **kwargs) -> tk.Frame:
        return tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, **kwargs)

    def _section_label(self, parent: tk.Widget, text: str) -> tk.Label:
        return tk.Label(parent, text=text, fg=TEXT, bg=parent.cget("bg"), font=("TkDefaultFont", 11, "bold"))

    def _build_dashboard(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(1, weight=1)

        hero = self._card(page)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        hero.grid_columnconfigure(1, weight=1)
        icon = tk.Label(hero, text="◉", fg=TEXT, bg=ACCENT, width=4, height=2, font=("TkDefaultFont", 17, "bold"))
        icon.grid(row=0, column=0, rowspan=2, padx=16, pady=16)
        self.hero_voice = tk.Label(hero, text="Clean", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 17, "bold"))
        self.hero_voice.grid(row=0, column=1, sticky="sw", pady=(16, 0))
        tk.Label(hero, textvariable=self.voice_description, fg=MUTED, bg=PANEL, font=("TkDefaultFont", 9), wraplength=520, justify="left").grid(row=1, column=1, sticky="nw", pady=(2, 16))
        self.hero_start = tk.Button(hero, text="Start voice changer", command=self._start, bg=ACCENT, fg="white", activebackground=ACCENT_ACTIVE, activeforeground="white", relief="flat", bd=0, padx=18, pady=10, font=("TkDefaultFont", 10, "bold"))
        self.hero_start.grid(row=0, column=2, rowspan=2, padx=18)

        voices = self._card(page)
        voices.grid(row=1, column=0, sticky="nsew", padx=(0, 7))
        tk.Label(voices, text="Quick voices", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 8))
        quick = tk.Frame(voices, bg=PANEL)
        quick.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        for col in range(3):
            quick.grid_columnconfigure(col, weight=1)
        for i, preset in enumerate(VOICE_PRESETS[:9]):
            self._voice_tile(quick, preset, i // 3, i % 3, compact=True)

        monitor = self._card(page)
        monitor.grid(row=1, column=1, sticky="nsew", padx=(7, 0))
        tk.Label(monitor, text="Live monitor", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(monitor, text="Input and processed output levels", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8)).pack(anchor="w", padx=16, pady=(0, 16))
        self.dashboard_in = self._meter(monitor, "MIC INPUT")
        self.dashboard_out = self._meter(monitor, "VIRTUAL OUTPUT")
        tk.Frame(monitor, bg=BORDER, height=1).pack(fill="x", padx=16, pady=15)
        self.dashboard_info = tk.Label(monitor, text="48 kHz  •  256 samples  •  Local DSP", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8))
        self.dashboard_info.pack(anchor="w", padx=16)
        tk.Button(monitor, text="Open audio routing", command=lambda: self._show_page("Audio"), bg=PANEL_2, fg=TEXT, activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0, padx=12, pady=9).pack(fill="x", padx=16, pady=16)
        return page

    def _build_voices(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        searchbar = self._card(page)
        searchbar.pack(fill="x", pady=(0, 12))
        tk.Label(searchbar, text="Search", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 9)).pack(side="left", padx=(14, 5), pady=11)
        entry = tk.Entry(searchbar, textvariable=self.search, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, font=("TkDefaultFont", 10))
        entry.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=11)
        self.search.trace_add("write", lambda *_: self._render_voice_library())

        cats = tk.Frame(page, bg=BG)
        cats.pack(fill="x", pady=(0, 10))
        self.category_buttons: dict[str, tk.Button] = {}
        for cat in CATEGORIES:
            btn = tk.Button(cats, text=cat, relief="flat", bd=0, padx=12, pady=6, bg=PANEL, fg=MUTED, activebackground=PANEL_2, activeforeground=TEXT, command=lambda c=cat: self._set_category(c))
            btn.pack(side="left", padx=(0, 6))
            self.category_buttons[cat] = btn

        self.voice_canvas = tk.Canvas(page, bg=BG, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(page, orient="vertical", command=self.voice_canvas.yview)
        self.voice_library = tk.Frame(self.voice_canvas, bg=BG)
        self.voice_library.bind("<Configure>", lambda _e: self.voice_canvas.configure(scrollregion=self.voice_canvas.bbox("all")))
        self.voice_window = self.voice_canvas.create_window((0, 0), window=self.voice_library, anchor="nw")
        self.voice_canvas.bind("<Configure>", lambda e: self.voice_canvas.itemconfigure(self.voice_window, width=e.width))
        self.voice_canvas.configure(yscrollcommand=scrollbar.set)
        self.voice_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._render_voice_library()
        return page

    def _build_studio(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)

        current = self._card(page)
        current.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        tk.Label(current, text="Voice Studio", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 14, "bold")).pack(anchor="w", padx=16, pady=(15, 2))
        tk.Label(current, text="Fine tune the active preset without changing the preset library.", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 9)).pack(anchor="w", padx=16, pady=(0, 14))

        basics = self._card(page)
        basics.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self._studio_slider(basics, "Output gain", self.gain, -18, 18, "dB")
        self._studio_slider(basics, "Effect mix", self.wet, 0, 100, "%")
        self._studio_slider(basics, "Noise gate", self.gate, -80, -20, "dB")

        rack = self._card(page)
        rack.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        tk.Label(rack, text="Effect rack", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=16, pady=(15, 8))
        for title, desc in (
            ("Tone shaping", "High-pass + low-pass filters from each voice preset"),
            ("Saturation", "Soft clipping for radio, megaphone and character voices"),
            ("Modulation", "Ring modulation and tremolo for synthetic voices"),
            ("Delay", "Streaming-safe short echo for creative presets"),
            ("Dynamics", "Lightweight compressor for broadcast-ready output"),
        ):
            row = tk.Frame(rack, bg=PANEL_2)
            row.pack(fill="x", padx=14, pady=4)
            tk.Label(row, text=title, fg=TEXT, bg=PANEL_2, font=("TkDefaultFont", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
            tk.Label(row, text=desc, fg=MUTED, bg=PANEL_2, font=("TkDefaultFont", 8), wraplength=360, justify="left").pack(anchor="w", padx=10, pady=(2, 8))
        return page

    def _build_audio(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        routing = self._card(page)
        routing.pack(fill="x", pady=(0, 12))
        tk.Label(routing, text="Audio routing", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 13, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(15, 3))
        tk.Label(routing, text="Choose your physical microphone and the sink connected to OxShift Virtual Microphone.", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 9)).grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 14))
        tk.Label(routing, text="INPUT MICROPHONE", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8, "bold")).grid(row=2, column=0, sticky="w", padx=(16, 8))
        tk.Label(routing, text="OUTPUT / VIRTUAL SINK", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8, "bold")).grid(row=2, column=1, sticky="w", padx=(8, 16))
        self.input_combo = ttk.Combobox(routing, state="readonly", style="Ox.TCombobox")
        self.input_combo.grid(row=3, column=0, sticky="ew", padx=(16, 8), pady=(5, 16), ipady=4)
        self.output_combo = ttk.Combobox(routing, state="readonly", style="Ox.TCombobox")
        self.output_combo.grid(row=3, column=1, sticky="ew", padx=(8, 16), pady=(5, 16), ipady=4)
        routing.grid_columnconfigure((0, 1), weight=1)

        control = self._card(page)
        control.pack(fill="x")
        tk.Label(control, text="Engine", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 5))
        tk.Label(control, text="Linux: run scripts/linux_virtual_mic.sh create once, then select the OxShift sink here and OxShift Microphone in Discord/OBS/Zoom.", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 9), wraplength=780, justify="left").pack(anchor="w", padx=16, pady=(0, 14))
        actions = tk.Frame(control, bg=PANEL)
        actions.pack(fill="x", padx=16, pady=(0, 16))
        self.start_btn = tk.Button(actions, text="Start processing", command=self._start, bg=ACCENT, fg="white", activebackground=ACCENT_ACTIVE, activeforeground="white", relief="flat", bd=0, padx=16, pady=9, font=("TkDefaultFont", 9, "bold"))
        self.start_btn.pack(side="left")
        self.stop_btn = tk.Button(actions, text="Stop", command=self._stop, bg=PANEL_2, fg=TEXT, activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0, padx=16, pady=9, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        tk.Button(actions, text="Refresh devices", command=self._load_devices, bg=PANEL_2, fg=TEXT, activebackground=BORDER, activeforeground=TEXT, relief="flat", bd=0, padx=14, pady=9).pack(side="right")
        return page

    def _meter(self, parent: tk.Widget, label: str) -> ttk.Progressbar:
        tk.Label(parent, text=label, fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=16, pady=(7, 4))
        bar = ttk.Progressbar(parent, maximum=1.0, style="Ox.Horizontal.TProgressbar")
        bar.pack(fill="x", padx=16, pady=(0, 8), ipady=3)
        return bar

    def _voice_tile(self, parent: tk.Widget, preset: VoicePreset, row: int, column: int, compact: bool = False) -> None:
        tile = tk.Frame(parent, bg=PANEL_2, highlightbackground=BORDER, highlightthickness=1)
        tile.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)
        tile.grid_columnconfigure(1, weight=1)
        tk.Label(tile, text=preset.emoji, fg=TEXT, bg=ACCENT if preset.name == self.selected_voice.get() else PANEL, width=3, height=2, font=("TkDefaultFont", 12, "bold")).grid(row=0, column=0, rowspan=2, padx=8, pady=8)
        tk.Label(tile, text=preset.name, fg=TEXT, bg=PANEL_2, anchor="w", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=1, sticky="sw", padx=(0, 6), pady=(7, 0))
        subtitle = preset.category if compact else preset.description
        tk.Label(tile, text=subtitle, fg=MUTED, bg=PANEL_2, anchor="w", justify="left", wraplength=220 if not compact else 110, font=("TkDefaultFont", 7 if compact else 8)).grid(row=1, column=1, sticky="nw", padx=(0, 6), pady=(1, 7))
        for widget in (tile,) + tuple(tile.winfo_children()):
            widget.bind("<Button-1>", lambda _e, n=preset.name: self._select_voice(n))
            widget.configure(cursor="hand2")

    def _studio_slider(self, parent: tk.Widget, title: str, variable: tk.DoubleVar, lo: float, hi: float, suffix: str) -> None:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=16, pady=12)
        top = tk.Frame(row, bg=PANEL)
        top.pack(fill="x")
        tk.Label(top, text=title, fg=TEXT, bg=PANEL, font=("TkDefaultFont", 9, "bold")).pack(side="left")
        value = tk.Label(top, text="", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 9))
        value.pack(side="right")
        scale = tk.Scale(row, from_=lo, to=hi, orient="horizontal", variable=variable, showvalue=False, bg=PANEL, fg=TEXT, troughcolor=PANEL_2, activebackground=ACCENT, highlightthickness=0, bd=0, command=lambda _v: self._sync_settings())
        scale.pack(fill="x", pady=(5, 0))
        def refresh(*_):
            value.configure(text=f"{variable.get():.0f}{suffix}")
        variable.trace_add("write", refresh)
        refresh()

    def _show_page(self, page: str) -> None:
        self.current_page = page
        self.page_title.configure(text=page)
        self.pages[page].tkraise()
        for name, btn in self.nav_buttons.items():
            btn.configure(bg=PANEL_2 if name == page else "#080d19", fg=TEXT if name == page else MUTED)

    def _set_category(self, category: str) -> None:
        self.selected_category.set(category)
        self._render_voice_library()

    def _render_voice_library(self) -> None:
        if not hasattr(self, "voice_library"):
            return
        for child in self.voice_library.winfo_children():
            child.destroy()
        category = self.selected_category.get()
        query = self.search.get().strip().lower()
        visible = [p for p in VOICE_PRESETS if (category == "All" or p.category == category) and (not query or query in p.name.lower() or query in p.description.lower() or query in p.category.lower())]
        for c in range(3):
            self.voice_library.grid_columnconfigure(c, weight=1)
        for i, preset in enumerate(visible):
            self._voice_tile(self.voice_library, preset, i // 3, i % 3)
        if not visible:
            tk.Label(self.voice_library, text="No voices match this filter.", fg=MUTED, bg=BG, font=("TkDefaultFont", 10)).grid(row=0, column=0, padx=12, pady=30, sticky="w")
        if hasattr(self, "category_buttons"):
            for cat, btn in self.category_buttons.items():
                btn.configure(bg=ACCENT if cat == category else PANEL, fg="white" if cat == category else MUTED)

    def _select_voice(self, name: str) -> None:
        preset = get_preset(name)
        self.selected_voice.set(preset.name)
        self.voice_description.set(preset.description)
        if hasattr(self, "hero_voice"):
            self.hero_voice.configure(text=preset.name)
        self._sync_settings()
        self._render_voice_library()

    def _load_devices(self) -> None:
        try:
            devices = self.engine.devices()
        except Exception as exc:
            messagebox.showerror("Audio backend", f"Could not load audio devices.\n\n{exc}\n\nInstall dependencies from requirements.txt and PortAudio.")
            devices = []
        self._devices = list(devices)
        inputs = [(i, d["name"]) for i, d in enumerate(self._devices) if d.get("max_input_channels", 0) > 0]
        outputs = [(i, d["name"]) for i, d in enumerate(self._devices) if d.get("max_output_channels", 0) > 0]
        self._inputs, self._outputs = inputs, outputs
        if hasattr(self, "input_combo"):
            self.input_combo["values"] = [f"{i}: {n}" for i, n in inputs]
            self.output_combo["values"] = [f"{i}: {n}" for i, n in outputs]
            if inputs:
                self.input_combo.current(0)
            if outputs:
                self.output_combo.current(0)

    def _sync_settings(self) -> None:
        self.engine.update_settings(preset=self.selected_voice.get(), gain_db=float(self.gain.get()), wet=float(self.wet.get()) / 100.0, gate_db=float(self.gate.get()))

    def _selected_index(self, combo: ttk.Combobox, items) -> int | None:
        idx = combo.current()
        return items[idx][0] if 0 <= idx < len(items) else None

    def _start(self) -> None:
        try:
            self._sync_settings()
            input_device = self._selected_index(self.input_combo, self._inputs) if hasattr(self, "input_combo") else None
            output_device = self._selected_index(self.output_combo, self._outputs) if hasattr(self, "output_combo") else None
            self.engine.start(input_device, output_device)
        except Exception as exc:
            messagebox.showerror("Could not start", str(exc))
            return
        if hasattr(self, "start_btn"):
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
        if hasattr(self, "hero_start"):
            self.hero_start.configure(text="Voice changer running", state="disabled", bg="#263253")
        self.status.set("Running")
        self.status_pill.configure(fg=GOOD)

    def _stop(self) -> None:
        self.engine.stop()
        if hasattr(self, "start_btn"):
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
        if hasattr(self, "hero_start"):
            self.hero_start.configure(text="Start voice changer", state="normal", bg=ACCENT)
        self.status.set("Stopped")
        self.status_pill.configure(fg=MUTED)

    def _tick(self) -> None:
        in_level = min(1.0, self.engine.input_level * 4.0)
        out_level = min(1.0, self.engine.output_level * 4.0)
        if hasattr(self, "dashboard_in"):
            self.dashboard_in["value"] = in_level
            self.dashboard_out["value"] = out_level
        if self.engine.last_status not in ("Running", "Stopped"):
            self.status.set(self.engine.last_status)
        self.root.after(60, self._tick)

    def _close(self) -> None:
        self.engine.stop()
        self.root.destroy()
