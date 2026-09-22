"""Traceable mass delta and explicit invariant contact review, no physical approval."""
from pathlib import Path
import json,hashlib,math,csv
import numpy as np
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())
m=load(O/'manifest.json');l=load(ROOT/'work/r23-power-integration/integration/mass_final/R23_mass_ledger.json');s=load(O/'assembly_selection.json')
rows=l['rows'];old=next(r for r in rows if r['name']==m['replaces'][0]);cam=next(r for r in rows if r['name']=='camera_module_and_included_cable');assert sum(r['name']==cam['name'] for r in rows)==1
M=l['mass_kg'];C=np.array(l['COM_HOME_mm']);oldm=old['mass_kg'];oldc=np.array(old['COM_HOME_m'])*1000
newm=sum(p['mass_from_CAD_g']/1000 for p in m['parts']);mom=sum((p['mass_from_CAD_g']/1000*np.array(p['center_mm']) for p in m['parts']),np.zeros(3))
camera_c=np.array([132.05,-.19194,269.007]);mass=M-oldm+newm;center=(M*C-oldm*oldc+mom+.015*(camera_c-np.array(cam['COM_HOME_m'])*1000))/mass
# Origin inertia, same camera nominal tensor relocated, not a new measured camera tensor.
pa=lambda c: np.eye(3)*(np.array(c)@np.array(c))-np.outer(c,c)
I=np.array(l['I_COM_HOME_kg_m2'])+M*pa(C/1000)-np.array(old['I_COM_HOME_kg_m2'])-oldm*pa(oldc/1000)
for p in m['parts']:
 I+=np.array(p['unit_density_inertia_mm5'])*p['density_assumption_g_cm3']*1e-12+p['mass_from_CAD_g']/1000*pa(np.array(p['center_mm'])/1000)
I+=.015*(pa(camera_c/1000)-pa(cam['COM_HOME_m']));I-=mass*pa(center/1000)
report=dict(status='ENGINEERING_MASS_SCENARIO_NOT_WEIGHED_NOT_GAIT_APPROVAL',mass_kg=mass,COM_HOME_mm=center.tolist(),I_COM_HOME_kg_m2=I.tolist(),delta_mass_g=(mass-M)*1000,delta_COM_HOME_mm=(center-C).tolist(),replaced_old_shell=old,added_material_rows=[dict(name=p['name'],mass_g=p['mass_from_CAD_g'],center_mm=p['center_mm'],density_g_cm3=p['density_assumption_g_cm3']) for p in m['parts']],camera=dict(mass_kg=.015,original_com_HOME_mm=(np.array(cam['COM_HOME_m'])*1000).tolist(),new_scenario_com_HOME_mm=camera_c.tolist(),action='Existing camera and cable15g moved once; body/lens envelopes add zero mass. COM at module center is a scenario, cable distribution and actual mass unknown.'),added_head_gravity_pitch_moment_about_y_Nm=9.80665*(mass*center[0]-M*C[0])/1000,sources={str(p.relative_to(ROOT)):sha(p) for p in [O/'manifest.json',O/'assembly_selection.json',ROOT/'work/r23-power-integration/integration/mass_final/R23_mass_ledger.json',Path(__file__)]},limits=['PA12 density0.93g/cm3 and steel7.9g/cm3 engineering assumptions. No parts weighed.','Camera/cable COM and inherited tensor unmeasured. No complete torque, gait, dynamic balance or endurance requalification.','New front parts do not resolve R23 converter4Tc/30oldinterfaces/original shell-mouth1.4mm/85percent utilization and8mm COP target issues.'],physical_approved=False,manufacturing_approved=False)
(O/'mass_delta.json').write_text(json.dumps(report,indent=2)+'\n')
# Exhaustive recorded-gait result: invariant seats do not become arbitrary allowed overlap.
r=load(O/'motion/final_v3/result.json');idx=load(O/'motion/final_v3/pair_index.json');aud=[];native={(q['a'],q['b']):q for q in m['native_seating_checks']}
for q in r['unresolved_spans']:
 a,b=[idx['items'][k]['name'] for k in idx['pairs'][q['pair_id']]];e=q['exact'];assert q['pair_id'] in r['invariant_pair_ids'];assert a.startswith('R24_') and b.startswith('R24_')
 vol=e.get('intersection_mm3') or 0
 if vol>1e-8:
  assert (a,b) in native and native[a,b]['intersection_mm3']<1e-8
  reason='Exact native screw head seats at faceX135.025. Single-precision STL head seatX135.024993896 gives6.104e-6mm roundoff. Native intersection proven zero; not an interference waiver.'
  assert vol<4.2e-5
 elif 'module_body' in a and 'lens' in b:reason='Boundary between two envelopes of the same purchased camera; no overlapping solid.'
 elif 'module_body' in b:reason='Camera rear housing nominal seat on four posts atX129; rear-housing flatness/land must be verified on first article.'
 else:reason='Named bearing surface/washer/screw-head/face-to-shell seat. Zero native or negligible floating-point volume; intentional contact on same rigid head.'
 aud.append(dict(pair_id=q['pair_id'],a=a,b=b,raw_exact=e,interpretation=reason,status='INTENTIONAL_NOMINAL_SEAT_NOT_SEPARATION_OR_STRENGTH_CERTIFICATE'))
summary=dict(status='RECORDED_GAIT_DELTA_GEOMETRY_WITH_EXPLICIT_SEATS',selection_sha256=sha(O/'assembly_selection.json'),rigid_selection_sha256=sha(O/'rigid_inputs.json'),result_sha256=sha(O/'motion/final_v3/result.json'),interval_count=r['interval_count'],rigid_delta_pair_count=r['pair_count'],dynamic_pair_count=r['dynamic_pair_count'],dynamic_unresolved_count=sum(q['pair_id'] in r['dynamic_pair_ids'] for q in r['unresolved_spans']),intentional_seat_count=len(aud),seats=aud,named_thread_count=len(r['named_invariant_representations']),named_threads=r['named_invariant_representations'],limits=['Recorded gait only; tiny recorded mouth angle does not validate useful opening. See separate0..25deg detail check.','31 flexible harnesses are HOME-only in static_check; no new flex pose scan was performed. Camera terminal lead and mated connector still need supplier geometry and route confirmation.','Engine records separation above0.0001mm, not all-pairs2.2mm clearance. Existing shell/mouth1.4mm remains.','Old-old pairs and external objects excluded from this delta check.'],physical_approved=False,manufacturing_approved=False)
assert summary['dynamic_unresolved_count']==0
(O/'contact_review.json').write_text(json.dumps(summary,indent=2)+'\n')
with (O/'BOM.csv').open('w',newline='',encoding='utf-8-sig')as f:
 w=csv.writer(f);w.writerow(['item','quantity','material/spec','source','status'])
 for p in m['parts'][:3]:w.writerow([p['name'],1,p['material'],p.get('manufacturing_master',p['mesh']),'Design candidate; SLS PA12, unit mm'])
 for n,qty,spec in [('OS05A10 5MP USB Camera(A),SKU33123',1,'Existing camera;25x25mm,21mm pitch,4xD2;D14 lens;USB SH1.0 lead pending'),('M2x10 screw',4,'HeadD3.8H2,hex1.5'),('M2x8 screw',4,'HeadD3.8H2,hex1.5'),('M2 hex nut',8,'AF4,H1.6'),('M2 washer',4,'OD5,ID2.2,H0.3'),('M1.6x14 screw',4,'HeadD3,H1.6,hex1.5 envelope;match actual vendor'),('M1.6 hex nut',4,'AF3.2,H1.3'),('M1.6 washer',4,'OD4,ID1.8,H0.3')]:w.writerow([n,qty,spec,'Dimensional purchasing acceptance envelope','Vendor drawing and first article required'])
print('MASS',mass,'delta',report['delta_mass_g'],'COM delta',report['delta_COM_HOME_mm'],'extra gravity moment',report['added_head_gravity_pitch_moment_about_y_Nm'])
