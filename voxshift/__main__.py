from __future__ import annotations

import argparse
import tkinter as tk
from tkinter import messagebox

from .alpha_ui import OxShiftAlphaUI
from .rvc_adapters import ValidatedStreamingOnnxAdapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OxShift local-first realtime voice studio")
    parser.add_argument(
        "--model-manifest",
        default="",
        help="activate one validated oxshift-model.json bundle (never accepts a raw model path)",
    )
    parser.add_argument(
        "--onnx-provider",
        default="",
        help="optional ONNX Runtime provider for a validated bundle, e.g. CPUExecutionProvider",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = tk.Tk()
    app = OxShiftAlphaUI(root)

    if args.model_manifest:
        try:
            # Manifest/checksum/schema/graph validation happens here on the UI/startup thread,
            # never inside PortAudio's realtime callback. Actual convert() calls run on the
            # RealtimeVoiceConverter worker once the audio engine starts.
            adapter = ValidatedStreamingOnnxAdapter.from_manifest(
                args.model_manifest,
                provider=args.onnx_provider or None,
            )
            if adapter.sample_rate != app.profiles.active.sample_rate:
                adapter.close()
                raise ValueError(
                    f"validated model is {adapter.sample_rate} Hz but active profile is "
                    f"{app.profiles.active.sample_rate} Hz; Alpha does not silently resample AI models"
                )
            app.engine.voice_converter.adapter = adapter
            app.engine.voice_converter.config.enabled = True
        except Exception as exc:
            messagebox.showerror(
                "Validated model rejected",
                f"OxShift did not activate the requested model.\n\n{exc}",
                parent=root,
            )

    root.mainloop()


if __name__ == "__main__":
    main()
