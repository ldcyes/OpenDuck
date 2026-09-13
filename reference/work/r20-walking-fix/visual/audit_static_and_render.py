"""Reopen viewer, verify source geometry/poses/visibility, then render reviewed views."""
from pathlib import Path
import bpy,numpy as np,json,hashlib,struct,sys
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
idx=json.loads((OUT/'static_build_index.json').read_text());blend=OUT/'Microduck_R20_修订与实际行走.blend'
for p,h in idx['sources'].items():assert sha(ROOT/p)==h,(p,'SOURCE_CHANGED')
bpy.ops.wm.open_mainfile(filepath=str(blend));scene=bpy.data.scenes[idx['main_scene']];bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0];scene.frame_set(1);deps=bpy.context.evaluated_depsgraph_get();deps.update()
by={o['part_id']:o for o in scene.objects if o.get('presentation_scope')=='R20_COMPLETE_557_STATIC'};assert len(by)==557
def sig(o):
 v=np.empty(len(o.data.vertices)*3,np.float32);o.data.vertices.foreach_get('co',v);o.data.calc_loop_triangles();tri=np.array([list(t.vertices) for t in o.data.loop_triangles],np.int32)
 return v,tri,hashlib.sha256(v.tobytes()).hexdigest(),hashlib.sha256(tri.tobytes()).hexdigest()
checks=[];oldvertex={}
for p in idx['main_parts']:
 o=by[p['part_id']];v,tri,vh,th=sig(o);assert vh==p['vertex_sha256'] and th==p['triangle_sha256']
 err=float(np.max(abs(np.array(o.evaluated_get(deps).matrix_world)-np.array(p['expected_matrix_m']))));assert err<1e-6
 hidden=o.hide_get(view_layer=scene.view_layers[0]);assert hidden==(not p['visible_default']) and o.hide_render==(not p['visible_default'])
 row=dict(part_id=p['part_id'],max_matrix_abs_error=err,vertices_equal=True,triangles_equal=True,visibility_preserved=True)
 if p['origin']=='R20_CURRENT_BOUND_STL_NO_MODIFICATION':
  f=ROOT/o['source_mesh'];data=f.read_bytes();n=struct.unpack('<I',data[80:84])[0];assert len(data)==84+50*n
  src=np.frombuffer(data[84:],dtype=[('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')],count=n)['v'].astype(np.float32)
  actual=v.reshape(-1,3)[tri]
  def coordinate_face_signature(faces):
   # Source normal ordering is independent of vertex-index deduplication; geometry is compared exactly.
   rows=[]
   for face in faces:
    rows.append(tuple(sorted(tuple(float(x) for x in vv) for vv in face)))
   return sorted(rows)
  assert coordinate_face_signature(src)==coordinate_face_signature(actual),(p['part_id'],'STL_TRIANGLES_CHANGED')
  row['raw_source_STL_triangles_exact']=True
 else:oldvertex[p['part_id']]=(vh,th)
 checks.append(row)
comparison=bpy.data.scenes[idx['comparison_scene']];bpy.context.window.scene=comparison;bpy.context.window.view_layer=comparison.view_layers[0];deps=bpy.context.evaluated_depsgraph_get();deps.update();cc=[]
for p in idx['comparison_parts']:
 o=bpy.data.objects[p['object']].evaluated_get(deps);error=float(np.max(abs(np.array(o.matrix_world)-np.array(p['expected_matrix_m']))));assert error<1e-6
 cc.append(dict(object=p['object'],part_id=p['part_id'],display_offset_m=p['display_offset_m'],matrix_error=error))
vol=[]
for p in idx['old_true_intersections']:
 o=bpy.data.objects[p['object']].evaluated_get(deps);v=np.array([o.matrix_world@x.co for x in o.data.vertices])*1000;v-=v.mean(0);o.data.calc_loop_triangles();t=np.array([list(x.vertices) for x in o.data.loop_triangles]);value=abs(float(np.einsum('ij,ij->i',v[t[:,0]],np.cross(v[t[:,1]],v[t[:,2]])).sum()/6));assert abs(value-p['common_mm3'])<.03
 vol.append(dict(object=p['object'],source_STEP_mm3=p['common_mm3'],displayed_mm3=value))
bpy.ops.wm.open_mainfile(filepath=str(ROOT/idx['source_viewer']['path']));orig=json.loads((ROOT/'outputs/Microduck_R13_5_照片外观与机构审查/模型/照片外观与机构审查_模型索引.json').read_text());count=0
for p in orig['main_parts']:
 if p['part_id'] not in oldvertex:continue
 _,_,vh,th=sig(bpy.data.objects[p['object']]);assert (vh,th)==oldvertex[p['part_id']],p['part_id'];count+=1
assert count==idx['unchanged_R18_mesh_count']
report=dict(passed=True,status='PASS_REOPENED557_EXACT_SOURCE_GEOMETRY_AND_DISPLAY',source_blend_sha256=sha(blend),old_source_mesh_comparisons=count,new_raw_STL_comparisons=idx['new_source_STL_count'],
 main_pose_checks=checks,comparison_pose_checks=cc,old_original_STEP_intersection_readback=vol,sources=idx['sources'],physical_approved=False,manufacturing_approved=False)
(OUT/'static_readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('STATIC_READBACK_PASS',count,idx['new_source_STL_count'],flush=True)
if '--render' not in sys.argv:raise SystemExit()
bpy.ops.wm.open_mainfile(filepath=str(blend));renders=[]
for name,file in [(idx['main_scene'],'R20_整机静态.png'),(idx['comparison_scene'],'R20_头部新旧对照.png')]:
 scene=bpy.data.scenes[name];bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0];scene.frame_set(1);scene.render.filepath=str(OUT/file);bpy.ops.render.render(write_still=True,scene=name)
 renders.append(dict(scene=name,PNG=str((OUT/file).relative_to(ROOT)),PNG_sha256=sha(OUT/file)))
(OUT/'static_render_index.json').write_text(json.dumps(dict(source_blend_sha256=sha(blend),renders=renders,physical_approved=False),ensure_ascii=False,indent=2)+'\n')
print('STATIC_RENDERED',len(renders),flush=True)
