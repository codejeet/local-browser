importScripts('connection.js','actions.js','gate.js');
let socket=null,paused=false,connecting=false,pingTimer=null,retryTimer=null,lastError='',lastAction=null,chain=Promise.resolve();
async function badge(text,color){await chrome.action.setBadgeText({text});await chrome.action.setBadgeBackgroundColor({color});}
async function connect(){
 if(paused||connecting||socket?.readyState===WebSocket.OPEN||socket?.readyState===WebSocket.CONNECTING)return;
 connecting=true;clearTimeout(retryTimer);
 try{
  const ws=new WebSocket(CONNECTION.url);socket=ws;
  ws.onopen=()=>{connecting=false;ws.send(JSON.stringify({type:'hello',token:CONNECTION.token,client:'Local Chrome',version:'1.0.0'}));};
  ws.onmessage=e=>{let m;try{m=JSON.parse(e.data);}catch{return;}
   if(m.type==='welcome'){lastError='';badge('ON','#187a37');clearInterval(pingTimer);pingTimer=setInterval(()=>{if(ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify({type:'ping'}));},20000);return;}
   if(m.type==='pong')return;
   if(!m.id)return;
   chain=chain.then(async()=>{let response;try{const result=await runGuarded(m,paused,()=>dispatch(m.action,m.params||{}));response={id:m.id,ok:true,result};lastAction={action:m.action,time:Date.now(),ok:true};}catch(err){response={id:m.id,ok:false,error:String(err.message||err)};lastAction={action:m.action,time:Date.now(),ok:false};}if(ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify(response));}).catch(err=>{lastError=String(err.message||err);});
  };
  ws.onclose=()=>{if(socket!==ws)return;socket=null;connecting=false;clearInterval(pingTimer);badge(paused?'OFF':'...','#666666');if(!paused)retryTimer=setTimeout(connect,5000);};
  ws.onerror=()=>{lastError='Connection unavailable. Check your network and Hermes relay.';};
 }catch(e){connecting=false;lastError=String(e.message);retryTimer=setTimeout(connect,5000);}
}
chrome.runtime.onMessage.addListener((m,sender,reply)=>{
 if(sender.id!==chrome.runtime.id||sender.tab)return;
 (async()=>{
  if(m.action==='toggle'){paused=!paused;await chrome.storage.local.set({paused});if(paused){clearTimeout(retryTimer);socket?.close();await badge('OFF','#666666');}else await connect();}
  if(m.action==='reconnect'){socket?.close();socket=null;connecting=false;await connect();}
  let userScripts=false;try{await chrome.userScripts.getScripts();userScripts=true;}catch{}
  reply({paused,connected:socket?.readyState===WebSocket.OPEN,lastError,lastAction,userScripts});
 })();return true;
});
chrome.alarms.onAlarm.addListener(()=>connect());
async function boot(){paused=(await chrome.storage.local.get('paused')).paused||false;await chrome.alarms.create('reconnect',{periodInMinutes:0.5});await connect();}
chrome.runtime.onStartup.addListener(boot);chrome.runtime.onInstalled.addListener(boot);boot();
