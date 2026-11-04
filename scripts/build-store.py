#!/usr/bin/env python3
"""Build a deterministic, credential-free Chrome Web Store ZIP."""
from pathlib import Path
import json
import zipfile
ROOT=Path(__file__).resolve().parents[1]
FILES=['manifest.json','background.js','connection-config.js','actions.js','gate.js','popup.html','popup.css','popup.js',*[f'icons/icon{n}.png' for n in (16,32,48,128)]]
def build(destination=None):
    manifest=json.loads((ROOT/'extension/manifest.json').read_text())
    manifest.pop('key',None) # The Web Store assigns the signed installation's ID.
    destination=Path(destination or ROOT/f'dist/local-browser-{manifest["version"]}.zip')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in FILES:
            raw=(json.dumps(manifest,indent=2)+'\n').encode() if name=='manifest.json' else (ROOT/'extension'/name).read_bytes()
            # Store worker does not attempt to load an absent legacy file.
            if name=='background.js':raw=raw.replace(b"try { importScripts('connection.js'); } catch {}",b'// Store installs pair through extension storage.')
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,raw)
    print(destination)
    return destination
if __name__=='__main__':build()
