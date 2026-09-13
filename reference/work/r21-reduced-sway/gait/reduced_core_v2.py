"""R21 diagnostic IK using immutable final R20 material and nominal mass."""
from pathlib import Path
import sys,json,hashlib,time,itertools
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'work/python-deps'),str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps'),str(ROOT/'work/r18-leg-hip-covers/review'),str(ROOT/'work/r20-walking-fix/dynamics'),str(ROOT/'work/r20-walking-fix/geometry')]
import numpy as np
import trimesh,manifold3d as md
from scipy.spatial.transform import Rotation
from scipy.spatial import ConvexHull
from scipy.optimize import minimize
from motion_core import Sources,transforms,apply_points
from quasistatic import StaticEvaluator
from collision_guard import LegBatteryGuard
SOURCES=Sources(ROOT);SOURCES.bind(__file__)
A=SOURCES.json('work/r20-walking-fix/assembly_final/assembly_selection.json');J=A['joints'];names=[j['joint']for j in J];LEGS=[n for n in names if n.startswith(('left_','right_'))];by={r['name']:r for r in A['items']}
MP=SOURCES.bind('work/r20-walking-fix/dynamics/release_v4/verified_models/current_robot_contact4.xml');CP=SOURCES.bind('work/r20-walking-fix/dynamics/release_v4/verified_models/model_contract_contact4.json');EV=StaticEvaluator(MP,CP)
assert abs(sum(EV.m.body_mass)-4.1950935502695295)<1e-12
GUARD=LegBatteryGuard('work/r20-walking-fix/assembly_final/assembly_selection.json')
# Add the two repaired left-hip pairs to the original twelve real leg/shell pairs.
for name in ['R20_left_hip_rail_offset','left_hip_roll_motor','left_hip_roll_fixed']:
 row=by[name];p=GUARD.sources.bind(row['mesh'],row['mesh_sha256']);mesh=trimesh.load(p,force='mesh');V=np.asarray(mesh.vertices)@np.array(row['R']).T+row['t_mm'];solid=md.Manifold(md.Mesh64(V.copy(),np.asarray(mesh.faces,np.uint64)));assert solid.status()==md.Error.NoError
 bb=np.array([V.min(0),V.max(0)]);GUARD.objects[name]=dict(vertices=V,solid=solid,corners=np.array(list(itertools.product(*zip(bb[0],bb[1])))))
GUARD.pairs += [('left_hip_roll_motor','R20_left_hip_rail_offset'),('left_hip_roll_fixed','R20_left_hip_rail_offset')]
feet={}
for r in A['items']:
 if '_TPU_contact_pad_W130'not in r['name']:continue
 m=trimesh.load(SOURCES.bind(r['mesh'],r['mesh_sha256']),force='mesh');V=np.asarray(m.vertices)@np.array(r['R']).T+r['t_mm'];bottom=V[V[:,2]<V[:,2].min()+1e-4];poly=bottom[ConvexHull(bottom[:,:2]).vertices];feet[r['link_frame']]=dict(vertices=V,sole=bottom,polygon=poly)
hr=by['R11_45_top_head_shell'];hm=trimesh.load(SOURCES.bind(hr['mesh'],hr['mesh_sha256']),force='mesh');hv=np.asarray(hm.vertices)@np.array(hr['R']).T+hr['t_mm'];HEAD_POINT=np.asarray(hm.center_mass)@np.array(hr['R']).T+hr['t_mm'];HEAD_LINK=hr['link_frame']
BOUNDS=[(-np.deg2rad(30),np.deg2rad(30))if'yaw'in n else(-np.pi/4,np.pi/4)for n in LEGS]
def zero():return dict.fromkeys(names,0.)
def qdict(x):q=zero();q.update(zip(LEGS,np.rad2deg(x)));return {k:float(v)for k,v in q.items()}
def to_m(B):B=np.array(B);B[:3,3]/=1000;return B.tolist()
def head_point(B,T):return apply_points(np.array([HEAD_POINT]),B@T[HEAD_LINK])[0]
def make_stance(toe,bend,split=0.):
 q=zero()
 for side,sign in [('left',1),('right',-1)]:q[side+'_hip_yaw']=-sign*toe;q[side+'_hip_pitch']=sign*(bend/2+split);q[side+'_knee']=sign*bend;q[side+'_ankle']=sign*(bend/2-split)
 T=transforms(J,q);pol={l:apply_points(f['polygon'],T[l])for l,f in feet.items()};B=np.eye(4);B[2,3]=-np.vstack(list(pol.values()))[:,2].mean();targets={l:B@T[l]for l in feet};pp={l:apply_points(feet[l]['polygon'],targets[l])for l in feet};gap=float(pp['ankle_left'][:,1].min()-pp['ankle_right'][:,1].max())
 return dict(id=f'toe{toe:g}_bend{bend:g}_split{split:g}',toe_deg=toe,bend_deg=bend,hip_ankle_pitch_split_deg=split,initial_q_HOME_delta_deg=q,initial_base_transform_m=to_m(B),foot_target_transforms_mm={l:t.tolist()for l,t in targets.items()},initial_head_point_world_mm=head_point(B,T).tolist(),foot_area_centers_mean_world_mm={l:p.mean(0).tolist()for l,p in pp.items()},foot_inner_Y_gap_mm=gap,foot_flatness_span_mm=float(np.ptp(np.vstack(list(pp.values()))[:,2])))
def evaluate(q,targets,support):
 T=transforms(J,q);B=targets[support]@np.linalg.inv(T[support]);other='ankle_right'if support=='ankle_left'else'ankle_left';err=np.linalg.inv(targets[other])@B@T[other];eq=np.r_[err[:3,3]/100,Rotation.from_matrix(err[:3,:3]).as_rotvec()];static=EV.evaluate(q,to_m(B),support);rpy=Rotation.from_matrix(B[:3,:3]).as_euler('xyz');return dict(q=q,T=T,B=B,eq=eq,static=static,rpy=rpy,head=head_point(B,T))
def endpoint(stance,seedq,support='ankle_left',roll_cap_deg=25.,head_side_cap_mm=150.,yaw_cap_deg=20.,maxiter=160):
 targets={l:np.array(t)for l,t in stance['foot_target_transforms_mm'].items()};initial=np.deg2rad([stance['initial_q_HOME_delta_deg'][n]for n in LEGS]);seed=np.deg2rad([seedq[n]for n in LEGS]);seed=np.clip(seed,np.array(BOUNDS)[:,0],np.array(BOUNDS)[:,1]);memo={};h0=np.array(stance['initial_head_point_world_mm']);start=time.time()
 def ev(x):
  key=x.tobytes()
  if memo.get('key')!=key:
   e=evaluate(qdict(x),targets,support);e['gaps']=GUARD.gaps(e['q'],cap_mm=3.);memo.update(key=key,e=e)
  return memo['e']
 def ine(x):
  e=ev(x);return np.r_[.85-np.array(list(e['static']['utilization'].values())),(e['static']['COP_margin_mm']-8.)/100,(e['gaps']-2.3)/10,np.deg2rad([roll_cap_deg,25.,yaw_cap_deg])-e['rpy'],np.deg2rad([roll_cap_deg,25.,yaw_cap_deg])+e['rpy'],(head_side_cap_mm-abs(e['head'][1]-h0[1]))/100]
 def objective(x):
  e=ev(x);return (e['rpy'][0]/np.deg2rad(12))**2+.25*(e['rpy'][2]/np.deg2rad(12))**2+.5*((e['head'][1]-h0[1])/100)**2+.03*(e['B'][1,3]/30)**2+.002*np.sum((x-initial)**2)
 sol=minimize(objective,seed,method='SLSQP',bounds=BOUNDS,constraints=[dict(type='eq',fun=lambda x:ev(x)['eq']),dict(type='ineq',fun=ine)],options=dict(maxiter=maxiter,ftol=3e-10));e=ev(sol.x);v=bool(abs(e['eq']).max()<1e-6 and ine(sol.x).min()>=-1e-5)
 return dict(support_link=support,numerically_feasible=v,solver_success=bool(sol.success),solver_message=sol.message,iterations=int(sol.nit),seconds=time.time()-start,q_HOME_delta_deg=e['q'],base_transform_m=to_m(e['B']),body_rpy_deg=np.rad2deg(e['rpy']).tolist(),root_lateral_mm=float(e['B'][1,3]),head_lateral_from_stance_mm=float(e['head'][1]-h0[1]),head_point_world_mm=e['head'].tolist(),closure_scaled_residual=float(abs(e['eq']).max()),minimum_inequality=float(ine(sol.x).min()),static=e['static'],guard_gaps_mm=e['gaps'].tolist(),guard_pairs=[list(p)for p in GUARD.pairs],roll_cap_deg=roll_cap_deg,yaw_cap_deg=yaw_cap_deg,head_side_cap_mm=head_side_cap_mm,objective=float(objective(sol.x)))
