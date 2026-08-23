import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from voxshift.model_validation import ModelValidationError, validate_bundle


class ModelValidationTests(unittest.TestCase):
    def _bundle(self, root: Path, **overrides):
        model = root / "model.onnx"
        model.write_bytes(b"safe-placeholder-graph")
        payload = {
            "name": "Test Voice",
            "schema": "oxshift-rvc-stream-v1",
            "version": 1,
            "sample_rate": 48000,
            "model": "model.onnx",
            "sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
        }
        payload.update(overrides)
        manifest = root / "oxshift-model.json"
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        return manifest

    def test_known_schema_and_checksum_validate_without_loading_graph(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = self._bundle(Path(temp))
            bundle = validate_bundle(manifest, inspect_graph=False)
            self.assertEqual(bundle.schema, "oxshift-rvc-stream-v1")
            self.assertEqual(bundle.sample_rate, 48000)
            self.assertEqual(bundle.model_path.name, "model.onnx")

    def test_unknown_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = self._bundle(Path(temp), schema="arbitrary-onnx")
            with self.assertRaisesRegex(ModelValidationError, "unsupported model schema"):
                validate_bundle(manifest, inspect_graph=False)

    def test_checksum_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = self._bundle(Path(temp), sha256="0" * 64)
            with self.assertRaisesRegex(ModelValidationError, "checksum"):
                validate_bundle(manifest, inspect_graph=False)

    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "bundle"
            root.mkdir()
            outside = Path(temp) / "model.onnx"
            outside.write_bytes(b"outside")
            manifest = self._bundle(root, model="../model.onnx", sha256=hashlib.sha256(outside.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ModelValidationError, "escapes bundle"):
                validate_bundle(manifest, inspect_graph=False)

    def test_unknown_manifest_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = self._bundle(Path(temp), command="run-me")
            with self.assertRaisesRegex(ModelValidationError, "unknown manifest fields"):
                validate_bundle(manifest, inspect_graph=False)


if __name__ == "__main__":
    unittest.main()
