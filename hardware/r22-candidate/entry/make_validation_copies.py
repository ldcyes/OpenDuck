from pathlib import Path
import json,shutil
R=Path(__file__).parent;N='Microduck_Entry_5V_R22'
for label in['full_rules','fabrication_rules']:
 dst=R/'verification'/label;dst.mkdir(exist_ok=True)
 for ext in['.kicad_pcb','.kicad_sch','.kicad_pro','.kicad_dru']:shutil.copyfile(R/(N+ext),dst/(N+ext))
 for n in ['fp-lib-table','sym-lib-table','Microduck_Entry_R8.kicad_sym']:
  if(R/n).exists():shutil.copyfile(R/n,dst/n)
 for q in R.iterdir():
  if q.is_dir()and(q.suffix=='.pretty'or q.name in['lib','libraries','footprints']):shutil.copytree(q,dst/q.name,dirs_exist_ok=True)
 p=dst/(N+'.kicad_pro');d=json.loads(p.read_text());sevs=d['board']['design_settings']['rule_severities'];promoted=[]
 for k,v in list(sevs.items()):
  if v=='ignore':sevs[k]='warning';promoted.append(k)
 p.write_text(json.dumps(d,indent=2))
 if label=='fabrication_rules':(dst/(N+'.kicad_dru')).write_text('''(version 1)
(rule "2oz absolute fabrication spacing" (constraint clearance (min 0.16mm)))
(rule "New traces minimum width" (condition "A.Type == 'Track'") (constraint track_width (min 0.20mm)))
(rule "Zone actual copper separation" (condition "A.Type == 'Zone' || B.Type == 'Zone'") (constraint clearance (min 0.20mm)))
''')
 (R/'verification/full_rule_promotions.json').write_text(json.dumps(promoted,indent=2))
