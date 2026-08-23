from __future__ import annotations

from copy import deepcopy
import tkinter as tk
from tkinter import messagebox

from .audio_devices import preflight_stream_format
from .pro_ui import GOOD, MUTED, WARN
from .realtime_preflight import find_safe_blocksize


class AudioPreflightUI:
    def __init__(self, app) -> None:
        self.app = app
        self._original_start = app._start
        self._checking = False
        app._start = self.start_with_preflight

    def start_with_preflight(self) -> None:
        if self._checking:
            return
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
                self.app.home_notice.configure(text="Audio preflight failed. Open Audio to change the route or performance preset.", fg=WARN)
            return

        # Native pitch/effect stages can be substantially heavier than Clean DSP. Measure
        # the active profile on this CPU before opening PortAudio and keep 20% headroom for
        # mixing, driver overhead and scheduling jitter. This work is deliberately outside
        # the realtime callback.
        self._checking = True
        if hasattr(self.app, "home_notice"):
            self.app.home_notice.configure(text="Checking realtime DSP headroom on this CPU…", fg=MUTED)
        try:
            self.app.root.update_idletasks()
        except tk.TclError:
            self._checking = False
            return

        try:
            snapshot = deepcopy(profile)
            recommendation, measured = find_safe_blocksize(snapshot, safe_ratio=0.80, iterations=12)
        except Exception as exc:
            self._checking = False
            messagebox.showerror(
                "Realtime performance check failed",
                f"OxShift did not start because the local DSP preflight could not complete.\n\n{exc}",
                parent=self.app.root,
            )
            return
        self._checking = False

        current_result = measured[0]
        if not recommendation.safe:
            messagebox.showwarning(
                "Preset is too heavy for realtime",
                (
                    f"'{profile.voice}' did not keep enough callback headroom even at {recommendation.blocksize} frames.\n\n"
                    f"Measured p95: {recommendation.p95_ms:.2f} ms\n"
                    f"Buffer budget: {recommendation.budget_ms:.2f} ms\n\n"
                    "Choose a lighter voice, bypass Pitch in Studio, or reduce other effects before starting."
                ),
                parent=self.app.root,
            )
            if hasattr(self.app, "home_notice"):
                self.app.home_notice.configure(text="Start blocked: active DSP chain failed realtime headroom preflight.", fg=WARN)
            return

        if recommendation.blocksize != profile.blocksize:
            accepted = messagebox.askyesno(
                "Increase audio buffer for this preset?",
                (
                    f"'{profile.voice}' is too heavy for the current {profile.blocksize}-frame buffer on this CPU.\n\n"
                    f"Current p95: {current_result.p95_ms:.2f} ms / {current_result.budget_ms:.2f} ms budget\n"
                    f"Recommended: {recommendation.blocksize} frames\n"
                    f"Measured p95 there: {recommendation.p95_ms:.2f} ms / {recommendation.budget_ms:.2f} ms budget\n\n"
                    "Apply the safer buffer to this profile and start OxShift?"
                ),
                parent=self.app.root,
            )
            if not accepted:
                if hasattr(self.app, "home_notice"):
                    self.app.home_notice.configure(text="Engine not started; keep the current buffer or change the DSP chain.", fg=MUTED)
                return
            self._apply_recommended_blocksize(recommendation.blocksize)

        if hasattr(self.app, "home_notice"):
            self.app.home_notice.configure(
                text=f"Realtime preflight passed: p95 {recommendation.p95_ms:.2f} ms / {recommendation.budget_ms:.2f} ms budget.",
                fg=GOOD,
            )
        self._original_start()

    def _apply_recommended_blocksize(self, blocksize: int) -> None:
        profile = self.app.profiles.update_active(blocksize=int(blocksize))
        self.app.engine.blocksize = profile.blocksize
        performance = getattr(self.app, "audio_performance_ui", None)
        if performance is not None:
            performance.sample_rate_var.set(str(profile.sample_rate))
            performance.blocksize_var.set(str(profile.blocksize))
            performance._refresh_status("CPU-safe buffer applied")
        self.app._render_profiles()


def install_audio_preflight(app) -> AudioPreflightUI:
    preflight = AudioPreflightUI(app)
    app.audio_preflight_ui = preflight
    return preflight
