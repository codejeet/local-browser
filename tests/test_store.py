import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('store_build', ROOT / 'scripts/build-store.py')
assert spec is not None and spec.loader is not None
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class StorePackageTests(unittest.TestCase):
    def test_store_package_is_reproducible_and_has_no_private_state(self):
        with tempfile.TemporaryDirectory() as directory:
            first = build.build(Path(directory) / 'first.zip')
            second = build.build(Path(directory) / 'second.zip')
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()), set(build.FILES))
                self.assertNotIn('connection.js', archive.namelist())
                manifest = json.loads(archive.read('manifest.json'))
                self.assertNotIn('key', manifest)
                self.assertNotIn('debugger', manifest['permissions'])
                self.assertIn('userScripts', manifest['permissions'])
                self.assertLessEqual(len(manifest['description']), 132)
                for icon in manifest['icons'].values():
                    self.assertIn(icon, archive.namelist())
                self.assertIn('chrome.userScripts.execute', archive.read('actions.js').decode())
                self.assertNotIn("importScripts('connection.js')", archive.read('background.js').decode())
                self.assertEqual(archive.read('connection-config.js'), (ROOT / 'extension/connection-config.js').read_bytes())


if __name__ == '__main__':
    unittest.main()
