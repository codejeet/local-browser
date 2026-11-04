# Store release files

The Chrome Web Store package is built from a fixed list of extension source files. No connection credentials, pairing files, cache or development dependencies are included. The build removes the development manifest key so Chrome can assign the signed store identity, and omits the legacy connection-script import.

```bash
python3 scripts/build-store.py
```

Upload `dist/local-browser-1.0.0.zip`. Use [listing.md](listing.md) for dashboard text and [reviewer-instructions.md](reviewer-instructions.md) for the test instructions. Upload the PNG artwork in this directory. The public [privacy policy](../privacy.md) and main README are linked from the extension.

## Tests

```bash
npm ci
node --test tests/*.test.cjs
.venv/bin/python -m unittest discover -s tests -q
```

The packaged-extension smoke needs Playwright and Pillow in the project's development environment:

```bash
.venv/bin/python -m pip install playwright pillow
.venv/bin/python -m playwright install chromium
.venv/bin/python scripts/build-store.py
.venv/bin/python scripts/smoke-browser.py
```

This runs the actual ZIP in a fresh Chromium profile, creates private temporary relay credentials, enables Chrome's User Scripts setting, and exercises pairing, reading, filling, clicking, custom JavaScript, screenshots, pause/resume, reconnect and forget. It does not connect to an existing user's browser. Browser captures and a result summary go in an `artifacts` directory beside the repository. The profile and credentials are removed after the run.

`render-brand.py` creates the icons and promo artwork. `render-screenshots.py` composes the store screenshots from the actual smoke captures; it requires DejaVu Sans fonts. The included demo page uses sample data.
