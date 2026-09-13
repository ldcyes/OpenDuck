"""Resolve sub-micrometre STL bearing gaps independently on captured STEP."""
from pathlib import Path
import sys,json,hashlib
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'work/r13-electronics/mechanics'))
from common import read,tf,common,volume,BRepExtrema_DistShapeShape,np
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
d=json.loads((OUT/'inputs.json').read_text());r=json.loads((OUT/'result.json').read_text());ix=json.loads((OUT/'pair_index.json').read_text());rows=[];sources={}
for u in r['unresolved_spans']:
 e=u['exact']
 if e.get('intersection_mm3')is not None or e['status']!='computed' or not(0<e['gap_mm']<1e-4):continue
 a,b=[d['items'][i]for i in ix['pairs'][u['pair_id']]];assert a['name']=='R22_Entry_PCB_FINISHED'and b['name']in [f'R22_Entry_H{i}_washer'for i in range(1,5)]
 shapes=[]
 for q in [a,b]:
  p=ROOT/q['step'];assert sha(p)==q['step_sha256'];sources[q['step']]=sha(p);shapes.append(tf(read(p),np.array(q['R']),np.array(q['t_mm'])))
 commonvol=abs(volume(common(*shapes)));dist=BRepExtrema_DistShapeShape(*shapes);dist.Perform();assert dist.IsDone()and commonvol<1e-10
 rows.append({'pair_id':u['pair_id'],'a':a['name'],'b':b['name'],'STL_gap_mm':e['gap_mm'],'STEP_gap_mm':dist.Value(),'STEP_intersection_mm3':commonvol,'status':'NOMINAL_ZERO_VOLUME_WASHER_TO_PCB_BEARING_CONTACT'})
assert len(rows)==4
(OUT/'bearing_STEP_supplement.json').write_text(json.dumps({'status':'FOUR_SUB_THRESHOLD_MESH_GAPS_ADJUDICATED_AS_NOMINAL_BEARING_CONTACTS','rows':rows,'sources':sources,'inputs_sha256':sha(OUT/'inputs.json'),'original_result_sha256':sha(OUT/'result.json'),'checker_sha256':sha(__file__)},ensure_ascii=False,indent=2)+'\n');print(rows)
