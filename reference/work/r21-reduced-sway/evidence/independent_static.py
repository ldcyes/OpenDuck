"""Source-row gravity moments and sole polygon support, independent of inverse dynamics."""
from pathlib import Path
import sys,json,hashlib,argparse,re
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'work/python-deps'),str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps'),str(ROOT/'work/r20-walking-fix/dynamics')]
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.spatial import ConvexHull
from quasistatic import StaticEvaluator
H=ROOT/'work/r20-walking-fix/dynamics/release_v4/verified_models'
ap=argparse.ArgumentParser();ap.add_argument('--trajectory',required=True);ap.add_argument('--label',required=True);args=ap.parse_args();assert re.fullmatch('[a-z0-9_]+',args.label)
TP=ROOT/args.trajectory
CP=H/'model_contract_contact4.json';MP=H/'current_robot_contact4.xml'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();sources={'work/r20-walking-fix/gait/independent_final_static.py':'2192bd0baf0e7d72e7ddf1803cc4d4e61be6c5ec986a07e0b1b8e508cf7f41f7'}
def read(p):
 sources[str(p.relative_to(ROOT))]=sha(p);d=json.loads(p.read_text())
 for rel,h in d.get('sources',{}).items():
  assert sha(ROOT/rel)==h,(rel,'SOURCE_CHANGED');sources[rel]=h
 return d
C=read(CP);D=read(TP);A=read(ROOT/'work/r20-walking-fix/assembly_final/assembly_selection.json')
delta=read(ROOT/'work/r20-walking-fix/hip_relief/candidate_v4/mass_inertia_delta.json')
assert C['joints']==A['joints'];rows=C['rows'];assert len(rows)==len({r['name']for r in rows})==501
assert not any(r['name']=='R11_hip_l_rail_2'for r in rows)
rail=next(r for r in rows if r['name']=='R20_left_hip_rail_offset')
assert abs(rail['mass_kg']-delta['add_mass_rows'][0]['nominal_g']/1000)<1e-14
mass=sum(r['mass_kg']for r in rows);assert abs(mass-delta['after_nominal_kg'])<1e-12
jn=[j['joint']for j in C['joints']];jm={j['child_link']:j for j in C['joints']};links=list(C['links'])
def ancestor(link):
 out=[]
 while link!='trunk_base':out.append(jm[link]['joint']);link=jm[link]['parent_link']
 return out
anc={l:set(ancestor(l))for l in links};caps=np.array([C['unmeasured_engineering_torque_caps_Nm'][n]for n in jn])
LM={l:sum(r['mass_kg']for r in rows if r['link']==l)for l in links}
LC={l:sum(r['mass_kg']*np.array(r['COM_HOME_m'])for r in rows if r['link']==l)/LM[l] for l in links}
feet={f['link']:np.array(f['source_contact_polygon_HOME_mm'])/1000 for f in C['foot_contact_models']}
def independent_fk(q):
 t={'trunk_base':np.eye(4)}
 def one(link):
  if link not in t:
   j=jm[link];axis=np.array(j['axis_trunk']);axis/=np.linalg.norm(axis);p=np.array(j['pivot_trunk_mm'])/1000
   r=Rotation.from_rotvec(axis*np.deg2rad(q[j['joint']])).as_matrix();local=np.eye(4);local[:3,:3]=r;local[:3,3]=p-r@p;t[link]=one(j['parent_link'])@local
  return t[link]
 for l in links:one(l)
 return t
ev=StaticEvaluator(MP,CP);checks=[];out=[];com_bounds=[];classified=0
for index,s in enumerate(D['samples']):
 T=independent_fk(s['q_HOME_delta_deg']);B=np.array(s['base_transform_m']);W={l:B@T[l]for l in links};worldcom={l:W[l][:3,:3]@LC[l]+W[l][:3,3]for l in links};COM=sum(LM[l]*worldcom[l]for l in links)/mass;com_bounds.append(COM)
 supplied=s['support_links'];fractions=s['desired_load_fraction_by_link'];support=None;kind=None
 if len(supplied)==1:support=supplied[0];kind='declared_single_support'
 else:
  nearly=[l for l in supplied if fractions.get(l,0)>=1-1e-12]
  if len(nearly)==1:support=nearly[0];kind='double_contact_with_other_prescribed_load_zero'
 if support is None:continue
 classified+=1
 poly=feet[support]@W[support][:3,:3].T+W[support][:3,3];point=poly.mean(0);force=np.array([0.,0.,mass*9.81]);moment=np.cross(COM-point,force)
 tau=[]
 for j in C['joints']:
  pw=B@T[j['parent_link']];pivot=pw[:3,:3]@(np.array(j['pivot_trunk_mm'])/1000)+pw[:3,3];axis=pw[:3,:3]@np.array(j['axis_trunk']);axis/=np.linalg.norm(axis)
  gravity=sum(LM[l]*9.81*np.dot(axis,np.cross(worldcom[l]-pivot,[0.,0.,1.]))for l in links if j['joint']in anc[l])
  contact=(np.dot(np.cross(axis,point-pivot),force)+axis@moment)if j['joint']in anc[support]else 0.
  tau.append(gravity-contact)
 tau=np.array(tau);cop=COM.copy();cop[2]=point[2];h=ConvexHull(poly[:,:2]);margin=float(np.min(-(h.equations[:,:2]@cop[:2]+h.equations[:,2]))*1000)
 result=dict(sample_index=index,time_s=s['time_s'],phase=s['phase'],support_link=support,interpretation=kind,max_utilization=float(max(abs(tau)/caps)),COP_margin_mm=margin,torque_Nm=dict(zip(jn,tau.tolist())),COM_world_m=COM.tolist())
 out.append(result)
 if classified%100==1:
  mj=ev.evaluate(s['q_HOME_delta_deg'],s['base_transform_m'],support);err=float(max(abs(tau-np.array([mj['torque_Nm'][n]for n in jn]))));assert err<1e-9,(index,err)
  assert abs(margin-mj['COP_margin_mm'])<1e-8
  checks.append(dict(sample_index=index,maximum_independent_vs_MuJoCo_torque_error_Nm=err,COP_margin_difference_mm=abs(margin-mj['COP_margin_mm'])))
sources[str(MP.relative_to(ROOT))]=sha(MP)
for p in [Path(__file__).resolve(),ROOT/'work/r20-walking-fix/dynamics/quasistatic.py']:sources[str(p.relative_to(ROOT))]=sha(p)
all_single=[r for r in out if r['interpretation']=='declared_single_support'];worst=max(all_single,key=lambda r:r['max_utilization']);minimum=min(all_single,key=lambda r:r['COP_margin_mm'])
report=dict(trajectory=str(TP.relative_to(ROOT)),status='INDEPENDENT_SOURCE_MASS_GRAVITY_AND_SUPPORT_RECHECK',physical_approved=False,model_mass_kg=mass,model_rows=501,all_reference_samples=len(D['samples']),declared_single_support_samples=len(all_single),zero_other_load_double_samples=len(out)-len(all_single),maximum_single_support_utilization=worst['max_utilization'],minimum_single_support_COP_margin_mm=minimum['COP_margin_mm'],worst_single_support_row=worst,worst_COP_row=minimum,all_effective_single_support_max_utilization=max(r['max_utilization']for r in out),independent_vs_MuJoCo_spot_checks=checks,COM_world_coordinate_ranges_m=np.stack([np.min(com_bounds,axis=0),np.max(com_bounds,axis=0)]).tolist(),rows=out,sources=sources,method='Independently compose each HOME joint transform with scipy axis-angle rotations; sum 501 source mass rows into link COMs. For each revolute axis sum downstream m g moments and subtract the single-sole wrench virtual work. Sole COP is the vertical whole-mass COM projection; true supplied source sole polygon gives margin. No MuJoCo inverse-dynamics calculation is used to obtain the reported torques; sparse cross-checks use the separate StaticEvaluator.',limitations=['Static gravity only. Acceleration, feedback error, contact discretization and torque-time saturation require the separate final free-base simulations.','Nonzero two-foot load sharing is not evaluated as hypothetical single support. Only actual declared single-support phases and explicitly zero-other-foot-load endpoints are reported here.','The 8 mm COP and 85 percent torque targets use the current final nominal mass. Actual deviations, if any, are reported without changing caps.','Nominal source masses, COM distributions and torque caps are unmeasured engineering assumptions; no hardware strength or balance qualification.'])
O=Path(__file__).resolve().parent/'independent_static'/f'{args.label}.json';O.parent.mkdir(exist_ok=True);assert not O.exists();O.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:report[k]for k in ['status','model_mass_kg','all_reference_samples','declared_single_support_samples','zero_other_load_double_samples','maximum_single_support_utilization','minimum_single_support_COP_margin_mm','all_effective_single_support_max_utilization']},indent=2));print(O,sha(O))
