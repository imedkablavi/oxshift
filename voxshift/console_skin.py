from __future__ import annotations

import tkinter as tk
from tkinter import ttk


# Neutral studio-console palette. Accent is reserved for controls/readouts instead of filling
# every card, which keeps the product closer to an audio tool than an AI dashboard.
COLOR_MAP = {
    "#090d16": "#101214",
    "#0c111d": "#15181b",
    "#111827": "#1b1f23",
    "#182235": "#25292e",
    "#273449": "#343a40",
    "#f2f5fb": "#e7e9eb",
    "#95a2b8": "#9aa0a6",
    "#6f7bf7": "#d39a4a",
    "#8993ff": "#e1b56f",
    "#38c991": "#58b57b",
    "#eab760": "#d5a24f",
    "#ef6c7d": "#c96565",
}

TEXT_REPLACEMENTS = {
    "OxShift Studio": "OxShift Audio Console",
    "VOICE + SOUND + AI": "VOICE PROCESSOR / MIXER",
    "LOCAL ENGINE": "AUDIO ENGINE",
    "No cloud audio transport": "Local realtime processing",
    "Your voice route, in one place": "Signal chain",
    "Setup checklist": "Routing",
    "Live engine health": "Meters & engine",
    "Fast workflow": "Workflow",
    "Audio stays on this computer.": "Local audio engine",
    "Voice transformation": "Voice strip",
    "Microphone conditioning": "Input processing",
    "Custom effects chain": "Insert chain",
    "No local AI models yet": "No voice models loaded",
}

PAGE_TITLES = {
    "Home": "Console",
    "Voices": "Voices",
    "Soundboard": "Soundboard",
    "Studio": "Mixer / EQ",
    "Profiles": "Profiles",
    "AI Models": "Voice Models",
    "Audio": "Audio I/O",
}


class ConsoleSkin:
    def __init__(self, app) -> None:
        self.app = app
        self._original_show = app._show
        self._install_show_hook()
        self._apply_style()
        self._rename_navigation()
        self._retitle_known_widgets(app.root)
        app.root.title("OxShift Audio Console")
        self._sync_page_title()

    def _install_show_hook(self) -> None:
        def show(page):
            result = self._original_show(page)
            self._sync_page_title()
            return result

        self.app._show = show

    def _sync_page_title(self) -> None:
        if hasattr(self.app, "title"):
            self.app.title.configure(text=PAGE_TITLES.get(self.app.current_page, self.app.current_page))

    def _rename_navigation(self) -> None:
        labels = {
            "Home": "  ▣   Console",
            "Voices": "  ◉   Voices",
            "Soundboard": "  ▶   Soundboard",
            "Studio": "  ≋   Mixer / EQ",
            "Profiles": "  ▤   Profiles",
            "AI Models": "  ◇   Voice Models",
            "Audio": "  ⌁   Audio I/O",
        }
        for page, text in labels.items():
            button = self.app.nav.get(page)
            if button is not None:
                button.configure(text=text)

    def _apply_style(self) -> None:
        self.app.root.configure(bg=COLOR_MAP["#090d16"])
        style = ttk.Style()
        style.configure(
            "Ox.Horizontal.TProgressbar",
            troughcolor=COLOR_MAP["#25292e"] if "#25292e" in COLOR_MAP else "#25292e",
            background="#58b57b",
            bordercolor="#25292e",
            lightcolor="#58b57b",
            darkcolor="#58b57b",
        )
        style.configure(
            "Ox.TCombobox",
            fieldbackground="#25292e",
            background="#25292e",
            foreground="#e7e9eb",
            arrowcolor="#e7e9eb",
            bordercolor="#343a40",
        )
        self._recolor_tree(self.app.root)

    def _recolor_tree(self, widget) -> None:
        try:
            config = widget.configure()
        except tk.TclError:
            config = {}
        pairs = {
            "background": "background",
            "foreground": "foreground",
            "activebackground": "activebackground",
            "activeforeground": "activeforeground",
            "highlightbackground": "highlightbackground",
            "highlightcolor": "highlightcolor",
            "selectcolor": "selectcolor",
            "troughcolor": "troughcolor",
            "insertbackground": "insertbackground",
        }
        changes = {}
        for option in pairs:
            if option not in config:
                continue
            try:
                current = str(widget.cget(option)).lower()
            except tk.TclError:
                continue
            replacement = COLOR_MAP.get(current)
            if replacement:
                changes[option] = replacement
        if changes:
            try:
                widget.configure(**changes)
            except tk.TclError:
                pass
        for child in widget.winfo_children():
            self._recolor_tree(child)

    def _retitle_known_widgets(self, widget) -> None:
        try:
            if "text" in widget.configure():
                text = str(widget.cget("text"))
                replacement = TEXT_REPLACEMENTS.get(text)
                if replacement:
                    widget.configure(text=replacement)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._retitle_known_widgets(child)


def install_console_skin(app) -> ConsoleSkin:
    extension = ConsoleSkin(app)
    app.console_skin = extension
    return extension
