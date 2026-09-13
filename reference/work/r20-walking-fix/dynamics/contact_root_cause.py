"""Conservative planned support-wrench feasibility and original numerical contact spread."""
from quasistatic import *
import urllib.request
fp=OUT/'first_step_ff_v4.json';tp=OUT/'first_step_r20_exactFF/trajectory.json';ff=json.loads(fp.read_text());trace=json.loads(tp.read_text());rows=[]
for s in ff['samples']:
 if len(s['support_links'])!=1:continue
 w=np.array(s['contact_wrenches'][0]);cop_shift=np.array([-w[4]/w[2],w[3]/w[2],0]);cop_residual_moment=w[3:]-np.cross(cop_shift,w[:3]);ratio=float(np.linalg.norm([w[0]/(.5*w[2]),w[1]/(.5*w[2]),cop_residual_moment[2]/(.01*w[2])]))
 rows.append(dict(time_s=s['time_s'],phase=s['phase'],wrench_at_source_sole_vertex_mean=w.tolist(),COP_shift_m=cop_shift.tolist(),residual_yaw_at_COP_Nm=float(cop_residual_moment[2]),conservative_mu0p5_torsion0p01_combined_ellipse_ratio=ratio))
actual=[]
for s in trace['samples']:
 if len(s['support_links'])!=1:continue
 link=s['support_links'][0];cc=[c for c in s['contacts']if c['foot']==link and c['normal_force_N']>2];p=np.array([c['pos_m'][:2]for c in cc]);com=np.array(s['COM_world_m'])[:2];dist=None
 if len(p)==2:
  v=p[1]-p[0];u=np.clip(np.dot(com-p[0],v)/np.dot(v,v),0,1);dist=float(np.linalg.norm(com-(p[0]+u*v))*1000)
 actual.append(dict(time_s=s['time_s'],loaded_contact_count=len(cc),COM_XY_distance_from_two_contact_segment_mm=dist))
url='https://raw.githubusercontent.com/google-deepmind/mujoco/3.3.7/src/engine/engine_collision_convex.c';sourcefile=OUT/'official_mujoco_3p3p7_engine_collision_convex.c';sourcefile.write_bytes(urllib.request.urlopen(url).read());assert 'const int maxplanemesh = 3;'in sourcefile.read_text()
report=dict(status='REFERENCE_CONTACT_WRENCH_FEASIBLE_BUT_ORIGINAL_CONTACT_SAMPLING_SPARSE',physical_approved=False,maximum_reference_combined_ratio=max(r['conservative_mu0p5_torsion0p01_combined_ellipse_ratio']for r in rows),maximum_reference_raw_world_Mz_Nm=max(abs(r['wrench_at_source_sole_vertex_mean'][5])for r in rows),maximum_COM_distance_from_two_loaded_contacts_mm=max((r['COM_XY_distance_from_two_contact_segment_mm']for r in actual if r['COM_XY_distance_from_two_contact_segment_mm']is not None),default=None),number_single_support_saved_states=len(actual),states_with_exactly_two_loaded_contacts=sum(r['loaded_contact_count']==2 for r in actual),reference_rows=rows,actual_contact_spread=actual,official_source_url=url,interpretation=['The static/small-motion wrench can be supported by the original full sole polygon with μ=.5 and torsion=.01; hip yaw torque is not floor torsion moment.','MuJoCo3.3.7 PlaneConvex chooses at most3 points and searches neighbors of the deepest vertex, with minimum spacing .3*bounding radius. A single foot mesh can present only a diagonal pair, which is not the full sole support polygon.','This identifies a model-discretization hypothesis; geometry-preserving partition and density sensitivity must be run before claiming it explains the drift.'],sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [fp,tp,sourcefile,Path(__file__)]});(OUT/'contact_root_cause.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print({k:v for k,v in report.items()if k not in ['reference_rows','actual_contact_spread','sources','interpretation']})
