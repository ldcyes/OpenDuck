"""Reproducible geometry and conservative trace-only DC resistance audit.
This does not replace temperature, low-battery, load-step or EMI measurements.
"""
from pathlib import Path
import json,math,sys,heapq,collections
R=Path(__file__).parent;sys.path.insert(0,str(R/'.deps'))
from shapely.geometry import LineString,Point,Polygon,box
from shapely.ops import unary_union
routes=json.loads((R/'routes.json').read_text());pads=json.loads((R/'pads.json').read_text());copper=json.loads((R/'verification/copper_polygons.json').read_text())
rho=1.7241e-5;thick=[.07,.035,.035,.07];layers={0:0,4:1,6:2,2:3}
def points(geo):
 if geo.is_empty:return[]
 if geo.geom_type=='Point':return[(geo.x,geo.y)]
 if geo.geom_type in['LineString','LinearRing']:return[list(geo.coords)[0],list(geo.coords)[-1]]
 if hasattr(geo,'geoms'):return[pt for g in geo.geoms for pt in points(g)]
 return[]
def resistance(net,source_refs,target_refs):
 rows=[s for s in routes['segments']if s['net']==net];lines=[LineString([s['a'],s['b']])for s in rows];cuts=[set([0.,g.length])for g in lines];graph=collections.defaultdict(dict)
 def node(l,pt):return(l,round(pt[0],6),round(pt[1],6))
 def edge(a,b,r):
  if a==b:return
  graph[a][b]=min(graph[a].get(b,1e99),r);graph[b][a]=min(graph[b].get(a,1e99),r)
 def attach(l,pt,key):
  for i,g in enumerate(lines):
   if rows[i]['layer']==l and g.distance(Point(pt))<1e-5:cuts[i].add(g.project(Point(pt)));edge(key,node(l,pt),0.)
 for i,g in enumerate(lines):
  for j in range(i):
   if rows[i]['layer']!=rows[j]['layer']:continue
   for pt in points(g.intersection(lines[j])):cuts[i].add(g.project(Point(pt)));cuts[j].add(lines[j].project(Point(pt)))
 for pd in pads:
  if pd['net']!=net or not pd['pin'].isdigit():continue
  key=('pad',pd['ref'],pd['pin']);pg=box(pd['x']-pd['sx']/2,pd['y']-pd['sy']/2,pd['x']+pd['sx']/2,pd['y']+pd['sy']/2)
  for i,g in enumerate(lines):
   if rows[i]['layer']not in pd['layers']:continue
   for pt in points(g.intersection(pg)):cuts[i].add(g.project(Point(pt)));edge(key,node(rows[i]['layer'],pt),0.)
 for vv in routes['vias']:
  if vv['net']!=net:continue
  keys=[node(l,vv['pos'])for l in range(4)];A=math.pi*((vv['drill']/2+.025)**2-(vv['drill']/2)**2);rv=rho*1.6/A
  for l in range(4):
   attach(l,vv['pos'],keys[l])
   for k in range(l):edge(keys[l],keys[k],rv)
 for i,g in enumerate(lines):
  distances=sorted(cuts[i]);row=rows[i]
  for a,b in zip(distances,distances[1:]):edge(node(row['layer'],g.interpolate(a).coords[0]),node(row['layer'],g.interpolate(b).coords[0]),rho*(b-a)/(row['width']*thick[row['layer']]))
 start=[('pad',*s.split('.'))for s in source_refs];target={('pad',*s.split('.'))for s in target_refs};dist={s:0.0 for s in start};q=[(0.,str(s),s)for s in start]
 while q:
  dd,_,s=heapq.heappop(q)
  if dd!=dist[s]:continue
  if s in target:return dd
  for t,w in graph[s].items():
   nd=dd+w
   if nd<dist.get(t,1e99):dist[t]=nd;heapq.heappush(q,(nd,str(t),t))
 return None
pairs=[('BAT_FUSED',['W1.1'],['RS1.1']),('BAT_MON',['RS1.4'],['W3.1']),('LOGIC_VIN',['F1.2'],['U3.4']),('MOBILE_5V',['U3.8'],['U4.6']),('BENCH_5V',['W5.1'],['U4.3']),('SYSTEM_5V',['U4.2','U4.7'],['W7.1'])]
dc=[]
for net,start,end in pairs:
 rr=resistance(net,start,end);dc.append(dict(net=net,from_pins=start,to_pins=end,trace_only_best_path_R20_mOhm=None if rr is None else rr*1000,trace_only_best_path_R85_mOhm=None if rr is None else rr*1000*(1+.00393*65),note='Best single centerline path; excludes beneficial parallel paths and power pours;ideal pads;25um minimum plated barrel assumption. Not a measured resistance.'))
areas=collections.defaultdict(float)
for q in copper['polys']:areas[(q['net'],q['layer'])]+=Polygon(q['outer'],q['holes']).area
rows=[dict(net=n,layer=layer,filled_area_mm2=round(area,3))for(n,layer),area in sorted(areas.items())]
barrel_A=math.pi*(.125**2-.1**2);barrel_R=rho*1.6/barrel_A
thermal=[]
for current in [2.7,3.0]:
 for efficiency in [.85,.90,.93]:
  loss=5.1*current*(1/efficiency-1)
  for theta in[25,35,45]:thermal.append(dict(load_A=current,assumed_efficiency=efficiency,assumed_theta_JA_K_W=theta,loss_W=round(loss,3),rise_C=round(theta*loss,1),TJ_at_50C_ambient_C=round(50+theta*loss,1)))
mobile=next(r['trace_only_best_path_R85_mOhm']for r in dc if r['net']=='MOBILE_5V');output=next(r['trace_only_best_path_R85_mOhm']for r in dc if r['net']=='SYSTEM_5V')
voltage=[]
if mobile is not None and output is not None:
 for current in[2.7,3.0]:
  minimum=4.99-current*(.033+(mobile+output)/1000)
  voltage.append(dict(load_A=current,module_minimum_assumed_V=4.99,mux_Ron_max_105C_Ohm=.033,trace_only_upper_drop_V=round(current*(mobile+output)/1000,4),before_ground_and_harness_V=round(minimum,4),remaining_drop_budget_to_4p75V_V=round(minimum-4.75,4),note='Conservative trace-only budget;actual wide-pour resistance is lower but must be measured. Ground return,harness,contacts,load-switch drops remain to subtract.'))
pgnd=[]
for q in copper['polys']:
 if q['net']=='GND'and q['layer']==0:
  pg=Polygon(q['outer'],q['holes']);hits=[]
  for number in['14','15','18']:
   if any(pg.covers(Point(pd['x'],pd['y']))for pd in pads if pd['ref']=='U3'and pd['pin']==number):hits.append(number)
  if hits:pgnd.append(dict(same_top_copper_polygon_pins=hits,area_mm2=round(pg.area,2)))
report=dict(status='ENGINEERING DC/THERMAL SCENARIO ANALYSIS; NO HARDWARE VALIDATION',board_mm=[52,42,1.6],area_mm2=2184,source_area_mm2=2925,area_reduction_percent=round((1-2184/2925)*100,4),external_copper_mm=.07,inner_copper_mm=.035,minimum_new_track_width_mm=min(s['width']for s in routes['segments']),trace_only_dc_paths=dc,filled_copper_areas=rows,via_assumptions=dict(finished_drill_mm=.2,pad_diameter_mm=.45,minimum_barrel_plating_mm=.025,barrel_cross_section_mm2=barrel_A,R20_single_mOhm=barrel_R*1000,R20_four_parallel_mOhm=barrel_R*250,P_3A_four_parallel_mW=3**2*barrel_R/4*1000,mux_parallel_via_groups=4,vias_per_mux_group=4,LMZM_PGND_thermal_vias=10,LMZM_VOUT_thermal_vias=10,filled_capped='IPC-4761 Type VII required where via-in-pad;manufacturer to confirm plating,stencil and void limits'),LMZM_top_PGND_polygon_connectivity=pgnd,voltage_budget_superseded_by="DC_New_vs_Source_Final.json; centerline screen is not supply acceptance",thermal_scenarios=thermal,limits=['Copper-pour areas are measured from native filled KiCad polygons;they are not effective heat-spreading area or a thermal qualification.','Thermal scenarios vary efficiency and effective thetaJA;enclosed-head airflow and board coupling are not measured.','The TI thetaJA vs area example cannot be directly substituted for this populated board.','Only same-net traces/pours were added;AGND remains separate and no SW via or external SW pour was added.','2.7A operating budget and3A ceiling remain conditional on terminal voltage and temperature tests.','15A upstream fuse is not a claim of15A continuous PCB qualification;main3.8mm trace and2mOhm shunt loss must be verified under actual battery current.'])
(R/'verification/power_copper_thermal_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(dict(dc_paths=dc,voltage_budget="See DC_New_vs_Source_Final.json"),ensure_ascii=False,indent=2))
