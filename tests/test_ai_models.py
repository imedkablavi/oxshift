from pathlib import Path
import tempfile
import unittest

from voxshift.ai_models import AIModelRegistry


class AIModelRegistryTests(unittest.TestCase):
    def test_import_and_scan_local_models(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "models"
            source = Path(temp) / "voice.onnx"
            index = Path(temp) / "voice.index"
            source.write_bytes(b"placeholder")
            index.write_bytes(b"placeholder")

            registry = AIModelRegistry(root=root)
            imported = registry.import_files([str(source), str(index)])
            self.assertEqual(len(imported), 2)

            models = registry.scan()
            self.assertEqual(len(models), 1)
            self.assertEqual(models[0].name, "voice")
            self.assertTrue(models[0].model_path.endswith("voice.onnx"))
            self.assertTrue(models[0].index_path.endswith("voice.index"))

    def test_duplicate_import_renames_safely(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "models"
            source = Path(temp) / "voice.pth"
            source.write_bytes(b"placeholder")
            registry = AIModelRegistry(root=root)
            registry.import_files([str(source)])
            second = registry.import_files([str(source)])
            self.assertEqual(second[0].name, "voice-2.pth")


if __name__ == "__main__":
    unittest.main()
