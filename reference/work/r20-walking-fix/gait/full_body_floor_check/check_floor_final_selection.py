"""Exact source mesh vertex minima against z=0 at frozen reference/dynamic poses."""
from pathlib import Path
import json,sys,hashlib,math,argparse
import numpy as np
import trimesh
from scipy.spatial import ConvexHull,QhullError
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--trajectory',required=True);ap.add_argument('--label',required=True);ap.add_argument('--selection',required=True);ap.add_argument('--manifest',required=True);args=ap.parse_args();OUT=HERE/args.label;OUT.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(ROOT/'work/r18-leg-hip-covers/review'))
from motion_core import transforms
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
SOURCES={}
def read(p):
 p=ROOT/p;SOURCES[str(p.relative_to(ROOT))]=sha(p);return json.loads(p.read_text())
def bind(p,h):
 actual=sha(ROOT/p);assert actual==h,(p,h,actual);SOURCES[p]=actual
A=read(args.selection);C=read(args.manifest);rows=A['items'];assert len(rows)==557
SOURCES['work/r18-leg-hip-covers/review/motion_core.py']=sha(ROOT/'work/r18-leg-hip-covers/review/motion_core.py')
SOURCES[str(Path(__file__).resolve().relative_to(ROOT))]=sha(Path(__file__).resolve())
paths={args.label:args.trajectory}
D={n:read(p)for n,p in paths.items()}
for d in D.values():
 for p,h in d.get('sources',{}).items():bind(p,h)

def category(r):
 if '_TPU_contact_pad_W130'in r['name']:return 'TPU_designed_contact'
 if r['link_frame']in ['ankle_left','ankle_right']:
  if r.get('part_role')=='cover':return 'shoe_skin_not_ground_contact'
  return 'foot_frame_and_other_foot_hardware_not_ground_contact'
 return 'body_linkage_motor_electronics_not_ground_contact'

cache={};parts=[]
for i,r in enumerate(rows):
 if r['mesh']not in cache:
  bind(r['mesh'],r['mesh_sha256']);mesh=trimesh.load(ROOT/r['mesh'],force='mesh',process=False);V=np.unique(np.asarray(mesh.vertices,float),axis=0);assert len(V)>0 and np.isfinite(V).all()
  try:hv=ConvexHull(V).vertices;mode='source_convex_hull_vertex_extrema_exact_for_plane'
  except QhullError:hv=np.arange(len(V));mode='all_source_vertices_degenerate_hull'
  cache[r['mesh']]=(V,hv,mode)
 V,hv,mode=cache[r['mesh']]; R=np.asarray(r['R'],float);t=np.asarray(r['t_mm'],float);assert np.allclose(r.get('geometry_scale',[1,1,1]),1);W=V@R.T+t
 parts.append(dict(name=r['name'],label_zh=r.get('label_zh',r['name']),link_frame=r['link_frame'],category=category(r),source_mesh=r['mesh'],source_mesh_sha256=r['mesh_sha256'],source_R=R.tolist(),source_t_mm=t.tolist(),vertex_count=len(V),extreme_vertex_count=len(hv),extreme_method=mode,full=W,extreme=W[hv],source_row=r))
 if i%100==0:print('LOAD',i,r['name'],len(V),len(hv),flush=True)
print('LOADED',len(parts),'parts',len(cache),'unique sources','vertices',sum(p['vertex_count']for p in parts),'extrema',sum(p['extreme_vertex_count']for p in parts),flush=True)

reports={}
for name,d in D.items():
 ss=d['samples'];N=len(ss);linknames=set(r['link_frame']for r in rows);rot={l:np.empty((N,3))for l in linknames};trans={l:np.empty(N)for l in linknames};time=np.array([s['time_s']for s in ss]);
 for k,s in enumerate(ss):
  B=np.array(s['base_transform_m'],float);B[:3,3]*=1000; T=transforms(A['joints'],s['q_HOME_delta_deg']);assert np.allclose(B[3],[0,0,0,1]);
  for l in linknames:
   W=B@T[l];rot[l][k]=W[2,:3];trans[l][k]=W[2,3]
 minima=np.empty((len(parts),N));full_rechecks=[]
 for i,p in enumerate(parts):
  l=p['link_frame'];v=p['extreme']
  for k in range(0,N,128):minima[i,k:k+128]=(v@rot[l][k:k+128].T).min(axis=0)+trans[l][k:k+128]
  idx=int(np.argmin(minima[i]));allz=p['full']@rot[l][idx]+trans[l][idx];exact=float(allz.min());error=abs(exact-minima[i,idx]);assert error<1e-8,(name,p['name'],error);vindex=int(np.argmin(allz));
  # Strong independent check at 5 spread instants using all source vertices.
  for k in np.unique(np.r_[np.linspace(0,N-1,5,dtype=int),idx]):assert abs(float((p['full']@rot[l][k]+trans[l][k]).min())-minima[i,k])<1e-8
  full_rechecks.append(dict(name=p['name'],maximum_numerical_difference_mm=float(error),sample_index=idx,all_vertex_min_z_mm=exact,lowest_vertex_HOME_mm=p['full'][vindex].tolist()))
  if i%100==0:print('FLOOR',name,i,p['name'],'min',exact,'time',time[idx],flush=True)
 per=[]
 for i,p in enumerate(parts):
  z=minima[i];ix=int(z.argmin());penetrating=np.flatnonzero(z < -1e-5)
  per.append(dict(**{k:p[k]for k in ['name','label_zh','link_frame','category','source_mesh','source_mesh_sha256','source_R','source_t_mm','vertex_count','extreme_vertex_count','extreme_method']},minimum_z_mm=float(z[ix]),minimum_net_floor_clearance_mm=float(z[ix]),maximum_penetration_depth_mm=max(0.,float(-z[ix])),worst_sample_index=ix,worst_time_s=float(time[ix]),penetrating_sample_count=int(len(penetrating)),first_penetrating_time_s=float(time[penetrating[0]])if len(penetrating)else None,last_penetrating_time_s=float(time[penetrating[-1]])if len(penetrating)else None,lowest_vertex_HOME_mm=full_rechecks[i]['lowest_vertex_HOME_mm']))
 summaries=[]
 cats=sorted(set(p['category']for p in parts));class_summary=[]
 for c in cats:
  ids=np.array([i for i,p in enumerate(parts)if p['category']==c]);sub=minima[ids];i,k=np.unravel_index(sub.argmin(),sub.shape);row=per[ids[i]];class_summary.append(dict(category=c,part_count=len(ids),worst_part=row['name'],worst_time_s=float(time[k]),minimum_net_floor_clearance_mm=float(sub[i,k]),maximum_penetration_depth_mm=max(0.,-float(sub[i,k])),penetrating_part_count=sum(per[ii]['penetrating_sample_count']>0 for ii in ids),penetrating_sample_count=int(np.count_nonzero(np.any(sub < -1e-5,axis=0)))))
 for k,t in enumerate(time):
  rec=dict(time_s=float(t),sample_index=k,categories={})
  for c in cats:
   ids=np.array([i for i,p in enumerate(parts)if p['category']==c]);ii=int(ids[np.argmin(minima[ids,k])]);rec['categories'][c]=dict(name=parts[ii]['name'],minimum_z_mm=float(minima[ii,k]),penetration_depth_mm=max(0.,-float(minima[ii,k])))
  summaries.append(rec)
 non=[r for r in per if r['category']!='TPU_designed_contact'];worst=min(non,key=lambda r:r['minimum_z_mm']);
 result=dict(status='SAMPLED_FULL_REAL_GEOMETRY_FLOOR_DIAGNOSTIC',physical_approved=False,geometry_approved=False,dynamic_approved=False,trajectory_path=paths[name],trajectory_sha256=SOURCES[paths[name]],sample_count=N,time_range_s=[float(time[0]),float(time[-1])],part_count=len(parts),floor_world_z_mm=0,numerical_record_penetration_threshold_mm=1e-5,method='Actual source mesh vertices → row R/t → current link HOME-delta FK → supplied root world transform. Plane Z is a linear functional; minimizing over actual source convex-hull vertices gives the same minimum as every full source vertex. No inflated AABB/contact proxy used. Full-vertex recheck at every part worst time and five spread times.',all_mesh_vertices_across_instances=sum(p['vertex_count']for p in parts),accelerating_extreme_vertices_across_instances=sum(p['extreme_vertex_count']for p in parts),all_part_worst_time_full_vertex_recheck_max_error_mm=max(r['maximum_numerical_difference_mm']for r in full_rechecks),category_summary=class_summary,lowest_non_TPU_part=worst,penetrating_parts=[r for r in per if r['penetrating_sample_count']>0],per_part_minima=per,limitations=['Finite supplied samples only, not continuous certification of world-floor separation.','Source nominal rigid geometry only; TPU penetration is recorded, never treated as elastic or contact approval.','Only two named TPU pads are designed ground-contact parts; every other component is separately screened.','Added photo skin/fixing candidate geometry remains unqualified; no fastening or load-bearing status upgraded.','MULTI_LINK_FLEX_HARNESS is the inherited frozen HOME path transformed with root, not a deformable wire simulation.','Each reference/dynamic trace supplies world root; no additional ground shift is applied here.'],sources=SOURCES)
 (OUT/(name+'_floor_report.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');(OUT/(name+'_floor_samples.json')).write_text(json.dumps(dict(samples=summaries,trajectory_sha256=SOURCES[paths[name]]),ensure_ascii=False,indent=2)+'\n');np.savez_compressed(OUT/(name+'_all_part_minimum_z_mm.npz'),minimum_z_mm=minima,time_s=time,part_names=np.array([p['name']for p in parts]))
 reports[name]=dict(sample_count=N,category_summary=class_summary,lowest_non_TPU_part=worst)
for p,h in SOURCES.items():assert sha(ROOT/p)==h,(p,'changed')
files=[]
for p in sorted(OUT.iterdir()):
 if p.is_file()and p.name not in ['index.json','check_floor.log']:files.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p),bytes=p.stat().st_size))
index=dict(status='SOURCE_HASH_VERIFIED_R20_REAL_VERTEX_FLOOR_CHECK',physical_approved=False,files=files,sources=SOURCES,summary=reports)
(OUT/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n');print(json.dumps(reports,ensure_ascii=False,indent=2),flush=True)
