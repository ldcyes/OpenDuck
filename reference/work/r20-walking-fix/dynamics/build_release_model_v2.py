"""Apply frozen R20 mass-row reallocation to the R19 rigid model without changing caps or joints."""
from quasistatic import *
from copy import deepcopy
from xml.etree import ElementTree as E

import argparse
ap=argparse.ArgumentParser();ap.add_argument('--delta',required=True);ap.add_argument('--out-dir',required=True);args=ap.parse_args()
MODEL=OUT/'current_robot_r20.xml';CONTRACT=OUT/'model_contract_r20.json';FINALOUT=ROOT/args.out_dir;FINALOUT.mkdir(exist_ok=True,parents=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def vec(x):return' '.join(f'{float(y):.16g}'for y in np.asarray(x).ravel())
delta_path=ROOT/args.delta;delta=json.loads(delta_path.read_text());old=json.loads(CONTRACT.read_text());sources=dict(old['sources']);sources[str(CONTRACT.relative_to(ROOT))]=sha(CONTRACT);sources[str(MODEL.relative_to(ROOT))]=sha(MODEL);sources[str(delta_path.relative_to(ROOT))]=sha(delta_path)
for p,h in delta['sources'].items():
 assert sha(ROOT/p)==h,(p,'CHANGED_DELTA_SOURCE');sources[p]=h
assert abs(old['mass_kg']-delta['before_nominal_kg'])<1e-12,'DELTA_BASELINE_MASS_MISMATCH'
remove=set(delta['remove_mass_rows']);assert len([r for r in old['rows']if r['name']in remove])==len(remove)
rows=[deepcopy(r)for r in old['rows']if r['name']not in remove]
for r in delta['add_mass_rows']:
 rows.append(dict(name=r['name'],link=r['link'],mass_kg=r['nominal_g']/1000,COM_HOME_m=(np.array(r['COM_home_mm'])/1000).tolist(),I_COM_HOME_kg_m2=r['I_COM_home_kg_m2'],inertia_basis=r.get('R13_inertia_basis',r['basis'])))
assert len(rows)==len(old['rows']);mass=sum(r['mass_kg']for r in rows);assert abs(mass-delta['after_nominal_kg'])<1e-12
links={}
for name in sorted({r['link']for r in rows}):
 rr=[r for r in rows if r['link']==name];m=sum(r['mass_kg']for r in rr);c=sum(r['mass_kg']*np.array(r['COM_HOME_m'])for r in rr)/m;I=np.zeros((3,3))
 for r in rr:
  dd=np.array(r['COM_HOME_m'])-c;I+=np.array(r['I_COM_HOME_kg_m2'])+r['mass_kg']*(dd@dd*np.eye(3)-np.outer(dd,dd))
 eig=np.linalg.eigvalsh(I);assert min(eig)>0 and max(eig)<sum(eig)/2+1e-12
 links[name]=dict(mass_kg=m,COM_HOME_m=c.tolist(),I_COM_HOME_kg_m2=I.tolist(),source_rows=[r['name']for r in rr])
root=E.parse(MODEL).getroot();root.set('model','R20_557part_15joint_source_mass_reallocation_diagnostic');pivots={j['child_link']:np.array(j['pivot_trunk_mm'])/1000 for j in old['joints']};pivots['trunk_base']=np.zeros(3)
for body in root.iter('body'):
 name=body.attrib['name'];r=links[name];I=np.array(r['I_COM_HOME_kg_m2']);inertial=body.find('inertial');inertial.set('mass',vec([r['mass_kg']]));inertial.set('pos',vec(np.array(r['COM_HOME_m'])-pivots[name]));inertial.set('fullinertia',vec([I[0,0],I[1,1],I[2,2],I[0,1],I[0,2],I[1,2]]));marker=next(g for g in body.findall('geom')if g.attrib['name'].endswith('_COM_marker'));marker.set('pos',inertial.attrib['pos'])
model_path=FINALOUT/'current_robot_final_raw.xml';E.indent(root);model_path.write_text(E.tostring(root,encoding='unicode')+'\n');model=mujoco.MjModel.from_xml_path(str(model_path));assert abs(sum(model.body_mass)-mass)<1e-12
oldmodel=mujoco.MjModel.from_xml_path(str(MODEL))
for name in ['actuator_forcerange','actuator_forcelimited','jnt_axis','jnt_range','jnt_limited','body_parentid','body_pos','geom_friction']:
 assert np.array_equal(getattr(model,name),getattr(oldmodel,name)),name
com=sum(r['mass_kg']*np.array(r['COM_HOME_m'])for r in rows)/mass;contract=deepcopy(old);contract.update(mass_kg=mass,COM_HOME_mm=(com*1000).tolist(),assembly_parts=557,mass_rows=len(rows),rows=rows,links=links,sources=sources,revision='R20_FINAL_HEAD_AND_HIP_FIX',mass_delta_from_previous_model_kg=mass-old['mass_kg']);contract.pop('mass_delta_from_R19_kg',None);contract['mass_delta_from_initial_R19_kg']=mass-4.194478291462334;contract['assumptions']=old['assumptions']+['Final R20 replaces the left hip rail with its source-bound offset solid and recomputes its nominal mass, COM and inertia. The head reserve allocation is retained.']
contract['historical_source_assumptions']=deepcopy(old['assumptions'])
contract['assumptions']=[('501 nominal mass/inertia rows represent the current557CADobjects, including grouped inherited assemblies and explicit remaining reserves; no per-object physical weighing.'if x.startswith('475 mass budget')else 'Retained source inertia estimates, source-CAD distributions and explicit residual-reserve m*r^2 assumptions are combined; none is physically identified.'if x.startswith('387 inherited row')else x)for x in contract['assumptions']]
contract['sources'][str(Path(__file__).relative_to(ROOT))]=sha(Path(__file__));contract['sources'][str(model_path.relative_to(ROOT))]=sha(model_path);contract_path=FINALOUT/'model_contract_final_raw.json';contract_path.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
# Independent row-vs-compiled-body COM check at HOME and varied encoded poses.
ev=StaticEvaluator(model_path,contract_path);checks=[]
for seed in range(4):
 rng=np.random.default_rng(seed);q={n:float(x)for n,x in zip(ev.names,rng.uniform(-15,15,len(ev.names)))};T=np.eye(4);T[:3,:3]=Rotation.from_euler('xyz',[.1,-.1,.15]).as_matrix();T[:3,3]=[.003,.004,.25];ev.set_state(q,T);rowmoment=np.zeros(3)
 for r in rows:
  bid=ev.m.body(r['link']).id;center=ev.d.xmat[bid].reshape(3,3)@(np.array(r['COM_HOME_m'])-pivots[r['link']])+ev.d.xpos[bid];rowmoment+=r['mass_kg']*center
 actual=ev.d.subtree_com[ev.m.body('trunk_base').id];error=float(np.max(abs(actual-rowmoment/mass)));assert error<1e-12;checks.append(dict(seed=seed,max_COM_coordinate_error_m=error))
summary=dict(status='FINAL_R20_HEAD_AND_HIP_MASS_COMPILED_AND_CHECKED',mass_kg=mass,COM_HOME_mm=(com*1000).tolist(),delta_kg=mass-old['mass_kg'],rows=len(rows),parts=557,unchanged_joint_and_contact_and_cap_arrays=True,COM_crosschecks=checks,physical_approved=False,sources={str(p.relative_to(ROOT)):sha(p)for p in [MODEL,CONTRACT,model_path,contract_path,delta_path,Path(__file__)]});(FINALOUT/'model_update_check.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False))
