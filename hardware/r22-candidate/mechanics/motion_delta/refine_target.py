"""Tighten only positive dynamic certificates below2.2mm, preserving raw result."""
from pathlib import Path
import sys,json,time
sys.dont_write_bytecode=True
import check_delta as c
import numpy as np
OUT=c.OUT;ROOT=c.ROOT;c.START=time.monotonic();c.LOG=(OUT/'target_progress.jsonl').open('w',buffering=1)
d=json.loads((OUT/'inputs.json').read_text());b=json.loads((ROOT/d['interval_bounds_path']).read_text());base=json.loads((OUT/'result.json').read_text());s=c.Scan(d,b);dynamic=set(base['dynamic_pair_ids']);original=[x for x in base['certificates']if x['level']=='positive_separation'and set(x['pair_ids'])&dynamic]
for e in base['exact_calls']:
 pid=e['pair_id'];q=e['anchor_HOME_deg'];active=np.flatnonzero(s.rho[pid]);s.exact_cache[(pid,tuple(float(q[s.jnames[j]])for j in active))]=e
certs=[];remaining=[];calls_before=len(s.exact_log);nodes=0

def visit(start,end,ids,original_positive_lower,depth=0):
 global nodes
 if not len(ids):return
 nodes+=1;anchor=(start+end)//2;q=s.anchor[anchor];lo=s.low[start:end].min(0);hi=s.high[start:end].max(0);dev=np.maximum(abs(lo-q),abs(hi-q));move=s.rho[ids]@(2*np.sin(np.radians(np.minimum(180.,dev))/2));ts,bbs=s.pose(q);g=s.broad(bbs,ids);lower=g-move-c.GUARD;ok=lower>=c.TARGET
 if ok.any():certs.append({'start_interval':start,'end_interval_exclusive':end,'pair_ids':ids[ok].tolist(),'minimum_lower_bound_mm':float(lower[ok].min()),'method':'refined_interval_AABB','anchor_interval_index':anchor})
 todo=ids[~ok];moves=move[~ok];split=[]
 for pid,movement in zip(todo,moves):
  gap,axis=s.planes(pid,ts);lb=gap-movement-c.GUARD
  if lb>=c.TARGET:certs.append({'start_interval':start,'end_interval_exclusive':end,'pair_ids':[int(pid)],'minimum_lower_bound_mm':float(lb),'method':'refined_interval_support_plane','anchor_interval_index':anchor});continue
  # Exact anchor may witness a true below-target distance even when the box is wide.
  e=s.exact(pid,ts,q,'target_refinement')
  if e['status']=='computed':
   lb=e['gap_mm']-movement-c.GUARD
   if lb>=c.TARGET:certs.append({'start_interval':start,'end_interval_exclusive':end,'pair_ids':[int(pid)],'minimum_lower_bound_mm':float(lb),'method':'refined_interval_mesh_distance','anchor_interval_index':anchor});continue
   if e['gap_mm']<c.TARGET-c.GUARD:
    remaining.append({'start_interval':start,'end_interval_exclusive':end,'pair_id':int(pid),'status':'BELOW_TARGET_AT_ACTUAL_ANCHOR','actual_anchor_interval':anchor,'actual_anchor_time_s':s.records[anchor]['start_s'],'actual_anchor_gap_mm':e['gap_mm'],'original_positive_lower_bound_mm':original_positive_lower,'maximum_distance_change_mm':float(movement)});continue
  if e['status']!='computed'or end-start==1:
   remaining.append({'start_interval':start,'end_interval_exclusive':end,'pair_id':int(pid),'status':'TARGET_NOT_PROVED','actual_anchor_interval':anchor,'exact':e,'original_positive_lower_bound_mm':original_positive_lower});continue
  split.append(pid)
 if nodes%10==0:c.log('target_node',node=nodes,start=start,end=end,input=len(ids),split=len(split),remaining=len(remaining))
 if split:
  mid=(start+end)//2;arr=np.array(split,dtype=np.int32);visit(start,mid,arr,original_positive_lower,depth+1);visit(mid,end,arr,original_positive_lower,depth+1)
try:
 for k,row in enumerate(original):
  visit(row['start_interval'],row['end_interval_exclusive'],np.array(row['pair_ids'],dtype=np.int32),row['minimum_lower_bound_mm'])
  if(k+1)%25==0:c.log('target_original_spans',completed=k+1,total=len(original))
finally:s.w.close()
result={'status':'DYNAMIC_TARGET_REFINEMENT_WITH_ACTUAL_ANCHOR_WITNESSES','base_result_sha256':c.sha(OUT/'result.json'),'inputs_sha256':c.sha(OUT/'inputs.json'),'script_sha256':c.sha(__file__),'original_positive_certificate_count':len(original),'target_mm':c.TARGET,'target_certificates':certs,'remaining_below_target_spans':remaining,'new_exact_calls':s.exact_log,'nodes':nodes,'elapsed_s':time.monotonic()-c.START,'limits':['Original positive separation remains valid for every refined/remaining span.','A below-target anchor is an actual recorded-state witness, not a whole-span minimum or whole-span collision.','No mechanical approval from the2.2mm threshold; tolerances, harness deformation and real motion remain unqualified.']}
(OUT/'target_refinement.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');c.log('target_complete',original_spans=len(original),target_certificates=len(certs),remaining_spans=len(remaining),new_exact_calls=len(s.exact_log))
