from feedforward_v2 import *
import argparse

def prepare(path,out,model=None,contract=None):
 ev=Feedforward(model or MODEL,contract or CONTRACT);d=json.loads(Path(path).read_text());ss=d['samples'];times=np.array([s['time_s']for s in ss]);qp=[]
 for s in ss:ev.set_state(s['q_HOME_delta_deg'],s['base_transform_m']);qp.append(ev.d.qpos.copy())
 qp=np.array(qp);vel=[]
 for i in range(len(ss)):
  a=max(0,i-1);b=min(len(ss)-1,i+1);v=np.zeros(ev.m.nv);mujoco.mj_differentiatePos(ev.m,v,times[b]-times[a],qp[a],qp[b]);vel.append(v)
 vel=np.array(vel)
 # Use supplied analytic quintic derivatives for actuated joints. Free-base
 # derivatives remain central finite differences of the supplied rigid transform.
 if all('joint_velocity_deg_s'in s for s in ss):
  vel[:,ev.vids]=np.deg2rad([[s['joint_velocity_deg_s'][n]for n in ev.names]for s in ss])
 acc=np.gradient(vel,times,axis=0,edge_order=1)
 if all('joint_acceleration_deg_s2'in s for s in ss):
  acc[:,ev.vids]=np.deg2rad([[s['joint_acceleration_deg_s2'][n]for n in ev.names]for s in ss])
 records=[]
 for i,s in enumerate(ss):
  support=s.get('support_links')
  if not support:
   support=[s['support_link']]if s.get('support_link')else['ankle_left','ankle_right']
  ff=ev.evaluate_dynamic(s['q_HOME_delta_deg'],s['base_transform_m'],support,vel[i],acc[i],s.get('desired_load_fraction_by_link'));records.append(dict(time_s=s['time_s'],q_HOME_delta_deg=s['q_HOME_delta_deg'],base_transform_m=s['base_transform_m'],support_links=support,phase=s.get('phase'),contact_mode=s.get('contact_mode'),desired_load_fraction_by_link=s.get('desired_load_fraction_by_link'),joint_qvel_rad_s=dict(zip(ev.names,vel[i,ev.vids].tolist())),generalized_velocity=vel[i].tolist(),generalized_acceleration=acc[i].tolist(),feedforward_torque_Nm=ff['torque_Nm'],feedforward_max_utilization=ff['max_utilization'],contact_wrenches=ff['contact_wrenches'],allocation=ff['allocation'],root_equilibrium_residual=ff['root_equilibrium_residual']))
  if i%50==0:print('FF',i,len(ss),ff['max_utilization'],flush=True)
 sources={str(Path(p).resolve().relative_to(ROOT)):hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in [path,ev.model_path,ev.contract_path,Path(__file__),OUT/'feedforward_v2.py',OUT/'quasistatic.py']};r=dict(status='RIGID_INVERSE_DYNAMICS_FEEDFORWARD_DIAGNOSTIC',samples=records,sources=sources,physical_approved=False,derivative_basis='Analytic joint quintic velocities/accelerations when supplied; central finite-difference free-base derivatives.');Path(out).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');return r
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--path',required=True);ap.add_argument('--out',required=True);ap.add_argument('--model');ap.add_argument('--contract');a=ap.parse_args();prepare(a.path,a.out,a.model,a.contract)
