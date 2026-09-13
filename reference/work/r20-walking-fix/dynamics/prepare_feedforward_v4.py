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
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--path',required=True);ap.add_argument('--out',required=True);ap.add_argument('--model');ap.add_argument('--contract');a=ap.parse_args();prepare(a.path,a.out,a.model,a.contract)
