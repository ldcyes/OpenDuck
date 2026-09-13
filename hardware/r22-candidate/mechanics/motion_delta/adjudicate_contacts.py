"""Independent nominal STEP checks of five tiny triangulation overlaps."""
from pathlib import Path
import sys,json,hashlib,time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'work/r13-electronics/mechanics'))
from common import read,tf,common,volume,BRepExtrema_DistShapeShape,np
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
d=json.loads((OUT/'inputs.json').read_text());r=json.loads((OUT/'result.json').read_text());ix=json.loads((OUT/'pair_index.json').read_text());cache={};sources={}
def solid(i):
 if i not in cache:
  q=d['items'][i];p=ROOT/q['step'];h=sha(p);assert h==q['step_sha256'];sources[str(p.relative_to(ROOT))]=h;cache[i]=tf(read(p),np.array(q['R']),np.array(q['t_mm']))
 return cache[i]
rows=[]
for u in r['unresolved_spans']:
 e=u.get('exact',{})
 if(e.get('intersection_mm3')or 0)<=1e-5:continue
 i,j=ix['pairs'][u['pair_id']];a,b=d['items'][i],d['items'][j];print('STEP_START',u['pair_id'],a['name'],b['name'],flush=True);t=time.monotonic();sa,sb=solid(i),solid(j);v=abs(volume(common(sa,sb)));dist=BRepExtrema_DistShapeShape(sa,sb);dist.Perform();assert dist.IsDone();row={'pair_id':u['pair_id'],'a':a['name'],'b':b['name'],'mesh_intersection_mm3':e['intersection_mm3'],'STEP_intersection_mm3':v,'STEP_gap_mm':dist.Value(),'elapsed_s':time.monotonic()-t};rows.append(row);print(row,flush=True)
for p,h in sources.items():assert sha(ROOT/p)==h
result={'status':'EXACT_CAPTURED_STEP_ADJUDICATION','rows':rows,'sources':sources,'inputs_sha256':sha(OUT/'inputs.json'),'checker_sha256':sha(__file__),'limits':['Nominal BRep geometry only; zero volume contact does not qualify compression, tolerance or strength.','This adjudication supplements the triangulation report; the raw mesh evidence remains preserved.']}
(OUT/'contact_STEP_adjudication.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
