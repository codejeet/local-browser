'use strict';
function tabId(p) { if (!Number.isInteger(p.tabId)) throw Error('Explicit tabId required. Use tabs first.'); return p.tabId; }
function safeUrl(url) { const u=new URL(url); if (!['http:','https:'].includes(u.protocol)) throw Error('Only HTTP(S) navigation is supported.'); return u.href; }
// This function is packaged with the extension, not fetched page code.
function pageAction(action,p) {
  try {
  const key='__hermesLocalBrowserRefsV1';
  const state=globalThis[key] ||= {seq:0,refs:new Map()};
  const all=(selector,root=document)=>{const out=[...root.querySelectorAll(selector)]; for(const e of root.querySelectorAll('*'))if(e.shadowRoot)out.push(...all(selector,e.shadowRoot));return out;};
  const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';};
  const label=e=>(e.getAttribute('aria-label')||e.labels?.[0]?.innerText||e.innerText||e.getAttribute('placeholder')||e.getAttribute('title')||'').trim().slice(0,250);
  const resolve=()=>{let e;if(p.ref){e=state.refs.get(p.ref);if(!e?.isConnected)throw Error('Stale element ref. Take a new snapshot.');}else if(p.selector){const found=all(p.selector);if(found.length!==1)throw Error(`Selector matched ${found.length} elements; use a unique selector or ref.`);e=found[0];}else throw Error('ref or selector required');return e;};
  const info=e=>{const r=e.getBoundingClientRect();return {tag:e.tagName.toLowerCase(),role:e.getAttribute('role'),name:label(e),type:e.type||undefined,disabled:!!e.disabled,checked:e.checked,value:e.type==='password'?'[redacted]':e.value,href:e.href,rect:{x:r.x,y:r.y,width:r.width,height:r.height}};};
  if(action==='snapshot'){
    state.refs.clear();const elements=[];const candidates=all('a,button,input,textarea,select,[role],summary,[contenteditable="true"],[tabindex]');
    const max=Math.min(p.limit||400,1500);let count=0;
    for(const e of candidates){if(!visible(e))continue;count++;if(elements.length>=max)continue;const ref='e'+(++state.seq);state.refs.set(ref,e);elements.push({ref,...info(e)});}
    return {url:location.href,title:document.title,text:(document.body?.innerText||'').slice(0,Math.min(p.maxText||18000,100000)),elements,truncated:count>max,viewport:{width:innerWidth,height:innerHeight,scrollX,scrollY},frames:[...document.querySelectorAll('iframe')].map(e=>({title:e.title,src:e.src}))};
  }
  if(action==='html'){const html=p.selector?resolve().outerHTML:document.documentElement.outerHTML;const max=Math.min(p.maxChars||100000,2000000);return {url:location.href,html:html.slice(0,max),truncated:html.length>max};}
  if(action==='scroll'){if(p.ref||p.selector){const e=resolve();if(p.intoView!==false)e.scrollIntoView({block:'center',behavior:'instant'});else e.scrollBy(p.x||0,p.y||0);}else window.scrollBy({left:p.x||0,top:p.y||0,behavior:'instant'});return {scrollX,scrollY};}
  const e=resolve();if(!visible(e))throw Error('Element is not visible');if(e.disabled)throw Error('Element is disabled');e.scrollIntoView({block:'center',behavior:'instant'});
  if(action==='click'){e.click();state.refs.clear();return {clicked:true,inputMode:'DOM'};}
  if(action==='fill'){
    e.focus();const value=String(p.value??'');
    if(e.isContentEditable)e.textContent=value;
    else if(e instanceof HTMLSelectElement){e.value=value;if(e.value!==value)throw Error('Option does not exist');}
    else {const proto=e instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;if(!setter)throw Error('Element is not fillable');setter.call(e,value);}
    e.dispatchEvent(new Event('input',{bubbles:true,composed:true}));e.dispatchEvent(new Event('change',{bubbles:true,composed:true}));state.refs.clear();return {filled:true,inputMode:'DOM',value:e.type==='password'?'[redacted]':e.value??e.textContent};
  }
  if(action==='key'){e.focus();for(const type of ['keydown','keyup'])e.dispatchEvent(new KeyboardEvent(type,{key:p.key,code:p.code||p.key,bubbles:true,cancelable:true,ctrlKey:!!p.ctrlKey,shiftKey:!!p.shiftKey,altKey:!!p.altKey,metaKey:!!p.metaKey}));state.refs.clear();return {dispatched:true,inputMode:'synthetic',key:p.key};}
  throw Error('Unknown DOM action');
  } catch(error) { return {__hermesError:String(error.message||error)}; }
}
async function dispatch(action,p={}) {
  if(action==='status'){let userScripts=false;try{await chrome.userScripts.getScripts();userScripts=true;}catch{}return {version:'1.0.0',userScripts,transport:'extension-websocket',cdp:false};}
  if(action==='tabs')return (await chrome.tabs.query({})).map(t=>({id:t.id,windowId:t.windowId,title:t.title,url:t.url,active:t.active,status:t.status,incognito:t.incognito}));
  if(action==='open')return chrome.tabs.create({url:safeUrl(p.url),active:p.active!==false,...(Number.isInteger(p.windowId)?{windowId:p.windowId}:{})});
  const id=tabId(p);
  if(action==='navigate')return chrome.tabs.update(id,{url:safeUrl(p.url)});
  if(action==='close'){await chrome.tabs.remove(id);return {closed:id};}
  if(action==='activate'){const t=await chrome.tabs.update(id,{active:true});if(p.focusWindow)await chrome.windows.update(t.windowId,{focused:true});return t;}
  if(action==='frames')return chrome.webNavigation.getAllFrames({tabId:id});
  if(action==='screenshot'){
    const t=await chrome.tabs.get(id);if(!t.active)throw Error('Screenshot requires the active tab. Call activate first.');
    const dataUrl=await chrome.tabs.captureVisibleTab(t.windowId,{format:'png'});
    const [after]=await chrome.tabs.query({windowId:t.windowId,active:true});if(after?.id!==id)throw Error('Active tab changed during capture; image discarded.');
    return {tabId:id,url:t.url,dataUrl};
  }
  const target={tabId:id,...(p.allFrames?{allFrames:true}:{frameIds:[p.frameId||0]})};
  if(action==='eval'){
    if(typeof p.code!=='string')throw Error('JavaScript code string required');
    if(!chrome.userScripts?.execute)throw Error('Enable Allow User Scripts in this extension’s Chrome details.');
    const body=p.body?p.code:`return (${p.code}\n);`;
    const code=`(async()=>{try{const value=await(async()=>{${body}\n})();return {__hermesSuccess:true,value:value===undefined?null:value};}catch(e){return {__hermesError:String(e.message||e)};}})()`;
    const results=await chrome.userScripts.execute({target,world:p.world==='MAIN'?'MAIN':'USER_SCRIPT',js:[{code}]});
    for(const r of results){if(r.error||r.result?.__hermesError)throw Error(`Frame ${r.frameId}: ${r.error||r.result.__hermesError}`);if(!r.result?.__hermesSuccess)throw Error(`Frame ${r.frameId}: JavaScript did not return a result. Check syntax; use body:true for statements.`);r.result=r.result.value;}return results;
  }
  if(!['snapshot','html','click','fill','scroll','key'].includes(action))throw Error('Unknown action: '+action);
  const results=await chrome.scripting.executeScript({target,world:'ISOLATED',func:pageAction,args:[action,p]});
  const failed=results.find(r=>r.error||r.result?.__hermesError);
  if(failed)throw Error(`Frame ${failed.frameId}: ${failed.error||failed.result.__hermesError}`);
  return results;
}
