"""Bootstrap tests use disposable release copies and never the real user config."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release = self.root / 'release'
        (self.release / 'extension').mkdir(parents=True)
        for name in ('setup.py', 'browser_config.py'):
            if (ROOT / name).exists():
                shutil.copy(ROOT / name, self.release / name)
        shutil.copy(ROOT / 'extension/manifest.json', self.release / 'extension/manifest.json')
        self.env = {**os.environ, 'HOME': str(self.root / 'home'), 'HERMES_HOME': str(self.root / 'hermes')}
        self.env.pop('HERMES_LOCAL_BROWSER_CONFIG', None)
        self.config = self.root / 'hermes/local-browser/config.json'
        self.connection = self.release / 'extension/connection.js'

    def run_setup(self, *args, success=True):
        result = subprocess.run([sys.executable, str(self.release / 'setup.py'), *args],
                                env=self.env, cwd=self.root, text=True, capture_output=True, timeout=10)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def fresh(self, *args):
        return self.run_setup('--relay-url', 'ws://127.0.0.1:18210/extension', *args)

    def connection_data(self):
        text = self.connection.read_text()
        return json.loads(text.split('Object.freeze(', 1)[1].split(');', 1)[0])

    def test_fresh_config_identity_private_files_and_no_token_output(self):
        result = self.fresh()
        config = json.loads(self.config.read_text())
        manifest = json.loads((self.release / 'extension/manifest.json').read_text())
        digest = hashlib.sha256(base64.b64decode(manifest['key'])).hexdigest()[:32]
        expected = ''.join(chr(ord('a') + int(c, 16)) for c in digest)
        self.assertEqual(config['extension_id'], expected)
        self.assertEqual(config['port'], 18210)
        self.assertEqual(self.connection_data(), {'url': 'ws://127.0.0.1:18210/extension', 'token': config['extension_token']})
        self.assertNotEqual(config['extension_token'], config['operator_token'])
        for key in ('extension_token', 'operator_token'):
            self.assertGreaterEqual(len(config[key]), 43)
            self.assertNotIn(config[key], result.stdout + result.stderr)
        for path in (self.config, self.connection):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.config.parent.stat().st_mode), 0o700)

    def test_rerun_preserves_tokens_extra_fields_and_port_updates_url(self):
        self.fresh('--port', '19321')
        config = json.loads(self.config.read_text())
        config['custom_setting'] = {'keep': True}
        self.config.write_text(json.dumps(config))
        self.config.chmod(0o644)
        self.connection.chmod(0o644)
        self.run_setup('--relay-url', 'wss://relay.example.com/extension')
        updated = json.loads(self.config.read_text())
        for key in ('extension_token', 'operator_token', 'custom_setting', 'port'):
            self.assertEqual(updated[key], config[key])
        self.assertEqual(self.connection_data()['url'], 'wss://relay.example.com/extension')
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.connection.stat().st_mode), 0o600)
        self.fresh('--port', '19322')
        self.assertEqual(json.loads(self.config.read_text())['port'], 19322)

    def test_default_home_and_environment_and_cli_config_precedence(self):
        self.env.pop('HERMES_HOME')
        self.fresh()
        self.assertTrue((self.root / 'home/.hermes/local-browser/config.json').exists())
        self.env['HERMES_LOCAL_BROWSER_CONFIG'] = str(self.root / 'env/config.json')
        self.fresh()
        self.assertTrue((self.root / 'env/config.json').exists())
        explicit = self.root / 'explicit/config.json'
        self.fresh('--config', str(explicit))
        self.assertTrue(explicit.exists())

    def test_validation_rejects_unsafe_or_invalid_urls_before_writes(self):
        for url in ('ws://example.com/extension', 'http://localhost/extension',
                    'https://example.com/extension', 'wss:///extension',
                    'wss://user:pass@example.com/extension', 'ws://127.0.0.1.evil/extension',
                    'ws://0.0.0.0/extension', 'wss://example.com/extension?token=secret',
                    'wss://example.com/extension#fragment', 'wss://example.com:99999/extension',
                    'wss://example.com/wrong', 'wss://exa mple.com/extension'):
            with self.subTest(url=url):
                self.run_setup('--relay-url', url, success=False)
                self.assertFalse(self.config.exists())
                self.assertFalse(self.connection.exists())

    def test_loopback_and_secure_remote_urls(self):
        for url in ('ws://localhost:18210/extension', 'ws://[::1]:18210/extension',
                    'wss://relay.example.com/browser/extension'):
            self.run_setup('--relay-url', url)
            self.assertEqual(self.connection_data()['url'], url)

    def test_bad_ports_leave_no_files(self):
        for port in ('0', '65536', 'abc', '-1'):
            self.run_setup('--relay-url', 'ws://localhost/extension', '--port', port, success=False)
            self.assertFalse(self.config.exists())

    def test_unrelated_invalid_and_mismatched_configs_are_not_overwritten(self):
        self.config.parent.mkdir(parents=True)
        for contents in ('{}', '{"mcp_servers":{}}', '[]', '{bad',
                         json.dumps({'extension_token': 'short', 'operator_token': 'short', 'extension_id': 'a'*32})):
            self.config.write_text(contents)
            self.run_setup('--relay-url', 'ws://localhost/extension', success=False)
            self.assertEqual(self.config.read_text(), contents)
            self.assertFalse(self.connection.exists())
        self.config.unlink()
        self.fresh()
        config = json.loads(self.config.read_text())
        config['extension_id'] = 'a' * 32
        self.config.write_text(json.dumps(config))
        before = self.config.read_bytes(), self.connection.read_bytes()
        self.run_setup('--relay-url', 'ws://localhost/extension', success=False)
        self.assertEqual(before, (self.config.read_bytes(), self.connection.read_bytes()))

    def test_existing_shared_or_invalid_tokens_are_rejected(self):
        self.fresh()
        config = json.loads(self.config.read_text())
        for value in ('short', config['operator_token'], None):
            bad = {**config, 'extension_token': value}
            self.config.write_text(json.dumps(bad))
            before = self.config.read_bytes()
            self.run_setup('--relay-url', 'ws://localhost/extension', success=False)
            self.assertEqual(before, self.config.read_bytes())

    @unittest.skipUnless(os.name == 'posix', 'POSIX symlinks')
    def test_symlink_targets_are_refused_without_touching_target(self):
        target = self.root / 'unrelated'
        target.write_text('unchanged')
        self.config.parent.mkdir(parents=True)
        self.config.symlink_to(target)
        self.run_setup('--relay-url', 'ws://localhost/extension', success=False)
        self.assertEqual(target.read_text(), 'unchanged')
        self.config.unlink()
        self.connection.symlink_to(target)
        self.run_setup('--relay-url', 'ws://localhost/extension', success=False)
        self.assertEqual(target.read_text(), 'unchanged')
        self.assertFalse(self.config.exists())

    def test_runtime_config_and_cache_follow_environment(self):
        import relay
        import client
        self.fresh()
        with patch.dict(os.environ, {'HERMES_HOME': str(self.root / 'hermes'),
                                    'HERMES_LOCAL_BROWSER_CONFIG': str(self.config)}):
            self.assertEqual(relay.load_config()['extension_id'], json.loads(self.config.read_text())['extension_id'])
            screenshot = client.save_screenshot('iVBORw0KGgo=')
            self.assertEqual(Path(screenshot).parent, self.config.parent / 'cache')


if __name__ == '__main__':
    unittest.main()
