from pathlib import Path
import sys,json,time,hashlib
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).parent
sys.path[:0]=[str(ROOT/'work/r3-mechanics/python-deps'),str(ROOT/'work/r13-electronics/mechanics')]
import common as c
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
S=json.loads((O/'rigid_inputs.json').read_text());by={p['name']:p for p in S['items']};pairs=json.loads((O/'motion/rigid_final/result.json').read_text())['near_invariant_pairs'];rows=[]
for p in pairs:
 if p['status']=='computed':continue
 shapes=[];sources={};t=time.monotonic()
 for n in [p['a'],p['b']]:
  q=by[n];shapes.append(c.tf(c.read(ROOT/q['step']),q['R'],q['t_mm']));sources[q['step']]=hashlib.sha256((ROOT/q['step']).read_bytes()).hexdigest()
 d=BRepExtrema_DistShapeShape(*shapes);d.Perform();assert d.IsDone()
 rows.append(dict(pair_id=p['pair_id'],a=p['a'],b=p['b'],native_gap_mm=d.Value(),intersection_mm3=abs(c.volume(c.common(*shapes))),elapsed_s=time.monotonic()-t,sources=sources));print(rows[-1],flush=True)
(O/'gap_retry.json').write_text(json.dumps(dict(rows=rows,source_result_sha256=hashlib.sha256((O/'motion/rigid_final/result.json').read_bytes()).hexdigest()),indent=2)+'\n')
