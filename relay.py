"""Loopback-only authenticated HTTP to Chrome-extension WebSocket relay."""
import argparse
import asyncio
import hmac
import json
from pathlib import Path
import re
import time
import uuid

from aiohttp import web, WSMsgType

from browser_config import config_path

CONFIG_PATH = config_path()
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_TIMEOUT = 120
ACTIONS = frozenset('status tabs open navigate close activate snapshot html eval click fill scroll key screenshot frames'.split())


def load_config(path=None):
    config = json.loads(config_path(path).read_text())
    if not isinstance(config, dict):
        raise ValueError('Configuration must be an object')
    for name in ('extension_token', 'operator_token'):
        if not isinstance(config.get(name), str) or not config[name]:
            raise ValueError('Missing configuration token')
    if not re.fullmatch(r'[a-p]{32}', config.get('extension_id', '')):
        raise ValueError('Invalid extension_id')
    port = config.get('port', 18210)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('Invalid port')
    return {**config, 'port': port}


def same_secret(value, expected):
    return isinstance(value, str) and hmac.compare_digest(value.encode(), expected.encode())


def error(message, status):
    return web.json_response({'ok': False, 'error': message}, status=status)


class Relay:
    def __init__(self, config, hello_timeout=5, max_pending=32):
        self.config = config
        self.hello_timeout = hello_timeout
        self.max_pending = max_pending
        self.ws = None
        self.reserved = False
        self.last_seen = None
        self.client = None
        self.pending = {}

    def authorize(self, request):
        if 'Origin' in request.headers:
            raise web.HTTPForbidden(text='Browser-origin requests are forbidden')
        if not same_secret(request.headers.get('Authorization'), 'Bearer ' + self.config['operator_token']):
            raise web.HTTPUnauthorized(text='Unauthorized')

    async def status(self, request):
        self.authorize(request)
        return web.json_response({'connected': self.ws is not None and not self.ws.closed,
                                  'last_seen': self.last_seen, 'client': self.client})

    def fail_pending(self):
        for future in self.pending.values():
            if not future.done():
                future.set_result({'ok': False, 'error': 'Extension disconnected; command outcome may be unknown', '_http_status': 503})
        self.pending.clear()

    async def extension(self, request):
        if request.headers.get('Origin') != 'chrome-extension://' + self.config['extension_id']:
            raise web.HTTPForbidden(text='Invalid extension origin')
        if self.reserved:
            raise web.HTTPConflict(text='An extension is already connected')
        self.reserved = True
        ws = web.WebSocketResponse(max_msg_size=MAX_JSON_BYTES, compress=False, heartbeat=30)
        try:
            await ws.prepare(request)
            try:
                hello = await asyncio.wait_for(ws.receive_json(), self.hello_timeout)
            except (ValueError, TypeError, asyncio.TimeoutError):
                await ws.close(code=1008, message=b'Hello required')
                return ws
            if not (isinstance(hello, dict) and hello.get('type') == 'hello'
                    and same_secret(hello.get('token'), self.config['extension_token'])
                    and hello.get('client') == 'Local Chrome' and hello.get('version') == '1.0.0'):
                await ws.close(code=1008, message=b'Invalid hello')
                return ws
            self.ws = ws
            self.client = hello['client']
            self.last_seen = time.time()
            await ws.send_json({'type': 'welcome'})
            async for message in ws:
                if message.type != WSMsgType.TEXT:
                    if message.type == WSMsgType.BINARY:
                        await ws.close(code=1003, message=b'JSON text required')
                    break
                try:
                    data = json.loads(message.data)
                except (ValueError, TypeError):
                    await ws.close(code=1008, message=b'Invalid JSON')
                    break
                if not isinstance(data, dict):
                    await ws.close(code=1008, message=b'JSON object required')
                    break
                self.last_seen = time.time()
                if data.get('type') == 'ping':
                    await ws.send_json({'type': 'pong'})
                    continue
                command_id = data.get('id')
                if not isinstance(command_id, str):
                    continue
                future = self.pending.get(command_id)
                if future is None or future.done():
                    continue  # Late/duplicate/unknown responses never affect another command.
                if data.get('ok') is True and 'result' in data:
                    future.set_result({'id': command_id, 'ok': True, 'result': data['result']})
                elif data.get('ok') is False and isinstance(data.get('error'), str):
                    future.set_result({'id': command_id, 'ok': False, 'error': data['error']})
        finally:
            if self.ws is ws:
                self.ws = None
                self.client = None
                self.fail_pending()
            self.reserved = False
        return ws

    async def command(self, request):
        self.authorize(request)
        try:
            body = await request.json()
        except (ValueError, UnicodeError):
            return error('Invalid JSON', 400)
        if not isinstance(body, dict):
            return error('Expected a JSON object', 400)
        action, params, timeout = body.get('action'), body.get('params'), body.get('timeout', 30)
        if not isinstance(action, str) or action not in ACTIONS or not isinstance(params, dict):
            return error('Unsupported action or invalid params object', 400)
        if (isinstance(timeout, bool) or not isinstance(timeout, (float, int))
                or not 0 < timeout <= MAX_TIMEOUT):
            return error('timeout must be greater than 0 and at most 120 seconds', 400)
        ws = self.ws
        if ws is None or ws.closed:
            return error('Extension not connected', 503)
        if len(self.pending) >= self.max_pending:
            return error('Too many pending commands', 429)
        command_id = uuid.uuid4().hex
        message = {'id': command_id, 'action': action, 'params': params,
                   'deadline': int((time.time() + timeout) * 1000)}
        try:
            payload = json.dumps(message, allow_nan=False)
        except (ValueError, TypeError):
            return error('Invalid JSON values', 400)
        if len(payload.encode()) > MAX_JSON_BYTES:
            return error('Command too large', 413)
        future = asyncio.get_running_loop().create_future()
        self.pending[command_id] = future
        try:
            async with asyncio.timeout(timeout):
                await ws.send_str(payload)
                result = await future
            status = result.pop('_http_status', 200 if result['ok'] else 502)
            return web.json_response(result, status=status)
        except asyncio.TimeoutError:
            return error('Command timed out; outcome may be unknown. No automatic retry.', 504)
        except (ConnectionError, RuntimeError):
            return error('Extension disconnected; command outcome may be unknown', 503)
        finally:
            self.pending.pop(command_id, None)
            if not future.done():
                future.cancel()

    async def shutdown(self, app):
        self.fail_pending()
        if self.ws is not None:
            await self.ws.close(code=1001, message=b'Relay shutdown')


FIXTURE = '''<!doctype html><html><head><meta charset="utf-8"><title>Hermes Browser Test</title>
<style>body{font:20px sans-serif;min-height:3000px;padding:32px}input,button{font:inherit}#result{margin:20px 0}</style>
</head><body><h1>Hermes Browser Test</h1><label>Name <input id="name"></label>
<button id="apply">Apply</button><div id="result" role="status">Ready</div>
<script>document.getElementById('apply').addEventListener('click',()=>{
document.getElementById('result').textContent=document.getElementById('name').value;
});</script></body></html>'''


async def fixture(request):
    return web.Response(text=FIXTURE, content_type='text/html', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


def create_app(config=None, *, hello_timeout=5, max_pending=32):
    relay = Relay(config if config is not None else load_config(), hello_timeout, max_pending)
    app = web.Application(client_max_size=MAX_JSON_BYTES)
    app.router.add_get('/extension', relay.extension)
    app.router.add_get('/status', relay.status)
    app.router.add_post('/command', relay.command)
    app.router.add_get('/fixture', fixture)
    app.on_shutdown.append(relay.shutdown)
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    web.run_app(create_app(config), host='127.0.0.1', port=config['port'], access_log=None, print=None)


if __name__ == '__main__':
    main()
