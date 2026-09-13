"""Static load allocation for the actual commanded support shares; not sensed forces."""
from reduced_core_v2 import *
from feedforward_v2 import Feedforward
import argparse
SOURCES.bind(__file__);SOURCES.bind(ROOT/'work/r20-walking-fix/dynamics/feedforward_v2.py');ap=argparse.ArgumentParser();ap.add_argument('--tag',required=True);args=ap.parse_args();p=OUT/f'trajectory_{args.tag}.json';D=SOURCES.json(p);FF=Feedforward(MP,CP);rows=[]
for i,r in enumerate(D['samples']):
 a=FF.evaluate_dynamic(r['q_HOME_delta_deg'],r['base_transform_m'],r['support_links'],desired_load_fraction_by_link=r['desired_load_fraction_by_link']);contacts=[]
 for link,w in zip(r['support_links'],a['contact_wrenches']):
  bid=FF.m.body(link).id;R=FF.d.xmat[bid].reshape(3,3);poly=(FF.feet[link]-FF.pivots[link])@R.T+FF.d.xpos[bid];point=poly.mean(0);fz=w[2]
  if fz>1e-6:
   cop=np.array([point[0]-w[4]/fz,point[1]+w[3]/fz]);h=ConvexHull(poly[:,:2]);cm=float(np.min(-(h.equations[:,:2]@cop+h.equations[:,2]))*1000);cone=(abs(w[0])/.5+abs(w[1])/.5+abs(w[5])/.01)/fz
  else:cop=None;cm=None;cone=None
  contacts.append(dict(link=link,Fz_N=fz,COP_world_xy_m=None if cop is None else cop.tolist(),COP_margin_mm=cm,conservative_mu05_torsion001_L1_ratio=cone,loaded_above_2N=bool(fz>2.)))
 rows.append(dict(time_s=r['time_s'],phase=r['phase'],contact_mode=r['contact_mode'],desired_load_fraction_by_link=r['desired_load_fraction_by_link'],static_allocated_torque_Nm=a['torque_Nm'],max_utilization=a['max_utilization'],contacts=contacts,root_equilibrium_residual=a['root_equilibrium_residual'],load_equalities_residual=a['all_equalities_residual']))
 if i%500==0:print('LOAD_SHARES',i,len(D['samples']),flush=True)
peak=max(rows,key=lambda r:r['max_utilization']);double=[c for r in rows if r['contact_mode']=='double'for c in r['contacts']if c['loaded_above_2N']];single=[c for r in rows if r['contact_mode']!='double'for c in r['contacts']if c['loaded_above_2N']];summary=dict(sample_count=len(rows),maximum_static_allocated_utilization=peak['max_utilization'],peak_time_s=peak['time_s'],peak_phase=peak['phase'],maximum_root_equilibrium_residual=max(r['root_equilibrium_residual']for r in rows),maximum_load_share_equality_residual=max(r['load_equalities_residual']for r in rows),minimum_loaded_double_contact_COP_margin_mm=min(c['COP_margin_mm']for c in double),minimum_loaded_single_contact_COP_margin_mm=min(c['COP_margin_mm']for c in single),maximum_loaded_double_L1_cone_ratio=max(c['conservative_mu05_torsion001_L1_ratio']for c in double),maximum_loaded_single_L1_cone_ratio=max(c['conservative_mu05_torsion001_L1_ratio']for c in single))
SOURCES.verify();(OUT/f'load_shares_{args.tag}.json').write_text(json.dumps(dict(status='COMPLETE_EXPORTED_REFERENCE_STATIC_COMMANDED_LOAD_ALLOCATION_NOT_ACTUAL_DYNAMIC_CONTACT',summary=summary,rows=rows,sources=SOURCES.entries,limits=['Uses prescribed support_links and commanded Fz fractions. They are not measurements of actual contact forces.','R20 double-support force distributor keeps2mm COP inset; single-support gait targets8mm.','Positive loaded contacts are classified at Fz>2N for comparison, without treating planned0load as measured unloading.','Final dynamic contact, inertia, saturation and friction sensitivity remain separate.']),indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)
