from pathlib import Path
import hashlib,json,re
R=Path(__file__).parent;V=R/'verification';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();N='Microduck_Entry_5V_R22'
checks={}
erc=json.loads((V/'ERC.json').read_text());checks['ERC_violations']=sum(len(q['violations'])for q in erc['sheets'])
for name in['DRC_original_rules','DRC_all_rules_enabled','DRC_fabrication_rules']:
 d=json.loads((V/(name+'.json')).read_text());checks[name]=dict(violations=len(d['violations']),unconnected=len(d['unconnected_items']),schematic_parity=len(d['schematic_parity']));assert all(v==0 for v in checks[name].values())
assert checks['ERC_violations']==0
nom=json.loads((V/'DRC_nominal_0p20.json').read_text());assert len(nom['violations'])==4 and all(v['type']=='clearance'and'0.1750' in v['description']for v in nom['violations'])
checks['strict_0p20_local_exceptions']=nom['violations']
source=R.parents[2]/'work/r13-electronics/inherited/Entry_5V_R8';sourcehash={p.name:sha(p)for p in source.glob('Microduck_Entry_5V_R8.*')if p.suffix in['.kicad_pcb','.kicad_sch','.kicad_pro']}
assert sourcehash['Microduck_Entry_5V_R8.kicad_pcb']=='864652875e261d18fdd1146cd26b4253dcd7b37ad463e8328c32e4d5fbdf2fbe'
assert sourcehash['Microduck_Entry_5V_R8.kicad_sch']=='706ad3ca2b3a332714a78366f6962d1604a7eb739af1dabbcde82db034ddddc1'
assert sha(R/(N+'.kicad_pro'))==sourcehash['Microduck_Entry_5V_R8.kicad_pro']
boardhash=sha(R/(N+'.kicad_pcb'));equiv=json.loads((V/'electrical_equivalence.json').read_text());iface=json.loads((R/'Board_Interface_R22_Entry.json').read_text());dc=json.loads((V/'DC_New_vs_Source_Final.json').read_text());binding=json.loads((V/'native_geometry_binding.json').read_text())
assert boardhash==equiv['pcb_sha256']==iface['native_pcb_sha256']==dc['file_sha256'][N+'.kicad_pcb']==binding['native_pcb_sha256']
for label in['full_rules','fabrication_rules','nominal_0p20']:assert sha(V/label/(N+'.kicad_pcb'))==boardhash
checks.update(status='FROZEN DESIGN REVIEW CANDIDATE; NOT MANUFACTURING/THERMAL QUALIFIED',native_pcb_sha256=boardhash,source_sha256=sourcehash,source_pro_unchanged=True,all_ref_value_and_IC_MPN_retained=True,all_159_schematic_pins_and_200_numeric_copper_pad_instances_equal=True,board_mm=[52,42,1.6],area_reduction_percent=25.3333333333333,physical_tests_performed=False)
(V/'FINAL_VALIDATION.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
files=[]
for ext in['.kicad_pro','.kicad_sch','.kicad_pcb','.kicad_dru']:files.append(R/(N+ext))
for name in['Microduck_Entry_R8.kicad_sym','fp-lib-table','sym-lib-table','Board_Interface_R22_Entry.json','README_R22_Entry.md','routes.json','build_entry.py','apply_routes.py','finalize_labels.py','export_interface.py','verify_electrical.py','export_dc_geometry.py','solve_dc_copper.py','validate_dc_solver.py','inspect_copper.py','power_audit.py','final_power_report.py','make_validation_copies.py','finalize_manifest.py']:files.append(R/name)
for sub in['footprints','preview','assembly']:files.extend(p for p in(R/sub).rglob('*')if p.is_file())
for name in['ERC.json','DRC_original_rules.json','DRC_all_rules_enabled.json','DRC_fabrication_rules.json','DRC_nominal_0p20.json','full_rule_promotions.json','electrical_equivalence.json','pin_equivalence.csv','source_schematic.xml','new_schematic.xml','DC_New_vs_Source_Final.json','power_copper_thermal_audit.json','copper_polygons.json','source_dc_geometry.json','r22_dc_geometry.json','native_geometry_binding.json','dc_solver_analytic_checks.json','FINAL_VALIDATION.json','ina226_DGS_land.png','ads1115_DGS_land.png','JST_SH_BM_3.png','JST_SH_BM_4.png']:files.append(V/name)
files.extend(V.glob('dc_sheet_*.json'))
manifest=dict(status='Review deliverables only; generated cache and exploratory history excluded',file_count=len(set(files)),files=[dict(path=str(p.relative_to(R)),bytes=p.stat().st_size,sha256=sha(p))for p in sorted(set(files))]);(R/'DELIVERABLE_SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print('Frozen',boardhash,'deliverable files',manifest['file_count'])
