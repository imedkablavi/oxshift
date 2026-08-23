import unittest

from voxshift.__main__ import build_parser


class MainCliTests(unittest.TestCase):
    def test_validated_model_activation_is_explicit(self):
        args = build_parser().parse_args(["--model-manifest", "/tmp/bundle/oxshift-model.json"])
        self.assertTrue(args.model_manifest.endswith("oxshift-model.json"))
        self.assertEqual(args.onnx_provider, "")

    def test_provider_can_be_selected_explicitly(self):
        args = build_parser().parse_args([
            "--model-manifest", "oxshift-model.json",
            "--onnx-provider", "CPUExecutionProvider",
        ])
        self.assertEqual(args.onnx_provider, "CPUExecutionProvider")


if __name__ == "__main__":
    unittest.main()
