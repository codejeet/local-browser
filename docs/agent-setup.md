# Agent setup guide

Use this guide when a user asks you to connect their existing Chrome browser to Local Browser. The goal is a working connection, verified on the included fixture page.

## Establish where each component runs

Read `README.md` and inspect the existing installation before changing anything.

- **Relay host:** Linux, macOS, or WSL with Python 3.11+. Run both `relay.py` and the MCP stdio process here.
- **Browser host:** The user's computer with Chrome 135+ and their intended profile.
- **Same host:** Use `ws://127.0.0.1:18210/extension`.
- **Separate hosts:** Use a private Tailscale Serve HTTPS endpoint and `wss://HOST:PORT/extension`.

Resolve ordinary paths and dependencies yourself. Ask the user only for facts you cannot discover, such as which Chrome profile they intend to connect. Preserve existing services, MCP entries, and browser tabs.

## Install

1. Clone `https://github.com/codejeet/local-browser` into a stable directory, or inspect and reuse an existing checkout.
2. Create a dedicated `.venv` using Python 3.11+ and install `requirements.txt`. Use its Python for the relay, client, and MCP server.
3. Check whether the default relay port is available. Reuse the current connection if already correctly installed. If a separate service owns the port, choose another port and use it consistently.
4. For a remote browser, inspect `tailscale serve status`, select an unused HTTPS port, and configure private Serve to proxy the loopback relay. Preserve existing Serve routes. The browser host must be on the same tailnet and able to reach that URL.
5. Run `python setup.py --relay-url URL`, adding `--port` or `--config` if needed. Let the script generate and preserve credentials. Do not print token values or paste them into chat.
6. Start `relay.py`, passing `--config` when using a custom path. Verify the listener and the client's `status` response.
7. Copy the complete `extension/` folder to a permanent location on the browser host through a private file-transfer route. Include generated `connection.js`; leave the operator config on the relay host. Never publish the generated extension folder as a public artifact.
8. Load the folder through `chrome://extensions` in the intended profile. Enable Developer mode and Allow User Scripts. Use an authorized desktop interaction tool if available; otherwise give the user the short sequence from the README.
9. Confirm that `client.py status` reports `connected: true` and `client.py call tabs` reaches the intended profile.

The extension's public manifest key gives it a stable ID. A fresh setup script calculates that ID automatically. Only one extension can connect to a relay at once.

## Register MCP

For Hermes, use the supported `hermes mcp add` command with absolute paths. Put `--args` last. Supply `HERMES_LOCAL_BROWSER_CONFIG` through `--env` if the default is not appropriate, including when Hermes uses a different profile home. Consult `hermes mcp add --help` and the current [Hermes MCP docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp).

For another client, merge the README's stdio entry into its MCP configuration. Do not replace other entries. If the agent runs remotely from the browser, the MCP process still belongs alongside the relay.

Test tool discovery, then reload MCP or start a new session as the client requires. Keep unrelated sessions running.

## Verify the user's result

Use only the included `/fixture` page for write tests:

1. Open a new fixture tab using the browser-reachable URL. Save its returned tab ID.
2. Snapshot it and confirm the title and form.
3. Fill `#name` with a distinctive test value, then click `#apply`.
4. Read `#result` through JavaScript and confirm the exact value.
5. Read the fixture HTML and exercise scrolling.
6. Activate the test tab, take a screenshot, and inspect the image with your image tool.
7. Close only the test tab and restore the previously active tab when appropriate.

If an action times out, inspect current state before repeating it. Browser actions are not automatically retried. Do not test submissions, purchases, or messages on the user's real accounts as part of setup.

After the foreground connection works, configure persistent startup if requested. Linux instructions are in `docs/service.md`. Show the user the popup's Pause and Reconnect controls.

## Finish with a useful handoff

Report the project path, extension location, config path, how the relay starts and stops, the MCP registration name, and the checks that actually passed. Include one example request they can make next. If a Chrome toggle or network step remains unresolved, name it plainly rather than declaring installation complete.

## Maintenance

Generated `connection.js` and the relay config are private installation state. Keep them out of commits and public archives. A source update alone does not update the unpacked extension on a separate browser computer: copy the updated extension files while preserving the intended connection settings, then reload it in Chrome. Restart only the relay if its Python code changed.
