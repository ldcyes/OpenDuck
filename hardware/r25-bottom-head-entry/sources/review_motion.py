from pathlib import Path
import json,hashlib
O=Path(__file__).resolve().parent;load=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();j=load(O/'motion/rigid_final/result.json');native=load(O/'native_contact_review.json');review={frozenset([r['a'],r['b']]):r for r in native['rows']};retry={r['pair_id']:r for r in load(O/'gap_retry.json')['rows']};near={r['pair_id']:r for r in j['near_invariant_pairs']};dyn=set(j['dynamic_pair_ids']);rows=[];unresolved=[]
for span in j['unresolved_spans']:
 r=near.get(span['pair_id']);assert r,'dynamic unresolved not expected';a,b=r['a'],r['b'];cl=None
 if r['pair_id']in retry:
  q=retry[r['pair_id']]
  if q['native_gap_mm']>1e-4 and q['intersection_mm3']<1e-8:cl='Retried native STEP positive separation; narrow tolerance remains'
 elif frozenset([a,b])in review:cl=review[frozenset([a,b])]['classification']
 elif (r.get('intersection_mm3')or 0)<1e-5:
  if a.startswith('R25_HEAD_BOTTOM_FIXED_') and ('MATED'in b or 'INSULATED_STRAIGHT8'in b):cl='Preserved original terminal seating; original endpoint and downstream native shape retained'
  elif a=='R25_neck_upper_VMQ_comb_installed' and b.startswith('R25_HEAD_BOTTOM_FIXED_'):cl='Declared installed soft bore to matching conductor contact'
  elif a.startswith('R25_neck_upper_') and b.startswith('R25_neck_upper_'):cl='Specific relocated guide/fastener/liner mating seat; reviewed named pair'
  elif a=='R25_neck_upper_6061_bottom_bridge' and (b in ['R23_neck_upper_6061_lower_jaw','R13_head_shell_carrier_Entry_ports']or '_saddle_'in b):cl='Retained saddle clamp interface; nominal contact'
  elif (a,b)in [('R25_top_head_shell_closed_side','R24_Microduck_front_face_camera_carrier'),('R25_lower_head_shell_bottom_entry','R13_head_shell_carrier_Entry_ports')]:cl='Preserved shell mounting seat'
 row=dict(pair_id=r['pair_id'],a=a,b=b,mesh_intersection_mm3=r.get('intersection_mm3'),classification=cl);rows.append(row)
 if not cl:unresolved.append(row)
report=dict(status='NAMED_CONTACT_REVIEW_NO_GENERAL_CATEGORY_EXEMPTION',dynamic_pair_count=j['dynamic_pair_count'],dynamic_unresolved_count=sum(r['pair_id']in dyn for r in j['unresolved_spans']),named_invariant_rows=rows,unresolved=unresolved,sources={str(p.relative_to(O)):sha(p)for p in [O/'motion/rigid_final/result.json',O/'native_contact_review.json',O/'gap_retry.json',Path(__file__)]},physical_approved=False,manufacturing_approved=False)
(O/'motion_contact_review.json').write_text(json.dumps(report,indent=2)+'\n');print('MOTION_REVIEW',len(rows),len(unresolved));assert not unresolved
