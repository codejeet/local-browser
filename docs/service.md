# Run the relay as a Linux user service

Complete the foreground setup and connection test from the README first. A user service runs the relay under your own account and starts it again after a crash.

## Install the service

The example assumes the project lives at `~/local-browser`, with its virtual environment at `~/local-browser/.venv` and its config at `~/.hermes/local-browser/config.json`.

If your paths differ, edit the **copied service file** before starting it. Use absolute paths or systemd's `%h` home-directory specifier. The explicit `--config` path should match the one created by setup.

```bash
mkdir -p ~/.config/systemd/user
cp docs/local-browser.service.example ~/.config/systemd/user/local-browser.service
```

Review `~/.config/systemd/user/local-browser.service`, then run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now local-browser.service
systemctl --user status local-browser.service
```

Stop any foreground relay using that same port before starting the service. To keep a user service running after logout, a system administrator can enable lingering for your account:

```bash
sudo loginctl enable-linger "$USER"
```

On WSL, user services require systemd support to be enabled. Keeping the Windows browser open remains necessary for browser commands.

## Operate it

```bash
systemctl --user stop local-browser.service
systemctl --user start local-browser.service
systemctl --user restart local-browser.service
journalctl --user -u local-browser.service -n 50 --no-pager
```

Check the end-to-end connection from the project directory:

```bash
.venv/bin/python client.py status
```

A running service confirms the relay process. `connected: true` confirms the extension's connection to it.

For a remote browser, Tailscale Serve configured with `--bg` keeps its route separately. Inspect that route with `tailscale serve status`. Pausing the extension disconnects browser access without removing the service or route.

On macOS, use the foreground command or a launch agent configured with the same absolute Python, script, and config paths.
