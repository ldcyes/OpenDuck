from reduced_core_v2 import *
SOURCES.bind(__file__);new=SOURCES.json('work/r21-reduced-sway/gait/support_pair_v4.json')['stance'];old=SOURCES.json('work/r20-walking-fix/gait/reserved_endpoints.json')['stance'];saved=SOURCES.json('work/r21-reduced-sway/gait/actual_stance_geometry_v1.json');out={}
for label,stance in [('R20',old),('R21',new)]:
 rows={};bound={}
 for link,f in feet.items():
  t=np.array(stance['foot_target_transforms_mm'][link]);p=apply_points(f['polygon'],t);xy=p[:,:2];n=np.roll(xy,-1,axis=0);cr=xy[:,0]*n[:,1]-n[:,0]*xy[:,1];area=cr.sum()/2;c=np.sum((xy+n)*cr[:,None],axis=0)/(6*area);vs=[];parts=[]
  for r in A['items']:
   if r['link_frame']!=link:continue
   m=trimesh.load(SOURCES.bind(r['mesh'],r['mesh_sha256']),force='mesh');vs.append(apply_points(np.asarray(m.vertices)@np.array(r['R']).T+r['t_mm'],t));parts.append(r['name'])
  V=np.vstack(vs);bound[link]=np.array([V.min(0),V.max(0)]);rows[link]=dict(parts=parts,actual_union_bounds_world_mm=bound[link].tolist(),support_polygon_centroid_world_xy_mm=c.tolist(),support_polygon_area_mm2=abs(float(area)))
 out[label]=dict(feet=rows,union_Y_separating_plane_gap_mm=float(bound['ankle_left'][0,1]-bound['ankle_right'][1,1]),support_polygon_centroid_spacing_mm=float(np.linalg.norm(np.array(rows['ankle_left']['support_polygon_centroid_world_xy_mm'])-rows['ankle_right']['support_polygon_centroid_world_xy_mm'])))
assert abs(out['R21']['union_Y_separating_plane_gap_mm']-saved['union_Y_separating_plane_gap_mm'])<1e-12;assert abs(out['R21']['support_polygon_centroid_spacing_mm']-saved['support_polygon_centroid_spacing_mm'])<1e-12
report=dict(status='SOURCE_MESH_ACTUAL_STANCE_COMPARISON',stances=out,foot_centroid_spacing_reduction_percent=100*(1-out['R21']['support_polygon_centroid_spacing_mm']/out['R20']['support_polygon_centroid_spacing_mm']),centroid_definition='Area centroid of each actual TPU sole convex support polygon computed by the shoelace formula; not the arithmetic mean of hull vertices used as a convenient wrench reference in earlier diagnostics.',sources=SOURCES.entries);p=OUT/'stance_comparison_v1.json';assert not p.exists();p.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k not in ['sources','stances']},indent=2));print({k:(v['union_Y_separating_plane_gap_mm'],v['support_polygon_centroid_spacing_mm'])for k,v in out.items()})
