const $=id=>document.getElementById(id);let snapshot;
async function call(m){const r=await chrome.runtime.sendMessage(m);if(!r.ok)throw Error(r.error);return r.data;}
function report(e){$('status').textContent=e.message||String(e);}
async function load(){snapshot=await call({type:'get'});for(const k of Object.keys(SynCore.defaults)){const el=$(k);if(el.type==='checkbox')el.checked=snapshot.prefs[k];else el.value=snapshot.prefs[k];}update();const s=SynCore.summarize(snapshot.history,snapshot.feedback);$('stats').textContent=`${s.n} observations vidéo/jour · ${s.channels.length} chaînes ou groupes identifiés · ${s.votes} avis. Chaîne dominante : ${s.channels[0]?.[0]||'aucune'} (${s.topShare} %).`;}
function update(){$('amount').value=$('exploration').value;}
$('exploration').oninput=update;
$('prefs').onsubmit=async e=>{e.preventDefault();try{const prefs={};for(const k of Object.keys(SynCore.defaults)){const el=$(k);prefs[k]=el.type==='checkbox'?el.checked:el.value;}await call({type:'save',prefs});$('status').textContent='Réglages enregistrés. YouTube les applique sous quelques secondes.';}catch(e){report(e);}};
$('ping').onclick=async()=>{try{$('status').textContent='Connexion…';const r=await call({type:'ping'});$('status').textContent=`Relais joignable : ${r.provider} / ${r.model}. Le modèle sera appelé à la prochaine vidéo.`;}catch(e){report(e);}};
$('clear').onclick=async()=>{if(!confirm('Effacer les observations, tes avis et les analyses ?'))return;try{await call({type:'clear'});await load();$('status').textContent='Traces effacées. Mets Prisme en pause pour arrêter toute nouvelle collecte.';}catch(e){report(e);}};
$('export').onclick=async()=>{try{const s=await call({type:'get'});const {token,...prefs}=s.prefs;const data={exportedAt:new Date().toISOString(),scope:'Cartes visibles : pas un historique de visionnage',prefs,history:s.history,feedback:s.feedback};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='syn-prisme-traces.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){report(e);}};
load().catch(report);
