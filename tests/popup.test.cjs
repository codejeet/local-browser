const {test}=require('node:test');
const assert=require('node:assert/strict');
const {JSDOM}=require('jsdom');
const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'../extension');
const tick=()=>new Promise(r=>setTimeout(r,20));
function popup(state){
 const dom=new JSDOM(fs.readFileSync(path.join(root,'popup.html'),'utf8'),{runScripts:'outside-only',url:'https://extension.test/'});
 const calls=[];dom.window.chrome={runtime:{sendMessage:async m=>{calls.push(m);return {...state,ok:true};},id:'a'.repeat(32)},tabs:{create:async()=>{}}};
 dom.window.setInterval=()=>0;
 dom.window.eval(fs.readFileSync(path.join(root,'popup.js'),'utf8'));
 return {w:dom.window,d:dom.window.document,calls};
}
test('fresh install explains pairing and exposes URL and masked token fields',async()=>{
 const {d}=popup({configured:false,userScripts:false});await tick();
 assert.match(d.querySelector('#state').textContent,/Connect your browser/);
 assert.equal(d.querySelector('#token').type,'password');
 assert.equal(d.querySelector('#connection-form').hidden,false);
});
test('pairing form saves through background and clears token from DOM',async()=>{
 const {w,d,calls}=popup({configured:false,userScripts:false});await tick();
 d.querySelector('#url').value='ws://127.0.0.1:18210/extension';d.querySelector('#token').value='a'.repeat(32);
 d.querySelector('#connection-form').dispatchEvent(new w.Event('submit',{cancelable:true}));await tick();
 assert.equal(calls.at(-1).action,'saveConnection');assert.equal(calls.at(-1).token,'a'.repeat(32));assert.equal(d.querySelector('#token').value,'');
});
test('connected view shows actual relay and pause control without token',async()=>{
 const {d,calls}=popup({configured:true,connected:true,url:'wss://relay.example/extension',extensionId:'a'.repeat(32),hasToken:true,userScripts:true});await tick();
 assert.match(d.querySelector('#state').textContent,/Connected/);
 assert.equal(d.querySelector('#connection-form').hidden,true);
 d.querySelector('#toggle').click();await tick();assert.equal(calls.at(-1).action,'toggle');
});
