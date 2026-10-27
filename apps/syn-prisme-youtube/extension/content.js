(async()=>{
'use strict';
const C=SynCore;
const call=async m=>{const r=await chrome.runtime.sendMessage(m);if(!r?.ok)throw Error(r?.error||'Extension rechargée : recharge YouTube.');return r.data;};
let state=await call({type:'get'}),videos=[],currentId='',lastAI='',aiBusy=false,timer,closed=false;
const host=document.createElement('div');host.id='syn-prisme-panel';
host.style.cssText='position:fixed;right:16px;bottom:16px;z-index:2147483646;width:340px;max-width:calc(100vw - 32px);';
const shadow=host.attachShadow({mode:'closed'});document.documentElement.append(host);
shadow.innerHTML=`<style>
:host{font:14px/1.5 system-ui,sans-serif;color:#f0f2eb;color-scheme:dark}*{box-sizing:border-box}section{background:#15201e;border:1px solid #61726b;border-radius:18px;box-shadow:0 10px 45px #0007;overflow:hidden}header{display:flex;align-items:center;gap:8px;padding:12px 16px;background:#1e302a}header strong{flex:1;letter-spacing:.06em}button{cursor:pointer;background:#294039;color:inherit;border:1px solid #647b70;border-radius:8px;padding:5px 9px;font:inherit}button:hover{background:#3b594b}button:focus-visible,a:focus-visible{outline:3px solid #d2e7a5}main{padding:0 15px 14px;max-height:58vh;overflow:auto}p{margin:10px 0}small,.muted{color:#b9c7be;font-size:12px}h3{font-size:13px;color:#d2e7a5;margin:14px 0 6px}article{padding:9px 0;border-bottom:1px solid #34483e}a{color:#f4f4e7;text-decoration:none;display:block;font-weight:600}a:hover{text-decoration:underline}.actions{display:flex;gap:6px;margin-top:6px}.actions button{font-size:12px}.tag{color:#cce7a0}details{margin-top:12px}#analysis{white-space:pre-wrap;font-size:13px}#message{color:#ead4aa}#restore{width:100%;border-radius:18px;padding:10px}[hidden]{display:none!important}</style>
<section id="panel" aria-label="SYN Prisme"><header><strong>SYN / PRISME</strong><button id="settings" title="Ouvrir les réglages">⚙</button><button id="close" aria-label="Réduire le panneau">−</button></header><main><p class="muted">Ton regard sur le fil. Titres et chaînes uniquement pour le tri local.</p><p id="message" role="status"></p><h3>Dans cette page</h3><div id="ranked"></div><details><summary>Recul sur mon fil</summary><p id="stats"></p><small>Vidéos distinctes visibles par jour, 30 jours maximum, 800 entrées. Ce n’est ni ton temps de visionnage ni tout ton historique YouTube.</small></details><h3>Lecture IA de la vidéo ouverte</h3><div id="analysis">Facultative : active le raccordement dans les réglages.</div><p><button id="retry">Relancer la lecture IA</button></p><small>La pertinence n’est pas une note de vérité. Aucune vérification web automatique dans cette version.</small></main></section><button id="restore" hidden>SYN — ouvrir Prisme</button>`;
const $=id=>shadow.getElementById(id);
$('retry').onclick=()=>{lastAI='';scan();};
$('settings').onclick=()=>call({type:'options'}).catch(e=>{$('message').textContent=e.message;});
$('close').onclick=()=>{closed=true;$('panel').hidden=true;$('restore').hidden=false;};
$('restore').onclick=()=>{closed=false;$('panel').hidden=false;$('restore').hidden=true;};
function extract(){
 const result=new Map();
 for(const anchor of document.querySelectorAll('a[href*="/watch?v="],a[href^="/shorts/"]')){
  const id=C.idOf(anchor.href);if(!id)continue;
  const card=anchor.closest('ytd-rich-item-renderer,ytd-video-renderer,ytd-compact-video-renderer,yt-lockup-view-model,ytd-grid-video-renderer');if(!card)continue;
  const rect=card.getBoundingClientRect();if(rect.bottom<=0||rect.top>=innerHeight||rect.width===0)continue;
  const titleNode=card.querySelector('#video-title,h3,.yt-lockup-metadata-view-model__title');
  const title=(titleNode?.textContent||anchor.getAttribute('title')||'').trim();if(!title)continue;
  const channel=(card.querySelector('ytd-channel-name,#channel-name,.yt-content-metadata-view-model__metadata-row a')?.textContent||'').trim();
  result.set(id,{id,title:title.slice(0,300),channel:channel.slice(0,160),url:'https://www.youtube.com/watch?v='+id});
 }
 return [...result.values()].slice(0,60);
}
function active(){
 if(location.pathname!=='/watch')return null;const id=C.idOf(location.href);if(!id)return null;const renderedId=document.querySelector('ytd-watch-flexy')?.getAttribute('video-id');if(renderedId&&renderedId!==id)return null;
 const title=(document.querySelector('ytd-watch-metadata h1,#title h1')?.textContent||'').trim();
 const channel=(document.querySelector('ytd-watch-metadata #owner #channel-name,#owner ytd-channel-name')?.textContent||'').trim();
 if(!title)return null;
 return{id,title,channel,url:'https://www.youtube.com/watch?v='+id};
}
function draw(){
 $('message').textContent=state.prefs.enabled?'Tri expliqué, réglable avec ⚙.':'En pause : aucune nouvelle observation.';
 $('ranked').replaceChildren();
 const ranked=C.rank(videos,state.prefs,state.history,state.feedback).slice(0,5);
 for(const v of ranked){
  const article=document.createElement('article'),link=document.createElement('a'),why=document.createElement('small'),tag=document.createElement('p'),actions=document.createElement('div');
  link.textContent=v.title;link.href=v.url;tag.className='tag';tag.textContent=v.label;why.textContent=v.reason;actions.className='actions';
  for(const [text,value] of [['+ Pour moi',1],['− Moins',-1],['Annuler',0]]){const b=document.createElement('button');b.textContent=text;b.setAttribute('aria-pressed',String((state.feedback[v.id]||0)===value));b.onclick=async()=>{try{state=await call({type:'vote',id:v.id,value});draw();}catch(e){$('message').textContent=e.message;}};actions.append(b);}
  article.append(link,tag,why,actions);$('ranked').append(article);
 }
 if(!ranked.length)$('ranked').textContent='Aucune carte vidéo visible reconnue. Fais défiler le fil ; la mise en page YouTube peut varier.';
 const stats=C.summarize(state.history,state.feedback);
 $('stats').textContent=stats.n?`${stats.n} observations vidéo/jour · ${stats.channels.length} chaînes ou groupes identifiés. La plus présente : ${stats.channels[0][0]} (${stats.topShare} %). ${stats.votes} avis explicites. Ces chiffres décrivent seulement ce que l’extension a observé.`:'Pas encore assez de traces : explore quelques vidéos.';
}
async function maybeAI(v){
 if(!v||!state.prefs.autoAI||!state.prefs.enabled||aiBusy)return;
 const description=(document.querySelector('ytd-watch-metadata #description')?.textContent||'').trim().slice(0,4000);
 const transcript=[...document.querySelectorAll('ytd-transcript-segment-renderer .segment-text')].map(n=>n.textContent.trim()).join('\n').slice(0,12000);
 const sig=JSON.stringify([v.id,v.title,transcript,state.prefs.topics,state.prefs.avoid]);if(sig===lastAI)return;
 lastAI=sig;aiBusy=true;$('analysis').textContent='Analyse en cours…';const id=v.id;
 try{
  const r=await call({type:'analyze',video:v,description,transcript});
  if(currentId!==id||!state.prefs.autoAI||!state.prefs.enabled)return;
  $('analysis').textContent=`${r.provider} · ${r.model}\nBase : ${r.evidence}\n\n${r.analysis.relevance}\n\nÀ éprouver : ${r.analysis.question}\n\nLimites : ${r.analysis.limits}`;
 }catch(e){if(currentId===id)$('analysis').textContent='IA indisponible : '+e.message+' Le tri local reste actif.';}
 finally{aiBusy=false;}
}
async function scan(){
 if(document.hidden)return;
 try{
  state=await call({type:'get'});
  const v=active(),nextId=v?.id||'';
  if(nextId!==currentId){currentId=nextId;lastAI='';$('analysis').textContent=v?'En attente du raccordement IA…':'Ouvre une vidéo pour l’analyse automatique.';}
  if(!state.prefs.autoAI||!state.prefs.enabled)$('analysis').textContent='Analyse IA désactivée. Ouvre les réglages pour la configurer.';
  if(state.prefs.enabled){videos=extract();state=await call({type:'observe',videos});}else videos=[];
  draw();await maybeAI(v);
 }catch(e){$('message').textContent=e.message;}
}
const schedule=()=>{clearTimeout(timer);timer=setTimeout(scan,1200);};
document.addEventListener('yt-navigate-finish',()=>{currentId='';lastAI='';schedule();});
window.addEventListener('scroll',schedule,{passive:true});
document.addEventListener('visibilitychange',schedule);
// Poll slowly to handle SPA rendering and settings changes without watching video-frame mutations.
setInterval(scan,6000);schedule();
})();
