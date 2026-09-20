import sys, shutil, json, re, time
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
sys.path.insert(0, '/mnt/data')

from synergesis_glyph_protocol import GlyphAuditGraph, GlyphLedger
from synergesis_glyph_cognitive import GlyphAuditedCognitiveCore
from synergesis_glyph_research import GlyphAuditedAura
from synergesis_aegis import AegisSecurityGraph
from synergesis_roam import (
    SourceRegistry, SourcePolicy, RetrievedItem, RoamLimits, RoamRuntime,
    MethodLedger, SelectionConfig, UtilityWeights, SynRoam, SearchStep,
    make_method, ResearchQuestion, OutcomeMetrics
)
from synergesis_roam_adaptive import AdaptiveResearchMethodLearner, AdaptiveSelectionConfig

SOURCE = Path('/mnt/data/syn_roam_live_web_longrun_2026/live_web_corpus.json')
ROOT = Path('/mnt/data/syn_roam_live_web_longrun_2026_v2')
if ROOT.exists(): shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)
docs = json.loads(SOURCE.read_text(encoding='utf-8'))
(ROOT/'live_web_corpus.json').write_text(json.dumps(docs,indent=2,ensure_ascii=False),encoding='utf-8')

def toks(x): return set(re.findall(r'[a-z0-9-]+', x.lower()))

class Adapter:
    def __init__(self, cls): self.cls, self.wave = cls, 1
    def set_wave(self, wave): self.wave = wave
    def search(self, *, query, max_items):
        q=toks(query)
        pool=[d for d in docs if d['source_class']==self.cls and d['wave']<=self.wave]
        ranked=[]
        for d in pool:
            hay=toks(d['title']+' '+' '.join(d['tags']))
            overlap=len(q & hay)
            quality=sum(d[k] for k in ('evidence_strength','reproducibility','deployment','formal','limitation_explicit'))/5
            ranked.append((overlap,quality+.12*d['wave'],d['id'],d))
        ranked.sort(key=lambda z:(-z[0],-z[1],z[2]))
        cost={'academic':.14,'benchmark':.11,'runtime':.09,'delegation':.10,'field':.08}[self.cls]
        return tuple(RetrievedItem(d['url'],d['title'],json.dumps(d,sort_keys=True),self.cls,cost) for *_,d in ranked[:max_items])

graph=GlyphAuditGraph(GlyphLedger(ROOT/'glyphs.jsonl'))
core=GlyphAuditedCognitiveCore(ROOT/'semantic.jsonl',graph=graph,actor='ZÆL-0')
aura=GlyphAuditedAura(core,graph=graph)
security=AegisSecurityGraph(graph)
classes=('academic','benchmark','runtime','delegation','field')
registry=SourceRegistry(); adapters={}
for cls in classes:
    registry.register(SourcePolicy(cls,cls,('agent-security',),4,True)); adapters[cls]=Adapter(cls)
runtime=RoamRuntime(graph=graph,aura=aura,security_graph=security,source_registry=registry,adapters=adapters,limits=RoamLimits(5,10,2.5),actor='SYN-ROAM-LIVE-WEB-LONGRUN')
ledger=MethodLedger(ROOT/'method_outcomes.jsonl')
learner=AdaptiveResearchMethodLearner(
    ledger=ledger,
    config=SelectionConfig(0.0,True),
    adaptive_config=AdaptiveSelectionConfig(8,7,.24,6.0),
    graph=graph,actor='SYN-ROAM-LIVE-WEB-LONGRUN')
methods=[
    make_method(name='academic_probe',domain='agent-security',created_by='experiment',steps=(SearchStep('academic','explore','{question}',3),SearchStep('academic','challenge','{question} {hypothesis}',2))),
    make_method(name='benchmark_probe',domain='agent-security',created_by='experiment',steps=(SearchStep('benchmark','explore','{question}',3),SearchStep('benchmark','challenge','{question} {hypothesis}',2))),
    make_method(name='runtime_probe',domain='agent-security',created_by='experiment',steps=(SearchStep('runtime','explore','{question}',2),SearchStep('field','challenge','{question} {hypothesis}',2))),
    make_method(name='delegation_probe',domain='agent-security',created_by='experiment',steps=(SearchStep('delegation','explore','{question}',3),SearchStep('delegation','challenge','{question} {hypothesis}',2))),
    make_method(name='triangulated',domain='agent-security',created_by='experiment',steps=(SearchStep('academic','explore','{question}',2),SearchStep('benchmark','challenge','{question} {hypothesis}',2),SearchStep('runtime','explore','{question}',2),SearchStep('delegation','challenge','{question} {hypothesis}',2))),
]
for m in methods: learner.register(m)
roam=SynRoam(learner=learner,runtime=runtime,utility_weights=UtilityWeights(1,.55,.85,.9,1,.75,.45))
questions=[
('stop indirect prompt injection steering consequential tool actions','provenance plus deterministic pre-execution policy'),
('defend long-term memory against delayed poisoning and laundering','origin authority must not amplify during consolidation'),
('prevent confused-deputy and delegation privilege escalation','delegation must attenuate privileges'),
('validate signed authorization receipts safely','signature alone is insufficient without replay revocation scope'),
('benchmark security without rewarding deny-everything','measure attacks false blocks provenance and utility'),
('separate application claims from runtime ground truth','runtime telemetry should outrank AI assertions'),
('make provenance useful rather than just logging','causality must connect evidence policy execution impact'),
('operate offline while credentials may be revoked','reconcile without rewriting history'),
('defend against adaptive multi-turn attackers','evaluate repeated adaptive attacks'),
('contain sandbox and egress failures','capability boundaries must remain independent of model behavior'),
]
by_url={d['url']:d for d in docs}
challenge_tags={'laundering','over-refusal','adaptive-attacker','field-incident','field-issue','revocation','replay','compositional-attack','dormant-trigger','privilege-escalation','provenance-erasure'}

def selected_docs(session):
    out=[]; seen=set()
    for ex in session.executions:
        for eid in ex.evidence_ids:
            ev=aura.research.store.get(eid); d=by_url.get(ev.source)
            if d and d['id'] not in seen: seen.add(d['id']); out.append(d)
    return out

def assess(session,qtext):
    ds=selected_docs(session); total=sum(ex.item_count for ex in session.executions)
    if not ds: return OutcomeMetrics(0,0,0,0,0,0,min(1,session.total_cost_units/2.5)),ds
    q=toks(qtext); rel=[]
    for d in ds:
        hay=toks(d['title']+' '+' '.join(d['tags'])); rel.append(len(q & hay)/max(1,len(q)))
    verified=sum(.55*d['evidence_strength']+.25*d['formal']+.20*d['reproducibility'] for d in ds)/len(ds)
    novelty=len(ds)/max(1,total)
    contradiction=min(1,.15+sum(any(t in challenge_tags for t in d['tags']) for d in ds)/len(ds))
    diversity=len({d['source_class'] for d in ds})/len(classes)
    limitations=sum(d['limitation_explicit'] for d in ds)/len(ds)
    calibration=min(1,.40*(sum(rel)/len(rel))+.35*diversity+.25*limitations)
    deployment=sum(d['deployment'] for d in ds)/len(ds); freshness=sum(d['wave']/3 for d in ds)/len(ds)
    transfer=min(1,.7*deployment+.3*freshness)
    redundancy=1-len(ds)/max(1,total); cost=min(1,session.total_cost_units/2.5)
    return OutcomeMetrics(verified,novelty,contradiction,calibration,transfer,redundancy,cost),ds

rows=[]; t0=time.perf_counter()
for cycle in range(1,121):
    wave=1 if cycle<=40 else 2 if cycle<=80 else 3
    for a in adapters.values(): a.set_wave(wave)
    qtext,hyp=questions[(cycle-1)%len(questions)]
    rq=ResearchQuestion.create(domain='agent-security',question=f'{qtext} [cycle {cycle}]',hypothesis=hyp)
    method=learner.select(rq); session=runtime.run(question=rq,method=method); metrics,ds=assess(session,qtext); outcome=roam.evaluate(session,metrics)
    rows.append(dict(cycle=cycle,wave=wave,method=method.name,utility=outcome.utility,verified=metrics.verified_yield,novelty=metrics.novelty_yield,contradiction=metrics.contradiction_yield,calibration=metrics.calibration_gain,operational_transfer_proxy=metrics.predictive_value,redundancy=metrics.redundancy,cost=metrics.normalized_cost,doc_count=len(ds),documents=';'.join(d['id'] for d in ds)))
elapsed=time.perf_counter()-t0

df=pd.DataFrame(rows); df.to_csv(ROOT/'iterations.csv',index=False)
summary=df.groupby(['wave','method']).agg(selections=('cycle','count'),mean_utility=('utility','mean'),mean_verified=('verified','mean'),mean_calibration=('calibration','mean'),mean_transfer=('operational_transfer_proxy','mean'),mean_redundancy=('redundancy','mean')).reset_index(); summary.to_csv(ROOT/'method_summary.csv',index=False)
windows=[]
for start in range(1,121,10):
    sub=df[(df.cycle>=start)&(df.cycle<=start+9)]; cnt=sub.method.value_counts().to_dict(); row={'cycles':f'{start}-{start+9}','wave':int(sub.wave.iloc[0]),'mean_utility':sub.utility.mean()}; row.update({m.name:cnt.get(m.name,0) for m in methods}); windows.append(row)
windows=pd.DataFrame(windows); windows.to_csv(ROOT/'selection_windows.csv',index=False)
exp=df.assign(documents=df.documents.str.split(';')).explode('documents'); id_to_class={d['id']:d['source_class'] for d in docs}; exp['source_class']=exp.documents.map(id_to_class); exposure=exp[exp.documents!=''].groupby(['wave','source_class']).size().reset_index(name='retrievals'); exposure.to_csv(ROOT/'source_exposure.csv',index=False)

plt.figure(figsize=(11,5))
for name in [m.name for m in methods]:
    sub=df[df.method==name]; plt.scatter(sub.cycle,sub.utility,s=22,label=name)
plt.axvline(40.5,linestyle='--'); plt.axvline(80.5,linestyle='--'); plt.xlabel('Cycle'); plt.ylabel('Observed research utility'); plt.title('SYN-ROAM: 120-cycle replay of current Internet evidence'); plt.legend(); plt.tight_layout(); plt.savefig(ROOT/'utility_by_cycle.png',dpi=170); plt.close()
plt.figure(figsize=(10,5))
for name in [m.name for m in methods]:
    xs=[];ys=[]
    for start in range(1,121,10):
        sub=df[(df.cycle>=start)&(df.cycle<=start+9)];xs.append(start+4.5);ys.append((sub.method==name).sum())
    plt.plot(xs,ys,marker='o',label=name)
plt.axvline(40.5,linestyle='--');plt.axvline(80.5,linestyle='--');plt.xlabel('10-cycle window midpoint');plt.ylabel('Selections per 10 cycles');plt.title('SYN-ROAM attention shifts as source landscape expands');plt.legend();plt.tight_layout();plt.savefig(ROOT/'method_selection_shift.png',dpi=170);plt.close()

checkpoint=graph.ledger.verify(); report={'current_web_sources':len(docs),'cycles':len(df),'elapsed_seconds':elapsed,'waves':{'1':'May-June core research/runtime','2':'July memory/adaptive benchmarks','3':'August-September runtime/delegation/field evidence'},'wave_most_selected':{},'wave_best_mean_utility':{},'final_method_stats':{m.name:{'observations':ledger.stats(m.method_id).observations,'mean_utility':ledger.stats(m.method_id).mean_utility} for m in methods},'glyph_events':checkpoint.event_count,'merkle_root':checkpoint.merkle_root,'scoring_note':'Utility is an explicit operational proxy over real retrieved sources, not a scientific ground-truth quality score or real future-prediction measurement.'}
for w in (1,2,3):
    s=summary[summary.wave==w]; report['wave_most_selected'][str(w)]=s.sort_values('selections',ascending=False).iloc[0].method; report['wave_best_mean_utility'][str(w)]=s.sort_values('mean_utility',ascending=False).iloc[0].method
(ROOT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('=== SYN-ROAM LONG REAL-WEB REPLAY ===')
print('sources',len(docs),'cycles',len(df),'elapsed',round(elapsed,3))
print('\nWINDOWS\n',windows.to_string(index=False))
print('\nSUMMARY\n',summary.to_string(index=False))
print('\nEXPOSURE\n',exposure.to_string(index=False))
print('\nMOST_SELECTED',report['wave_most_selected'])
print('BEST_UTILITY',report['wave_best_mean_utility'])
print('GLYPH_EVENTS',checkpoint.event_count)
print('MERKLE',checkpoint.merkle_root)
