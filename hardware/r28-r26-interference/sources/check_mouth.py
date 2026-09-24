"""Recompute R26 mouth/lower-shell penetration on actual R26 selection."""
from pathlib import Path
import json,hashlib,sys,math
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps'),str(ROOT/'work/r18-leg-hip-covers/review')]
import numpy as np,trimesh,manifold3d as md
from motion_core import transforms
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sp=ROOT/'work/r26-cover-first/assembly_selection.json';S=json.loads(sp.read_text());by={p['name']:p for p in S['items']};a=by['R25_lower_head_shell_bottom_entry'];b=by['R12_mouth_load_carrier']
old=json.loads((ROOT/'work/r25-bottom-head-entry/mouth_check.json').read_text())
def load(p):
 path=ROOT/p.get('analysis_mesh',p['mesh']);assert sha(path)==p.get('analysis_mesh_sha256',p['mesh_sha256'])
 m=trimesh.load(path,force='mesh',process=p.get('mesh_load_process',True));v=np.array(m.vertices)@np.array(p['R']).T+np.array(p['t_mm']);solid=md.Manifold(md.Mesh64(np.array(v,dtype=float),np.array(m.faces,dtype=np.uint64)));assert solid.status()==md.Error.NoError
 return solid
shell=load(a);mouth=load(b);angles=np.arange(0,25.00001,.25);hits=[];sample=[]
for angle in angles:
 q={j['joint']:0.0 for j in S['joints']};q['mouth_candidate']=float(angle);ts=transforms(S['joints'],q);T=ts[b['link_frame']]
 moved=mouth.transform(T[:3]);v=float(abs((shell^moved).volume()))
 if v>1e-6:hits.append(dict(angle_deg=float(angle),common_mm3=v))
 if angle in [0,8.5,8.75,9,25]:sample.append(dict(angle_deg=float(angle),common_mm3=v))
assert hits and hits[0]['angle_deg']==8.75
for row in sample:
 prior=next((x for x in old['intersections']if x['a']==a['name']and x['b']==b['name']and x['angle_deg']==row['angle_deg']),None)
 if prior:assert abs(row['common_mm3']-prior['common_mm3'])<1e-5,(row,prior)
report=dict(status='R26_EXISTING_MOUTH_LOWER_SHELL_INTERFERENCE_CONFIRMED',source_selection_sha256=sha(sp),pair=[a['name'],b['name']],first_sampled_intersection_deg=hits[0]['angle_deg'],sample_step_deg=.25,representative_samples=sample,intersecting_samples=len(hits),max_sampled_intersection_mm3=max(x['common_mm3']for x in hits),scope='Nominal rigid geometry; this four-step gait commands mouth_candidate=0 deg; off-gait opening remains a real collision.',physical_approved=False,manufacturing_approved=False,sources={str(Path(__file__).relative_to(ROOT)):sha(__file__),a['mesh']:a['mesh_sha256'],b['mesh']:b['mesh_sha256']})
(OUT/'mouth_interference.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k]for k in ['status','first_sampled_intersection_deg','representative_samples','max_sampled_intersection_mm3']},ensure_ascii=False,indent=2))
