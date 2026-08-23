from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from .audio_devices import preflight_stream_format


class AudioPreflightUI:
    def __init__(self, app) -> None:
        self.app = app
        self._original_start = app._start
        app._start = self.start_with_preflight

    def start_with_preflight(self) -> None:
        if self.app.engine.last_status == "Running":
            return self._original_start()
        if not hasattr(self.app, "input_combo"):
            return self._original_start()
        input_pos = self.app.input_combo.current()
        output_pos = self.app.output_combo.current() if hasattr(self.app, "output_combo") else -1
        if not (0 <= input_pos < len(self.app._inputs)) or not (0 <= output_pos < len(self.app._outputs)):
            return self._original_start()

        input_index = self.app._inputs[input_pos][0]
        output_index = self.app._outputs[output_pos][0]
        profile = self.app.profiles.active
        try:
            import sounddevice as sd

            preflight_stream_format(
                sd,
                input_device=input_index,
                output_device=output_index,
                sample_rate=profile.sample_rate,
            )
        except Exception as exc:
            messagebox.showerror(
                "Audio route is not compatible",
                f"OxShift did not start the audio engine.\n\n{exc}\n\nTry Balanced (48 kHz / 256) or another input/output device.",
                parent=self.app.root,
            )
            if hasattr(self.app, "home_notice"):
                self.app.home_notice.configure(text="Audio preflight failed. Open Audio to change the route or performance preset.")
            return
        self._original_start()


def install_audio_preflight(app) -> AudioPreflightUI:
    preflight = AudioPreflightUI(app)
    app.audio_preflight_ui = preflight
    return preflight
