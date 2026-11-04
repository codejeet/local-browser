importScripts('connection-config.js', 'actions.js', 'gate.js');
// Legacy unpacked installs may supply this file; store installs do not need it.
// Keep imports synchronous so Chrome can cache service-worker dependencies.
try { importScripts('connection.js'); } catch {}

let socket = null, authenticated = false, connection = null, paused = false;
let pingTimer = null, retryTimer = null, lastError = '', lastAction = null;
let chain = Promise.resolve(), messages = Promise.resolve(), initializationError = '';

function badge(text, color) {
  Promise.all([chrome.action.setBadgeText({text}), chrome.action.setBadgeBackgroundColor({color})]).catch(() => {});
}
function stopConnection() {
  const old = socket;
  socket = null;
  authenticated = false;
  clearTimeout(retryTimer);
  clearInterval(pingTimer);
  retryTimer = pingTimer = null;
  old?.close();
  badge(paused ? 'OFF' : connection ? '...' : '', '#666666');
}
function connect() {
  if (initializationError || paused || !connection || socket) return;
  clearTimeout(retryTimer);
  try {
    const config = connection;
    const ws = new WebSocket(config.url);
    socket = ws;
    const current = () => socket === ws && !paused;
    const usable = () => current() && authenticated && ws.readyState === WebSocket.OPEN;
    badge('...', '#666666');
    ws.onopen = () => {
      if (!current()) return;
      ws.send(JSON.stringify({type:'hello', token:config.token, client:'Local Chrome', version:'1.0.0'}));
    };
    ws.onmessage = event => {
      if (!current()) return;
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      if (!message || typeof message !== 'object') return;
      if (message.type === 'welcome') {
        authenticated = true;
        lastError = '';
        badge('ON', '#187a37');
        clearInterval(pingTimer);
        pingTimer = setInterval(() => {
          if (usable()) ws.send(JSON.stringify({type:'ping'}));
        }, 20000);
        return;
      }
      if (!usable() || message.type === 'pong' || !message.id) return;
      chain = chain.then(async () => {
        // A command can have waited behind another async browser action. Never
        // execute queued work from a paused, replaced, or disconnected socket.
        if (!usable()) return;
        let response;
        try {
          const result = await runGuarded(message, paused, () => dispatch(message.action, message.params || {}));
          response = {id:message.id, ok:true, result};
        } catch (error) {
          response = {id:message.id, ok:false, error:String(error.message || error)};
        }
        if (!usable()) return;
        lastAction = {action:message.action, time:Date.now(), ok:response.ok};
        ws.send(JSON.stringify(response));
      }).catch(() => {
        if (current()) lastError = 'Unable to return browser action result';
      });
    };
    ws.onclose = event => {
      if (!current()) return;
      const wasAuthenticated = authenticated;
      stopConnection();
      if (!wasAuthenticated) lastError = event?.code === 1008
        ? 'Pairing rejected. Check your token and extension ID in relay setup.'
        : 'Connection unavailable. Check your network and relay setup.';
      retryTimer = setTimeout(connect, 5000);
    };
    ws.onerror = () => {
      if (current()) lastError = 'Connection unavailable. Check your network and relay setup.';
    };
  } catch {
    stopConnection();
    lastError = 'Connection unavailable. Check your network and relay setup.';
    retryTimer = setTimeout(connect, 5000);
  }
}
async function status() {
  let userScripts = false;
  try { await chrome.userScripts.getScripts(); userScripts = true; } catch {}
  return {
    paused, connected:Boolean(authenticated && socket?.readyState === WebSocket.OPEN),
    lastError, lastAction, userScripts, configured:Boolean(connection),
    url:connection?.url || '', extensionId:chrome.runtime.id, hasToken:Boolean(connection?.token)
  };
}
async function handleMessage(message) {
  await ready;
  let mutation = false;
  let error = initializationError;
  try {
    if (error) return {...await status(), ok:false, error};
    if (message.action === 'saveConnection') {
      mutation = true;
      let next;
      try { next = ConnectionConfig.parse(message, connection); }
      catch (validation) { return {...await status(), ok:false, error:validation.message}; }
      await chrome.storage.local.set({connection:next, connectionMigrationDone:true});
      stopConnection();
      connection = next;
      lastError = '';
      connect();
    } else if (message.action === 'disconnect') {
      mutation = true;
      // The marker prevents a legacy generated file from pairing again on boot.
      await chrome.storage.local.set({connectionMigrationDone:true});
      await chrome.storage.local.remove('connection');
      connection = null;
      stopConnection();
      lastError = '';
      lastAction = null;
    } else if (message.action === 'toggle') {
      mutation = true;
      const next = !paused;
      await chrome.storage.local.set({paused:next});
      paused = next;
      stopConnection();
      connect();
    } else if (message.action === 'reconnect') {
      mutation = true;
      stopConnection();
      lastError = '';
      connect();
    }
  } catch {
    error = 'Unable to save connection settings. Please try again.';
    lastError = error;
  }
  const result = await status();
  return error ? {...result, ok:false, error} : mutation ? {...result, ok:true} : result;
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== chrome.runtime.id || (sender.tab && sender.url !== `chrome-extension://${chrome.runtime.id}/popup.html`)) return;
  // Serialize setting changes so overlapping popup requests cannot restore old
  // credentials or open a connection after a later disconnect.
  messages = messages.then(() => handleMessage(message || {})).then(reply).catch(() => {});
  return true;
});
async function boot() {
  await chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
  const saved = await chrome.storage.local.get(['paused', 'connection', 'connectionMigrationDone']);
  paused = saved.paused === true;
  let next = null;
  if (saved.connection) {
    try { next = ConnectionConfig.parse(saved.connection); }
    catch { lastError = 'Saved connection is invalid. Enter your relay URL and pairing token again.'; }
  } else if (!saved.connectionMigrationDone && typeof CONNECTION !== 'undefined') {
    try { next = ConnectionConfig.parse(CONNECTION); }
    catch { lastError = 'Legacy connection is invalid. Enter your relay URL and pairing token again.'; }
  }
  if (!saved.connectionMigrationDone) {
    await chrome.storage.local.set({connectionMigrationDone:true, ...(next ? {connection:next} : {})});
  }
  connection = next;
  badge(paused ? 'OFF' : '', '#666666');
  await chrome.alarms.create('reconnect', {periodInMinutes:0.5});
  connect();
}
const ready = boot().catch(() => {
  initializationError = lastError = 'Unable to load private connection settings. Reload the extension and try again.';
  stopConnection();
});
const resume = () => ready.then(connect);
chrome.alarms.onAlarm.addListener(resume);
chrome.runtime.onStartup.addListener(resume);
chrome.runtime.onInstalled.addListener(resume);
