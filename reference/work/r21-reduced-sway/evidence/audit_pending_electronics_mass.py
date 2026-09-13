"""Read-only audit of inherited electronics rows; no model or CAD mutation."""
import json, hashlib
from pathlib import Path
ROOT=Path.cwd(); OUT=ROOT/'work/r21-reduced-sway/evidence'
paths={
 'final_contract':Path('work/r20-walking-fix/dynamics/release_v4/verified_models/model_contract_contact4.json'),
 'R17_mass':Path('work/r17-module-mount/mass_COM_update.json'),
 'R13_mass':Path('work/r13-electronics/torque/inputs/mass_R13_inertia_envelope.json'),
}
data={k:json.loads(p.read_text()) for k,p in paths.items()}
names={
 'Regen':'electrical_Regen','IMU':'electrical_IMU','Thermal75':'electrical_Thermal75','Thermal65':'electrical_Thermal65',
 'MIC':'electrical_MIC','AMP_and_speaker_group':'electrical_AUDIO_internal_no_external_wing',
 'U2D2':'electrical_U2D2_USB_TTL','camera_with_included_cable':'camera_module_and_included_cable'}
rows=[]
for item,name in names.items():
 matches={k:[(i,r) for i,r in d['rows'] and enumerate(d['rows']) if r['name']==name] for k,d in data.items()}
 assert all(len(v)==1 for v in matches.values())
 final=matches['final_contract'][0][1]; source=matches['R17_mass'][0][1]
 assert abs(final['mass_kg']*1000-source['nominal_g'])<1e-10
 assert max(abs(a*1000-b) for a,b in zip(final['COM_HOME_m'],source['COM_home_mm']))<1e-10
 assert abs(matches['R13_mass'][0][1]['nominal_g']-source['nominal_g'])<1e-10
 rows.append({'item':item,'mass_row_name':name,'nominal_g':source['nominal_g'],'low_g':source['low_g'],'high_g':source['high_g'],'link':final['link'],'COM_HOME_mm':source['COM_home_mm'],'mass_category':source['category'],'basis':source['basis'],'measured':source['measured'],'mass_and_COM_equal_R17':True,'nominal_mass_equal_R13':True,'locations':{k:{'path':str(paths[k]),'json_pointer':f'/rows/{v[0][0]}'} for k,v in matches.items()},'final_model_row':final,'inherited_source_row':source})
poolnames=['head_audio_chamber_unbuilt','electrical_mounts_trunk_remaining_after_R13','non_CM4_head_electrical_mounts_remaining_remaining_after_R13','wire_loom_trunk_remaining_after_R13','wire_loom_head_remaining_after_R13']
pools=[]
for n in poolnames:
 f=next(r for r in data['final_contract']['rows'] if r['name']==n); s=next(r for r in data['R17_mass']['rows'] if r['name']==n)
 pools.append({'final_model_row':f,'inherited_source_row':s,'nominal_g':f['mass_kg']*1000,'interpretation':'Shared remaining allowance; not allocated exclusively to these missing installations; not proof the future hardware fits this mass/COM.'})
sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()}
sources[str(Path(__file__).relative_to(ROOT))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
result={'status':'MASS_BUDGET_INCLUDED_INSTALLATION_GEOMETRY_AND_FINAL_INERTIA_NOT_PROVEN','model_unchanged':True,'final_nominal_total_kg':data['final_contract']['mass_kg'],'pending_electronics_groups_nominal_g':sum(r['nominal_g'] for r in rows),'pending_electronics_groups_low_g':sum(r['low_g'] for r in rows),'pending_electronics_groups_high_g':sum(r['high_g'] for r in rows),'rows':rows,'shared_remaining_pools':pools,'sources':sources,'scope':['All eight named groups occur exactly once in final v4 mass rows. The six PCBs plus U2D2/camera are not zero-mass omissions in that model.','AMP group includes its speaker; this is not bare-PCB mass and must not be added a second time.','Camera 15 g is inherited OS05A10 catalogue mass including cable, with placement pending; other seven groups reuse component mass budgets. No physical weighing is claimed.','All assigned COMs/inertias remain engineering assumptions, so comparison of two gaits on the same model is valid only within that model.','Absent installation geometry, connectors, clearances, support rigidity, actual cable routing and final COM are outside the whole-CAD motion certificate. Shared pools do not establish they will fit.','Do not add these same board masses again when materializing CAD. Replace the existing rows and debit corresponding mount/wire pools using actual part masses and locations, then rerun dynamics.','This audit does not revise or requalify the current model.']}
p=OUT/'pending_electronics_mass_audit.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(p.relative_to(ROOT));print('nominal_g',result['pending_electronics_groups_nominal_g']);print('SHA',hashlib.sha256(p.read_bytes()).hexdigest())
