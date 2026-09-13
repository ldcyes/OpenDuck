from pathlib import Path
import sys
sys.dont_write_bytecode=True
_R21_ROOT=Path(__file__).resolve().parents[3]
_R21_OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(_R21_ROOT/"work/r20-walking-fix/dynamics"))
from feedforward_v2 import *
import argparse

def prepare(path,out,model=None,contract=None):
 ev=Feedforward(model or MODEL,contract or CONTRACT);d=json.loads(Path(path).read_text());ss=d['samples'];times=np.array([s['time_s']for s in ss]);vel=[];acc=[]
 # Exact fixed-support velocity map plus directional Jacobian derivative.
 # This avoids spurious accelerations from unequal sampling intervals near knots.
 for s in ss:
  ev.set_state(s['q_HOME_delta_deg'],s['base_transform_m']);m,data=ev.m,ev.d
  support=s.get('support_link')or s['support_links'][0];bid=m.body(support).id
  def support_jacobian():
   jp=np.zeros((3,m.nv));jr=np.zeros((3,m.nv));mujoco.mj_jac(m,data,jp,jr,data.xpos[bid],bid);return np.vstack([jp,jr])
  J=support_jacobian();v=np.zeros(m.nv);v[ev.vids]=np.deg2rad([s['joint_velocity_deg_s'][n]for n in ev.names]);v[:6]=-np.linalg.solve(J[:,:6],J[:,ev.vids]@v[ev.vids]);a=np.zeros(m.nv);a[ev.vids]=np.deg2rad([s['joint_acceleration_deg_s2'][n]for n in ev.names]);qp=data.qpos.copy();epsilon=1e-5
  data.qpos[:]=qp;mujoco.mj_integratePos(m,data.qpos,v,epsilon);mujoco.mj_forward(m,data);Jp=support_jacobian()
  data.qpos[:]=qp;mujoco.mj_integratePos(m,data.qpos,v,-epsilon);mujoco.mj_forward(m,data);Jm=support_jacobian()
  a[:6]=-np.linalg.solve(J[:,:6],J[:,ev.vids]@a[ev.vids]+((Jp-Jm)/(2*epsilon))@v);vel.append(v);acc.append(a)
 vel=np.array(vel);acc=np.array(acc)
 records=[]
 for i,s in enumerate(ss):
  support=s.get('support_links')
  if not support:
   support=[s['support_link']]if s.get('support_link')else['ankle_left','ankle_right']
  ff=ev.evaluate_dynamic(s['q_HOME_delta_deg'],s['base_transform_m'],support,vel[i],acc[i],s.get('desired_load_fraction_by_link'));records.append(dict(time_s=s['time_s'],q_HOME_delta_deg=s['q_HOME_delta_deg'],base_transform_m=s['base_transform_m'],support_links=support,phase=s.get('phase'),contact_mode=s.get('contact_mode'),desired_load_fraction_by_link=s.get('desired_load_fraction_by_link'),joint_qvel_rad_s=dict(zip(ev.names,vel[i,ev.vids].tolist())),generalized_velocity=vel[i].tolist(),generalized_acceleration=acc[i].tolist(),feedforward_torque_Nm=ff['torque_Nm'],feedforward_max_utilization=ff['max_utilization'],contact_wrenches=ff['contact_wrenches'],allocation=ff['allocation'],root_equilibrium_residual=ff['root_equilibrium_residual']))
  if i%50==0:print('FF',i,len(ss),ff['max_utilization'],flush=True)
 sources={str(Path(p).resolve().relative_to(ROOT)):hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in [path,ev.model_path,ev.contract_path,Path(__file__),OUT/'feedforward_v2.py',OUT/'quasistatic.py']};r=dict(status='RIGID_INVERSE_DYNAMICS_FEEDFORWARD_DIAGNOSTIC',samples=records,sources=sources,physical_approved=False,derivative_basis='Analytic supplied joint quintic qdot/qddot; free-base velocity solved by exact designated fixed-foot Jacobian and acceleration by its directional derivative (central +/-10 microseconds). No uneven time-grid differentiation.');Path(out).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');return r

def _r21_model_guard(model,contract):
 import hashlib
 allowed={'work/r20-walking-fix/dynamics/release_v4/verified_models/current_robot_contact4.xml': '07853dbc0732042d31aae1c6c935a3374a355a07e74eeffe04efe46aefb23839', 'work/r20-walking-fix/dynamics/release_v4/verified_models/model_contract_contact4.json': '2fdcdd4d4f24594692a2e48eb7b8880ff190228a84131265bca1190b4765c240', 'work/r20-walking-fix/dynamics/release_v4/verified_models/current_robot_contact9.xml': '4c86e42449eb3766336d94c28a63bba62c0b56845305928192cff765adee8405', 'work/r20-walking-fix/dynamics/release_v4/verified_models/model_contract_contact9.json': 'e179f11e98109f5f482c923244f4b7d5a62b310b9b0592b17105751647dd1fe5'}
 for value in [model,contract]:
  p=Path(value).resolve();key=str(p.relative_to(_R21_ROOT))
  if key not in allowed or hashlib.sha256(p.read_bytes()).hexdigest()!=allowed[key]:raise ValueError("R21_REQUIRES_FROZEN_R20_FINAL_V4_MODEL_AND_CONTRACT")
def _r21_output_guard(folder):
 p=Path(folder).resolve()
 if not p.is_relative_to(_R21_OUT):raise ValueError("R21_OUTPUT_MUST_STAY_INSIDE_R21_DYNAMICS")

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--path',required=True);ap.add_argument('--out',required=True);ap.add_argument('--model',required=True);ap.add_argument('--contract',required=True);a=ap.parse_args();_r21_model_guard(a.model,a.contract);_r21_output_guard(Path(a.out).parent);prepare(a.path,a.out,a.model,a.contract)
