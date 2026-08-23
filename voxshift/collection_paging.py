from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk

from .pro_ui import ACCENT_2, BG, MUTED, PANEL, TEXT
from .voices import VOICE_PRESETS


class CollectionPagingUI:
    """Bounded rendering for catalog-style pages.

    Tk widgets are not virtualized, so rendering hundreds of sounds/voices at once makes the
    desktop UI slow and clips content on smaller windows. This extension keeps each render
    bounded while preserving the existing search/category behavior.
    """

    def __init__(self, app, *, sounds_per_page: int = 8, voices_per_page: int = 9) -> None:
        self.app = app
        self.sounds_per_page = max(4, int(sounds_per_page))
        self.voices_per_page = max(6, int(voices_per_page))
        self.sound_page = 0
        self.voice_page = 0
        app._render_sounds = self.render_sounds
        app._render_voices = self.render_voices
        self.render_sounds()
        self.render_voices()

    def render_sounds(self) -> None:
        if not hasattr(self.app, "sound_list"):
            return
        container = self.app.sound_list
        for child in container.winfo_children():
            child.destroy()

        query = self.app.search_sound.get().casefold().strip()
        items = [
            item
            for item in self.app.engine.soundboard.items
            if not query or query in item.name.casefold() or query in item.category.casefold()
        ]
        if not items:
            self.sound_page = 0
            self._sound_empty(container, bool(self.app.engine.soundboard.items))
            return

        pages = max(1, math.ceil(len(items) / self.sounds_per_page))
        self.sound_page = max(0, min(self.sound_page, pages - 1))
        start = self.sound_page * self.sounds_per_page
        visible = items[start : start + self.sounds_per_page]

        for item in visible:
            row = self.app._card(container)
            row.pack(fill="x", pady=3)
            left = tk.Frame(row, bg=PANEL)
            left.pack(side="left", fill="x", expand=True, padx=10, pady=8)
            tk.Label(left, text=item.name, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
            suffix = Path(item.path).suffix.upper().lstrip(".") or "AUDIO"
            meta = f"{item.category} · {suffix} · {int(item.volume * 100)}%"
            if item.hotkey:
                meta += f" · {item.hotkey}"
            tk.Label(left, text=meta, bg=PANEL, fg=MUTED).pack(anchor="w", pady=(2, 0))
            self.app._button(row, "Remove", lambda i=item.id: self.app._remove_sound_alpha(i), danger=True).pack(side="right", padx=3, pady=6)
            self.app._button(row, "Edit", lambda i=item.id: self.app._render_sound_editor(i)).pack(side="right", padx=3, pady=6)
            self.app._button(row, "+ Playlist", lambda i=item.id: self.app._add_to_playlist(i)).pack(side="right", padx=3, pady=6)
            self.app._button(row, "Play", lambda i=item.id: self.app._play_sound(i), primary=True).pack(side="right", padx=3, pady=6)

        self._pager(
            container,
            page=self.sound_page,
            pages=pages,
            total=len(items),
            previous=lambda: self._move_sound_page(-1),
            next_=lambda: self._move_sound_page(1),
        )

    def _sound_empty(self, container, has_library: bool) -> None:
        box = self.app._card(container)
        box.pack(fill="x", pady=8)
        if has_library:
            title = "No matching sounds"
            detail = "Clear the search or try a different name/category."
            action_text = "Clear search"
            action = lambda: self.app.search_sound.set("")
        else:
            title = "Your Soundboard is empty"
            detail = "Import a clip or song. OxShift streams it from disk and mixes it into the virtual microphone."
            action_text = "Import sounds"
            action = self.app._import_sounds
        tk.Label(box, text=title, bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 3))
        tk.Label(box, text=detail, bg=PANEL, fg=MUTED, wraplength=620, justify="left").pack(anchor="w", padx=14, pady=(0, 10))
        self.app._button(box, action_text, action, primary=True).pack(anchor="w", padx=14, pady=(0, 14))

    def _move_sound_page(self, delta: int) -> None:
        self.sound_page = max(0, self.sound_page + delta)
        self.render_sounds()

    def render_voices(self) -> None:
        if not hasattr(self.app, "voice_list"):
            return
        container = self.app.voice_list
        for child in container.winfo_children():
            child.destroy()

        query = self.app.search_voice.get().casefold().strip()
        category = self.app.category.get()
        items = [
            preset
            for preset in VOICE_PRESETS
            if (category == "All" or preset.category == category)
            and (not query or query in preset.name.casefold() or query in preset.description.casefold())
        ]
        if not items:
            self.voice_page = 0
            box = self.app._card(container)
            box.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=8)
            tk.Label(box, text="No matching voices", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 3))
            tk.Label(box, text="Clear search or select another category.", bg=PANEL, fg=MUTED).pack(anchor="w", padx=14, pady=(0, 10))
            self.app._button(box, "Show all voices", self._clear_voice_filters, primary=True).pack(anchor="w", padx=14, pady=(0, 14))
            return

        pages = max(1, math.ceil(len(items) / self.voices_per_page))
        self.voice_page = max(0, min(self.voice_page, pages - 1))
        start = self.voice_page * self.voices_per_page
        visible = items[start : start + self.voices_per_page]
        for column in range(3):
            container.grid_columnconfigure(column, weight=1)

        for index, preset in enumerate(visible):
            card = self.app._card(container)
            card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=5, pady=5)
            tk.Label(card, text=f"{preset.emoji}  {preset.name}", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=12, pady=(12, 2))
            tk.Label(card, text=preset.category, bg=PANEL, fg=ACCENT_2, font=("TkDefaultFont", 8, "bold")).pack(anchor="w", padx=12)
            tk.Label(card, text=preset.description, bg=PANEL, fg=MUTED, wraplength=270, justify="left").pack(anchor="w", padx=12, pady=(5, 10))
            self.app._button(
                card,
                "Use voice",
                lambda n=preset.name: self.app._select_voice(n),
                primary=preset.name == self.app.voice.get(),
            ).pack(fill="x", padx=10, pady=(0, 10))

        footer_row = math.ceil(len(visible) / 3)
        footer = tk.Frame(container, bg=BG)
        footer.grid(row=footer_row, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self._pager(
            footer,
            page=self.voice_page,
            pages=pages,
            total=len(items),
            previous=lambda: self._move_voice_page(-1),
            next_=lambda: self._move_voice_page(1),
            packed=True,
        )

    def _move_voice_page(self, delta: int) -> None:
        self.voice_page = max(0, self.voice_page + delta)
        self.render_voices()

    def _clear_voice_filters(self) -> None:
        self.app.search_voice.set("")
        self.app.category.set("All")
        self.voice_page = 0
        self.render_voices()

    def _pager(self, parent, *, page: int, pages: int, total: int, previous, next_, packed: bool = False) -> None:
        bar = parent if packed else tk.Frame(parent, bg=BG)
        if not packed:
            bar.pack(fill="x", pady=(8, 0))
        previous_button = self.app._button(bar, "Previous", previous)
        previous_button.pack(side="left")
        previous_button.configure(state="normal" if page > 0 else "disabled")
        next_button = self.app._button(bar, "Next", next_)
        next_button.pack(side="right")
        next_button.configure(state="normal" if page + 1 < pages else "disabled")
        tk.Label(bar, text=f"Page {page + 1} / {pages} · {total} items", bg=BG, fg=MUTED).pack(side="left", expand=True)


def install_collection_paging(app) -> CollectionPagingUI:
    extension = CollectionPagingUI(app)
    app.collection_paging = extension
    return extension
