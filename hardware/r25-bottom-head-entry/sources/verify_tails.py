from pathlib import Path
import json,numpy as np,hashlib
O=Path(__file__).resolve().parent;T=json.loads((O/'tails/manifest.json').read_text());F=json.loads((O/'flex/selected_home/manifest.json').read_text());fr=json.loads((O.parent.parent.parent/F['parts'][0]['source_route']).read_text()) if False else None
# Independently derive underside port endpoints from frozen original contracts and prescribed rigid transform.
ROOT=O.parents[1];M=json.loads((O/'mechanics/manifest.json').read_text());R=np.array(M['transform']['R']);t=np.array(M['transform']['t_mm']);old=json.loads((ROOT/'work/r23-power-integration/mechanics_neck/endpoint_contract.json').read_text());ports=old['anchors']['upper']['ports'];ports+=json.loads((ROOT/'work/r23-power-integration/harness/flex_power_pair_v7/guide_occupancy/endpoint_contract.json').read_text())['anchors']['upper']['ports'];ports={p['id']:p for p in ports}
def unit(v):return v/np.linalg.norm(v)
def tangent(s,end=False):
 if s['type']=='line':return unit(np.array(s['end'])-s['start'])
 a=np.array(s['start'])-s['center'];b=np.array(s['end'])-s['center'];n=unit(np.cross(a,b));return unit(np.cross(n,b if end else a))
checks=[]
for row in T['routes']:
 s=row['segments'];rev=row['port']in ['P5','P6'];e=np.array(s[-1]['end']if rev else s[0]['start']);want=R@np.array(ports[row['port']]['free_exit_mm'])+t
 gaps=[float(np.linalg.norm(np.array(a['end'])-b['start']))for a,b in zip(s,s[1:])];turns=[float(np.linalg.norm(tangent(a,True)-tangent(b)))for a,b in zip(s,s[1:])]
 q=dict(port=row['port'],endpoint_error_mm=float(np.linalg.norm(e-want)),maximum_segment_gap_mm=max(gaps),maximum_tangent_vector_error=max(turns),minimum_radius_mm=row['minimum_radius_mm'],first_guide_straight_mm=row['guide_straight_mm'],original_electrical_endpoint_preserved=row['electrical_endpoint_preserved']);checks.append(q)
 assert q['endpoint_error_mm']<1e-8 and q['maximum_segment_gap_mm']<1e-7 and q['maximum_tangent_vector_error']<.002 and q['first_guide_straight_mm']>=12 and q['original_electrical_endpoint_preserved'],q
(O/'tail_validation.json').write_text(json.dumps(dict(status='31_FIXED_TAIL_ENDPOINT_AND_ANALYTIC_CONTINUITY_PASS',rows=checks,sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [O/'tails/manifest.json',O/'mechanics/manifest.json',Path(__file__)]}),indent=2)+'\n');print('TAILS31_PASS',max(r['maximum_tangent_vector_error']for r in checks))
