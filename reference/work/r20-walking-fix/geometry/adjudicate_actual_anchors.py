"""Independently transform original STEP at actual integration anchor witnesses."""
from pathlib import Path
import sys,json,hashlib,argparse
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'work/r13-electronics/mechanics'),str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import common as c
import numpy as np
from scipy.spatial.transform import Rotation
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID

def independent_FK(joints,q):
 T={'trunk_base':np.eye(4),'MULTI_LINK_FLEX_HARNESS':np.eye(4)};pending=list(joints)
 while pending:
  ready=[j for j in pending if j['parent_link']in T]
  if not ready:raise ValueError('INVALID_KINEMATIC_TREE')
  for j in ready:
   axis=np.array(j['axis_trunk']);axis/=np.linalg.norm(axis);R=Rotation.from_rotvec(axis*np.deg2rad(q.get(j['joint'],0))).as_matrix();p=np.array(j['pivot_trunk_mm']);H=np.eye(4);H[:3,:3]=R;H[:3,3]=p-R@p;T[j['child_link']]=T[j['parent_link']]@H;pending.remove(j)
 return T

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--selection',required=True);ap.add_argument('--boxes',required=True);ap.add_argument('--label',required=True);a=ap.parse_args();sources={}
 def bind(p,h=None):
  p=Path(p);p=p if p.is_absolute()else ROOT/p;actual=hashlib.sha256(p.read_bytes()).hexdigest()
  if h and actual!=h:raise ValueError(('SOURCE_CHANGED',str(p)))
  sources[str(p.relative_to(ROOT))]=actual;return p
 def read(p):return json.loads(bind(p).read_text())
 sel=read(a.selection);by={r['name']:r for r in sel['items']};raw=read(a.boxes);route=read('work/r13-electronics/pdb/feed_routes/head_pillar_front_v6/manifest.json');tail=read('work/r13-electronics/pdb/HEAD3/formed_tails/manifest.json');rows=[]
 for hit in raw['raw_positive_actual_anchors']:
  names=[hit['a'],hit['b']];T=independent_FK(sel['joints'],hit['q_HOME_delta_deg']);shapes=[]
  for name in names:
   r=by[name];bind(r['mesh'],r['mesh_sha256']);s=c.tf(c.read(bind(r['step'],r['step_sha256'])),r['R'],r['t_mm']);H=T[r['link_frame']];s=c.tf(s,H[:3,:3],H[:3,3])
   if not BRepCheck_Analyzer(s).IsValid():raise ValueError(('INVALID_STEP',name))
   ex=TopExp_Explorer(s,TopAbs_SOLID);vol=[]
   while ex.More():vol.append(c.volume(ex.Current()));ex.Next()
   if not vol or min(vol)<=0:raise ValueError(('NONPOSITIVE_STEP',name))
   shapes.append(s)
  A,B=shapes;v=float(c.volume(c.common(A,B)));dist=BRepExtrema_DistShapeShape(A,B);dist.Perform()
  classification='UNCLASSIFIED_REQUIRES_REVIEW';detail={}
  if set(names)in [set(['neck_pitch_motor',n])for n in ['R13p3_neck_pitch_active_through_M3_ears','R13p3_neck_pitch_idler_through_M3_ears']]:
   classification='SOURCE_MESH_MICRO_RESIDUE_ORIGINAL_STEP_ZERO_AT_THIS_ACTUAL_ANCHOR'if v<=1e-9 else 'ORIGINAL_STEP_POSITIVE_REQUIRES_REPAIR_REVIEW'
   detail['limits']='This exact numerical anchor only; no general rotating-interface clearance or physical fit approval.'
  else:
   for n in [1,2]:
    an=f'PDB_H3__HEAD3_W{n}_INSULATED_STRAIGHT8_MAX';bn=f'SP{n+2}_HEAD_PILLAR_FRONT_V6'
    if set(names)!={an,bn}:continue
    rr=next(r for r in route['parts']if r['name']==bn);tt=next(r for r in tail['parts']if r['name']==f'HEAD3_W{n}_INSULATED_STRAIGHT8_MAX')
    assert rr['pad']==f'W{n}'and rr['board']=='PDB_H'and rr['source_node']==f'SP{n+2}'
    assert rr['sha256_STEP']==by[bn]['step_sha256']and tt['sha256_STEP']==by[an]['step_sha256']
    classification='SAME_WIRE_TAIL_AND_HOME_ROUTE_REFERENCE_OVERLAP';detail=dict(board=rr['board'],pad=rr['pad'],source_node=rr['source_node'],limits='Two representations of one conductor, not distinct rigid materials. Wire deformation/bend/lifetime remain unqualified.')
  rows.append(dict(pair=names,time_s=hit['time_s'],q_HOME_delta_deg=hit['q_HOME_delta_deg'],raw_mesh_common_mm3=hit['common_mm3'],independent_original_STEP_common_mm3=v,independent_original_STEP_gap_mm=float(dist.Value()),classification=classification,detail=detail,source_part_rows={n:by[n]for n in names}));print(names,v,classification,flush=True)
 bind(__file__)
 for p,h in sources.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
 out=Path(__file__).resolve().parent/a.label;out.mkdir(exist_ok=True);d=dict(status='NAMED_ACTUAL_ANCHORS_ONLY_NOT_ALL_MOTOR_INTERFACES_QUALIFIED',physical_approved=False,rows=rows,unclassified_or_positive_original_material=[r for r in rows if r['classification']in ['UNCLASSIFIED_REQUIRES_REVIEW','ORIGINAL_STEP_POSITIVE_REQUIRES_REPAIR_REVIEW']],sources=sources);(out/'actual_anchor_adjudication.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
