from pathlib import Path
import sys
sys.dont_write_bytecode=True
_R21_ROOT=Path(__file__).resolve().parents[3]
_R21_OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(_R21_ROOT/"work/r20-walking-fix/dynamics"))
from quasistatic import *
import argparse

def _r21_model_guard(model,contract):
 import hashlib
 allowed={'work/r20-walking-fix/dynamics/release_v4/verified_models/current_robot_contact4.xml': '07853dbc0732042d31aae1c6c935a3374a355a07e74eeffe04efe46aefb23839', 'work/r20-walking-fix/dynamics/release_v4/verified_models/model_contract_contact4.json': '2fdcdd4d4f24594692a2e48eb7b8880ff190228a84131265bca1190b4765c240', 'work/r20-walking-fix/dynamics/release_v4/verified_models/current_robot_contact9.xml': '4c86e42449eb3766336d94c28a63bba62c0b56845305928192cff765adee8405', 'work/r20-walking-fix/dynamics/release_v4/verified_models/model_contract_contact9.json': 'e179f11e98109f5f482c923244f4b7d5a62b310b9b0592b17105751647dd1fe5'}
 for value in [model,contract]:
  p=Path(value).resolve();key=str(p.relative_to(_R21_ROOT))
  if key not in allowed or hashlib.sha256(p.read_bytes()).hexdigest()!=allowed[key]:raise ValueError("R21_REQUIRES_FROZEN_R20_FINAL_V4_MODEL_AND_CONTRACT")
def _r21_output_guard(folder):
 p=Path(folder).resolve()
 if not p.is_relative_to(_R21_OUT):raise ValueError("R21_OUTPUT_MUST_STAY_INSIDE_R21_DYNAMICS")

p=argparse.ArgumentParser();p.add_argument('folder');a=p.parse_args();folder=Path(a.folder).resolve();_r21_output_guard(folder);tp=folder/'trajectory.json';rp=folder/'report.json';bp=folder/'interval_joint_bounds.json';data=json.loads(tp.read_text());report=json.loads(rp.read_text());ss=[]
for s in data['samples']:
 q=np.array(s['root_quaternion_wxyz']);T=np.eye(4);T[:3,:3]=Rotation.from_quat(q[[1,2,3,0]]).as_matrix();T[:3,3]=s['root_xyz_m'];ss.append(dict(time_s=s['time_s'],q_HOME_delta_deg=s['q_HOME_delta_deg'],base_transform_m=T.tolist(),phase=s['phase'],support_links=s['support_links'],contact_mode=s.get('contact_mode'),COM_world_m=s['COM_world_m'],root_reference_orientation_error_deg=s['root_orientation_error_deg']))
sources=dict(data['sources']);sources.update({str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()for x in [tp,rp,bp,Path(__file__)]});result=dict(status='ACTUAL_CONTINUOUS_FREE_BASE_NUMERICAL_INTEGRATION_FOR_CAD_POSTCHECK',physical_approved=False,model_mass_kg=report['mass_kg'],time_s=report['simulated_duration_s'],saved_sample_period_s=.02,interval_bounds_path=str(bp.relative_to(ROOT)),samples=ss,sources=sources);out=folder/'dynamic_trace_for_CAD.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(str(out.relative_to(ROOT)),hashlib.sha256(out.read_bytes()).hexdigest(),len(ss))
