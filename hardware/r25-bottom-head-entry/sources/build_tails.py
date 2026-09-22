from pathlib import Path
import sys,json,copy,hashlib
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).parent/'tails';O.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT/'work/r3-mechanics/python-deps'),str(ROOT/'work/r23-power-integration/harness')]
import route_geometry as g,numpy as np
c=g.c;load=lambda p:json.loads(Path(p).read_text());old={p['name']:p for p in load(ROOT/'work/r24-head-front/assembly_selection.json')['items']};B=ROOT/'work/r23-power-integration/harness'
base=load(B/'upper_tail_refine/refined_v1/manifest.json');routes={r['upper_port']:r for r in base['routes']}
for r in load(B/'pth_material_finish/manifest.json')['routes']:
 if 'upper_port' in r:routes[r['upper_port']]=r
for r in load(B/'dynamic_relief_final/manifest.json')['routes']:
 if 'S03' in r.get('name',''):routes['S03']=r
routes['S06']=load(B/'bench_j10/manifest.json')['s06_route']
for r in load(B/'head_feed_fixed/upper_selected/manifest.json')['routes']:routes[r['id']]=r
M=load(ROOT/'work/r25-bottom-head-entry/mechanics/manifest.json');R=np.array(M['transform']['R']);T=np.array(M['transform']['t_mm']);parts=[];results=[]
def reverse(seg):
 out=[]
 for s in seg[::-1]:
  q=copy.deepcopy(s);q['start'],q['end']=s['end'],s['start'];out.append(q)
 return out
for port,r in routes.items():
 rev=port in ['P5','P6'];sg=reverse(r['segments'])if rev else r['segments'];a=np.array(sg[0]['start']);join=np.array(sg[0]['end']);new=R@a+T;back=g.unit(join-a);radius=12 if port[0]=='P'else 5
 points=[new,new+[0,0,28],join-back*14,join]
 pre,stats=g.rounded(points,radius)
 assert pre[0]['length_mm']>=12
 ss=pre+sg[1:];ss=reverse(ss)if rev else ss
 oldname=(f'R23_HEAD_SERVO_UPPER_{port}'if rev else f'R23_NECK_UPPER_{port}')
 names=[n for n in old if n==oldname or n.startswith(oldname+'_')];assert len(names)==1,(port,names);p=old[names[0]]
 od=1.778 if port[0]=='P'else .7366
 original=c.tf(c.read(ROOT/p['step']),p['R'],p['t_mm'])
 cutter=c.cylinder((a+join)/2-back*.100001,od/2+.1,12.2,back)
 shape=g.tube(ss,od/2) if rev else c.union(c.cut(original,cutter),g.tube(pre,od/2));q=c.export(f'R25_HEAD_BOTTOM_FIXED_{port}',shape,O,'TE55A0111 maximum insulation envelope',0,'jaw_soft','New underside entry, original electrical termination and downstream bends retained.')
 rb=c.properties(c.read(O/q['STEP']));assert rb['valid_BRep']and rb['solid_count']==1
 L=sum(s['length_mm']for s in ss);oldL=sum(s['length_mm']for s in r['segments'])
 q.update(step=str((O/q['STEP']).relative_to(ROOT)),mesh=str((O/q['STL']).relative_to(ROOT)),R=np.eye(3).tolist(),t_mm=[0,0,0],link_frame='jaw_soft',kind='fixed_harness',is_new=True,input_group='R25_bottom_entry',reference_only=True,replaces=names,route_length_mm=L,mass_from_CAD_g=L*(8.3 if port[0]=='P'else .91)*453.59237/304800,STEP_readback_verified=True,physical_approved=False,manufacturing_approved=False)
 parts.append(q);results.append(dict(port=port,source_name=names[0],name=q['name'],segments=ss,length_mm=L,old_length_mm=oldL,delta_length_mm=L-oldL,od_mm=od,minimum_radius_mm=min(s['radius_mm']for s in ss if s['type']=='arc'),guide_straight_mm=pre[0]['length_mm'],electrical_endpoint_preserved=ss[0 if rev else -1]['start'if rev else 'end']==r['segments'][0 if rev else -1]['start'if rev else 'end']))
 print(port,L,flush=True)
(O/'manifest.json').write_text(json.dumps(dict(status='CANDIDATE_PENDING_INTERFERENCE_CHECK',parts=parts,routes=results,replaces=[n for p in parts for n in p['replaces']],physical_approved=False,manufacturing_approved=False),indent=2)+'\n')
