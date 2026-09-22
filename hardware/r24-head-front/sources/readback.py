from pathlib import Path
import bpy
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
index = json.loads((OUT / 'build_index.json').read_text())
path = OUT / 'Microduck_R24_摄像头前盖.blend'
bpy.ops.wm.open_mainfile(filepath=str(path))
scene = bpy.data.scenes[index['main_scene']]
errors = []
for record in index['main_parts'] + index['service_parts']:
    obj = scene.objects[record['object']]
    vertices = np.empty(len(obj.data.vertices) * 3, np.float32)
    obj.data.vertices.foreach_get('co', vertices)
    assert len(obj.data.vertices) == record['vertices']
    assert hashlib.sha256(vertices.tobytes()).hexdigest() == record['vertex_sha256']
    delta = np.array(obj.matrix_world) - np.array(record['matrix_m'])
    corners = np.array([list(corner) + [1] for corner in obj.bound_box])
    error = float(np.linalg.norm((corners @ delta.T)[:, :3], axis=1).max() * 1000)
    assert error < .0001, (record['part_id'], error)
    assert obj.animation_data is None and obj.parent is None
    errors.append(error)
assert len(errors) == index['part_count'] + index['service_count']
for source, expected in index['sources'].items():
    assert sha(ROOT / source) == expected, source
result = dict(status='R24_STATIC_MODEL_READBACK_PASS', part_count=index['part_count'],
              service_count=index['service_count'],
              max_float_roundtrip_displacement_mm=max(errors), pose_tolerance_mm=.0001,
              blend_sha256=sha(path), build_index_sha256=sha(OUT / 'build_index.json'),
              source_hashes_checked=len(index['sources']),
              renders={p.name: sha(p) for p in OUT.glob('0*.png')},
              physical_approved=False,
              limits=['Saved visual mesh, pose and provenance only; physics uses source CAD.',
                      'The STL importer may drop zero-area triangles; source STEP/STL is unchanged.'])
(OUT / 'readback.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False), flush=True)
