"""Audit source equality before combining unchanged and revised pair certificates."""
from pathlib import Path
import argparse,json,hashlib,itertools
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--selection',required=True);ap.add_argument('--revision-folder',required=True);ap.add_argument('--revision-label',required=True);ap.add_argument('--output',default='final_reference_review.json');a=ap.parse_args();sources={}
 def bind(p,h=None):
  p=Path(p);p=p if p.is_absolute()else ROOT/p;v=hashlib.sha256(p.read_bytes()).hexdigest()
  if h and h!=v:raise ValueError(('SOURCE_CHANGED',str(p)))
  key=str(p.relative_to(ROOT))
  if key in sources and sources[key]!=v:raise ValueError('CONFLICTING_SOURCE_BINDING')
  sources[key]=v;return p
 def read(p):
  d=json.loads(bind(p).read_text())
  for x,h in d.get('sources',{}).items():
   if isinstance(h,str)and len(h)==64:bind(x,h)
  return d
 basefolder='work/r20-walking-fix/geometry/four_steps_R20_v1/'
 Bf=read(basefolder+'four_steps_R20_v1_finite.json');Bc=read(basefolder+'four_steps_R20_v1_continuous.json');D=read(a.revision_folder+'/revision_scope.json');Rf=read(a.revision_folder+'/'+a.revision_label+'_finite.json');Rc=read(a.revision_folder+'/'+a.revision_label+'_continuous.json')
 original=read('work/r20-walking-fix/geometry/four_steps_input_v1.json');current=read('work/r20-walking-fix/geometry/final_reference_input_v2.json');oldsel=read(D['prior_selection']);reviewed=read(D['current_selection']);final=read(a.selection);O={r['name']:r for r in oldsel['items']};R={r['name']:r for r in reviewed['items']};F={r['name']:r for r in final['items']}
 fields=['mesh','mesh_sha256','step','step_sha256','R','t_mm','link_frame','geometry_scale']
 assert R.keys()==F.keys()and all(all(R[n].get(k)==F[n].get(k)for k in fields)for n in F),'FINAL_GEOMETRY_NOT_REVIEWED'
 assert oldsel['joints']==reviewed['joints']==final['joints']
 assert D['changed_material_names']==['R20_left_hip_rail_offset']and D['removed_names']==['R11_hip_l_rail_2']
 oldname=D['removed_names'][0];newname=D['changed_material_names'][0];unchanged=set(F)-{newname}
 assert len(unchanged)==556 and all(all(O[n].get(k)==F[n].get(k)for k in fields)for n in unchanged)
 assert len(original['segments'])==len(current['segments'])==Bc['segment_count']==Rc['segment_count']==772
 for old,new in zip(original['segments'],current['segments']):
  assert old['id']==new['id']and old['q0']==new['q0']and old['q1']==new['q1'],'RETIMING_CHANGED_GEOMETRIC_PATH'
 assert len(original['poses'])==len(current['poses'])==Bf['pose_count']==Rf['pose_count']
 assert all(x['q']==y['q']for x,y in zip(original['poses'],current['poses']))
 pairs=list(itertools.combinations(F,2));cross=sum(F[x]['link_frame']!=F[y]['link_frame']for x,y in pairs);fresh=[(x,y)for x,y in pairs if newname in [x,y]];freshcross=sum(F[x]['link_frame']!=F[y]['link_frame']for x,y in fresh)
 assert len(pairs)==Bf['pair_count']==154846 and cross==Bc['cross_link_pairs']==105219
 assert len(fresh)==Rf['pair_count']==556 and freshcross==Rc['cross_link_pairs']==551
 assert sum(r['requested_cross_link_pairs']for r in Bc['coverage'])==772*cross
 assert sum(r['requested_cross_link_pairs']for r in Rc['coverage'])==772*freshcross
 # All changed free-motion pairs must satisfy the full nominal target.
 assert not Rc['positive_pairs']and not Rc['below2p2_or_unproven_pairs']and all(r['not_certified2p2mm']==0 for r in Rc['coverage']),'REVISED_PATH_NOT_CLEAR'
 retained_positive=[r for r in Bc['positive_pairs']if oldname not in [r['maximum']['a'],r['maximum']['b']]]
 retained_low=[r for r in Bc['below2p2_or_unproven_pairs']if oldname not in [r['a'],r['b']]]
 finite_positive=[r for r in Bf['positive_pairs']if oldname not in [r['maximum']['a'],r['maximum']['b']]]+Rf['positive_pairs']
 expected={frozenset(['neck_pitch_motor',n])for n in ['R13p3_neck_pitch_active_through_M3_ears','R13p3_neck_pitch_idler_through_M3_ears']}
 assert {frozenset([r['maximum']['a'],r['maximum']['b']])for r in retained_positive}==expected
 assert all(s[k].get('neck_pitch',0)==0 for s in current['segments']for k in ['q0','q1'])
 historical=read('work/r19-walking-simulation/review/four_baseline_pairs/adjudication.json');neck=[r for r in historical['rows']if frozenset(r['pair'])in expected]
 assert {frozenset(r['pair'])for r in neck}==expected
 for r in neck:
  assert r['original_analytic_STEP_common_mm3']<=1e-9
  for n,b in r['source_part_rows'].items():assert all(b.get(k)==F[n].get(k)for k in fields)
 head=read('work/r20-walking-fix/head_mount/contact_adjudication.json')
 assert head['unexpected_positive_count']==0 and head['positive_count']==len(head['rows'])==57
 hip=read('work/r20-walking-fix/hip_relief/candidate_v4/local_release_audit.json')
 for sourcefield in ['inputs','verified_sources']:
  for p,h in hip[sourcefield].items():bind(p,h)
 hip_manifest=read('work/r20-walking-fix/hip_relief/candidate_v4/candidate_manifest.json')
 hr=hip_manifest['parts'][0]
 assert all(hr.get(k)==F[newname].get(k)for k in fields)
 allowed_host_pairs={frozenset([newname,n])for n in ['left_hip_roll_idler','left_hip_pitch_active']}
 assert {frozenset([r['maximum']['a'],r['maximum']['b']])for r in Rf['positive_pairs']}<=allowed_host_pairs,'NEW_STATIC_MATERIAL_POSITIVE_OUTSIDE_REVIEWED_PORTS'
 assert hip['summaries']['native_STEP_hosts_common_mm3']==[0.0,0.0]
 assert all(v['failed_intervals']==0 and v['minimum_certified_mesh_gap_mm']>=2.2 for v in hip['summaries']['continuous_mesh_clearance'].values())
 guard=read('work/r19-walking-simulation/review/six_walking_penetrations/adjudication.json');targetpairs={frozenset(r['pair'])for r in guard['rows']}
 assert not any(frozenset([r['a'],r['b']])in targetpairs for r in retained_low)
 assert not any(n in F for n in ['R11_CM4_front_clamp_bar_1','R11_CM4_front_clamp_bar_2'])
 bind(__file__)
 out=dict(status='REFERENCE_GEOMETRY_COMPOSITION_VERIFIED_WITH_DECLARED_INTERFACE_LIMITS',physical_approved=False,manufacturing_approved=False,all_assembly_free_clearances_2p2mm_passed=False,assembly_parts=557,whole_pair_count=len(pairs),reference_pose_count=len(current['poses']),reference_segment_count=772,cross_link_pairs=cross,cross_link_pair_segments=772*cross,retained_cross_pair_segments=772*(cross-freshcross),new_cross_pair_segments=772*freshcross,final_selection=a.selection,retiming_geometry_exactly_identical=True,final_metadata_geometry_exactly_identical=True,head_duplicate_bars_removed=True,original_six_gait_collision_pairs_certified_at_least2p2mm=True,new_hip_rail_all_cross_link_reference_pairs_certified_at_least2p2mm=True,remaining_raw_cross_positive_pairs=retained_positive,neck_original_STEP_zero_and_reference_relative_pose_constant=True,remaining_below2p2_or_unproven_pair_count=len(retained_low),remaining_below2p2_or_unproven_pairs=retained_low,finite_raw_positive_pair_union=finite_positive,limits=['Reference only; actual integration uses a separate joint-box and floor review.','The source reports retain original and retimed time labels; this composition certifies identical q0/q1 lines with monotone scalar timing, not the old wall-clock labels.','Nominal rotating-motor contacts, electronic/reference envelopes, and remaining inherited narrow gaps are not silently converted into approved fits.','Hardware tolerances, flexible wiring, retention and loaded strength remain separate qualifications.'],sources=sources)
 p=HERE/a.output;p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('COMPOSED',len(retained_low),'remaining narrow/interface pairs;',len(finite_positive),'raw finite pairs')
if __name__=='__main__':main()
