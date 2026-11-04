const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const copy=value=>JSON.parse(JSON.stringify(value));

function worker({storage={},legacy=null,dispatch=async()=>({ok:true})}={}) {
  const sockets=[], timers=new Map(), calls=[], imports=[];
  let listener, alarm, timerId=0;
  const chrome={
    runtime:{id:'abcdefghijklmnopabcdefghijklmnop',onMessage:{addListener:fn=>listener=fn},
      onStartup:{addListener(){}},onInstalled:{addListener(){}}},
    storage:{local:{
      setAccessLevel:async value=>calls.push(['access',copy(value)]),
      get:async keys=>{calls.push(['get']);return copy(storage);},
      set:async value=>{calls.push(['set',copy(value)]);Object.assign(storage,copy(value));},
      remove:async keys=>{for(const key of [keys].flat())delete storage[key];}
    }},
    action:{setBadgeText:async()=>{},setBadgeBackgroundColor:async()=>{}},
    userScripts:{getScripts:async()=>[]},
    alarms:{create:async()=>{},onAlarm:{addListener:fn=>alarm=fn}}
  };
  class Socket {
    static CONNECTING=0;static OPEN=1;static CLOSED=3;
    constructor(url){this.url=url;this.readyState=0;this.sent=[];sockets.push(this);}
    send(value){this.sent.push(JSON.parse(value));}
    close(){this.readyState=3;}
    open(){this.readyState=1;this.onopen?.();}
    message(value){this.onmessage?.({data:JSON.stringify(value)});}
    welcome(){this.open();this.message({type:'welcome'});}
  }
  const ctx={chrome,URL,console,Date,WebSocket:Socket,
    setTimeout:(fn)=>{timers.set(++timerId,fn);return timerId;},
    clearTimeout:id=>timers.delete(id),
    setInterval:(fn)=>{timers.set(++timerId,fn);return timerId;},
    clearInterval:id=>timers.delete(id)};
  vm.createContext(ctx);
  ctx.importScripts=(...files)=>{for(const file of files){
    imports.push(file);
    if(file==='connection.js'){
      if(!legacy)throw Error('connection.js not packaged');
      vm.runInContext('const CONNECTION='+JSON.stringify(legacy),ctx);
    }else vm.runInContext(fs.readFileSync(path.join(__dirname,'../extension',file),'utf8'),ctx,{filename:file});
  }};
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../extension/background.js'),'utf8'),ctx);
  ctx.dispatch=dispatch;
  return {sockets,storage,calls,imports,timers,chrome,alarm:()=>alarm(),
    message:(message={},sender={id:chrome.runtime.id})=>new Promise(resolve=>listener(message,sender,value=>resolve(copy(value)))),
    rawMessage:(message,sender,reply)=>listener(message,sender,reply)};
}
const pairing={url:'ws://127.0.0.1:18210/extension',token:'test-private-pairing-token'};
const command=id=>({id,action:'tabs',deadline:Date.now()+10000});

// These run the real classic service worker with browser API boundaries simulated.
test('fresh store boot works without connection.js and exposes safe default status',async()=>{
  const w=worker();const status=await w.message();
  assert.deepEqual(Object.keys(status).sort(),['paused','connected','lastError','lastAction','userScripts','configured','url','extensionId','hasToken'].sort());
  assert.equal(status.configured,false);assert.equal(status.connected,false);assert.equal(status.url,'');
  assert.equal(status.hasToken,false);assert.equal(status.userScripts,true);
  assert.equal(status.extensionId,w.chrome.runtime.id);assert.equal(w.sockets.length,0);
  assert.deepEqual(w.calls[0],['access',{accessLevel:'TRUSTED_CONTEXTS'}]);
});

test('save persists pairing; connected means authenticated; blank token reuses saved token',async()=>{
  const w=worker();let status=await w.message({action:'saveConnection',...pairing});
  assert.equal(status.ok,true);assert.equal(status.configured,true);assert.equal(status.hasToken,true);
  assert.equal(status.connected,false);assert.equal(JSON.stringify(status).includes(pairing.token),false);
  assert.deepEqual(w.storage.connection,pairing);
  const old=w.sockets[0];old.open();assert.equal(old.sent[0].token,pairing.token);
  assert.equal((await w.message()).connected,false);
  old.message({type:'welcome'});assert.equal((await w.message()).connected,true);
  status=await w.message({action:'saveConnection',url:'wss://relay.example/browser/extension',token:'  '});
  assert.equal(status.ok,true);assert.equal(status.connected,false);assert.equal(old.readyState,3);
  assert.equal(w.storage.connection.token,pairing.token);assert.equal(w.sockets.length,2);
  const restarted=worker({storage:w.storage});await restarted.message();
  assert.equal(restarted.sockets[0].url,'wss://relay.example/browser/extension');
});

test('unsafe URLs and missing token fail without replacing a working connection',async()=>{
  const w=worker();let result=await w.message({action:'saveConnection',url:pairing.url,token:''});
  assert.equal(result.ok,false);assert.equal(w.sockets.length,0);
  await w.message({action:'saveConnection',...pairing});
  for(const url of ['ws://remote.example/extension','https://localhost/extension',
    'ws://127.0.0.1.evil/extension','ws://0.0.0.0/extension','wss://user:secret@relay.example/extension',
    'wss://@relay.example/extension','wss://relay.example/extension?','wss://relay.example/extension#',
    'wss://relay.example/extension?token=secret','wss://relay.example/extension#fragment',
    'wss://relay.example:0/extension','wss://relay.example:65536/extension','wss://relay.example/other',
    ' wss://relay.example/extension','wss://relay.example/extension\n','wss://relay.example\\extension']){
    result=await w.message({action:'saveConnection',url,token:'replacement'});
    assert.equal(result.ok,false,url);assert.deepEqual(w.storage.connection,pairing);
    assert.equal(w.sockets.length,1);
  }
});

test('loopback IPv4 IPv6 localhost and TLS remote endpoints are accepted',async()=>{
  const w=worker();
  for(const url of ['ws://localhost:18210/extension','ws://localhost./extension','ws://127.12.1.1/extension',
    'ws://[::1]:18210/extension','wss://relay.example/browser/extension']){
    assert.equal((await w.message({action:'saveConnection',url,token:pairing.token})).ok,true,url);
  }
});

test('legacy import migrates once; disconnect forgets credential and cannot resurrect legacy config',async()=>{
  const storage={};const w=worker({storage,legacy:pairing});
  assert.equal((await w.message()).configured,true);assert.deepEqual(storage.connection,pairing);
  const status=await w.message({action:'disconnect'});
  assert.equal(status.ok,true);assert.equal(status.configured,false);assert.equal(status.hasToken,false);
  assert.equal(status.connected,false);assert.equal(status.url,'');
  assert.equal(JSON.stringify(storage).includes(pairing.token),false);
  const restarted=worker({storage,legacy:pairing});
  assert.equal((await restarted.message()).configured,false);assert.equal(restarted.sockets.length,0);
});

test('pause persists, resume reconnects, reconnect while paused never opens socket',async()=>{
  const w=worker();await w.message({action:'saveConnection',...pairing});w.sockets[0].welcome();
  assert.equal((await w.message({action:'toggle'})).paused,true);
  assert.equal(w.storage.paused,true);assert.equal(w.sockets[0].readyState,3);
  await w.message({action:'reconnect'});assert.equal(w.sockets.length,1);
  const restarted=worker({storage:w.storage});assert.equal((await restarted.message()).paused,true);
  assert.equal(restarted.sockets.length,0);
  assert.equal((await w.message({action:'toggle'})).paused,false);assert.equal(w.sockets.length,2);
  await w.message({action:'reconnect'});assert.equal(w.sockets.length,3);
});

test('only trusted extension pages can read or mutate connection settings',async()=>{
  const w=worker();await w.message();let replies=0;
  for(const sender of [{id:'other'},{id:w.chrome.runtime.id,tab:{id:7}}]){
    assert.equal(w.rawMessage({action:'saveConnection',...pairing},sender,()=>replies++),undefined);
  }
  await tick();assert.equal(replies,0);assert.equal(w.sockets.length,0);
});

test('popup opened in its own tab can configure the connection',async()=>{
  const w=worker();await w.message();let reply;
  w.rawMessage({action:'status'},{id:w.chrome.runtime.id,url:`chrome-extension://${w.chrome.runtime.id}/popup.html`,tab:{id:7}},value=>reply=value);
  await tick();assert.equal(reply?.configured,false);
});

test('stale socket events cannot authenticate, send credentials, set errors or reconnect',async()=>{
  const w=worker();await w.message({action:'saveConnection',...pairing});const old=w.sockets[0];
  await w.message({action:'saveConnection',url:pairing.url,token:'new-private-token'});
  old.open();old.message({type:'welcome'});old.onerror?.();old.onclose?.();
  const status=await w.message();assert.equal(status.connected,false);assert.equal(status.lastError,'');
  assert.equal(old.sent.length,0);assert.equal(w.timers.size,0);assert.equal(w.sockets.length,2);
});

for(const action of ['saveConnection','toggle','disconnect','reconnect']){
  test(`${action} invalidates commands already queued on old connection`,async()=>{
    let release;const held=new Promise(resolve=>release=resolve);const ran=[];
    const w=worker({dispatch:async(_,params)=>{ran.push(params.label);if(params.label==='first')await held;return params.label;}});
    await w.message({action:'saveConnection',...pairing});const old=w.sockets[0];old.welcome();
    old.message({...command('one'),params:{label:'first'}});await tick();
    old.message({...command('two'),params:{label:'queued'}});
    await w.message({action,...pairing});release();await tick();await tick();
    assert.deepEqual(ran,['first']);assert.equal(old.sent.filter(m=>m.id).length,0);
    assert.equal((await w.message()).lastAction,null);
  });
}

test('commands cannot execute before authentication, and eval still delegates through guarded dispatch',async()=>{
  const ran=[];const w=worker({dispatch:async(action,params)=>{ran.push([action,params]);return 42;}});
  await w.message({action:'saveConnection',...pairing});const ws=w.sockets[0];ws.open();
  ws.message(command('early'));await tick();assert.equal(ran.length,0);
  ws.message({type:'welcome'});ws.message({...command('eval-1'),action:'eval',params:{tabId:7,code:'6*7'}});
  await tick();assert.equal(ran[0][0],'eval');assert.equal(ws.sent.at(-1).result,42);
  assert.equal((await w.message()).lastAction.action,'eval');
});
