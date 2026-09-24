"""Conservative delta-only motion enclosure. Immutable source captures, mm/deg.

Certificates enclose every combination in each source interval joint box. Anchor
samples only evaluate distance; they are not used as a substitute for enclosures.
Unproved pairs remain in an explicit, exhaustive interval partition.
"""
from pathlib import Path
import sys,os,json,hashlib,time,itertools,multiprocessing as mp,traceback
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'work/r18-leg-hip-covers/review'),str(ROOT/'work/rk-mechanics/python-deps')]
import numpy as np
import trimesh
from motion_core import transforms,relative_transform,relative_motion_budget,apply_points
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
GUARD=1e-5;POSITIVE=1e-4;TARGET=2.2;TIMEOUT=4.0
LOG=None;OBJECTS=[]
def log(stage,**kw):
 r={'elapsed_s':round(time.monotonic()-START,3),'stage':stage,**kw}
 if LOG:LOG.write(json.dumps(r,ensure_ascii=False)+'\n');LOG.flush()
 print(json.dumps(r,ensure_ascii=False),flush=True)
def named(a,b):
 na,nb=a['name'],b['name'];ka,kb=a.get('kind'),b.get('kind');ra,rb=a.get('reference'),b.get('reference')
 if nb in a.get('host_thread_engagement',[])or na in b.get('host_thread_engagement',[]):return 'Exact source-named screw/thread host; smooth major-diameter thread representation, no engagement/strength qualification.'
 if a['input_group']==b['input_group']and a['input_group']in ['entry_reference','power_reference']and ra and ra==rb:
  kinds={ka,kb}
  if ra.startswith('J')and kinds=={'component_reference','mating_union_budget'}:return 'Same exact header reference BODY and MATED union; assembled union contains header body by construction.'
  if ra.startswith('J')and kinds=={'wire_straight_clearance_budget','formed_wire_clearance_budget'}:return 'Same exact header straight exit union and per-pin formed continuation; overlapping representation of one installed lead segment.'
  if ra.startswith(('W','P'))and kinds in [{'solder_process_budget','wire_straight_clearance_budget'},{'wire_straight_clearance_budget','formed_wire_clearance_budget'}]:return 'Same exact terminal reference: joint/straight conductor or straight/formed continuation representations.'
 for k in [1,2]:
  if {na,nb}=={f'R22_C101_lacing_{k}_installed_envelope',f'R22_C101_lacing_{k}_knot_budget'}:return 'Same exact PTFE lacing loop and its local knot budget representation.'
 return None

def exact_worker(conn):
 try:
  sys.path.insert(0,str(ROOT/'work/r12-motion/python-deps'))
  import manifold3d as md
  cache={}
  def one(i):
   if i not in cache:
    o=OBJECTS[i];m=md.Manifold(md.Mesh64(o['v'].astype(np.float64),o['f'].astype(np.uint64)))
    if m.status()!=md.Error.NoError:raise RuntimeError('INVALID_MANIFOLD '+o['q']['name']+' '+str(m.status()))
    cache[i]=m
   return cache[i]
  while True:
   task=conn.recv()
   if task is None:break
   a,b,rel,cap=task;t=time.monotonic()
   try:
    sa,sb=one(a),one(b).transform(np.asarray(rel)[:3]);gap=float(sa.min_gap(sb,cap));vol=None
    if gap<1e-7:vol=abs(float((sa^sb).volume()))
    conn.send({'status':'computed','gap_mm':gap,'intersection_mm3':vol,'worker_elapsed_s':time.monotonic()-t,'cap_mm':cap})
   except Exception as e:conn.send({'status':'error','error':repr(e)})
 except EOFError:pass
 except Exception as e:
  try:conn.send({'status':'worker_error','error':repr(e)})
  except Exception:pass

class Worker:
 def __init__(self):self.p=None;self.conn=None
 def close(self):
  if self.p is not None:
   if self.p.is_alive():self.p.terminate()
   self.p.join(timeout=1)
   self.conn.close();self.p=None
 def call(self,a,b,rel,cap=3.):
  if self.p is None:
   ctx=mp.get_context('fork');self.conn,child=ctx.Pipe();self.p=ctx.Process(target=exact_worker,args=(child,),daemon=True);self.p.start();child.close()
  start=time.monotonic();self.conn.send((a,b,rel.tolist(),cap))
  if not self.conn.poll(TIMEOUT):self.close();return {'status':'timeout','timeout_s':TIMEOUT,'wall_s':time.monotonic()-start}
  try:r=self.conn.recv()
  except EOFError:r={'status':'worker_eof'};self.close()
  r['wall_s']=time.monotonic()-start;return r

class Scan:
 def __init__(self,d,b):
  self.d=d;self.joints=d['joints'];self.jnames=[j['joint']for j in self.joints];self.J=len(self.jnames);self.N=len(b['intervals']);self.records=b['intervals']
  self.low=np.array([[r['q_min_HOME_deg'][j]for j in self.jnames]for r in self.records]);self.high=np.array([[r['q_max_HOME_deg'][j]for j in self.jnames]for r in self.records]);self.anchor=np.array([[r['q_start_HOME_deg'][j]for j in self.jnames]for r in self.records])
  assert np.all(self.low<=self.high)and np.all(self.low<=self.anchor+1e-10)and np.all(self.high>=self.anchor-1e-10)
  assert self.N==b['interval_count']and sum(r['integration_steps']for r in self.records)==b['total_integration_steps']
  for i,r in enumerate(self.records):
   assert set(r['q_min_HOME_deg'])==set(self.jnames)==set(r['q_max_HOME_deg'])
   qe=np.array([r['q_end_HOME_deg'][j]for j in self.jnames]);assert np.all(qe>=self.low[i]-1e-10)and np.all(qe<=self.high[i]+1e-10)
   assert abs((r['end_s']-r['start_s'])-r['integration_steps']*b['dt_s'])<1e-7
   if i:assert abs(self.records[i-1]['end_s']-r['start_s'])<1e-12 and self.records[i-1]['q_end_HOME_deg']==r['q_start_HOME_deg']
  self.objs=OBJECTS;self.sources={};self.items=d['items'];self.by={q['name']:q for q in self.items}
  for i,q in enumerate(self.items):
   p=ROOT/q.get('analysis_mesh',q['mesh']);h=q.get('analysis_mesh_sha256',q['mesh_sha256']);assert sha(p)==h,q['name'];self.sources[str(p.relative_to(ROOT))]=h
   m=trimesh.load(p,force='mesh');v=np.array(m.vertices)@np.array(q['R']).T+q['t_mm'];assert np.isfinite(v).all()
   bb=np.array([v.min(0),v.max(0)]);corners=np.array(list(itertools.product(*zip(bb[0],bb[1]))))
   centered=v-v.mean(0);ev,evec=np.linalg.eigh(centered.T@centered/max(1,len(v)))
   self.objs.append(dict(q=q,v=v,f=np.array(m.faces),bb=bb,corners=corners,axes=evec.T,center=v.mean(0)))
   if(i+1)%100==0:log('load_mesh',completed=i+1,total=len(self.items))
  K=d['new_installed_count'];assert all(q['is_new']for q in self.items[:K])and not any(q['is_new']for q in self.items[K:]);self.K=K
  pairs=list(itertools.product(range(K),range(K,len(self.items))))+list(itertools.combinations(range(K),2));self.pairs=np.array(pairs,dtype=np.int32);self.ia=self.pairs[:,0];self.ib=self.pairs[:,1];self.P=len(pairs)
  self.rho=np.zeros((self.P,self.J));cache={};zero={j:0 for j in self.jnames};one={j:1 for j in self.jnames}
  for pid,(a,b0)in enumerate(pairs):
   a,b0=self.objs[a],self.objs[b0]
   budget=relative_motion_budget(self.joints,a['q']['link_frame'],b0['q']['link_frame'],a['v'],b0['v'],zero,one,cache)
   for r,_,j in budget.terms:self.rho[pid,self.jnames.index(j)]+=r
   if(pid+1)%25000==0:log('motion_radii',completed=pid+1,total=self.P)
  self.dynamic=np.flatnonzero(np.any(self.rho>0,axis=1));self.static=np.flatnonzero(~np.any(self.rho>0,axis=1));self.w=Worker();self.exact_cache={};self.named_rows=[];self.near_static=[];self.exact_log=[];self.certs=[];self.unresolved=[];self.covered=np.zeros(self.P,np.int32);self.unsolved=np.zeros(self.P,np.int32);self.near_bounds=[];self.node_count=0;self.timeout_count=0
  log('context_ready',parts=len(self.items),pairs=self.P,dynamic_pairs=len(self.dynamic),invariant_pairs=len(self.static))
 def pose(self,q):
  ts=transforms(self.joints,dict(zip(self.jnames,q)));bbs=[]
  for o in self.objs:
   v=apply_points(o['corners'],ts[o['q']['link_frame']]);bbs.append([v.min(0),v.max(0)])
  return ts,np.array(bbs)
 def broad(self,bbs,ids):
  a=bbs[self.ia[ids]];b=bbs[self.ib[ids]];return np.linalg.norm(np.maximum(0,np.maximum(a[:,0]-b[:,1],b[:,0]-a[:,1])),axis=1)
 def planes(self,pid,ts):
  a,b=[self.objs[i]for i in self.pairs[pid]];ta,tb=ts[a['q']['link_frame']],ts[b['q']['link_frame']];rel=relative_transform(ta,tb);va=a['v'];vb=apply_points(b['v'],rel)
  dc=vb.mean(0)-va.mean(0);ax=np.vstack([np.eye(3),a['axes'],b['axes']@rel[:3,:3].T,dc/(np.linalg.norm(dc)+1e-30)])
  pa=va@ax.T;pb=vb@ax.T;gap=np.maximum(pb.min(0)-pa.max(0),pa.min(0)-pb.max(0));k=int(np.argmax(gap));return max(0.,float(gap[k])),ax[k].tolist()
 def exact(self,pid,ts,q,stage):
  a,b=map(int,self.pairs[pid]);active=np.flatnonzero(self.rho[pid]);key=(int(pid),tuple(float(q[j])for j in active))
  if key in self.exact_cache:return self.exact_cache[key]
  rel=relative_transform(ts[self.items[a]['link_frame']],ts[self.items[b]['link_frame']]);log('exact_start',phase=stage,pair=int(pid),a=self.items[a]['name'],b=self.items[b]['name'])
  r=self.w.call(a,b,rel,3.);r={**r,'pair_id':int(pid),'phase':stage,'anchor_HOME_deg':dict(zip(self.jnames,map(float,q)))};self.exact_log.append(r);self.exact_cache[key]=r
  if r['status']=='timeout':self.timeout_count+=1
  log('exact_done',phase=stage,pair=int(pid),result=r['status'],gap_mm=r.get('gap_mm'),intersection_mm3=r.get('intersection_mm3'),wall_s=round(r['wall_s'],3));return r
 def certify(self,a,b,ids,lbs,method,anchor_index=None):
  if not len(ids):return
  ids=np.asarray(ids);lbs=np.asarray(lbs);assert np.all(lbs>=POSITIVE)
  for level,mask in [('target_2.2mm',lbs>=TARGET),('positive_separation',lbs<TARGET)]:
   if not mask.any():continue
   chosen=ids[mask];self.covered[chosen]+=b-a
   self.certs.append(dict(start_interval=int(a),end_interval_exclusive=int(b),pair_ids=chosen.tolist(),method=method,level=level,minimum_lower_bound_mm=float(lbs[mask].min()),anchor_interval_index=anchor_index))
 def fail(self,a,b,pid,reason,**kw):
  self.unsolved[pid]+=b-a;self.unresolved.append(dict(start_interval=int(a),end_interval_exclusive=int(b),pair_id=int(pid),reason=reason,**kw))
 def static_check(self):
  q=np.zeros(self.J);ts,bbs=self.pose(q);ids=self.static;g=self.broad(bbs,ids)-GUARD;mask=g>=POSITIVE;self.certify(0,self.N,ids[mask],g[mask],'invariant_AABB',None);todo=ids[~mask];log('static_narrow',pairs=len(todo))
  for k,pid in enumerate(todo):
   a,b=[self.items[i]for i in self.pairs[pid]];basis=named(a,b)
   if basis:self.named_rows.append(dict(pair_id=int(pid),a=a['name'],b=b['name'],basis=basis,calculation='No numerical gap or Boolean claim; invariant relationship only.'));self.unsolved[pid]+=self.N;continue
   gap,axis=self.planes(pid,ts)
   if gap-GUARD>=POSITIVE:self.certify(0,self.N,[pid],[gap-GUARD],'invariant_support_plane',None);continue
   r=self.exact(pid,ts,q,'invariant')
   if r['status']=='computed'and r['gap_mm']-GUARD>=POSITIVE:self.certify(0,self.N,[pid],[r['gap_mm']-GUARD],'invariant_mesh_distance',None)
   else:self.fail(0,self.N,pid,'INVARIANT_CONTACT_OR_UNRESOLVED',exact=r)
   self.near_static.append(dict(pair_id=int(pid),a=a['name'],b=b['name'],**{k:v for k,v in r.items()if k not in ['anchor_HOME_deg','pair_id']}))
   if(k+1)%25==0:self.checkpoint();log('static_progress',completed=k+1,total=len(todo))
  self.checkpoint();log('static_complete',named=len(self.named_rows),unresolved=len(self.unresolved))
 def visit(self,start,end,ids,depth=0):
  if not len(ids):return
  self.node_count+=1;anchor=(start+end)//2;q=self.anchor[anchor];low=self.low[start:end].min(0);high=self.high[start:end].max(0);dev=np.maximum(abs(low-q),abs(high-q));move=self.rho[ids]@(2*np.sin(np.radians(np.minimum(180.,dev))/2));ts,bbs=self.pose(q);gap=self.broad(bbs,ids);lb=gap-move-GUARD;ok=lb>=POSITIVE;self.certify(start,end,ids[ok],lb[ok],'interval_box_AABB',anchor);pending=ids[~ok];moves=move[~ok]
  log('interval_node',node=self.node_count,start=start,end=end,depth=depth,input=len(ids),broad_certified=int(ok.sum()),remaining=len(pending))
  split=[]
  for pid,movement in zip(pending,moves):
   g,axis=self.planes(pid,ts);lb=g-movement-GUARD
   if lb>=POSITIVE:self.certify(start,end,[pid],[lb],'interval_box_support_plane',anchor);continue
   if movement>=2.9998 and end-start>1:split.append(pid);continue
   r=self.exact(pid,ts,q,'dynamic')
   if r['status']=='computed':
    lb=r['gap_mm']-movement-GUARD
    if lb>=POSITIVE:self.certify(start,end,[pid],[lb],'interval_box_mesh_distance',anchor);continue
    if r['gap_mm']<=POSITIVE+GUARD:self.fail(start,end,pid,'ACTUAL_ANCHOR_CONTACT_REQUIRES_REVIEW',anchor_interval_index=anchor,maximum_motion_mm=float(movement),exact=r);continue
   elif r['status']in ['timeout','error','worker_error','worker_eof']:
    self.fail(start,end,pid,'EXACT_CHECK_FAILED_OR_TIMED_OUT',anchor_interval_index=anchor,maximum_motion_mm=float(movement),exact=r);continue
   if end-start==1:self.fail(start,end,pid,'SINGLE_SOURCE_INTERVAL_NOT_PROVED',anchor_interval_index=anchor,maximum_motion_mm=float(movement),exact=r)
   else:split.append(pid)
  if split:
   split=np.array(split,dtype=np.int32);mid=(start+end)//2
   self.visit(start,mid,split,depth+1);self.visit(mid,end,split,depth+1)
  if self.node_count%10==0 or depth==0:self.checkpoint()
 def checkpoint(self):
  result={'status':'PARTIAL_CHECKPOINT','pair_count':self.P,'dynamic_pair_count':len(self.dynamic),'invariant_pair_count':len(self.static),'interval_count':self.N,'certificates':self.certs,'named_invariant_representations':self.named_rows,'unresolved_spans':self.unresolved,'exact_calls':self.exact_log,'near_invariant_pairs':self.near_static,'covered_interval_counts':self.covered.tolist(),'unresolved_or_named_interval_counts':self.unsolved.tolist(),'elapsed_s':time.monotonic()-START}
  tmp=OUT/'checkpoint.tmp';tmp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n');tmp.replace(OUT/'checkpoint.json')
 def run(self):
  # Motion first gives the requested high-value Entry/neck/hip evidence early.
  self.visit(0,self.N,self.dynamic);log('dynamic_complete',unresolved_spans=len(self.unresolved));self.checkpoint();self.static_check();self.w.close()
  assert np.all(self.covered+self.unsolved==self.N),np.where(self.covered+self.unsolved!=self.N)
  for p,h in self.sources.items():assert sha(ROOT/p)==h,p
  self.checkpoint();r=json.loads((OUT/'checkpoint.json').read_text());r['status']='EXHAUSTIVE_DELTA_INTERVAL_LEDGER_WITH_EXPLICIT_CONTACTS_AND_UNRESOLVED_ITEMS';r['full_partition_verified']=True;r['sources']=self.sources;r['input_sha256']=sha(OUT/'inputs.json');r['checker_sha256']=sha(__file__);r['motion_core_sha256']=sha(ROOT/'work/r18-leg-hip-covers/review/motion_core.py');r['target_mm']=TARGET;r['positive_separation_threshold_mm']=POSITIVE;r['numerical_guard_mm']=GUARD;r['dynamic_pair_ids']=self.dynamic.tolist();r['invariant_pair_ids']=self.static.tolist();r['global_joint_box_HOME_deg']={j:[float(self.low[:,k].min()),float(self.high[:,k].max())]for k,j in enumerate(self.jnames)};r['interval_source_status']=self.d.get('interval_source_status');r['interval_duration_s']=[self.records[0]['start_s'],self.records[-1]['end_s']]
  r['limits']=['Encloses recorded numerical integration states and linear connections using every source interval joint min/max; not a real-hardware continuous trajectory or controller proof.','Same-link and common-ancestor transforms cancel; global floating-base rigid pose cancels. Ground/external objects and old-old pairs are outside this delta task.','MULTI_LINK_FLEX_HARNESS remains exactly the baseline fixed-HOME rigid reference; actual harness deformation is not modeled.','All installed reference/wire envelopes included; 9 unplug/service budgets excluded and separately preserved.','Named invariant representation contacts are explicit exclusions from separation proof, not mesh/strength/manufacturing approvals.','Unresolved span counts are exhaustive, not asserted collision-free; actual anchor contacts are witnesses only, not claims that an entire span intersects.','STL surface distances are to the captured triangulations; nominal BRep comparisons, if added, are separately labeled.']
  (OUT/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
  np.savez_compressed(OUT/'pair_arrays.npz',pairs=self.pairs,radii_mm=self.rho,covered=self.covered,unresolved_or_named=self.unsolved)
  (OUT/'pair_index.json').write_text(json.dumps({'items':[{'id':i,'name':q['name'],'group':q['input_group'],'link_frame':q['link_frame'],'mesh_sha256':q['mesh_sha256']}for i,q in enumerate(self.items)],'pairs':self.pairs.tolist()},ensure_ascii=False,separators=(',',':'))+'\n')
  log('complete',certificates=len(self.certs),unresolved_spans=len(self.unresolved),named_pairs=len(self.named_rows),exact_calls=len(self.exact_log),timeouts=self.timeout_count)
if __name__=='__main__':
 START=time.monotonic();LOG=(OUT/'progress.jsonl').open('w',buffering=1)
 d=json.loads((OUT/'inputs.json').read_text());bp=ROOT/d['interval_bounds_path'];assert sha(bp)==d['interval_bounds_sha256'];b=json.loads(bp.read_text());d['interval_source_status']=b['status'];s=Scan(d,b)
 try:s.run()
 finally:s.w.close()
