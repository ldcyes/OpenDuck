"""Pair exact controller phase intervals; this does not create actual motion."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();sources={}
def read(p,h):
 assert sha(ROOT/p)==h,p;sources[p]=h;return json.loads((ROOT/p).read_text())
a=read('work/r20-walking-fix/dynamics/retimed_segments_v2.json','0c287a4def1d8674b032e53e4b43bb0800e8c585d5281e7b0dced48dfc53430d')
b=read('work/r21-reduced-sway/gait/phase_boundaries_4steps_v3.json','77b27deeee5e699b29b2181acefa812af552f1a6d060c7c646601022a345cd2f')
for p,h in b['sources'].items():assert sha(ROOT/p)==h;sources[p]=h
phases=[]
for s in a['trajectories']['forward']['segments']:
 if phases and phases[-1]['name']==s['phase']:
  assert abs(phases[-1]['end_s']-s['start_s'])<1e-10;phases[-1]['end_s']=s['end_s']
 else:phases.append(dict(name=s['phase'],start_s=s['start_s'],end_s=s['end_s']))
assert [p['name']for p in phases]==[p['name']for p in b['rows']]
rows=[dict(name=p['name'],baseline_s=[p['start_s'],p['end_s']],candidate_s=[q['start_s'],q['end_s']])for p,q in zip(phases,b['rows'])]
for label in ['baseline_s','candidate_s']:
 assert rows[0][label][0]==0
 for i,r in enumerate(rows):
  assert r[label][1]>r[label][0]
  if i:assert r[label][0]==rows[i-1][label][1]
sources[str(Path(__file__).relative_to(ROOT))]=sha(__file__)
result=dict(status='REFERENCE_PHASE_PAIRING_ONLY_WAITING_COMPLETE_ACTUAL_TRACE',semantics='Exact controller/reference phases; not measured contact-force event alignment.',rows=rows,baseline_reference_duration_s=rows[-1]['baseline_s'][1],candidate_reference_duration_s=rows[-1]['candidate_s'][1],final_actual_map_pending=True,physical_approved=False,sources=sources)
(HERE/'phase_reference_mapping_v3.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('REFERENCE_PHASES_PAIRED',len(rows))
