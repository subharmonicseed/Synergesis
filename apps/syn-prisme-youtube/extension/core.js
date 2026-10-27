/* Shared pure functions: browser, worker and Node tests. */
(function(root){
'use strict';
const defaults={enabled:true,topics:'',avoid:'',exploration:30,autoAI:false,token:''};
const norm=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
const terms=s=>String(s||'').split(',').map(x=>norm(x.trim())).filter(Boolean).slice(0,30);
const idOf=s=>{try{const u=new URL(s,'https://www.youtube.com');if(u.hostname!=='www.youtube.com')return null;const id=u.pathname==='/watch'?u.searchParams.get('v'):u.pathname.match(/^\/shorts\/([^/]+)$/)?.[1];return /^[\w-]{11}$/.test(id||'')?id:null;}catch{return null;}};
function clean(v){if(!v||!/^[\w-]{11}$/.test(v.id||''))return null;return{id:v.id,title:String(v.title||'').slice(0,300),channel:String(v.channel||'').slice(0,160),url:'https://www.youtube.com/watch?v='+v.id};}
function score(v,p,history=[],feedback={}){
 const text=norm(v.title+' '+v.channel),positive=terms(p.topics).filter(t=>text.includes(t)),negative=terms(p.avoid).filter(t=>text.includes(t));
 const known=!!v.channel&&history.some(h=>h.channel===v.channel&&h.id!==v.id), vote=feedback[v.id]||0;
 const affinity=Math.min(60,positive.length*20)-Math.min(90,negative.length*35)+vote*45;
 const novelty=known?0:Number(p.exploration||0)*0.6;
 return {value:affinity+novelty, label:vote<0?'Moins pour moi':negative.length?'À réduire':positive.length?'Dans tes thèmes':'Hors mots-clés',
 reason:[positive.length?'Correspondances : '+positive.join(', '):'Aucun mot-clé retrouvé dans le titre ou la chaîne',negative.length?'À réduire : '+negative.join(', '):'',!known&&v.channel?'Chaîne nouvelle dans les traces locales':'',vote?'Ton avis explicite pris en compte':''].filter(Boolean).join(' · ')};
}
function rank(videos,p,history,feedback){return [...videos].map(v=>({...v,...score(v,p,history,feedback)})).sort((a,b)=>b.value-a.value);}
function summarize(history,feedback={}){
 const by=new Map();for(const h of history){const k=h.channel||'Chaîne non identifiée';by.set(k,(by.get(k)||0)+1);}
 const channels=[...by].sort((a,b)=>b[1]-a[1]);const n=history.length;
 return{n,channels,topShare:n&&channels.length?Math.round(channels[0][1]/n*100):0,votes:Object.values(feedback).filter(x=>x===1||x===-1).length};
}
function prune(history,now=Date.now()){return history.filter(x=>Number.isFinite(x.at)&&x.at>now-30*86400000).slice(-800);}
root.SynCore={defaults,norm,terms,idOf,clean,score,rank,summarize,prune};
if(typeof module!=='undefined')module.exports=root.SynCore;
})(globalThis);
