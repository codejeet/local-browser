"""CLI and async client for the owner's local Chrome bridge. Never retries commands."""
import argparse
import asyncio
import base64
import binascii
import json
import os
from pathlib import Path
import sys
import tempfile

import aiohttp

from relay import ACTIONS, MAX_JSON_BYTES, MAX_TIMEOUT, load_config
from browser_config import cache_path

CACHE_DIR = cache_path()


class BridgeError(RuntimeError):
    """Action or transport failure with no automatic retry."""


async def request(action, params=None, timeout=30, *, config_path=None):
    """Return an action result, or relay connection status for action='status'."""
    if not isinstance(action, str) or action not in ACTIONS:
        raise BridgeError('Unsupported action')
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise BridgeError('params must be a JSON object')
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not 0 < timeout <= MAX_TIMEOUT):
        raise BridgeError('timeout must be greater than 0 and at most 120 seconds')
    try:
        config = load_config(config_path)
    except (OSError, ValueError, TypeError):
        raise BridgeError('Unable to read valid local browser configuration') from None
    url = f"http://127.0.0.1:{config['port']}"
    headers = {'Authorization': 'Bearer ' + config['operator_token']}
    try:
        payload = json.dumps({'action': action, 'params': params, 'timeout': timeout}, allow_nan=False)
    except (ValueError, TypeError):
        raise BridgeError('params must contain JSON values') from None
    if len(payload.encode()) > MAX_JSON_BYTES:
        raise BridgeError('Command too large')
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout + 5), trust_env=False) as session:
            kwargs = {'headers': headers, 'allow_redirects': False}
            if action == 'status':
                method, endpoint = 'GET', '/status'
            else:
                method, endpoint = 'POST', '/command'
                kwargs['data'] = payload
                headers['Content-Type'] = 'application/json'
            async with session.request(method, url + endpoint, **kwargs) as response:
                raw = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    raw.extend(chunk)
                    if len(raw) > MAX_JSON_BYTES:
                        raise BridgeError('Relay response too large')
                try:
                    data = json.loads(raw)
                except (ValueError, UnicodeError):
                    raise BridgeError(f'Relay HTTP {response.status}: invalid response') from None
                if not isinstance(data, dict):
                    raise BridgeError('Invalid relay response')
                if response.status != 200 or data.get('ok') is False:
                    raise BridgeError(data.get('error', f'Relay HTTP {response.status}'))
                if action == 'status':
                    return data
                if data.get('ok') is not True or 'result' not in data:
                    raise BridgeError('Invalid relay action response')
                return data['result']
    except (aiohttp.ClientError, asyncio.TimeoutError):
        raise BridgeError('Relay unavailable or transport timed out; command outcome may be unknown. No automatic retry.') from None


def screenshot_bytes(result):
    value = result
    if isinstance(result, dict):
        value = result.get('dataUrl') or result.get('data_url') or result.get('base64')
    if not isinstance(value, str):
        raise BridgeError('Screenshot result has no PNG data')
    if value.startswith('data:'):
        if not value.startswith('data:image/png;base64,'):
            raise BridgeError('Screenshot must be a PNG')
        value = value.partition(',')[2]
    if len(value) > MAX_JSON_BYTES:
        raise BridgeError('Screenshot too large')
    try:
        image = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise BridgeError('Invalid screenshot encoding') from None
    if not image.startswith(b'\x89PNG\r\n\x1a\n'):
        raise BridgeError('Screenshot must be a PNG')
    return image


def write_private(path, content):
    path = Path(path).expanduser().absolute()
    # Refuse symlink targets, and make permissions private before writing contents.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(content)
    return str(path)


def save_screenshot(result, *, cache_dir=None):
    image = screenshot_bytes(result)
    directory = Path(cache_dir if cache_dir is not None else cache_path()).expanduser().absolute()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    fd, path = tempfile.mkstemp(prefix='screenshot-', suffix='.png', dir=directory)
    with os.fdopen(fd, 'wb') as output:
        output.write(image)
    return path


async def run_cli(args):
    try:
        params = json.loads(args.params) if args.command == 'call' else {}
        action = args.action if args.command == 'call' else 'status'
        result = await request(action, params, getattr(args, 'timeout', 30), config_path=args.config)
        if args.output:
            if action == 'screenshot' and Path(args.output).suffix.lower() != '.json':
                path = write_private(args.output, screenshot_bytes(result))
            else:
                path = write_private(args.output, (json.dumps(result, indent=2, ensure_ascii=False) + '\n').encode())
            print(json.dumps({'path': path}))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (BridgeError, ValueError, OSError) as exc:
        # Errors are delivered to the caller, never logged with browser results/tokens.
        print(json.dumps({'ok': False, 'error': str(exc)}), file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=None)
    sub = parser.add_subparsers(dest='command', required=True)
    status = sub.add_parser('status', help='Relay connection status')
    status.add_argument('--output', type=Path)
    call = sub.add_parser('call', help='Execute one browser action')
    call.add_argument('action', choices=sorted(ACTIONS))
    call.add_argument('--params', default='{}', help='JSON object')
    call.add_argument('--timeout', type=float, default=30)
    call.add_argument('--output', type=Path, help='JSON file, or decoded PNG for screenshot (unless .json)')
    return asyncio.run(run_cli(parser.parse_args()))


if __name__ == '__main__':
    sys.exit(main())
