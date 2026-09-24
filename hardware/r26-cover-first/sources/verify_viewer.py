"""Fresh-process R26 assembly readback, including retained R25 identity."""
from pathlib import Path
import hashlib,json
import bpy
import numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent/'visual'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
index=json.loads((OUT/'build_index.json').read_text())
old=json.loads((ROOT/'work/r25-bottom-head-entry/visual/build_index.json').read_text())
by={p['part_id']:p for p in old['main_parts']+old['service_parts']}
selection=json.loads((ROOT/'work/r26-cover-first/assembly_selection.json').read_text())
blend=OUT/'OpenDuck_R26_cover_first.blend';bpy.ops.wm.open_mainfile(filepath=str(blend))
scene=bpy.data.scenes[index['main_scene']];bpy.context.window.scene=scene;scene.frame_set(scene.frame_current);scene.view_layers[0].update();errors=[];bounds=[];retained=0;retained_errors=[]
ids=[o.get('part_id') for o in scene.objects if o.type=='MESH']
assert len(ids)==len(set(ids))==index['part_count']+index['service_count']
for r in index['main_parts']+index['service_parts']:
    o=scene.objects[r['object']];v=np.empty(len(o.data.vertices)*3,np.float32);o.data.vertices.foreach_get('co',v)
    assert len(o.data.vertices)==r['vertices']
    assert hashlib.sha256(v.tobytes()).hexdigest()==r['vertex_sha256']
    matrix=np.array(o.matrix_world);delta=matrix-np.array(r['matrix_m'])
    corners=np.array([list(p)+[1] for p in o.bound_box]);error=float(np.linalg.norm((corners@delta.T)[:,:3],axis=1).max()*1000)
    assert error<.0001,(r['part_id'],error);errors.append(error)
    assert o.parent is None and o.animation_data is None
    if r['part_id'] in by:
        prior=by[r['part_id']]
        assert r['vertex_sha256']==prior['vertex_sha256'], (r['part_id'],'retained mesh')
        points=np.c_[v.reshape(-1,3),np.ones(len(v)//3)]
        displacement=float(np.linalg.norm((points@(matrix-np.array(prior['matrix_m'])).T)[:,:3],axis=1).max()*1000)
        assert displacement<.0001,(r['part_id'],'retained displacement',displacement)
        retained_errors.append(displacement)
        retained+=1
    else:
        part=next(p for p in selection['items'] if p['name']==r['part_id'])
        path=ROOT/part['mesh'];assert sha(path)==part['mesh_sha256']
        # Indexed PLY is read through a fresh importer without welding.
        bpy.ops.wm.ply_import(filepath=str(path),merge_verts=False);source=bpy.context.object
        sv=np.empty(len(source.data.vertices)*3,np.float32);source.data.vertices.foreach_get('co',sv)
        assert np.array_equal(sv,v)
        expected=np.eye(4);expected[:3,:3]=np.array(part['R'])*.001
        expected[:3,3]=(np.array(part['t_mm'])+np.array(index['native_to_scene_shift_mm']))/1000
        points=np.c_[v.reshape(-1,3),np.ones(len(v)//3)]
        assert np.linalg.norm((points@(matrix-expected).T)[:,:3],axis=1).max()*1000<.0001
        bpy.data.objects.remove(source,do_unlink=True)
    if not o.hide_render:
        world=v.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3];bounds.extend([world.min(0),world.max(0)])
for p,h in index['sources'].items():assert sha(ROOT/p)==h,p
frames=[]
for name in [index['main_scene']]+index['comparison_scenes']:
    sc=bpy.data.scenes[name];bpy.context.window.scene=sc;sc.frame_set(sc.frame_current)
    sc.view_layers[0].update();bpy.context.evaluated_depsgraph_get().update()
    objs=[o for o in sc.objects if o.type in ['MESH','FONT'] and not o.hide_render]
    deps=sc.view_layers[0].depsgraph;deps.update()
    inv=sc.camera.evaluated_get(deps).matrix_world.inverted()
    evaluated=[o.evaluated_get(deps) for o in objs]
    pts=np.array([inv@(o.matrix_world@Vector(corner)) for o in evaluated for corner in o.bound_box])
    frame=np.array([list(corner) for corner in sc.camera.data.view_frame(scene=sc)])
    assert np.all(pts.min(0)[:2]>=frame.min(0)[:2]-1e-6),(name,'frame minimum',pts.min(0),frame.min(0))
    assert np.all(pts.max(0)[:2]<=frame.max(0)[:2]+1e-6),(name,'frame maximum',pts.max(0),frame.max(0))
    frames.append(dict(scene=name,visible_objects=len(objs),complete_frame=True))
bounds=np.array(bounds)*1000
report=dict(status='R26_COMPLETE_MODEL_READBACK_PASS',part_count=index['part_count'],service_count=index['service_count'],
    unchanged_mesh_and_matrix_records=retained,new_source_meshes_verified=2,
    max_roundtrip_displacement_mm=max(errors),max_retained_geometry_displacement_mm=max(retained_errors),bounds_scene_mm=[bounds.min(0).tolist(),bounds.max(0).tolist()],
    HOME_height_mm=float(np.ptp(bounds[:,2])),blend_sha256=sha(blend),
    build_index_sha256=sha(OUT/'build_index.json'),verifier_sha256=sha(__file__),camera_frame_checks=frames,renders={p.name:sha(p) for p in OUT.glob('0*.png')},
    physical_approved=False,manufacturing_approved=False)
(OUT/'readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False),flush=True)
