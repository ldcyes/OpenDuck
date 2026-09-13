"""Actual-FK stance families and fixed-sole static support endpoints (no release)."""
from pathlib import Path
import sys,json,hashlib,time
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'work/python-deps'),str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps'),str(ROOT/'work/r19-walking-simulation/path_support'),str(ROOT/'work/r20-walking-fix/dynamics')]
from kinematic_inputs import J,A,M,feet,transforms,apply_points,zero,to_m,G
from quasistatic import StaticEvaluator
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.optimize import minimize
EV=StaticEvaluator();LEGS=[j['joint']for j in J if j['joint'].startswith(('left_','right_'))];names=[j['joint']for j in J]

def qdict(x):d=zero();d.update(zip(LEGS,np.rad2deg(x).tolist()));return d

def polygon_centroid(poly):
 x=poly[:,0];y=poly[:,1];xn=np.roll(x,-1);yn=np.roll(y,-1);c=x*yn-xn*y;A=c.sum()/2;return np.array([((x+xn)*c).sum()/(6*A),((y+yn)*c).sum()/(6*A),poly[:,2].mean()])
centers={l:polygon_centroid(f['polygon'])for l,f in feet.items()}

bounds=[(-np.deg2rad(30),np.deg2rad(30))if 'yaw'in n else(-np.pi/4,np.pi/4)for n in LEGS]

def make_stance(toe,bend):
 q=zero()
 for side,sign in [('left',1),('right',-1)]:
  q[side+'_hip_yaw']=-sign*toe;q[side+'_hip_pitch']=sign*bend/2;q[side+'_knee']=sign*bend;q[side+'_ankle']=sign*bend/2
 T=transforms(J,q);poly={l:apply_points(f['polygon'],T[l])for l,f in feet.items()};B=np.eye(4);B[2,3]=-np.vstack(list(poly.values()))[:,2].mean();targets={l:B@T[l]for l in feet};pc={l:apply_points(np.array([centers[l]]),targets[l])[0]for l in feet};groundspan=float(np.ptp(np.vstack([apply_points(f['polygon'],targets[l])for l,f in feet.items()])[:,2]))
 return dict(id=f'toe{toe:+g}_bend{bend:+g}',toe_deg=toe,knee_symmetric_delta_deg=bend,initial_q_HOME_delta_deg=q,initial_base_transform_m=to_m(B),foot_target_transforms_mm={l:t.tolist()for l,t in targets.items()},foot_area_centers_world_mm={l:p.tolist()for l,p in pc.items()},foot_center_distance_xy_mm=float(np.linalg.norm(pc['ankle_left'][:2]-pc['ankle_right'][:2])),ground_plane_span_mm=groundspan,initial_COM_world_mm=(np.array(EV.evaluate(q,to_m(B),'ankle_left')['COM_world_m'])*1000).tolist())

def endpoint(stance,support='ankle_left',seedq=None,body_limit_deg=18.,cop_margin_mm=8.,guard=None):
 targets={l:np.array(t)for l,t in stance['foot_target_transforms_mm'].items()};other='ankle_right'if support=='ankle_left'else'ankle_left';initial=np.deg2rad([stance['initial_q_HOME_delta_deg'][n]for n in LEGS]);seed=initial if seedq is None else np.deg2rad([seedq[n]for n in LEGS]);seed=np.clip(seed,np.array(bounds)[:,0],np.array(bounds)[:,1]);memo={}
 def ev(x):
  key=x[:10].tobytes()
  if memo.get('key')==key:return memo['v']
  q=qdict(x[:10]);T=transforms(J,q);B=targets[support]@np.linalg.inv(T[support]);err=np.linalg.inv(targets[other])@B@T[other];eq=np.r_[err[:3,3]/100,Rotation.from_matrix(err[:3,:3]).as_rotvec()];st=EV.evaluate(q,to_m(B),support);rp=Rotation.from_matrix(B[:3,:3]).as_euler('xyz');v=dict(q=q,B=B,eq=eq,static=st,rpy=rp);
  if guard is not None:v['guard']=guard.gaps(q,cap_mm=5.)
  memo.update(key=key,v=v);return v
 def ine(x):
  e=ev(x);u=np.array(list(e['static']['utilization'].values()));v=np.r_[(e['static']['COP_margin_mm']-cop_margin_mm)/100,x[10]-u,np.deg2rad(body_limit_deg)-e['rpy'][:2],np.deg2rad(body_limit_deg)+e['rpy'][:2]]
  return np.r_[v,(e['guard']-2.3)/10]if guard is not None else v
 st=time.time();sol=minimize(lambda x:x[10]+.003*np.sum((x[:10]-initial)**2),np.r_[seed,1.2],method='SLSQP',bounds=bounds+[(0,5)],constraints=[dict(type='eq',fun=lambda x:ev(x)['eq']),dict(type='ineq',fun=ine)],options=dict(maxiter=200,ftol=2e-9))
 e=ev(sol.x);valid=bool(np.max(np.abs(e['eq']))<1e-6 and ine(sol.x).min()>=-1e-5);return dict(support_link=support,q_HOME_delta_deg=e['q'],base_transform_m=to_m(e['B']),body_rpy_deg=np.rad2deg(e['rpy']).tolist(),static=e['static'],numerically_feasible=valid,solver_success=bool(sol.success),solver_message=sol.message,iterations=int(sol.nit),solve_seconds=time.time()-st,closure_scaled_residual=float(np.max(np.abs(e['eq']))),minimum_inequality=float(ine(sol.x).min()),geometry_guard_applied=guard is not None,guard_gaps_mm=e.get('guard',np.array([])).tolist(),body_limit_deg=body_limit_deg,cop_margin_requirement_mm=cop_margin_mm)

def main():
 source=json.loads((ROOT/'work/r19-walking-simulation/path_support/forward_trajectory.json').read_text());oldleft=next(s['q_HOME_delta_deg']for s in source['samples']if s['time_s']==9.);out=[]
 for toe in [0,5,-5,10,15]:
  for bend in [0,-15,15]:
   s=make_stance(toe,bend);e=endpoint(s,seedq=oldleft);s['left_support_endpoint']=e;out.append(s);print(s['id'],'width',round(s['foot_center_distance_xy_mm'],3),'hCOM',round(s['initial_COM_world_mm'][2],2),'valid',e['numerically_feasible'],'util',round(e['static']['max_utilization'],3),'ankle',round(e['static']['torque_Nm']['left_ankle'],3),'roll',round(e['static']['torque_Nm']['left_hip_roll'],3),'rpy',np.round(e['body_rpy_deg'],2),'closure',e['closure_scaled_residual'],flush=True)
   (OUT/'stance_screen.json').write_text(json.dumps(dict(status='FINITE_STANCE_AND_STATIC_SCREEN_NO_GEOMETRY_GUARD_YET',physical_approved=False,candidates=out,limits='Actual stance from FK, no fictitious independent foot narrowing. Single-support static inverse dynamics at nominal mass/caps, not actual balance. Numeric yaw±30/otherleg±45 search bounds only. Candidate all-part collision check pending.'),ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
