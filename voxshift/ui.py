from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .audio_engine import AudioEngine


class VoxShiftUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("OxShift — Real-time Voice Changer")
        self.root.minsize(760, 540)
        self.engine = AudioEngine()

        self.preset = tk.StringVar(value="Clean")
        self.gain = tk.DoubleVar(value=0.0)
        self.wet = tk.DoubleVar(value=100.0)
        self.gate = tk.DoubleVar(value=-55.0)
        self.status = tk.StringVar(value="Stopped")

        self._build()
        self._load_devices()
        self._sync_settings()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(60, self._tick)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="OxShift", font=("TkDefaultFont", 22, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Local real-time voice processing · MVP 0.1").pack(anchor="w", pady=(0, 16))

        io = ttk.LabelFrame(outer, text="Audio routing", padding=12)
        io.pack(fill="x")
        ttk.Label(io, text="Input microphone").grid(row=0, column=0, sticky="w")
        self.input_combo = ttk.Combobox(io, state="readonly")
        self.input_combo.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(4, 8))
        ttk.Label(io, text="Output / virtual sink").grid(row=0, column=1, sticky="w")
        self.output_combo = ttk.Combobox(io, state="readonly")
        self.output_combo.grid(row=1, column=1, sticky="ew", pady=(4, 8))
        io.columnconfigure(0, weight=1)
        io.columnconfigure(1, weight=1)

        fx = ttk.LabelFrame(outer, text="Voice", padding=12)
        fx.pack(fill="x", pady=14)
        ttk.Label(fx, text="Preset").grid(row=0, column=0, sticky="w")
        preset_combo = ttk.Combobox(
            fx,
            textvariable=self.preset,
            values=["Clean", "Radio", "Robot", "Anonymous"],
            state="readonly",
            width=18,
        )
        preset_combo.grid(row=1, column=0, sticky="w", pady=(4, 12))
        preset_combo.bind("<<ComboboxSelected>>", lambda _e: self._sync_settings())

        self._slider(fx, "Gain (dB)", self.gain, -18, 18, 1)
        self._slider(fx, "Effect mix (%)", self.wet, 0, 100, 2)
        self._slider(fx, "Noise gate (dB)", self.gate, -80, -20, 3)

        meters = ttk.Frame(outer)
        meters.pack(fill="x", pady=(0, 14))
        ttk.Label(meters, text="Input").grid(row=0, column=0, sticky="w")
        self.in_meter = ttk.Progressbar(meters, maximum=1.0)
        self.in_meter.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Label(meters, text="Output").grid(row=0, column=1, sticky="w")
        self.out_meter = ttk.Progressbar(meters, maximum=1.0)
        self.out_meter.grid(row=1, column=1, sticky="ew")
        meters.columnconfigure((0, 1), weight=1)

        actions = ttk.Frame(outer)
        actions.pack(fill="x")
        self.start_btn = ttk.Button(actions, text="Start processing", command=self._start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(actions, text="Stop", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=8)
        ttk.Label(actions, textvariable=self.status).pack(side="right")

        note = (
            "Linux: create the virtual microphone first with scripts/linux_virtual_mic.sh create, "
            "route OxShift output to voxshift_sink, then select VoxShift Microphone in Discord/OBS."
        )
        ttk.Label(outer, text=note, wraplength=710, justify="left").pack(fill="x", pady=(16, 0))

    def _slider(self, parent, text, variable, lo, hi, row) -> None:
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w")
        scale = ttk.Scale(parent, from_=lo, to=hi, variable=variable, command=lambda _v: self._sync_settings())
        scale.grid(row=row, column=1, sticky="ew", padx=(12, 0))
        value = ttk.Label(parent, width=8)
        value.grid(row=row, column=2, sticky="e")
        parent.columnconfigure(1, weight=1)

        def refresh(*_):
            value.configure(text=f"{variable.get():.0f}")

        variable.trace_add("write", refresh)
        refresh()

    def _load_devices(self) -> None:
        try:
            devices = self.engine.devices()
        except Exception as exc:
            messagebox.showerror(
                "Audio backend",
                f"Could not load audio devices.\n\n{exc}\n\nInstall dependencies from requirements.txt and PortAudio.",
            )
            devices = []
        self._devices = list(devices)
        inputs = [(i, d["name"]) for i, d in enumerate(self._devices) if d.get("max_input_channels", 0) > 0]
        outputs = [(i, d["name"]) for i, d in enumerate(self._devices) if d.get("max_output_channels", 0) > 0]
        self._inputs, self._outputs = inputs, outputs
        self.input_combo["values"] = [f"{i}: {n}" for i, n in inputs]
        self.output_combo["values"] = [f"{i}: {n}" for i, n in outputs]
        if inputs:
            self.input_combo.current(0)
        if outputs:
            self.output_combo.current(0)

    def _sync_settings(self) -> None:
        self.engine.update_settings(
            preset=self.preset.get(),
            gain_db=float(self.gain.get()),
            wet=float(self.wet.get()) / 100.0,
            gate_db=float(self.gate.get()),
        )

    def _selected_index(self, combo: ttk.Combobox, items) -> int | None:
        idx = combo.current()
        return items[idx][0] if 0 <= idx < len(items) else None

    def _start(self) -> None:
        try:
            self._sync_settings()
            self.engine.start(
                self._selected_index(self.input_combo, self._inputs),
                self._selected_index(self.output_combo, self._outputs),
            )
        except Exception as exc:
            messagebox.showerror("Could not start", str(exc))
            return
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status.set("Running")

    def _stop(self) -> None:
        self.engine.stop()
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status.set("Stopped")

    def _tick(self) -> None:
        self.in_meter["value"] = min(1.0, self.engine.input_level * 4.0)
        self.out_meter["value"] = min(1.0, self.engine.output_level * 4.0)
        if self.engine.last_status not in ("Running", "Stopped"):
            self.status.set(self.engine.last_status)
        self.root.after(60, self._tick)

    def _close(self) -> None:
        self.engine.stop()
        self.root.destroy()
