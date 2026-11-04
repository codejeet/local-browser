"""Local HTTP/WS integration tests; the WS peer is a protocol fixture."""
import asyncio
import base64
import json
import io
import os
import sys
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from aiohttp import WSMsgType, WSServerHandshakeError
from aiohttp.test_utils import TestClient, TestServer

from relay import create_app, load_config, MAX_JSON_BYTES

CONFIG = {"extension_token": "extension-test-secret", "operator_token": "operator-test-secret",
          "extension_id": "a" * 32, "port": 18210}
AUTH = {"Authorization": "Bearer " + CONFIG["operator_token"]}
ORIGIN = "chrome-extension://" + CONFIG["extension_id"]


class RelayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.http = TestClient(TestServer(create_app(CONFIG, hello_timeout=0.08, max_pending=2)))
        await self.http.start_server()
        self.sockets = []

    async def asyncTearDown(self):
        for ws in self.sockets:
            await ws.close()
        await self.http.close()

    async def connect(self):
        ws = await self.http.ws_connect('/extension', origin=ORIGIN)
        self.sockets.append(ws)
        await ws.send_json({"type": "hello", "token": CONFIG['extension_token'],
                            "client": "Local Chrome", "version": "1.0.0"})
        self.assertEqual(await ws.receive_json(), {"type": "welcome"})
        return ws

    async def command(self, action='tabs', params=None, timeout: float = 1):
        return await self.http.post('/command', headers=AUTH,
                                    json={"action": action, "params": params or {}, "timeout": timeout})

    async def test_auth_and_origin(self):
        for path in ('/status', '/command'):
            method = self.http.get if path == '/status' else self.http.post
            self.assertEqual((await method(path)).status, 401)
            self.assertEqual((await method(path, headers={"Authorization": "Bearer wrong"})).status, 401)
            self.assertEqual((await method(path, headers={**AUTH, "Origin": ORIGIN})).status, 403)
        for origin in ('https://evil.example', 'chrome-extension://' + 'b' * 32, None):
            with self.assertRaises(WSServerHandshakeError) as caught:
                await self.http.ws_connect('/extension', origin=origin)
            self.assertEqual(caught.exception.status, 403)

    async def test_hello_auth_and_deadline(self):
        ws = await self.http.ws_connect('/extension', origin=ORIGIN)
        await ws.send_json({"type": "hello", "token": "wrong", "client": "Local Chrome", "version": "1.0.0"})
        self.assertEqual((await ws.receive()).type, WSMsgType.CLOSE)
        await ws.close()
        ws = await self.http.ws_connect('/extension', origin=ORIGIN)
        self.assertEqual((await asyncio.wait_for(ws.receive(), 1)).type, WSMsgType.CLOSE)
        await ws.close()
        await self.connect()

    async def test_status_roundtrip_ping_fixture(self):
        response = await self.http.get('/status', headers=AUTH)
        self.assertEqual(await response.json(), {"connected": False, "last_seen": None, "client": None})
        ws = await self.connect()
        await ws.send_json({"type": "ping"})
        self.assertEqual(await ws.receive_json(), {"type": "pong"})
        status = await (await self.http.get('/status', headers=AUTH)).json()
        self.assertTrue(status['connected'])
        self.assertEqual(status['client'], 'Local Chrome')
        self.assertIsInstance(status['last_seen'], float)
        task = asyncio.create_task(self.command('snapshot', {"tabId": 12}))
        command = await ws.receive_json()
        self.assertEqual(command['action'], 'snapshot')
        self.assertEqual(command['params'], {"tabId": 12})
        self.assertTrue(time.time() * 1000 < command['deadline'] < (time.time() + 2) * 1000)
        await ws.send_json({"id": command['id'], "ok": True, "result": {"title": "fixture"}})
        response = await task
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())['result'], {"title": "fixture"})
        fixture = await self.http.get('/fixture')
        html = await fixture.text()
        for text in ('Hermes Browser Test', 'id="name"', 'id="apply"', 'id="result"', 'textContent', '3000px'):
            self.assertIn(text, html)
        self.assertNotIn('Access-Control-Allow-Origin', fixture.headers)
        for path in ('/config.json', '/.hermes/local-browser/config.json', '/relay.py'):
            self.assertEqual((await self.http.get(path)).status, 404)

    async def test_duplicate_does_not_replace_live_connection(self):
        ws = await self.connect()
        with self.assertRaises(WSServerHandshakeError) as caught:
            await self.http.ws_connect('/extension', origin=ORIGIN)
        self.assertEqual(caught.exception.status, 409)
        await ws.send_json({"type": "ping"})
        self.assertEqual(await ws.receive_json(), {"type": "pong"})

    async def test_timeout_stale_response_and_no_retry(self):
        ws = await self.connect()
        task = asyncio.create_task(self.command('click', timeout=0.03))
        first = await ws.receive_json()
        response = await task
        self.assertEqual(response.status, 504)
        await ws.send_json({"id": first['id'], "ok": True, "result": "late"})
        task = asyncio.create_task(self.command())
        second = await ws.receive_json()
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(second['action'], 'tabs')
        await ws.send_json({"id": first['id'], "ok": True, "result": "stale"})
        await ws.send_json({"id": second['id'], "ok": True, "result": []})
        self.assertEqual((await (await task).json())['result'], [])

    async def test_disconnect_fails_pending_and_reconnect_is_clean(self):
        ws = await self.connect()
        task = asyncio.create_task(self.command(timeout=30))
        await ws.receive_json()
        await ws.close()
        response = await asyncio.wait_for(task, 1)
        self.assertEqual(response.status, 503)
        self.assertEqual((await self.command()).status, 503)
        await self.connect()

    async def test_pending_limit_and_extension_error(self):
        ws = await self.connect()
        tasks = [asyncio.create_task(self.command()) for _ in range(2)]
        messages = [await ws.receive_json(), await ws.receive_json()]
        self.assertEqual((await self.command()).status, 429)
        for message in messages:
            await ws.send_json({"id": message['id'], "ok": False, "error": "No matching element"})
        for task in tasks:
            response = await task
            self.assertEqual(response.status, 502)
            self.assertEqual((await response.json())['error'], 'No matching element')

    async def test_input_validation_and_size(self):
        for body in ([], {"action": "shell", "params": {}}, {"action": "tabs", "params": []},
                     {"action": "tabs", "params": {}, "timeout": -1},
                     {"action": "tabs", "params": {}, "timeout": 121},
                     {"action": "tabs", "params": {}, "timeout": True}):
            response = await self.http.post('/command', headers=AUTH, json=body)
            self.assertEqual(response.status, 400)
        response = await self.http.post('/command', headers=AUTH, data='{')
        self.assertEqual(response.status, 400)
        response = await self.http.post('/command', headers=AUTH, data=io.BytesIO(b'x' * (MAX_JSON_BYTES + 1)))
        self.assertEqual(response.status, 413)
    async def test_client_request_cli_and_private_screenshot(self):
        from client import request, save_screenshot, BridgeError
        ws = await self.connect()
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / 'config.json'
            config_path.write_text(json.dumps({**CONFIG, 'port': self.http.server.port}))
            status = await request('status', {}, config_path=config_path)
            self.assertTrue(status['connected'])
            task = asyncio.create_task(request('tabs', {}, config_path=config_path))
            message = await ws.receive_json()
            await ws.send_json({'id': message['id'], 'ok': True, 'result': [{'id': 8}]})
            self.assertEqual(await task, [{'id': 8}])
            task = asyncio.create_task(request('click', {}, 0.02, config_path=config_path))
            await ws.receive_json()
            with self.assertRaisesRegex(BridgeError, 'timed out'):
                await task
            png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5xkAAAAASUVORK5CYII=')
            path = save_screenshot({'dataUrl': 'data:image/png;base64,' + base64.b64encode(png).decode()}, cache_dir=Path(temp) / 'cache')
            self.assertTrue(Path(path).is_absolute())
            self.assertEqual(Path(path).read_bytes(), png)
            self.assertEqual(Path(path).stat().st_mode & 0o777, 0o600)
            self.assertEqual(Path(path).parent.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(BridgeError):
                save_screenshot({'dataUrl': 'data:text/html;base64,PHNjcmlwdD4='}, cache_dir=Path(temp) / 'cache')
            output = Path(temp) / 'status.json'
            proc = await asyncio.create_subprocess_exec(sys.executable, 'client.py', '--config', str(config_path),
                                                       'status', '--output', str(output), stdout=asyncio.subprocess.PIPE,
                                                       stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            self.assertEqual(proc.returncode, 0, stderr.decode())
            self.assertTrue(json.loads(output.read_text())['connected'])
            proc = await asyncio.create_subprocess_exec(sys.executable, 'client.py', '--config', str(config_path),
                                                       'call', 'screenshot', '--params', '{"tabId":8}',
                                                       '--output', str(Path(temp) / 'shot.png'),
                                                       stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            message = await ws.receive_json()
            self.assertEqual(message['action'], 'screenshot')
            await ws.send_json({'id': message['id'], 'ok': True, 'result': {'dataUrl': 'data:image/png;base64,' + base64.b64encode(png).decode()}})
            stdout, stderr = await proc.communicate()
            self.assertEqual(proc.returncode, 0, stderr.decode())
            self.assertEqual((Path(temp) / 'shot.png').read_bytes(), png)

    async def test_malformed_websocket_and_oversize_fail_pending(self):
        ws = await self.connect()
        task = asyncio.create_task(self.command(timeout=30))
        await ws.receive_json()
        await ws.send_str('{')
        self.assertEqual((await ws.receive()).type, WSMsgType.CLOSE)
        self.assertEqual((await asyncio.wait_for(task, 1)).status, 503)
        await ws.close()
        ws = await self.connect()
        try:
            await ws.send_str('x' * (MAX_JSON_BYTES + 1))
        except ConnectionError:
            pass  # aiohttp can reject the frame header before its body finishes sending.
        message = await ws.receive()
        self.assertIn(message.type, (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR))
        await ws.close()
        status = await (await self.http.get('/status', headers=AUTH)).json()
        self.assertFalse(status['connected'])

    async def test_extreme_timeout_rejected_without_server_error(self):
        response = await self.command(timeout=10 ** 1000)
        self.assertEqual(response.status, 400)
        from client import request, BridgeError
        with self.assertRaises(BridgeError):
            await request('tabs', {}, 10 ** 1000)

    async def test_config_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'config.json'
            path.write_text(json.dumps(CONFIG))
            self.assertEqual(load_config(path), CONFIG)
            for bad in ({**CONFIG, 'port': True}, {**CONFIG, 'extension_id': '../bad'},
                        {**CONFIG, 'extension_token': ''}, []):
                path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    load_config(path)

    async def test_mcp_stdio_discovery_and_call(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        # Import deliberately ensures missing module gives the initial RED.
        import mcp_server
        self.assertEqual(mcp_server.mcp.settings.log_level, 'CRITICAL')
        ws = await self.connect()
        with tempfile.TemporaryDirectory() as temp:
            config_path = Path(temp) / 'config.json'
            config_path.write_text(json.dumps({**CONFIG, 'port': self.http.server.port}))
            from client import save_screenshot
            with patch.dict(os.environ, {'HERMES_LOCAL_BROWSER_CONFIG': str(config_path)}), \
                 patch.object(mcp_server, 'save_screenshot', side_effect=lambda result: save_screenshot(result, cache_dir=Path(temp) / 'cache')):
                task = asyncio.create_task(mcp_server.local_browser('screenshot', {'tabId': 8}))
                command = await ws.receive_json()
                await ws.send_json({'id': command['id'], 'ok': True, 'result': {'dataUrl': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5xkAAAAASUVORK5CYII='}})
                result = await task
                self.assertEqual(result['mimeType'], 'image/png')
                self.assertTrue(Path(result['path']).is_file())
            server = StdioServerParameters(command=sys.executable, args=[str(Path('mcp_server.py').resolve())],
                                          env={'HERMES_LOCAL_BROWSER_CONFIG': str(config_path)})
            async with stdio_client(server) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    self.assertEqual([tool.name for tool in tools], ['local_browser'])
                    description = tools[0].description
                    for phrase in ("the user's real local Chrome", 'explicit owner', 'activate', 'JavaScript expression', 'synthetic DOM', 'trusted OS'):
                        self.assertIn(phrase, description)
                    result = await session.call_tool('local_browser', {'action': 'status', 'params': {}})
                    self.assertFalse(result.isError)
                    self.assertTrue(json.loads(result.content[0].text)['connected'])


if __name__ == '__main__':
    unittest.main()
