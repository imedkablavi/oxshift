from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from .ai_models import AIModelRegistry
from .audio_engine import AudioEngine
from .hotkeys import GlobalHotkeyManager
from .voices import CATEGORIES, VOICE_PRESETS, VoicePreset, get_preset


BG = "#0b1020"
SIDEBAR = "#080d19"
PANEL = "#121a2d"
PANEL_2 = "#182239"
TEXT = "#eef3ff"
MUTED = "#8e9ab4"
ACCENT = "#6d7cff"
ACCENT_ACTIVE = "#8591ff"
BORDER = "#25314d"
GOOD = "#35c98a"
WARN = "#f4b860"
DANGER = "#ef6a7a"


class VoxShiftUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("OxShift — Voice Studio & Soundboard")
        self.root.geometry("1240x790")
        self.root.minsize(980, 650)
        self.root.configure(bg=BG)

        self.engine = AudioEngine()
        self.hotkeys = GlobalHotkeyManager()
        self.ai_registry = AIModelRegistry()

        self.selected_voice = tk.StringVar(value="Clean")
        self.selected_category = tk.StringVar(value="All")
        self.search = tk.StringVar(value="")
        self.sound_search = tk.StringVar(value="")
        self.gain = tk.DoubleVar(value=0.0)
        self.wet = tk.DoubleVar(value=100.0)
        self.gate = tk.DoubleVar(value=-55.0)
        self.pitch = tk.DoubleVar(value=0.0)
        self.formant_color = tk.DoubleVar(value=0.0)
        self.status = tk.StringVar(value="Stopped")
        self.voice_description = tk.StringVar(value=get_preset("Clean").description)
        self.soundboard_master = tk.DoubleVar(value=self.engine.soundboard.settings.master_volume * 100.0)
        self.soundboard_duck = tk.DoubleVar(value=self.engine.soundboard.settings.ducking_db)
        self.soundboard_overlap = tk.BooleanVar(value=self.engine.soundboard.settings.allow_overlap)
        self.current_page = "Dashboard"

        self._configure_styles()
        self._build_shell()
        self._load_devices()
        self._select_voice("Clean")
        self._refresh_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(80, self._tick)

    def _configure_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Ox.Horizontal.TProgressbar",
            troughcolor=PANEL_2,
            background=ACCENT,
            bordercolor=PANEL_2,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )
        style.configure(
            "Ox.TCombobox",
            fieldbackground=PANEL_2,
            background=PANEL_2,
            foreground=TEXT,
            arrowcolor=TEXT,
            bordercolor=BORDER,
        )

    def _build_shell(self) -> None:
        self.sidebar = tk.Frame(self.root, bg=SIDEBAR, width=205)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=SIDEBAR)
        brand.pack(fill="x", padx=18, pady=(20, 24))
        tk.Label(brand, text="OX", fg=TEXT, bg=ACCENT, font=("TkDefaultFont", 11, "bold"), width=3, pady=5).pack(side="left")
        tk.Label(brand, text="  OxShift", fg=TEXT, bg=SIDEBAR, font=("TkDefaultFont", 15, "bold")).pack(side="left")

        self.nav_buttons: dict[str, tk.Button] = {}
        navigation = (
            ("Dashboard", "⌂"),
            ("Voices", "◉"),
            ("Soundboard", "▶"),
            ("Studio", "≋"),
            ("AI Models", "◇"),
            ("Audio", "⌁"),
        )
        for name, symbol in navigation:
            btn = tk.Button(
                self.sidebar,
                text=f"  {symbol}   {name}",
                anchor="w",
                relief="flat",
                bd=0,
                padx=15,
                pady=11,
                bg=SIDEBAR,
                fg=MUTED,
                activebackground=PANEL_2,
                activeforeground=TEXT,
                font=("TkDefaultFont", 10, "bold"),
                command=lambda page=name: self._show_page(page),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[name] = btn

        tk.Frame(self.sidebar, bg=SIDEBAR).pack(fill="both", expand=True)
        privacy = self._card(self.sidebar)
        privacy.pack(fill="x", padx=12, pady=14)
        tk.Label(privacy, text="LOCAL-FIRST", fg=GOOD, bg=PANEL, font=("TkDefaultFont", 9, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(
            privacy,
            text="Mic, sounds and model files stay on this device.",
            fg=MUTED,
            bg=PANEL,
            font=("TkDefaultFont", 8),
            wraplength=155,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 10))

        right = tk.Frame(self.root, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        topbar = tk.Frame(right, bg=BG)
        topbar.pack(fill="x", padx=24, pady=(18, 8))
        self.page_title = tk.Label(topbar, text="Dashboard", fg=TEXT, bg=BG, font=("TkDefaultFont", 19, "bold"))
        self.page_title.pack(side="left")
        self.status_pill = tk.Label(topbar, textvariable=self.status, fg=MUTED, bg=PANEL, padx=12, pady=6, font=("TkDefaultFont", 9, "bold"))
        self.status_pill.pack(side="right")

        self.content = tk.Frame(right, bg=BG)
        self.content.pack(fill="both", expand=True, padx=24, pady=(4, 18))
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.pages: dict[str, tk.Frame] = {
            "Dashboard": self._build_dashboard(self.content),
            "Voices": self._build_voices(self.content),
            "Soundboard": self._build_soundboard(self.content),
            "Studio": self._build_studio(self.content),
            "AI Models": self._build_ai_models(self.content),
            "Audio": self._build_audio(self.content),
        }
        self._show_page("Dashboard")

    def _page(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=0, column=0, sticky="nsew")
        return frame

    def _card(self, parent: tk.Widget, **kwargs) -> tk.Frame:
        return tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, **kwargs)

    def _button(self, parent: tk.Widget, text: str, command, primary: bool = False, danger: bool = False) -> tk.Button:
        bg = ACCENT if primary else (DANGER if danger else PANEL_2)
        active = ACCENT_ACTIVE if primary else BORDER
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg="white" if primary or danger else TEXT,
            activebackground=active,
            activeforeground="white" if primary or danger else TEXT,
            relief="flat",
            bd=0,
            padx=13,
            pady=8,
            font=("TkDefaultFont", 9, "bold"),
        )

    def _build_dashboard(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(1, weight=1)

        hero = self._card(page)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        hero.grid_columnconfigure(1, weight=1)
        tk.Label(hero, text="◉", fg=TEXT, bg=ACCENT, width=4, height=2, font=("TkDefaultFont", 17, "bold")).grid(row=0, column=0, rowspan=2, padx=16, pady=16)
        self.hero_voice = tk.Label(hero, text="Clean", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 17, "bold"))
        self.hero_voice.grid(row=0, column=1, sticky="sw", pady=(16, 0))
        tk.Label(hero, textvariable=self.voice_description, fg=MUTED, bg=PANEL, font=("TkDefaultFont", 9), wraplength=570, justify="left").grid(row=1, column=1, sticky="nw", pady=(2, 16))
        self.hero_start = self._button(hero, "Start engine", self._start, primary=True)
        self.hero_start.grid(row=0, column=2, rowspan=2, padx=18)

        left = self._card(page)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 7))
        tk.Label(left, text="Quick voices", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 8))
        quick = tk.Frame(left, bg=PANEL)
        quick.pack(fill="x", padx=12)
        for col in range(3):
            quick.grid_columnconfigure(col, weight=1)
        for i, preset in enumerate(VOICE_PRESETS[:9]):
            self._voice_tile(quick, preset, i // 3, i % 3, compact=True)

        board_strip = tk.Frame(left, bg=PANEL_2)
        board_strip.pack(fill="x", padx=14, pady=14)
        tk.Label(board_strip, text="SOUNDBOARD", fg=MUTED, bg=PANEL_2, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
        self.dashboard_soundboard = tk.Label(board_strip, text="0 sounds · idle", fg=TEXT, bg=PANEL_2, font=("TkDefaultFont", 10, "bold"))
        self.dashboard_soundboard.pack(anchor="w", padx=10, pady=(2, 8))
        self._button(board_strip, "Open Soundboard", lambda: self._show_page("Soundboard")).pack(side="right", padx=8, pady=(0, 8))

        monitor = self._card(page)
        monitor.grid(row=1, column=1, sticky="nsew", padx=(7, 0))
        tk.Label(monitor, text="Performance monitor", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        self.dashboard_in = self._meter(monitor, "MIC INPUT")
        self.dashboard_board = self._meter(monitor, "SOUNDBOARD")
        self.dashboard_out = self._meter(monitor, "VIRTUAL OUTPUT")
        tk.Frame(monitor, bg=BORDER, height=1).pack(fill="x", padx=16, pady=12)
        self.performance_text = tk.Label(monitor, text="Engine stopped", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8), justify="left")
        self.performance_text.pack(anchor="w", padx=16)
        self._button(monitor, "Audio routing", lambda: self._show_page("Audio")).pack(fill="x", padx=16, pady=16)
        return page

    def _build_voices(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        searchbar = self._card(page)
        searchbar.pack(fill="x", pady=(0, 12))
        tk.Label(searchbar, text="Search", fg=MUTED, bg=PANEL).pack(side="left", padx=(14, 5), pady=11)
        tk.Entry(searchbar, textvariable=self.search, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0).pack(side="left", fill="x", expand=True, padx=(0, 12), pady=11)
        self.search.trace_add("write", lambda *_: self._render_voice_library())

        cats = tk.Frame(page, bg=BG)
        cats.pack(fill="x", pady=(0, 10))
        self.category_buttons: dict[str, tk.Button] = {}
        for cat in CATEGORIES:
            btn = self._button(cats, cat, lambda c=cat: self._set_category(c))
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

    def _build_soundboard(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        toolbar = self._card(page)
        toolbar.pack(fill="x", pady=(0, 10))
        tk.Label(toolbar, text="Soundboard / Music", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 13, "bold")).pack(side="left", padx=14, pady=12)
        self._button(toolbar, "Import audio", self._import_sounds, primary=True).pack(side="right", padx=(6, 12), pady=8)
        self._button(toolbar, "Stop all", self._stop_all_sounds, danger=True).pack(side="right", padx=6, pady=8)

        controls = self._card(page)
        controls.pack(fill="x", pady=(0, 10))
        tk.Label(controls, text="Search", fg=MUTED, bg=PANEL).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))
        search_entry = tk.Entry(controls, textvariable=self.sound_search, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0)
        search_entry.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self.sound_search.trace_add("write", lambda *_: self._render_soundboard())

        tk.Label(controls, text="Master volume", fg=MUTED, bg=PANEL).grid(row=0, column=1, sticky="w", padx=12, pady=(10, 2))
        ttk.Scale(controls, from_=0, to=120, variable=self.soundboard_master, command=lambda _v: self._sync_soundboard_settings()).grid(row=1, column=1, sticky="ew", padx=12, pady=(0, 10))
        tk.Label(controls, text="Mic ducking (dB)", fg=MUTED, bg=PANEL).grid(row=0, column=2, sticky="w", padx=12, pady=(10, 2))
        ttk.Scale(controls, from_=0, to=24, variable=self.soundboard_duck, command=lambda _v: self._sync_soundboard_settings()).grid(row=1, column=2, sticky="ew", padx=12, pady=(0, 10))
        tk.Checkbutton(
            controls,
            text="Allow overlap",
            variable=self.soundboard_overlap,
            command=self._sync_soundboard_settings,
            bg=PANEL,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=PANEL,
            activeforeground=TEXT,
        ).grid(row=1, column=3, padx=12)
        for col in range(3):
            controls.grid_columnconfigure(col, weight=1)

        hint = tk.Label(
            page,
            text="Supported: WAV, MP3, OGG, FLAC, AIFF. Hotkey examples: <f8> or <ctrl>+<alt>+1. Audio is mixed with your microphone into the selected virtual output.",
            fg=MUTED,
            bg=BG,
            font=("TkDefaultFont", 8),
            anchor="w",
            justify="left",
        )
        hint.pack(fill="x", pady=(0, 8))

        self.sound_canvas = tk.Canvas(page, bg=BG, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(page, orient="vertical", command=self.sound_canvas.yview)
        self.sound_list = tk.Frame(self.sound_canvas, bg=BG)
        self.sound_list.bind("<Configure>", lambda _e: self.sound_canvas.configure(scrollregion=self.sound_canvas.bbox("all")))
        self.sound_window = self.sound_canvas.create_window((0, 0), window=self.sound_list, anchor="nw")
        self.sound_canvas.bind("<Configure>", lambda e: self.sound_canvas.itemconfigure(self.sound_window, width=e.width))
        self.sound_canvas.configure(yscrollcommand=scrollbar.set)
        self.sound_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._render_soundboard()
        return page

    def _build_studio(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)

        intro = self._card(page)
        intro.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        tk.Label(intro, text="Voice Studio", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 14, "bold")).pack(anchor="w", padx=16, pady=(15, 2))
        tk.Label(intro, text="Realtime controls override the active preset. Pitch uses Pedalboard/Rubber Band when available.", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 9)).pack(anchor="w", padx=16, pady=(0, 14))

        voice = self._card(page)
        voice.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self._studio_slider(voice, "Pitch", self.pitch, -12, 12, "st")
        self._studio_slider(voice, "Timbre / formant color", self.formant_color, -100, 100, "%")
        tk.Label(voice, text="Formant color is an experimental spectral-envelope control, not independent AI formant conversion.", fg=WARN, bg=PANEL, wraplength=420, justify="left", font=("TkDefaultFont", 8)).pack(fill="x", padx=16, pady=(0, 12))

        basics = self._card(page)
        basics.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        self._studio_slider(basics, "Output gain", self.gain, -18, 18, "dB")
        self._studio_slider(basics, "Effect mix", self.wet, 0, 100, "%")
        self._studio_slider(basics, "Noise gate", self.gate, -80, -20, "dB")
        return page

    def _build_ai_models(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        header = self._card(page)
        header.pack(fill="x", pady=(0, 12))
        tk.Label(header, text="Local AI Voice Models", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 13, "bold")).pack(anchor="w", padx=16, pady=(14, 3))
        tk.Label(
            header,
            text="Model storage and ONNX provider detection are implemented. RVC inference remains adapter-gated so incompatible or untrusted graphs are not executed blindly.",
            fg=MUTED,
            bg=PANEL,
            wraplength=830,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))
        actions = tk.Frame(header, bg=PANEL)
        actions.pack(fill="x", padx=16, pady=(0, 14))
        self._button(actions, "Import .onnx / .pth / .index", self._import_ai_models, primary=True).pack(side="left")
        self._button(actions, "Refresh", self._refresh_ai_models).pack(side="left", padx=8)

        capability = self._card(page)
        capability.pack(fill="x", pady=(0, 12))
        self.ai_capability_text = tk.Label(capability, text="Detecting backends…", fg=MUTED, bg=PANEL, justify="left")
        self.ai_capability_text.pack(anchor="w", padx=16, pady=14)

        self.ai_list = self._card(page)
        self.ai_list.pack(fill="both", expand=True)
        self._refresh_ai_models()
        return page

    def _build_audio(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        routing = self._card(page)
        routing.pack(fill="x", pady=(0, 12))
        tk.Label(routing, text="Audio routing", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 13, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(15, 3))
        tk.Label(routing, text="Physical microphone in, virtual sink out. Soundboard and processed voice share this output.", fg=MUTED, bg=PANEL).grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 14))
        tk.Label(routing, text="INPUT MICROPHONE", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8, "bold")).grid(row=2, column=0, sticky="w", padx=16)
        tk.Label(routing, text="OUTPUT / VIRTUAL SINK", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8, "bold")).grid(row=2, column=1, sticky="w", padx=16)
        self.input_combo = ttk.Combobox(routing, state="readonly", style="Ox.TCombobox")
        self.output_combo = ttk.Combobox(routing, state="readonly", style="Ox.TCombobox")
        self.input_combo.grid(row=3, column=0, sticky="ew", padx=16, pady=(5, 14))
        self.output_combo.grid(row=3, column=1, sticky="ew", padx=16, pady=(5, 14))
        routing.grid_columnconfigure(0, weight=1)
        routing.grid_columnconfigure(1, weight=1)

        actions = self._card(page)
        actions.pack(fill="x")
        self.start_btn = self._button(actions, "Start engine", self._start, primary=True)
        self.start_btn.pack(side="left", padx=(14, 6), pady=14)
        self.stop_btn = self._button(actions, "Stop", self._stop)
        self.stop_btn.pack(side="left", padx=6, pady=14)
        self._button(actions, "Refresh devices", self._load_devices).pack(side="left", padx=6, pady=14)
        tk.Label(actions, text="Linux helper: ./scripts/linux_virtual_mic.sh create", fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8)).pack(side="right", padx=14)
        return page

    def _voice_tile(self, parent: tk.Widget, preset: VoicePreset, row: int, column: int, compact: bool = False) -> None:
        selected = self.selected_voice.get() == preset.name
        bg = ACCENT if selected else PANEL_2
        card = tk.Button(
            parent,
            text=f"{preset.emoji}  {preset.name}" if compact else f"{preset.emoji}\n{preset.name}\n{preset.category}",
            command=lambda n=preset.name: self._select_voice(n),
            bg=bg,
            fg=TEXT,
            activebackground=ACCENT_ACTIVE,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            justify="left" if compact else "center",
            anchor="w" if compact else "center",
            padx=10,
            pady=9 if compact else 14,
            font=("TkDefaultFont", 9, "bold"),
        )
        card.grid(row=row, column=column, sticky="nsew", padx=4, pady=4)

    def _render_voice_library(self) -> None:
        if not hasattr(self, "voice_library"):
            return
        for child in self.voice_library.winfo_children():
            child.destroy()
        query = self.search.get().strip().lower()
        category = self.selected_category.get()
        presets = [p for p in VOICE_PRESETS if (category == "All" or p.category == category) and (not query or query in p.name.lower() or query in p.description.lower())]
        for col in range(3):
            self.voice_library.grid_columnconfigure(col, weight=1)
        for i, preset in enumerate(presets):
            self._voice_tile(self.voice_library, preset, i // 3, i % 3)

    def _render_soundboard(self) -> None:
        if not hasattr(self, "sound_list"):
            return
        for child in self.sound_list.winfo_children():
            child.destroy()
        query = self.sound_search.get().strip().lower()
        items = [item for item in self.engine.soundboard.items if not query or query in item.name.lower() or query in item.category.lower()]
        if not items:
            empty = self._card(self.sound_list)
            empty.pack(fill="x", pady=4)
            tk.Label(empty, text="No sounds yet. Import audio files to build your local library.", fg=MUTED, bg=PANEL, pady=20).pack()
            return

        active_ids = {state.item_id: state for state in self.engine.soundboard.states()}
        for item in items:
            row = self._card(self.sound_list)
            row.pack(fill="x", pady=4)
            row.grid_columnconfigure(1, weight=1)
            state = active_ids.get(item.id)
            marker = "▶" if state and state.active and not state.paused else ("Ⅱ" if state and state.paused else "■")
            tk.Label(row, text=marker, fg=GOOD if state and state.active else MUTED, bg=PANEL, width=3).grid(row=0, column=0, rowspan=2, padx=(10, 4))
            tk.Label(row, text=item.name, fg=TEXT, bg=PANEL, font=("TkDefaultFont", 10, "bold"), anchor="w").grid(row=0, column=1, sticky="ew", pady=(8, 0))
            details = Path(item.path).suffix.upper().lstrip(".") + f"  ·  {int(item.volume * 100)}%"
            if state:
                details += f"  ·  {state.position_seconds:.1f}s"
                if state.underruns:
                    details += f"  ·  underruns {state.underruns}"
            tk.Label(row, text=details, fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8), anchor="w").grid(row=1, column=1, sticky="ew", pady=(0, 8))

            hotkey = tk.StringVar(value=item.hotkey)
            hot_entry = tk.Entry(row, textvariable=hotkey, width=18, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0)
            hot_entry.grid(row=0, column=2, rowspan=2, padx=5, pady=9)
            self._button(row, "Save key", lambda i=item.id, v=hotkey: self._save_hotkey(i, v.get())).grid(row=0, column=3, rowspan=2, padx=4, pady=8)
            self._button(row, "Play", lambda i=item.id: self._play_sound(i), primary=True).grid(row=0, column=4, rowspan=2, padx=4, pady=8)
            self._button(row, "Pause", lambda i=item.id: self._pause_sound(i)).grid(row=0, column=5, rowspan=2, padx=4, pady=8)
            self._button(row, "Stop", lambda i=item.id: self._stop_sound(i)).grid(row=0, column=6, rowspan=2, padx=4, pady=8)
            self._button(row, "×", lambda i=item.id: self._remove_sound(i), danger=True).grid(row=0, column=7, rowspan=2, padx=(4, 10), pady=8)

    def _studio_slider(self, parent: tk.Widget, label: str, variable: tk.DoubleVar, lo: float, hi: float, unit: str) -> None:
        box = tk.Frame(parent, bg=PANEL)
        box.pack(fill="x", padx=16, pady=(14, 3))
        tk.Label(box, text=label, fg=TEXT, bg=PANEL, font=("TkDefaultFont", 9, "bold")).pack(side="left")
        value_label = tk.Label(box, fg=MUTED, bg=PANEL)
        value_label.pack(side="right")
        scale = ttk.Scale(parent, from_=lo, to=hi, variable=variable, command=lambda _v: self._sync_settings())
        scale.pack(fill="x", padx=16, pady=(2, 8))

        def refresh(*_):
            value_label.configure(text=f"{variable.get():.1f} {unit}")

        variable.trace_add("write", refresh)
        refresh()

    def _meter(self, parent: tk.Widget, title: str):
        box = tk.Frame(parent, bg=PANEL)
        box.pack(fill="x", padx=16, pady=7)
        tk.Label(box, text=title, fg=MUTED, bg=PANEL, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", pady=(0, 4))
        meter = ttk.Progressbar(box, maximum=1.0, style="Ox.Horizontal.TProgressbar")
        meter.pack(fill="x")
        return meter

    def _set_category(self, category: str) -> None:
        self.selected_category.set(category)
        self._render_voice_library()
        for name, btn in self.category_buttons.items():
            btn.configure(bg=ACCENT if name == category else PANEL_2)

    def _select_voice(self, name: str) -> None:
        preset = get_preset(name)
        self.selected_voice.set(preset.name)
        self.voice_description.set(preset.description)
        self.pitch.set(preset.pitch_semitones)
        self.formant_color.set(preset.formant_color * 100.0)
        if hasattr(self, "hero_voice"):
            self.hero_voice.configure(text=preset.name)
        self._sync_settings()
        self._render_voice_library()

    def _sync_settings(self) -> None:
        self.engine.update_settings(
            preset=self.selected_voice.get(),
            gain_db=float(self.gain.get()),
            wet=float(self.wet.get()) / 100.0,
            gate_db=float(self.gate.get()),
            pitch_semitones=float(self.pitch.get()),
            formant_color=float(self.formant_color.get()) / 100.0,
        )

    def _sync_soundboard_settings(self) -> None:
        settings = self.engine.soundboard.settings
        settings.master_volume = float(self.soundboard_master.get()) / 100.0
        settings.ducking_db = float(self.soundboard_duck.get())
        settings.allow_overlap = bool(self.soundboard_overlap.get())
        self.engine.soundboard.save()

    def _load_devices(self) -> None:
        try:
            devices = list(self.engine.devices())
        except Exception as exc:
            messagebox.showerror("Audio backend", f"Could not load audio devices.\n\n{exc}")
            devices = []
        self._devices = devices
        self._inputs = [(i, d["name"]) for i, d in enumerate(devices) if d.get("max_input_channels", 0) > 0]
        self._outputs = [(i, d["name"]) for i, d in enumerate(devices) if d.get("max_output_channels", 0) > 0]
        if hasattr(self, "input_combo"):
            self.input_combo["values"] = [f"{i}: {name}" for i, name in self._inputs]
            self.output_combo["values"] = [f"{i}: {name}" for i, name in self._outputs]
            if self._inputs and self.input_combo.current() < 0:
                self.input_combo.current(0)
            if self._outputs and self.output_combo.current() < 0:
                preferred = next((j for j, (_, name) in enumerate(self._outputs) if "voxshift" in name.lower() or "oxshift" in name.lower()), 0)
                self.output_combo.current(preferred)

    @staticmethod
    def _selected_index(combo: ttk.Combobox, items) -> int | None:
        idx = combo.current()
        return items[idx][0] if 0 <= idx < len(items) else None

    def _start(self) -> None:
        if not hasattr(self, "input_combo"):
            self._show_page("Audio")
            return
        try:
            self._sync_settings()
            self._sync_soundboard_settings()
            self.engine.start(
                self._selected_index(self.input_combo, self._inputs),
                self._selected_index(self.output_combo, self._outputs),
            )
            self.status.set("Running")
        except Exception as exc:
            messagebox.showerror("Could not start", str(exc))

    def _ensure_engine(self) -> bool:
        if self.engine.last_status == "Running":
            return True
        self._start()
        return self.engine.last_status == "Running"

    def _stop(self) -> None:
        self.engine.stop()
        self.status.set("Stopped")

    def _import_sounds(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Import sounds or music",
            filetypes=[("Audio", "*.wav *.mp3 *.ogg *.flac *.aiff *.aif"), ("All files", "*")],
        )
        if not paths:
            return
        added = self.engine.soundboard.add_files(list(paths))
        if not added:
            messagebox.showinfo("Soundboard", "No new supported audio files were added.")
        self._render_soundboard()

    def _play_sound(self, item_id: str) -> None:
        if not self._ensure_engine():
            return
        self.engine.soundboard.play(item_id)
        self.root.after(120, self._render_soundboard)

    def _pause_sound(self, item_id: str) -> None:
        self.engine.soundboard.toggle_pause(item_id)
        self._render_soundboard()

    def _stop_sound(self, item_id: str) -> None:
        self.engine.soundboard.stop(item_id)
        self._render_soundboard()

    def _stop_all_sounds(self) -> None:
        self.engine.soundboard.stop_all()
        self._render_soundboard()

    def _remove_sound(self, item_id: str) -> None:
        self.engine.soundboard.remove(item_id)
        self._refresh_hotkeys()
        self._render_soundboard()

    def _save_hotkey(self, item_id: str, hotkey: str) -> None:
        self.engine.soundboard.update_item(item_id, hotkey=hotkey.strip())
        self._refresh_hotkeys()
        if self.hotkeys.last_error:
            messagebox.showwarning("Global hotkeys", f"Hotkey saved, but the global listener could not start:\n\n{self.hotkeys.last_error}")

    def _refresh_hotkeys(self) -> None:
        bindings = {}
        for item in self.engine.soundboard.items:
            if item.hotkey.strip():
                bindings[item.hotkey.strip()] = lambda item_id=item.id: self.root.after(0, lambda: self._play_sound(item_id))
        self.hotkeys.start(bindings)

    def _import_ai_models(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Import local voice models",
            filetypes=[("Voice models", "*.onnx *.pth *.index"), ("All files", "*")],
        )
        if paths:
            self.ai_registry.import_files(list(paths))
            self._refresh_ai_models()

    def _refresh_ai_models(self) -> None:
        if not hasattr(self, "ai_list"):
            return
        capabilities = self.ai_registry.capabilities()
        providers = ", ".join(capabilities.providers) if capabilities.providers else "none"
        self.ai_capability_text.configure(
            text=f"ONNX Runtime: {'available' if capabilities.onnxruntime else 'not installed'}\nProviders: {providers}\nRVC realtime adapter: {'ready' if capabilities.rvc_adapter_ready else 'not enabled yet'}"
        )
        for child in self.ai_list.winfo_children():
            child.destroy()
        models = self.ai_registry.scan()
        tk.Label(self.ai_list, text=f"Model library ({len(models)})", fg=TEXT, bg=PANEL, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 6))
        if not models:
            tk.Label(self.ai_list, text="No local models imported.", fg=MUTED, bg=PANEL).pack(anchor="w", padx=14, pady=(0, 12))
            return
        for model in models:
            row = tk.Frame(self.ai_list, bg=PANEL_2)
            row.pack(fill="x", padx=12, pady=4)
            tk.Label(row, text=model.name, fg=TEXT, bg=PANEL_2, font=("TkDefaultFont", 9, "bold")).pack(side="left", padx=10, pady=10)
            tk.Label(row, text=f"{model.format.upper()} · {model.backend}", fg=GOOD if model.backend != "unavailable" else WARN, bg=PANEL_2).pack(side="right", padx=10)

    def _show_page(self, page: str) -> None:
        self.current_page = page
        self.pages[page].tkraise()
        self.page_title.configure(text=page)
        for name, button in self.nav_buttons.items():
            button.configure(bg=PANEL_2 if name == page else SIDEBAR, fg=TEXT if name == page else MUTED)
        if page == "Soundboard":
            self._render_soundboard()
        elif page == "AI Models":
            self._refresh_ai_models()

    def _tick(self) -> None:
        def level(value: float) -> float:
            return min(1.0, max(0.0, value * 4.0))

        if hasattr(self, "dashboard_in"):
            self.dashboard_in["value"] = level(self.engine.input_level)
            self.dashboard_board["value"] = level(self.engine.soundboard_level)
            self.dashboard_out["value"] = level(self.engine.output_level)
            active = len(self.engine.soundboard.states())
            self.dashboard_soundboard.configure(text=f"{len(self.engine.soundboard.items)} sounds · {active} active")
            if self.engine.last_status == "Running":
                self.performance_text.configure(
                    text=(
                        f"Buffer: {self.engine.estimated_buffer_latency_ms:.2f} ms\n"
                        f"DSP callback: {self.engine.callback_ms:.2f} ms  ·  peak {self.engine.callback_peak_ms:.2f} ms\n"
                        f"XRuns/over-budget: {self.engine.xruns}\n"
                        f"Pitch backend: {self.engine.pitch_backend}"
                    )
                )
            else:
                self.performance_text.configure(text="Engine stopped")

        if self.engine.last_status not in ("Running", "Stopped"):
            self.status.set(self.engine.last_status)
        else:
            self.status.set(self.engine.last_status)
        self.root.after(80, self._tick)

    def _close(self) -> None:
        self.hotkeys.stop()
        self.engine.stop()
        self.root.destroy()
