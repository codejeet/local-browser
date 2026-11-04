# Chrome Web Store reviewer instructions

Local Browser lets a user connect their own agent to their existing Chrome profile. No developer account or paid service is needed. The extension starts disconnected; the reviewer creates a private local relay and pairs it. The same relay supports the command-line client and the MCP tool.

## Run the relay

On Linux, macOS or WSL with Python 3.11+:

```bash
git clone https://github.com/codejeet/local-browser.git
cd local-browser
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Install the submitted extension. Open its popup and expand **Extension ID**. Use that exact 32-character ID below, since Chrome's signed store ID differs from a locally loaded package:

```bash
python setup.py --config "$PWD/reviewer-private/config.json" \
  --relay-url ws://127.0.0.1:18210/extension \
  --extension-id REPLACE_WITH_INSTALLED_EXTENSION_ID
python relay.py --config "$PWD/reviewer-private/config.json"
```

Keep the relay running. In the extension popup, import `reviewer-private/pairing.json` and click **Connect my agent**. The popup explains the browser access and data flow before connecting. Confirm **Connected to your agent**. In Chrome extension Details, enable **Allow User Scripts** for custom JavaScript (Chrome 138+; Chrome 135–137 uses Developer mode).

The generated pairing token belongs to this reviewer setup. It is never a shared developer credential. Python services can run in WSL with Windows Chrome when localhost forwarding is enabled. For separate computers, follow the README's private Tailscale WSS setup.

## Exercise the extension without a model account

Open a second shell in the same repository:

```bash
source .venv/bin/activate
export HERMES_LOCAL_BROWSER_CONFIG="$PWD/reviewer-private/config.json"
python client.py status
python client.py call open --params '{"url":"http://127.0.0.1:18210/fixture"}'
```

Use the returned tab ID in place of `123`:

```bash
python client.py call snapshot --params '{"tabId":123}'
python client.py call fill --params '{"tabId":123,"selector":"#name","value":"Browser connected"}'
python client.py call click --params '{"tabId":123,"selector":"#apply"}'
python client.py call eval --params '{"tabId":123,"code":"document.querySelector(\"#result\").textContent"}'
python client.py call activate --params '{"tabId":123}'
python client.py call screenshot --params '{"tabId":123}' --output /tmp/local-browser-review.png
```

The page and JavaScript result show **Browser connected**. The PNG shows that page. Click **Pause** in the popup; status becomes disconnected and new commands fail with Extension not connected. **Resume** reconnects. **Connection settings → Forget connection** removes the saved pairing. Close only the fixture tab after testing.

## Exercise MCP

Use any MCP client with this stdio entry, substituting the absolute repository path:

```json
{
  "mcpServers": {
    "local-browser": {
      "command": "/absolute/path/local-browser/.venv/bin/python",
      "args": ["/absolute/path/local-browser/mcp_server.py"],
      "env": {
        "HERMES_LOCAL_BROWSER_CONFIG": "/absolute/path/local-browser/reviewer-private/config.json"
      }
    }
  }
}
```

The `local_browser` tool accepts `action`, `params` and `timeout`. The CLI commands above exercise the same relay/extension action implementation. An MCP client can call `status`, `tabs`, `snapshot`, `fill`, `click`, `eval` and `screenshot` on the fixture tab. No model API key is required by the extension, relay or MCP server.

## Code map

- `background.js`: credential storage, authenticated WebSocket connection, status and pause controls.
- `connection-config.js`: relay URL validation; remote hosts require WSS, plaintext is loopback-only.
- `actions.js`: bundled browser/DOM actions. Custom page JavaScript uses `chrome.userScripts.execute`, never a remote script import or eval in the extension context.
- `gate.js`: prevents expired, duplicate or paused commands from running.
- `popup.html`, `popup.css`, `popup.js`: pairing, disclosure, connection and script settings UI.

The relay checks the exact configured extension origin and an independent pairing token. Its operator endpoint uses a separate token and rejects browser-origin requests. Remote connections can use a user-configured private WSS endpoint; the developer supplies no runtime endpoint.
