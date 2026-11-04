const $ = id => document.getElementById(id);
let editing = false, initialized = false, current = null, busy = false;
function render(s) {
 current = s;
 $('state').textContent = !s.configured ? 'Connect your browser' : s.paused ? 'Browser paused' : s.connected ? 'Connected to your agent' : 'Connecting to your relay';
 $('description').textContent = !s.configured ? 'Let your AI agent work in the tabs you already use.' : s.paused ? 'New browser commands are stopped. Resume when you’re ready.' : s.connected ? 'Your tabs are ready. Ask your agent to read a page or complete a task.' : 'Keep your relay running on your agent’s computer.';
 $('dot').className = s.connected ? 'connected' : '';
 $('relay').hidden = !s.configured;
 $('relay').textContent = s.url || '';
 $('controls').hidden = !s.configured;
 $('toggle').textContent = s.paused ? 'Resume' : 'Pause';
 $('connection-form').hidden = s.configured && !editing;
 $('cancel').hidden = !s.configured;
 $('edit').hidden = !s.configured || editing;
 $('disconnect').hidden = !s.configured || !editing;
 $('scripts-panel').hidden = !s.configured;
 const version = Number(navigator.userAgent.match(/(?:Chrome|Chromium)\/(\d+)/)?.[1] || 138);
 $('scripts').textContent = s.userScripts ? 'Ready for scripts from your agent.' : version >= 138 ? 'For custom JavaScript, turn on “Allow User Scripts” in this extension’s settings. Page reading, forms and screenshots work without it.' : 'For custom JavaScript, enable Developer mode at chrome://extensions.';
 $('script-settings').hidden = s.userScripts;
 $('extension-id').textContent = s.extensionId || chrome.runtime.id;
 $('last').textContent = s.lastAction ? `Last task: ${s.lastAction.action} · ${s.lastAction.ok ? 'Done' : 'Could not finish'}` : '';
 if (!initialized) { $('url').value = s.url || ''; initialized = true; }
 $('token').placeholder = s.hasToken ? 'Saved in this Chrome profile' : 'From your relay setup';
 if (!editing) $('error').textContent = s.error || s.lastError || '';
}
async function update(action='status', values={}) {
 try {
  const result = await chrome.runtime.sendMessage({action,...values});
  if (!result) throw new Error('Could not reach the extension. Close this popup and try again.');
  render(result);
  return result;
 } catch (error) { $('error').textContent = error.message; return {ok:false}; }
}
$('connection-form').onsubmit = async event => {
 event.preventDefault();busy=true;$('save').disabled=true;
 const result = await update('saveConnection',{url:$('url').value,token:$('token').value});
 $('token').value='';busy=false;$('save').disabled=false;
 if (result.ok) {editing=false;render(result);} else $('error').textContent=result.error || 'Could not save. Check your connection details.';
};
$('pairing').onchange = async () => {
 const file=$('pairing').files[0];if(!file)return;
 try {
  if(file.size>8192)throw new Error();
  const pair=JSON.parse(await file.text());
  if(typeof pair.url!=='string'||typeof pair.token!=='string')throw new Error();
  $('url').value=pair.url;$('token').value=pair.token;$('error').textContent='';
 }catch{$('error').textContent='Choose the pairing.json file created by relay setup.';}
 $('pairing').value='';
};
$('toggle').onclick=()=>update('toggle');
$('reconnect').onclick=()=>update('reconnect');
$('edit').onclick=()=>{editing=true;$('url').value=current.url;render(current);};
$('cancel').onclick=()=>{editing=false;$('token').value='';render(current);};
$('disconnect').onclick=async()=>{const s=await update('disconnect');if(s.ok){editing=false;$('url').value='';$('token').value='';render(s);}};
$('script-settings').onclick=()=>chrome.tabs.create({url:`chrome://extensions/?id=${chrome.runtime.id}`});
update();setInterval(()=>{if(!busy)update();},1500);
