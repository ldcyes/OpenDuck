"""Same closed foot prism union, partitioned only to diagnose mesh-plane contact discretization."""
from quasistatic import *
from xml.etree import ElementTree as E
from copy import deepcopy
import argparse

FINALOUT=OUT/'final_models'
def clip(poly,axis,value,sign):
 out=[]
 for a,b in zip(poly,np.roll(poly,-1,axis=0)):
  da=sign*(a[axis]-value);db=sign*(b[axis]-value)
  if da<=1e-14:out.append(a)
  if (da<0 and db>0)or(da>0 and db<0):out.append(a+(b-a)*(-da)/(db-da))
 return np.array(out)
def vec(x):return ' '.join(f'{float(y):.16g}'for y in np.asarray(x).ravel())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(n):
 src=FINALOUT/'current_robot_final_raw.xml';cp=FINALOUT/'model_contract_final_raw.json';c=json.loads(cp.read_text());root=E.parse(src).getroot();asset=root.find('asset');records=[]
 for f in c['foot_contact_models']:
  link=f['link'];points=np.array(f['source_contact_polygon_HOME_mm'])/1000;xy=points[ConvexHull(points[:,:2]).vertices];pivot=np.array(next(j['pivot_trunk_mm']for j in c['joints']if j['child_link']==link))/1000;body=root.find(".//body[@name='"+link+"']");old=body.find("geom[@name='"+link+"_sole_prism']");attrib=dict(old.attrib);old.set('contype','0');old.set('conaffinity','0');polygons=[]
  for i in range(n):
   for j in range(n):
    poly=xy.copy()
    for axis,index in [(0,i),(1,j)]:
     lo=float(xy[:,axis].min());hi=float(xy[:,axis].max());a=lo+(hi-lo)*index/n;b=lo+(hi-lo)*(index+1)/n;poly=clip(poly,axis,a,-1);poly=clip(poly,axis,b,1)
    polygons.append(poly);nn=len(poly);verts=np.vstack([poly,poly+[0,0,.002]])-pivot;faces=[]
    for k in range(1,nn-1):faces += [[0,k+1,k],[nn,nn+k,nn+k+1]]
    for k in range(nn):kk=(k+1)%nn;faces += [[k,kk,nn+kk],[k,nn+kk,nn+k]]
    name=f'{link}_sole_partition_{i}_{j}';E.SubElement(asset,'mesh',name=name,vertex=vec(verts),face=' '.join(str(v)for face in faces for v in face));attrs=dict(attrib,name=name,mesh=name);E.SubElement(body,'geom',**attrs)
  areas=[ConvexHull(p[:,:2]).volume for p in polygons];area=ConvexHull(xy[:,:2]).volume;assert abs(sum(areas)-area)<1e-14
  records.append(dict(link=link,partition_count=n*n,source_area_m2=area,sum_partition_area_m2=sum(areas),area_error_m2=sum(areas)-area,partition_polygons_HOME_m=[p.tolist()for p in polygons],height_m=.002,note='Axis-aligned clipping creates an exact nonoverlapping partition of the existing convex sole prism. No added pad, footprint, mass or friction.'))
 out=FINALOUT/f'current_robot_contact{n*n}.xml';E.indent(root);out.write_text(E.tostring(root,encoding='unicode')+'\n');m=mujoco.MjModel.from_xml_path(str(out));oldm=mujoco.MjModel.from_xml_path(str(src))
 for key in ['body_mass','body_inertia','body_ipos','body_iquat','actuator_forcerange','jnt_axis','body_pos']:assert np.array_equal(getattr(m,key),getattr(oldm,key)),key
 c=deepcopy(c);c['contact_partition_diagnostic']=records;c['sources'][str(src.relative_to(ROOT))]=sha(src);c['sources'][str(cp.relative_to(ROOT))]=sha(cp);c['sources'][str(out.relative_to(ROOT))]=sha(out);c['sources'][str(Path(__file__).relative_to(ROOT))]=sha(Path(__file__));c['assumptions']+=['Ground contact uses an exact partition of the original sole prism because MuJoCo3.3.7 plane-mesh collider selects at most3 points per mesh, potentially two points on a diagonal. This tests discretization, not a friction or physical-material improvement.'];cpath=FINALOUT/f'model_contract_contact{n*n}.json';cpath.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n');(FINALOUT/f'contact_partition{n*n}_check.json').write_text(json.dumps(dict(status='GEOMETRY_PRESERVING_CONTACT_PARTITION_DIAGNOSTIC',model=str(out.relative_to(ROOT)),contract=str(cpath.relative_to(ROOT)),checks=records,unchanged_inertial_and_joint_and_torque_arrays=True,physical_approved=False),ensure_ascii=False,indent=2)+'\n');print(out)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--n',type=int,default=2);p.add_argument('--out-dir',required=True);a=p.parse_args();FINALOUT=ROOT/a.out_dir;build(a.n)
