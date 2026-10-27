importScripts('core.js');
const C=SynCore;
let queue=Promise.resolve();
chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
const inflight=new Map();
async function state(){const s=await chrome.storage.local.get(['prefs','history','feedback','analyses','generation']);return{prefs:{...C.defaults,...s.prefs},history:C.prune(s.history||[]),feedback:s.feedback||{},analyses:s.analyses||{},generation:s.generation||0};}
const publicState=s=>({...s,prefs:{...s.prefs,token:undefined,paired:!!s.prefs.token}});
function isOptions(sender){return sender.url?.startsWith(chrome.runtime.getURL('options.html'));}
function allowed(sender){return isOptions(sender)||sender.url?.startsWith('https://www.youtube.com/');}
async function localCall(path,body,token){
 const res=await fetch('http://127.0.0.1:8765/'+path,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify(body),signal:AbortSignal.timeout(20000)});
 const result=await res.json();if(!res.ok)throw Error(result.error||'Raccordement indisponible');return result;
}
async function analyze(m){
 const s=await state();if(!s.prefs.enabled||!s.prefs.autoAI||!s.prefs.token)throw Error('Analyse IA désactivée. Ouvre les réglages SYN.');
 const v=C.clean(m.video);if(!v||!v.title)throw Error('Titre pas encore disponible.');
 const transcript=String(m.transcript||'').slice(0,12000),description=String(m.description||'').slice(0,4000);
 const raw=JSON.stringify([v,s.prefs.topics,s.prefs.avoid,description,transcript]);
 const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(raw));
 const key=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
 if(s.analyses[key]?.at>Date.now()-7*86400000)return s.analyses[key];
 if(inflight.has(key))return inflight.get(key);
 const job=(async()=>{
  let result=await localCall('analyze',{video:v,description,transcript,topics:s.prefs.topics,avoid:s.prefs.avoid},s.prefs.token);
  for(let n=0;result.pending&&n<50;n++){await new Promise(resolve=>setTimeout(resolve,2000));result=await localCall('result',{job:result.job},s.prefs.token);}
  if(result.pending)throw Error('Le moteur prend trop de temps ; réessaie plus tard.');
  result.at=Date.now();
  // Serialize storage changes without holding the mutation queue during inference.
  await mutate(async()=>{const fresh=await state();if(!fresh.prefs.enabled||!fresh.prefs.autoAI||fresh.generation!==s.generation)return;fresh.analyses[key]=result;const entries=Object.entries(fresh.analyses).sort((a,b)=>a[1].at-b[1].at).slice(-60);await chrome.storage.local.set({analyses:Object.fromEntries(entries)});});
  return result;
 })();inflight.set(key,job);try{return await job;}finally{inflight.delete(key);}
}
function mutate(fn){const next=queue.then(fn,fn);queue=next.catch(()=>{});return next;}
async function handle(m,sender){
 if(!allowed(sender))throw Error('Origine refusée');
 if(m.type==='options'){await chrome.runtime.openOptionsPage();return{ok:true};}
 if(m.type==='analyze')return analyze(m);
 if(m.type==='ping'){if(!isOptions(sender))throw Error('Réglages requis');const s=await state();return localCall('status',{},s.prefs.token);}
 return mutate(async()=>{
  const s=await state();
  if(m.type==='get')return isOptions(sender)?s:publicState(s);
  if(m.type==='save'){
   if(!isOptions(sender))throw Error('Réglages requis');const p=m.prefs||{};
   s.prefs={enabled:!!p.enabled,topics:String(p.topics||'').slice(0,1000),avoid:String(p.avoid||'').slice(0,1000),exploration:Math.max(0,Math.min(100,Number(p.exploration)||0)),autoAI:!!p.autoAI,token:String(p.token||'').slice(0,200)};
   await chrome.storage.local.set({prefs:s.prefs});return publicState(s);
  }
  if(m.type==='clear'){if(!isOptions(sender))throw Error('Réglages requis');await chrome.storage.local.set({history:[],feedback:{},analyses:{},generation:s.generation+1});return{ok:true};}
  if(m.type==='observe'&&s.prefs.enabled){
   const day=new Date().toISOString().slice(0,10);const known=new Set(s.history.map(x=>x.id+':'+x.day));
   for(const raw of (Array.isArray(m.videos)?m.videos:[]).slice(0,60)){const v=C.clean(raw);if(v&&v.title&&!known.has(v.id+':'+day)){s.history.push({...v,day,at:Date.now()});known.add(v.id+':'+day);}}
   s.history=C.prune(s.history);await chrome.storage.local.set({history:s.history});
  }
  if(m.type==='vote'&&/^[\w-]{11}$/.test(m.id||'')&&[1,0,-1].includes(m.value)){
   delete s.feedback[m.id];if(m.value)s.feedback[m.id]=m.value;
   s.feedback=Object.fromEntries(Object.entries(s.feedback).slice(-800));await chrome.storage.local.set({feedback:s.feedback});
  }
  return publicState(s);
 });
}
chrome.runtime.onMessage.addListener((message,sender,send)=>{handle(message,sender).then(data=>send({ok:true,data}),err=>send({ok:false,error:String(err.message||err)}));return true;});
