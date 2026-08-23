from __future__ import annotations

from threading import Thread
import tkinter as tk
from tkinter import messagebox, ttk

from .pro_ui import GOOD, MUTED, PANEL, TEXT, WARN
from .rvc_adapters import ValidatedStreamingOnnxAdapter


class AIProductControls:
    """Safe UI activation for already-validated local AI bundles.

    Validation and ONNX Runtime session construction happen on a background/UI worker, never
    in the PortAudio callback. Model swaps are only allowed while the audio engine is stopped
    so the existing voice-conversion worker cannot race an adapter replacement.
    """

    def __init__(self, app) -> None:
        self.app = app
        self._loading = False
        self._model_by_label: dict[str, object] = {}
        self.selected = tk.StringVar(master=app.root, value="")
        self._original_refresh_models = app._refresh_models
        self._install_panel()
        app._refresh_models = self.refresh_all
        self.refresh_catalog()

    def _install_panel(self) -> None:
        page = self.app.pages.get("AI Models")
        if page is None:
            return
        panel = self.app._card(page)
        before = getattr(self.app, "ai_status", None)
        pack_kwargs = {"fill": "x", "pady": (0, 10)}
        if before is not None:
            pack_kwargs["before"] = before
        panel.pack(**pack_kwargs)

        tk.Label(panel, text="Validated model activation", bg=PANEL, fg=TEXT, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 3))
        tk.Label(
            panel,
            text="Only allow-listed bundles that passed manifest, checksum and ONNX graph validation can be activated. Stop the engine before changing models.",
            bg=PANEL,
            fg=MUTED,
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 8))

        row = tk.Frame(panel, bg=PANEL)
        row.pack(fill="x", padx=10, pady=(0, 8))
        self.combo = ttk.Combobox(row, textvariable=self.selected, state="readonly", style="Ox.TCombobox")
        self.combo.pack(side="left", fill="x", expand=True, padx=4)
        self.activate_button = self.app._button(row, "Activate", self.activate_selected, primary=True)
        self.activate_button.pack(side="left", padx=4)
        self.app._button(row, "Deactivate AI", self.deactivate).pack(side="left", padx=4)

        self.status = tk.Label(panel, text="No AI model active", bg=PANEL, fg=MUTED, justify="left", wraplength=900)
        self.status.pack(anchor="w", padx=14, pady=(0, 12))

    def refresh_all(self) -> None:
        self._original_refresh_models()
        self.refresh_catalog()

    def refresh_catalog(self) -> None:
        models = [model for model in self.app.ai_registry.scan() if model.executable and model.manifest_path]
        self._model_by_label.clear()
        labels: list[str] = []
        for index, model in enumerate(models, start=1):
            label = f"{model.name} · {model.schema}"
            if label in self._model_by_label:
                label = f"{label} #{index}"
            labels.append(label)
            self._model_by_label[label] = model
        self.combo["values"] = labels
        if labels and self.selected.get() not in self._model_by_label:
            self.selected.set(labels[0])
        elif not labels:
            self.selected.set("")
        self._sync_status()

    def _sync_status(self) -> None:
        converter = self.app.engine.voice_converter
        if converter.config.enabled and converter.ready:
            adapter = converter.adapter
            name = getattr(adapter, "model_name", "validated model")
            self.status.configure(text=f"Active: {name}", fg=GOOD)
        elif self._loading:
            self.status.configure(text="Validating and loading model…", fg=MUTED)
        else:
            self.status.configure(text="No AI model active", fg=MUTED)

    def activate_selected(self) -> None:
        if self._loading:
            return
        if self.app.engine.last_status == "Running":
            messagebox.showinfo(
                "Change AI model",
                "Stop the OxShift engine before activating or changing an AI model.",
                parent=self.app.root,
            )
            return
        model = self._model_by_label.get(self.selected.get())
        if model is None:
            messagebox.showinfo(
                "Validated AI model",
                "Import a validated oxshift-model.json bundle first.",
                parent=self.app.root,
            )
            return

        self._loading = True
        self.activate_button.configure(state="disabled", text="Loading…")
        self._sync_status()
        manifest_path = model.manifest_path
        active_rate = self.app.profiles.active.sample_rate

        def worker() -> None:
            try:
                adapter = ValidatedStreamingOnnxAdapter.from_manifest(manifest_path)
                if adapter.sample_rate != active_rate:
                    adapter.close()
                    raise ValueError(
                        f"model is {adapter.sample_rate} Hz but active profile is {active_rate} Hz; "
                        "OxShift Alpha does not silently resample AI models"
                    )
                self.app.root.after(0, lambda: self._finish_activation(adapter, None))
            except Exception as exc:
                self.app.root.after(0, lambda: self._finish_activation(None, str(exc)))

        Thread(target=worker, name="OxShiftModelLoad", daemon=True).start()

    def _finish_activation(self, adapter, error: str | None) -> None:
        self._loading = False
        try:
            self.activate_button.configure(state="normal", text="Activate")
        except tk.TclError:
            if adapter is not None:
                adapter.close()
            return
        if error:
            self.status.configure(text=f"Model rejected: {error}", fg=WARN)
            return
        if self.app.engine.last_status == "Running":
            adapter.close()
            self.status.configure(text="Model was loaded but engine started before activation; stopped for safety.", fg=WARN)
            return

        converter = self.app.engine.voice_converter
        converter.stop()
        converter.adapter = adapter
        converter.config.enabled = True
        self._sync_status()
        if hasattr(self.app, "home_notice"):
            self.app.home_notice.configure(text="Validated local AI model activated. Start the engine to use it.", fg=GOOD)

    def deactivate(self) -> None:
        if self.app.engine.last_status == "Running":
            messagebox.showinfo(
                "Deactivate AI",
                "Stop the OxShift engine before deactivating its AI model.",
                parent=self.app.root,
            )
            return
        converter = self.app.engine.voice_converter
        converter.config.enabled = False
        converter.stop()
        converter.adapter = None
        self._sync_status()
        if hasattr(self.app, "home_notice"):
            self.app.home_notice.configure(text="AI model deactivated; local DSP remains available.", fg=GOOD)


def install_ai_product_controls(app) -> AIProductControls:
    controls = AIProductControls(app)
    app.ai_product_controls = controls
    return controls
