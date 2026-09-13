"""Current-robot single-support static inverse dynamics; source-owned R19 untouched."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'work/python-deps'),str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import numpy as np,mujoco
from scipy.spatial.transform import Rotation
from scipy.spatial import ConvexHull
MODEL=ROOT/'work/r19-walking-simulation/physics/current_robot_v2.xml'
CONTRACT=ROOT/'work/r19-walking-simulation/physics/model_contract_v2.json'
class StaticEvaluator:
 def __init__(self,model_path=MODEL,contract_path=CONTRACT):
  self.model_path=Path(model_path);self.contract_path=Path(contract_path);self.c=json.loads(self.contract_path.read_text());self.m=mujoco.MjModel.from_xml_path(str(self.model_path));self.d=mujoco.MjData(self.m);self.names=[j['joint']for j in self.c['joints']];self.qids=np.array([self.m.jnt_qposadr[self.m.joint(n).id]for n in self.names]);self.vids=np.array([self.m.jnt_dofadr[self.m.joint(n).id]for n in self.names]);self.pivots={j['child_link']:np.array(j['pivot_trunk_mm'])/1000 for j in self.c['joints']};self.feet={f['link']:np.array(f['source_contact_polygon_HOME_mm'])/1000 for f in self.c['foot_contact_models']};self.caps=np.array([self.c['unmeasured_engineering_torque_caps_Nm'][n]for n in self.names])
 def set_state(self,q_deg,base_transform_m):
  T=np.array(base_transform_m);self.d.qpos[:3]=T[:3,3];quat=Rotation.from_matrix(T[:3,:3]).as_quat();self.d.qpos[3:7]=quat[[3,0,1,2]];self.d.qpos[self.qids]=np.deg2rad([q_deg.get(n,0)for n in self.names]);self.d.qvel[:]=0;self.d.ctrl[:]=self.d.qpos[self.qids];mujoco.mj_forward(self.m,self.d)
 def evaluate(self,q_deg,base_transform_m,support_link):
  self.set_state(q_deg,base_transform_m);m,d=self.m,self.d;bid=m.body(support_link).id;R=d.xmat[bid].reshape(3,3);poly=(self.feet[support_link]-self.pivots[support_link])@R.T+d.xpos[bid];point=poly.mean(0);jp=np.zeros((3,m.nv));jr=np.zeros((3,m.nv));mujoco.mj_jac(m,d,jp,jr,point,bid);J=np.vstack([jp,jr]);wrench=np.linalg.solve(J[:,:6].T,d.qfrc_bias[:6]);tau=d.qfrc_bias[self.vids]-J[:,self.vids].T@wrench;cop=point.copy();cop[:2]+=np.array([-wrench[4],wrench[3]])/wrench[2];hull=ConvexHull(poly[:,:2]);margin=float(np.min(-(hull.equations[:,:2]@cop[:2]+hull.equations[:,2])));com=d.subtree_com[m.body('trunk_base').id].copy();ankle=next(j for j in self.c['joints']if j['child_link']==support_link);jid=m.joint(ankle['joint']).id;pivot=d.xanchor[jid].copy();axis=d.xaxis[jid].copy();gravmoment=float(np.dot(np.cross(com-pivot,np.array([0,0,-sum(m.body_mass)*9.81])),axis));util=np.abs(tau)/self.caps
  return dict(torque_Nm=dict(zip(self.names,tau.tolist())),utilization=dict(zip(self.names,util.tolist())),max_utilization=float(util.max()),support_link=support_link,contact_wrench_world_force_torque_at_point=wrench.tolist(),support_reference_point_world_m=point.tolist(),COP_world_m=cop.tolist(),COP_margin_mm=margin*1000,COM_world_m=com.tolist(),ankle_pivot_world_m=pivot.tolist(),ankle_axis_world=axis.tolist(),COM_minus_ankle_world_mm=((com-pivot)*1000).tolist(),whole_robot_gravity_moment_about_support_ankle_Nm=gravmoment,static_equilibrium_root_residual=float(np.max(abs(J[:,:6].T@wrench-d.qfrc_bias[:6]))))
if __name__=='__main__':
 ev=StaticEvaluator();path=ROOT/'work/r19-walking-simulation/path_support/forward_trajectory.json';data=json.loads(path.read_text());out=[]
 for target in [0,8,9,9.7,10,11,12,12.15475,16,17,29,37]:
  s=min(data['samples'],key=lambda x:abs(x['time_s']-target));sup=s['support_link']or'ankle_left';r=ev.evaluate(s['q_HOME_delta_deg'],s['base_transform_m'],sup);r.update(time_s=s['time_s'],reference_phase=s['phase'],single_support_assumption=True);out.append(r);print(s['time_s'],sup,'ankle',round(r['torque_Nm'][sup.replace('ankle_left','left_ankle').replace('ankle_right','right_ankle')],4),'roll',round(r['torque_Nm'][('left'if sup.endswith('left')else'right')+'_hip_roll'],4),'COP',round(r['COP_margin_mm'],2),'COMlever',r['COM_minus_ankle_world_mm'])
 report=dict(status='SINGLE_SUPPORT_STATIC_INVERSE_DYNAMICS_DIAGNOSIS',physical_approved=False,rows=out,sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [MODEL,CONTRACT,path,Path(__file__)]},note='Early double-support phases here are deliberately evaluated as the hypothetical single-foot worst case, not the actual load split.')
 (OUT/'r19_static_failure_diagnosis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
