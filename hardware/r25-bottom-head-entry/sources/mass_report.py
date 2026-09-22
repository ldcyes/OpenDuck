from pathlib import Path
import json,numpy as np,hashlib
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).parent
load=lambda p:json.loads(Path(p).read_text());S=load(O/'assembly_selection.json');base=load(ROOT/'work/r24-head-front/mass_delta.json');r23=load(ROOT/'work/r23-power-integration/integration/mass_final/R23_mass_ledger.json');old={p['name']:p for p in load(ROOT/'work/r24-head-front/assembly_selection.json')['items']}
lookup={r['name']:dict(mass_g=r['mass_kg']*1000,center_mm=(np.array(r['COM_HOME_m'])*1000).tolist())for r in r23['rows']+r23['free_rows']}
lookup.update({r['name']:r for r in base['added_material_rows']});removed=[];added=[]
for n in S['replaces']:
 if n not in lookup and old[n].get('mass_budget_g')==0:lookup[n]=dict(mass_g=0,center_mm=old[n]['center_mm'])
 assert n in lookup,n
 removed.append(dict(name=n,**{k:lookup[n][k]for k in ['mass_g','center_mm']}))
for p in S['items'][:S['new_installed_count']]:
 mass=p.get('physical_mass_g',p.get('manufacturer_mass_g',p.get('mass_budget_g',p.get('maximum_free_wire_mass_g',p.get('mass_from_CAD_g')))))
 assert mass is not None,p['name']
 added.append(dict(name=p['name'],mass_g=mass,center_mm=p['center_mm']))
M=base['mass_kg']*1000;moment=M*np.array(base['COM_HOME_mm'])
for sg,rows in [(-1,removed),(1,added)]:
 for r in rows:M+=sg*r['mass_g'];moment+=sg*r['mass_g']*np.array(r['center_mm'])
report=dict(status='ENGINEERING_MAX_WIRE_MASS_SCENARIO_NOT_WEIGHED',mass_kg=M/1000,COM_HOME_mm=(moment/M).tolist(),delta_mass_g=M-base['mass_kg']*1000,delta_COM_HOME_mm=(moment/M-np.array(base['COM_HOME_mm'])).tolist(),removed=removed,added=added,notes=['Baseline R24 camera/cable15g retained once.','Free conductor mass counted once, no duplicated support50 rows.','Spatial scenario uses maximum-envelope CAD center, unmeasured.','No new inertia/torque/endurance/physical gait qualification implied.'],physical_approved=False,manufacturing_approved=False)
(O/'mass_delta.json').write_text(json.dumps(report,indent=2)+'\n');print(M/1000,report['delta_mass_g'])
