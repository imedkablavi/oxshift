from __future__ import annotations

import argparse
import tkinter as tk
from tkinter import messagebox

from .ai_product_controls import install_ai_product_controls
from .collection_paging import install_collection_paging
from .product_extras import install_product_extras
from .product_ui import OxShiftProductUI
from .profile_extras import install_profile_templates
from .runtime_controls import install_runtime_controls
from .rvc_adapters import ValidatedStreamingOnnxAdapter
from .support_ui import install_support_ui


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
    app = OxShiftProductUI(root)
    install_product_extras(app)
    install_profile_templates(app)
    install_collection_paging(app)
    install_runtime_controls(app)
    install_ai_product_controls(app)
    install_support_ui(app)

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
            if hasattr(app, "ai_product_controls"):
                app.ai_product_controls._sync_status()
        except Exception as exc:
            messagebox.showerror(
                "Validated model rejected",
                f"OxShift did not activate the requested model.\n\n{exc}",
                parent=root,
            )

    root.mainloop()


if __name__ == "__main__":
    main()
