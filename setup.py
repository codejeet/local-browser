#!/usr/bin/env python3
"""Configure the local Chrome bridge. This is a setup CLI, not a package installer."""
import argparse
import base64
import binascii
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
from urllib.parse import urlsplit
from typing import Any

from browser_config import config_path

ROOT = Path(__file__).resolve().parent


def extension_id(manifest_path):
    """Chrome IDs encode the first 128 bits of the public-key SHA-256 as a-p."""
    try:
        manifest = json.loads(Path(manifest_path).read_text())
        key = base64.b64decode(manifest['key'], validate=True)
        if not key:
            raise ValueError
    except (ValueError, KeyError, TypeError, binascii.Error):
        raise ValueError('Manifest must contain a valid public key') from None
    digest = hashlib.sha256(key).hexdigest()[:32]
    return ''.join(chr(ord('a') + int(char, 16)) for char in digest)


def validate_url(url):
    """Remote relays require TLS; plaintext WebSockets are loopback-only."""
    try:
        if not url or any(char.isspace() or ord(char) < 32 for char in url) or '\\' in url:
            raise ValueError
        parsed = urlsplit(url)
        host = parsed.hostname
        if (parsed.scheme not in ('ws', 'wss') or not host or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment
                or '?' in url or '#' in url or not parsed.path.endswith('/extension')):
            raise ValueError
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError
        # Validate literal addresses or DNS host labels without resolving the host.
        try:
            address = ipaddress.ip_address(host)
            loopback = address.is_loopback
        except ValueError:
            if not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                       for label in host.rstrip('.').split('.')):
                raise ValueError
            loopback = host.lower() in ('localhost', 'localhost.')
        if parsed.scheme == 'ws' and not loopback:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('Relay URL must use wss:// for remote hosts or ws:// for loopback, '
                         'end in /extension, and contain no credentials, query or fragment') from None
    return url


def validate_port(port):
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('Port must be an integer from 1 to 65535')
    return port


def check_target(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('Configuration targets must be regular files, not symlinks')


def write_private(path, text):
    """Atomically replace a file without ever writing credentials with public permissions."""
    check_target(path)
    # Only newly created directories get private modes; unrelated parents are untouched.
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            os.chmod(temporary, 0o600)
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        check_target(path)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def bootstrap(relay_url, *, config=None, port=None, root=ROOT):
    validate_url(relay_url)
    if port is not None:
        validate_port(port)
    path = config_path(config)
    connection = Path(root) / 'extension' / 'connection.js'
    check_target(path)
    check_target(connection)
    if path.resolve() == connection.resolve():
        raise ValueError('Config path must differ from extension/connection.js')
    identity = extension_id(Path(root) / 'extension' / 'manifest.json')
    values: dict[str, Any]
    if path.exists():
        try:
            values = json.loads(path.read_text())
        except (ValueError, UnicodeError):
            raise ValueError('Existing config is not valid JSON; it was left unchanged') from None
        if not isinstance(values, dict) or not {'extension_id', 'extension_token', 'operator_token'} <= values.keys():
            raise ValueError('Existing file is not a local-browser config; it was left unchanged')
        if values['extension_id'] != identity:
            raise ValueError('Existing config belongs to a different extension; it was left unchanged')
        for name in ('extension_token', 'operator_token'):
            token = values[name]
            if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,}', token):
                raise ValueError('Existing config has an invalid token; it was left unchanged')
        if secrets.compare_digest(values['extension_token'], values['operator_token']):
            raise ValueError('Extension and operator tokens must be independent; config was left unchanged')
        validate_port(values.get('port', 18210))
    else:
        values = {'extension_id': identity, 'extension_token': secrets.token_urlsafe(32),
                  'operator_token': secrets.token_urlsafe(32)}
    values['port'] = port if port is not None else values.get('port', 18210)
    values['relay_url'] = relay_url
    javascript = ('// Generated by setup.py. Contains a private token; do not share or commit.\n'
                  'const CONNECTION = Object.freeze(' + json.dumps({'url': relay_url,
                  'token': values['extension_token']}, ensure_ascii=True) + ');\n')
    write_private(path, json.dumps(values, indent=2) + '\n')
    write_private(connection, javascript)
    return path, connection, identity


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--relay-url', required=True, help='Extension WebSocket endpoint: loopback ws:// or remote wss://')
    parser.add_argument('--config', type=Path, help='Config path (overrides HERMES_LOCAL_BROWSER_CONFIG and HERMES_HOME)')
    parser.add_argument('--port', type=int, help='Loopback relay port (default: existing port, otherwise 18210)')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error('Python 3.11 or newer is required')
    try:
        path, connection, identity = bootstrap(args.relay_url, config=args.config, port=args.port)
    except ValueError as exc:
        parser.error(str(exc))
    except OSError:
        # Do not echo filesystem exception payloads or credential-bearing contents.
        parser.error('Unable to read or write setup files; check paths and permissions')
    print(f'Configuration: {path}\nExtension connection: {connection}\nExtension ID: {identity}')
    print('Setup complete. Credentials are stored privately and were not printed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
