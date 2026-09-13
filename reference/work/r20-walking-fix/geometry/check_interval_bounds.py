"""Whole-assembly material separation over boxes of every numerical joint state.

A box contains every recorded integrator endpoint and any linear connections.
This proves rigid CAD separation where certified, not true-time ODE solutions,
elastic motion, unmodelled cables, or physical hardware. Positive witnesses are
only evaluated at actual recorded numerical anchors. No same-link fit exemption.
"""
from pathlib import Path
import sys,json,argparse,time
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
from check_candidate_v2 import previous,new_context

def displacement_bound(rho,anchor,lo,hi):
 deviation=np.maximum(np.abs(lo-anchor),np.abs(hi-anchor))
 return np.asarray(rho)@(2*np.sin(np.radians(np.minimum(180.,deviation))/2))

def validate_intervals(data,names):
 rows=data['intervals'];prior=None;steps=0
 if not np.isfinite(data['dt_s'])or data['dt_s']<=0:raise ValueError('INVALID_DT')
 if type(data['total_integration_steps'])is not int or type(data['interval_count'])is not int:raise ValueError('NONINTEGER_TOTAL_COUNT')
 if not rows or len(rows)!=data['interval_count']:raise ValueError('INTERVAL_COUNT')
 for row in rows:
  if not np.isfinite([row['start_s'],row['end_s']]).all()or row['end_s']<=row['start_s']:raise ValueError('INVALID_TIME')
  if any(set(row[k])!=set(names) for k in ['q_min_HOME_deg','q_max_HOME_deg','q_start_HOME_deg','q_end_HOME_deg']):raise ValueError('MISSING_OR_EXTRA_JOINT')
  lo=np.array([row['q_min_HOME_deg'][n]for n in names]);hi=np.array([row['q_max_HOME_deg'][n]for n in names]);a=np.array([row['q_start_HOME_deg'][n]for n in names]);b=np.array([row['q_end_HOME_deg'][n]for n in names])
  if not np.isfinite([lo,hi,a,b]).all()or np.any(lo>hi)or np.any(np.minimum(a,b)<lo-1e-10)or np.any(np.maximum(a,b)>hi+1e-10):raise ValueError('INVALID_EXTREMA_OR_ENDPOINT')
  if prior is not None and (abs(row['start_s']-prior['end_s'])>1e-8 or any(abs(row['q_start_HOME_deg'][n]-prior['q_end_HOME_deg'][n])>1e-9 for n in names)):raise ValueError('DISCONNECTED_INTERVALS')
  count=row['integration_steps']
  if type(count)is not int or count<1 or abs(row['end_s']-row['start_s']-count*data['dt_s'])>1e-7:raise ValueError('DT_STEP_COUNT_MISMATCH')
  steps+=count;prior=row
 if steps!=data['total_integration_steps']:raise ValueError('INTEGRATION_COVERAGE_MISMATCH')

def scan(data,scanner):
 validate_intervals(data,scanner.jnames);rows=data['intervals'];N=len(rows);P=len(scanner.pairs)
 low=np.array([[r['q_min_HOME_deg'][n]for n in scanner.jnames]for r in rows]);high=np.array([[r['q_max_HOME_deg'][n]for n in scanner.jnames]for r in rows]);anchors=np.array([[r['q_start_HOME_deg'][n]for n in scanner.jnames]for r in rows])
 clear=np.zeros(P,dtype=np.int64);margin=np.zeros(P,dtype=np.int64);unproven=np.zeros(P,dtype=np.int64);witnesses={};exceptions={};certificates=[];nodes=0;started=time.time()
 def certify(ids,a,b,level,lower):
  if not len(ids):return
  clear[ids]+=b-a
  if level=='2.2mm':margin[ids]+=b-a
  certificates.append(dict(first_interval=a,end_interval_exclusive=b,pair_ids=ids.tolist(),level=level,minimum_lower_bound_mm=float(np.min(lower))))
 def unresolved(ids,a,b,reason):
  unproven[ids]+=b-a
  for i0 in ids:
   i=int(i0)
   if i not in exceptions:exceptions[i]=dict(pair=list(scanner.pairs[i]),first_interval=a,end_interval_exclusive=b,reason=reason)
 def visit(a,b,ids):
  nonlocal nodes
  if not len(ids):return
  nodes+=1;mid=(a+b)//2;anchor=anchors[mid];lo=low[a:b].min(0);hi=high[a:b].max(0);q=dict(zip(scanner.jnames,anchor.tolist()));ts=previous.transforms(scanner.joints,q)
  moving=displacement_bound(scanner.rho[ids],anchor,lo,hi);br=scanner.broad(scanner.bounds(ts))[ids];lower=br-moving-1e-5
  ok=lower>=2.2;certify(ids[ok],a,b,'2.2mm',lower[ok]);small=(lower>=1e-4)&~ok;certify(ids[small],a,b,'positive_material',lower[small]);remain=~(ok|small);ids=ids[remain];moving=moving[remain]
  deferred=[]
  for i0,motion in zip(ids,moving):
   i=int(i0)
   # min_gap is capped at 3 mm; an exact call cannot certify a larger bound.
   if motion>=2.9998 and b-a>1:deferred.append(i);continue
   r=scanner.exact(i,q,ts);lb=r['gap_mm']-motion-1e-5
   if lb>=1e-4:certify(np.array([i]),a,b,'2.2mm'if lb>=2.2 else 'positive_material',np.array([lb]));continue
   if r['common_mm3']>1e-9:
    if i not in witnesses:witnesses[i]=scanner.row(i,r,q,time_s=rows[mid]['start_s'],interval_anchor=mid)
    unresolved(np.array([i]),a,b,'ACTUAL_ANCHOR_RAW_POSITIVE_REQUIRES_NAMED_ADJUDICATION');continue
   if r['gap_mm']<=1e-4:
    # A touching nominal interface cannot satisfy strict separation. Preserve
    # this entire box as unresolved; do not spend every integration interval
    # repeating a zero-gap result or silently promote it to a fit exemption.
    unresolved(np.array([i]),a,b,'ACTUAL_ANCHOR_ZERO_GAP_ENTIRE_BOX_EXPLICITLY_UNRESOLVED');continue
   if b-a==1:unresolved(np.array([i]),a,b,'ENCLOSURE_TOO_LOOSE_OR_ZERO_GAP');continue
   deferred.append(i)
  if nodes%100==0:print('BOX',nodes,'interval',a,b,'deferred',len(deferred),'exact',scanner.calls,'seconds',round(time.time()-started,1),flush=True)
  if deferred:
   cut=(a+b)//2;dd=np.array(deferred,dtype=int);visit(a,cut,dd);visit(cut,b,dd)
 ids=np.flatnonzero(scanner.cross);visit(0,N,ids)
 if not np.all((clear+unproven)[ids]==N):raise AssertionError('PAIR_INTERVAL_PARTITION_INCOMPLETE')
 scanner.ctx['sources'].verify()
 return dict(status='NUMERICAL_STATE_JOINT_BOX_MATERIAL_CERTIFICATES_WITH_EXPLICIT_UNRESOLVED_PAIRS',physical_approved=False,all_material_separation_certified=bool(np.all(unproven[ids]==0)),assembly_parts=len(scanner.names),full_pair_count=P,cross_link_pairs=len(ids),same_link_pairs_require_static_material_review=int((~scanner.cross).sum()),interval_count=N,total_integration_steps=data['total_integration_steps'],dt_s=data['dt_s'],pair_interval_requests=int(N*len(ids)),certified_material_pair_intervals=int(clear.sum()),certified_2p2mm_pair_intervals=int(margin.sum()),unresolved_pair_intervals=int(unproven.sum()),pair_index=[list(p)for p in scanner.pairs],certificates=certificates,unresolved_pairs=[dict(e,unresolved_intervals=int(unproven[i]),certified_material_intervals=int(clear[i]))for i,e in exceptions.items()],raw_positive_actual_anchors=list(witnesses.values()),scope=__doc__,sources=scanner.ctx['sources'].entries.copy())

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--bounds',required=True);ap.add_argument('--selection',required=True);ap.add_argument('--manifest',required=True);ap.add_argument('--label',required=True);a=ap.parse_args()
 ctx=new_context(a.selection,a.manifest);ctx['sources'].bind(__file__);data=ctx['sources'].json(a.bounds)
 for p,h in data['sources'].items():ctx['sources'].bind(p,h)
 scanner=previous.Scan(ctx);result=scan(data,scanner);out=HERE/a.label;out.mkdir(exist_ok=True);p=out/'numerical_state_box_check.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('DONE',p,'raw_positive',len(result['raw_positive_actual_anchors']),'unresolved',len(result['unresolved_pairs']),flush=True)
if __name__=='__main__':main()
