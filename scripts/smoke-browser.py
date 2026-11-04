"""Exercise the packaged extension in isolated Chromium and save real UI captures.
Run: .venv/bin/python scripts/smoke-browser.py (playwright + pillow required).
"""
import asyncio,base64,json,sys,tempfile,zipfile
from pathlib import Path
from aiohttp import web,ClientSession
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from relay import create_app
from setup import bootstrap
OUT=ROOT.parent/'artifacts';OUT.mkdir(exist_ok=True)
async def main():
 async with async_playwright() as p:
  with tempfile.TemporaryDirectory(prefix='local-browser-') as tmp:
   tmp=Path(tmp);extension=tmp/'extension';zipfile.ZipFile(ROOT/'dist/local-browser-1.0.0.zip').extractall(extension)
   context=await p.chromium.launch_persistent_context(str(tmp/'profile'),channel='chromium',headless=True,viewport={'width':1280,'height':800},args=[f'--disable-extensions-except={extension}',f'--load-extension={extension}','--no-sandbox'])
   worker=context.service_workers[0] if context.service_workers else await context.wait_for_event('serviceworker')
   identity=worker.url.split('/')[2]
   ui=await context.new_page();errors=[];ui.on('pageerror',lambda e:errors.append(str(e)))
   await ui.goto(f'chrome-extension://{identity}/popup.html')
   await ui.get_by_text('Connect your browser',exact=True).wait_for()
   await ui.locator('main').screenshot(path=str(OUT/'setup-ui.png'))
   assert await worker.evaluate('connection === null')
   config={'extension_id':identity,'extension_token':'unused','operator_token':'unused'}
   app=create_app(config)
   async def demo(request):return web.Response(text=(ROOT/'docs/demo.html').read_text(),content_type='text/html')
   app.router.add_get('/demo',demo)
   runner=web.AppRunner(app);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start();port=site._server.sockets[0].getsockname()[1]
   path,_,_=bootstrap(f'ws://127.0.0.1:{port}/extension',config=tmp/'config.json',port=port,store_extension_id=identity)
   config.update(json.loads(path.read_text()))
   async with ClientSession(headers={'Authorization':'Bearer '+config['operator_token']}) as session:
    async def request(action,params={}):
     async with session.post(f'http://127.0.0.1:{port}/command',json={'action':action,'params':params,'timeout':15}) as response:
      value=await response.json();assert value.get('ok'),value;return value['result']
    async def connected(expected=True):
     for _ in range(80):
      async with session.get(f'http://127.0.0.1:{port}/status') as response: s=await response.json()
      if s['connected']==expected:return
      await asyncio.sleep(.1)
     raise AssertionError('Connection state not reached')
    try:
     await ui.locator('#pairing').set_input_files(tmp/'pairing.json')
     await ui.locator('#save').click();await connected()
     await ui.get_by_text('Connected to your agent',exact=True).wait_for()
     assert await ui.locator('#token').input_value()==''
     # Enable the real per-extension user script setting through Chrome's UI.
     settings=await context.new_page();await settings.goto(f'chrome://extensions/?id={identity}')
     await settings.locator('extensions-detail-view').wait_for()
     await settings.screenshot(path=str(OUT/'extension-settings.png'))
     toggle=settings.locator('#allow-user-scripts').locator('cr-toggle')
     await toggle.wait_for()
     if await toggle.get_attribute('aria-pressed')!='true':await toggle.click()
     await settings.close()
     for _ in range(40):
      if await worker.evaluate('chrome.userScripts.getScripts().then(()=>true).catch(()=>false)'):break
      await asyncio.sleep(.1)
     tab=await request('open',{'url':f'http://127.0.0.1:{port}/demo'})
     demo_page=next((page for page in context.pages if '/demo' in page.url),None)
     if not demo_page:
      await asyncio.sleep(.2);demo_page=next(page for page in context.pages if '/demo' in page.url)
     await demo_page.wait_for_load_state()
     tabid=tab['id'];snapshot=await request('snapshot',{'tabId':tabid});assert 'Create a task' in json.dumps(snapshot)
     await request('fill',{'tabId':tabid,'selector':'#name','value':'Review the launch checklist'})
     await request('fill',{'tabId':tabid,'selector':'#priority','value':'High'})
     await request('click',{'tabId':tabid,'selector':'#apply'})
     result=await request('eval',{'tabId':tabid,'code':'document.querySelector("#result").textContent'})
     assert 'Saved: Review the launch checklist' in json.dumps(result)
     await request('activate',{'tabId':tabid})
     await demo_page.locator('#result').filter(has_text='Saved: Review the launch checklist').wait_for()
     await demo_page.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
     await asyncio.sleep(.15) # Allow the compositor to publish the completed frame.
     image=await request('screenshot',{'tabId':tabid})
     data=image.get('dataUrl') if isinstance(image,dict) else image
     if not data:raise AssertionError('Screenshot shape: '+str(image)[:200])
     (OUT/'workflow.png').write_bytes(base64.b64decode(data.split(',',1)[1]))
     await ui.bring_to_front();await ui.reload();await ui.get_by_text('Connected to your agent',exact=True).wait_for()
     await ui.locator('main').screenshot(path=str(OUT/'connected-ui.png'))
     await ui.locator('#toggle').click();await connected(False);await ui.get_by_text('Browser paused',exact=True).wait_for()
     await ui.locator('main').screenshot(path=str(OUT/'paused-ui.png'))
     await ui.locator('#toggle').click();await connected()
     await ui.locator('#reconnect').click();await connected()
     await ui.locator('#edit').click();await ui.locator('#disconnect').click();await connected(False)
     await ui.reload();await ui.get_by_text('Connect your browser',exact=True).wait_for()
     assert not errors,errors
     receipt={'passed':['fresh packaged install','private pairing-file import','authenticated relay connection','read','fill input','select','click','userScripts eval','screenshot','pause','resume','reconnect','forget and reload'],'browser':context.browser.version,'extensionId':identity,'pageErrors':errors}
     (OUT/'smoke.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
    finally:
     await context.close();await runner.cleanup()
asyncio.run(main())
