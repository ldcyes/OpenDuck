from pathlib import Path
import json,copy,math,csv,hashlib
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).parent;load=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
basepath=ROOT/'work/r23-power-integration/harness/final/Complete_Conductor_Lengths.json';j=load(basepath);new=copy.deepcopy(j);rows={r['conductor_id']:r for r in new['rows']};tails={r['port']:r for r in load(O/'tails/manifest.json')['routes']};selected=load(O/'assembly_selection.json');freepath=ROOT/Path(next(p for p in selected['items']if p['name']=='R25_NECK_FREE_P1')['step']).parent.parent/'manifest.json';free=load(freepath)['parts'];oldfree={r['name']:r for r in load(ROOT/'work/r23-power-integration/integration/mass_final/R23_mass_ledger.json')['free_rows']};changes=[]
for p in free:
 port=p['port_id'];r=rows[p['conductor_id']];t=tails[port];delta=t['delta_length_mm']+p['nominal_common_length_mm']-oldfree['R23_NECK_FREE_'+port]['length_mm'];awg=16 if port[0]=='P'else 28;mg=(8.3 if awg==16 else .91)*453.59237/304800;res=(4.81 if awg==16 else 68.6)/304800
 before=copy.deepcopy(r)
 for k in ['installed_length_lower_mm','installed_length_upper_mm']:r[k]+=delta
 r['raw_cut_nominal_mm']=math.ceil(r['installed_length_upper_mm']+10);r['minimum_discard_trim_mm']=r['raw_cut_nominal_mm']-1-r['installed_length_upper_mm'];r['maximum_installed_wire_mass_g']+=delta*mg;r['R20_wire_max_ohm']+=delta*res;r['R105_wire_max_ohm']+=delta*res*1.33405
 if 'gauge_installed_upper_lengths_mm'in r:r['gauge_installed_upper_lengths_mm']['16']+=delta
 r['R25_delta_length_mm']=delta;r['R25_upper_port']=port;r['R25_motion_release']=False;r['stages'].append(dict(role='R25_replace_free_and_upper_fixed_delta',length_mm=delta,free_source=str(freepath.relative_to(O)),upper_source='tails/manifest.json'))
 r['process_notes']+=' R25 bottom-entry candidate: form and terminate after guide assembly; finite pose checks do not authorize cutting or motion. Verify first-article length and slack. No discarded trim stored as hidden loop.'
 changes.append(dict(port=port,conductor_id=p['conductor_id'],delta_mm=delta,old_raw_cut_mm=before['raw_cut_nominal_mm'],candidate_raw_cut_mm=r['raw_cut_nominal_mm'],new_free_mm=p['nominal_common_length_mm'],new_upper_fixed_mm=t['length_mm']))
new.update(status='R25_FULL59_CUT_CANDIDATE_31_CHANGED_NOT_RELEASED',R25_changes=changes,R25_sources={str(p.relative_to(ROOT)):sha(p)for p in [basepath,O/'tails/manifest.json',freepath,Path(__file__)]},physical_approved=False,manufacturing_approved=False)
(O/'Complete_Conductor_Lengths_R25.json').write_text(json.dumps(new,indent=2)+'\n')
fields=['conductor_id','R25_upper_port','from_endpoint','to_endpoint','net','color','awg','MPN','installed_length_lower_mm','installed_length_upper_mm','raw_cut_nominal_mm','raw_cut_tolerance_mm','R25_delta_length_mm','R20_wire_max_ohm','R105_wire_max_ohm']
with(O/'Conductor_Cut_Candidate_R25.csv').open('w',encoding='utf-8-sig',newline='')as f:
 w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(new['rows'])
print('WIRE_LEDGER',len(new['rows']),len(changes))
