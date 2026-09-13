"""Native copper sheet-network estimate, with plated-via resistors.
Grid convergence is reported; this is not an electrothermal or hardware validation.
"""
from pathlib import Path
import json,sys,math,time
R=Path(__file__).parent;sys.path.insert(0,str(R/'.deps'))
import numpy as np
from shapely.geometry import Polygon,Point,LineString
from shapely.ops import unary_union
from shapely import contains_xy
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import cg,spsolve
rho=1.7241e-5
pairs=[('LOGIC_VIN',['F1.2'],['U3.4']),('MOBILE_5V',['U3.8'],['U4.6']),('BENCH_5V',['W5.1'],['U4.3']),('SYSTEM_5V',['U4.2','U4.7'],['W7.1']),('GND',['W8.1'],['U3.14','U3.15','U3.18']),('GND',['W8.1'],['W6.1'])]
def solve(d,net,src,dst,h):
 ls=d['layers'];geos=[]
 for l in ls:
  shapes=[Polygon(q['outer'],q['holes']).buffer(0)for q in d['polys']if q['net']==net and q['layer']==l]
  shapes +=[LineString([t['a'],t['b']]).buffer(t['width']/2,quad_segs=8)for t in d['tracks']if t['net']==net and t['layer']==l]
  shapes +=[Point(v['pos']).buffer(v['diameter']/2,quad_segs=16)for v in d['vias']if v['net']==net]
  g=unary_union(shapes)
  holes=unary_union([Point(v['pos']).buffer(v['drill']/2,quad_segs=16)for v in d['vias']if v['net']==net])
  geos.append(g.difference(holes))
 bounds=unary_union(geos).bounds;x=np.arange(math.floor(bounds[0]/h)*h+h*.431,bounds[2],h);y=np.arange(math.floor(bounds[1]/h)*h+h*.379,bounds[3],h);xx,yy=np.meshgrid(x,y);shape=xx.shape
 indices=[];n=0;edges=[]
 for k,g in enumerate(geos):
  m=contains_xy(g,xx,yy);ix=np.full(shape,-1,dtype=np.int32);ix[m]=np.arange(n,n+m.sum());n+=m.sum();indices.append(ix)
  sheet=d['thickness_mm'][k]/rho
  for a,b in[(ix[:,:-1],ix[:,1:]),(ix[:-1,:],ix[1:,:])]:
   valid=(a>=0)&(b>=0);edges.append((a[valid],b[valid],np.full(valid.sum(),sheet)))
 # Through-via metal barrel joins adjacent copper-layer annuli.
 for v in d['vias']:
  if v['net']!=net:continue
  cx=int(np.argmin(abs(x-v['pos'][0])));cy=int(np.argmin(abs(y-v['pos'][1])));delta=math.ceil((v['diameter']/2+h)/h);ys=slice(max(0,cy-delta),min(len(y),cy+delta+1));xs=slice(max(0,cx-delta),min(len(x),cx+delta+1));vx=xx[ys,xs];vy=yy[ys,xs];vindices=[ix[ys,xs]for ix in indices]
  distance=(vx-v['pos'][0])**2+(vy-v['pos'][1])**2
  A=math.pi*((v['drill']/2+.025)**2-(v['drill']/2)**2)
  # Circumference is distributed over 32 barrel sectors; avoid a fictitious
  # single-point contact resistance at the center of a drilled-out hole.
  sectors=[]
  for angle in np.arange(32)*2*math.pi/32:
   targetxy=np.array(v['pos'])+(v['drill']/2+.0125)*np.array([math.cos(angle),math.sin(angle)])
   distxy=(vx-targetxy[0])**2+(vy-targetxy[1])**2;nodes=[]
   for ix in vindices:
    eligible=(ix>=0)&(distance<(v['diameter']/2+h*.5)**2)
    nodes.append(None if not eligible.any()else int(ix.flat[np.argmin(np.where(eligible,distxy,np.inf))]))
   sectors.append(nodes)
  for nodes in sectors:
   for k in range(len(ls)-1):
    if nodes[k]is not None and nodes[k+1]is not None:edges.append((np.array([nodes[k]]),np.array([nodes[k+1]]),np.array([A/(32*rho*(d['z_mm'][k+1]-d['z_mm'][k]))])))
 def terminals(names):
  result=[]
  for pad in d['pads']:
   if pad['name']not in names:continue
   for q in pad['polys']:
    ix=indices[ls.index(q['layer'])];g=Polygon(q['outer'],q['holes']);m=contains_xy(g,xx,yy)&(ix>=0);result.extend(ix[m])
  return np.unique(result)
 source=terminals(src);target=terminals(dst)
 if len(source)==0 or len(target)==0:return dict(error='terminal missing',nodes=int(n))
 aa=np.concatenate([e[0]for e in edges]);bb=np.concatenate([e[1]for e in edges]);ww=np.concatenate([e[2]for e in edges]);diag=np.bincount(np.r_[aa,bb],weights=np.r_[ww,ww],minlength=n)
 mat=coo_matrix((np.r_[diag,-ww,-ww],(np.r_[np.arange(n),aa,bb],np.r_[np.arange(n),bb,aa])),shape=(n,n)).tocsr()
 from scipy.sparse.csgraph import connected_components
 _,comp=connected_components(mat,directed=False)
 useful=np.isin(comp,comp[source])
 if not np.any(useful[target]):return dict(error='grid disconnected',nodes=int(n))
 fixed=np.zeros(n,dtype=bool);fixed[source]=True;fixed[target]=True;free=(~fixed)&useful
 rhs=-np.asarray(mat[free][:,source].sum(axis=1)).ravel();A=mat[free][:,free]
 # Tiny isolated islands outside source component are omitted. A grounded component is SPD.
 if A.shape[0]==0:sol=np.zeros(0);info=0
 elif A.shape[0]<160000:sol=spsolve(A,rhs);info=0
 else:sol,info=cg(A,rhs,rtol=1e-9,atol=1e-11,maxiter=10000,M=diags(1/A.diagonal()))
 potential=np.zeros(n);potential[source]=1;potential[free]=sol;current=(mat@potential)[source].sum();res=1/current
 return dict(nodes=int(n),solver_info=int(info),R20_mOhm=float(res*1000),R85_mOhm=float(res*1000*(1+.00393*65)),source_grid_nodes=len(source),target_grid_nodes=len(target),grid_mm=h,filled_area_mm2=[round(g.area,3)for g in geos],residual_relative=float(np.linalg.norm(A@sol-rhs)/max(np.linalg.norm(rhs),1e-30)))
if __name__=='__main__':
 results=[]
 labels=sys.argv[1:2]or['source','r22'];hs=[float(sys.argv[2])]if len(sys.argv)>2 else[.1]
 for label in labels:
  d=json.loads((R/f'verification/{label}_dc_geometry.json').read_text())
  for net,src,dst in pairs:
   for h in hs:
    t=time.time();q=solve(d,net,src,dst,h);row=dict(board=label,net=net,from_pins=src,to_pins=dst,**q,elapsed_s=round(time.time()-t,2));results.append(row);print(json.dumps(row),flush=True)
    (R/f'verification/dc_sheet_{label}_{h}.json').write_text(json.dumps(results,indent=2))
