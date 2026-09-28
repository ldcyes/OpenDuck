"""Refine the R28 interval proof for R26 right cover versus left ankle motor.

All distances are millimetres. Each source integration interval is enclosed by
its saved joint min/max box. The proof uses the same conservative relative-motion
bound as R28; it only splits blocks that failed the 2.2 mm target.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
for rel in ['work/rk-mechanics/python-deps', 'work/r18-leg-hip-covers/review']:
    sys.path.insert(0, str(ROOT / rel))
import numpy as np
import trimesh
from motion_core import apply_points, relative_motion_budget, relative_transform, transforms

GUARD = 1e-5
PAIR = ('R26_R_thigh_short_cover', 'left_ankle_motor')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_part(item):
    path = ROOT / item.get('analysis_mesh', item['mesh'])
    expected = item.get('analysis_mesh_sha256', item['mesh_sha256'])
    assert sha(path) == expected, item['name']
    mesh = trimesh.load(path, force='mesh')
    vertices = np.asarray(mesh.vertices) @ np.asarray(item['R']).T + np.asarray(item['t_mm'])
    box = np.array([vertices.min(0), vertices.max(0)])
    corners = np.array([[x, y, z] for x in box[:, 0] for y in box[:, 1] for z in box[:, 2]])
    centered = vertices - vertices.mean(0)
    _, evec = np.linalg.eigh(centered.T @ centered / len(vertices))
    return dict(item=item, vertices=vertices, corners=corners, axes=evec.T, source=path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-mm", type=float, default=2.2)
    parser.add_argument("--interval-bounds", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = args.target_mm
    assert target >= 2.2
    input_path = ROOT / 'work/r28-r26-interference/mechanics/motion_delta/inputs.json'
    inp = json.loads(input_path.read_text())
    bound_path = ROOT / args.interval_bounds
    assert bound_path.is_file()
    bounds = json.loads(bound_path.read_text())
    selection_path = ROOT / 'work/r29-r26-resolution/assembly_selection.json'
    selection = json.loads(selection_path.read_text())
    assert selection['status'] == 'R29_R26_FIVE_PART_CLEARANCE_CANDIDATE'
    assert inp['joints'] == selection['joints']
    selection_items = {item['name']: item for item in selection['items']}
    for name in PAIR:
        source_item = next(item for item in inp['items'] if item['name'] == name)
        current_item = selection_items[name]
        for field in ('mesh', 'mesh_sha256', 'R', 't_mm', 'link_frame'):
            assert source_item[field] == current_item[field], (name, field)
    joints = inp['joints']
    names = [j['joint'] for j in joints]
    parts = {x['name']: x for x in inp['items']}
    a, b = [load_part(parts[n]) for n in PAIR]
    zero = {j: 0.0 for j in names}
    one = {j: 1.0 for j in names}
    motion = relative_motion_budget(joints, a['item']['link_frame'], b['item']['link_frame'],
                                    a['vertices'], b['vertices'], zero, one, {})
    rho = np.zeros(len(names))
    for radius, _, joint in motion.terms:
        rho[names.index(joint)] += radius
    records = bounds['intervals']
    low = np.array([[r['q_min_HOME_deg'][n] for n in names] for r in records])
    high = np.array([[r['q_max_HOME_deg'][n] for n in names] for r in records])
    anchors = np.array([[r['q_start_HOME_deg'][n] for n in names] for r in records])
    assert len(records) == bounds['interval_count'] == 9773
    certificates = []
    failures = []

    def visit(start, end):
        anchor = (start + end) // 2
        q = anchors[anchor]
        dev = np.maximum(np.abs(low[start:end].min(0) - q), np.abs(high[start:end].max(0) - q))
        movement = float(rho @ (2 * np.sin(np.radians(np.minimum(180.0, dev)) / 2)))
        ts = transforms(joints, dict(zip(names, q)))
        ta = ts[a['item']['link_frame']]
        tb = ts[b['item']['link_frame']]
        av = apply_points(a['corners'], ta)
        bv = apply_points(b['corners'], tb)
        aa = np.array([av.min(0), av.max(0)])
        bb = np.array([bv.min(0), bv.max(0)])
        gap = float(np.linalg.norm(np.maximum(0, np.maximum(aa[0] - bb[1], bb[0] - aa[1]))))
        lower = gap - movement - GUARD
        method = 'interval_box_AABB'
        if lower < target:
            rel = relative_transform(ta, tb)
            va = a['vertices']
            vb = apply_points(b['vertices'], rel)
            dc = vb.mean(0) - va.mean(0)
            axes = np.vstack([np.eye(3), a['axes'], b['axes'] @ rel[:3, :3].T,
                              dc / (np.linalg.norm(dc) + 1e-30)])
            pa, pb = va @ axes.T, vb @ axes.T
            gaps = np.maximum(pb.min(0) - pa.max(0), pa.min(0) - pb.max(0))
            support = max(0.0, float(np.max(gaps)))
            if support - movement - GUARD > lower:
                lower = support - movement - GUARD
                method = 'interval_box_support_plane'
        if lower >= target:
            certificates.append(dict(start_interval=start, end_interval_exclusive=end,
                                     anchor_interval=anchor, method=method,
                                     lower_bound_mm=lower, movement_bound_mm=movement))
        elif end - start > 1:
            mid = (start + end) // 2
            visit(start, mid)
            visit(mid, end)
        else:
            failures.append(dict(start_interval=start, lower_bound_mm=lower,
                                 movement_bound_mm=movement))

    visit(0, len(records))
    assert not failures, failures[:5]
    cover = np.zeros(len(records), dtype=np.int32)
    for c in certificates:
        cover[c['start_interval']:c['end_interval_exclusive']] += 1
    assert np.all(cover == 1)
    result = dict(status='TARGET_CLEARANCE_CERTIFIED_R29_MASS_TRACE_R26_GEOMETRY', pair=list(PAIR),
                  interval_count=len(records), certificate_count=len(certificates),
                  minimum_conservative_clearance_mm=min(c['lower_bound_mm'] for c in certificates),
                  target_mm=target, exact_partition_coverage=True, failures=failures,
                  certificates=certificates,
                  sources={str(p.relative_to(ROOT)): sha(p) for p in [input_path, bound_path,
                                                                      a['source'], b['source'], ROOT / 'work/r18-leg-hip-covers/review/motion_core.py',
                                                                      Path(__file__)]})
    result['sources'][str(selection_path.relative_to(ROOT))] = sha(selection_path)
    result['motion_basis'] = 'R29 final nominal free-base integration with R29 assembled mass and inertias'
    result['geometry_basis'] = 'Unchanged R26 right thigh cover and left ankle motor in R29 five-part selection'
    result['integration_steps'] = bounds['total_integration_steps']
    OUT.mkdir(parents=True, exist_ok=True)
    filename = args.output
    (OUT / filename).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'interval_count', 'certificate_count',
                                             'minimum_conservative_clearance_mm', 'failures']}, indent=2))


if __name__ == '__main__':
    main()
