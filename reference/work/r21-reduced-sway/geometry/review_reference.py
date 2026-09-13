"""Reconcile R21 whole-CAD reference coverage with frozen R20 interface findings."""
from pathlib import Path
import argparse, hashlib, json, re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCES = {}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def bind(rel, expected=None):
    p = ROOT / rel
    h = sha(p)
    assert expected is None or h == expected, ('SOURCE_CHANGED', rel)
    assert rel not in SOURCES or SOURCES[rel] == h
    SOURCES[rel] = h
    return p

def read(rel):
    d = json.loads(bind(rel).read_text())
    for p, h in d.get('sources', {}).items():
        bind(p, h)
    return d

def pair(row):
    r = row.get('first', row)
    return frozenset([r['a'], r['b']])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--scan-label', required=True)
    ap.add_argument('--label', required=True)
    a = ap.parse_args()
    assert all(re.fullmatch('[a-z0-9_]+', x) for x in [a.label, a.scan_label])
    resultpath = HERE / a.label / 'reference_review.json'
    assert not resultpath.exists()
    inp = read(a.input)
    ref = read(inp['trajectory'])
    stem = 'work/r21-reduced-sway/geometry/' + a.scan_label + '/' + a.scan_label
    finite = read(stem + '_finite.json')
    cont = read(stem + '_continuous.json')
    old = read('work/r20-walking-fix/geometry/final_reference_review.json')
    selection = 'work/r20-walking-fix/assembly_final/assembly_selection.json'
    sel = read(selection)
    by = {r['name']: r for r in sel['items']}
    assert len(by) == 557
    for d in [finite, cont]:
        assert d['sources'][selection] == SOURCES[selection]
    assert finite['parts'] == cont['assembly_parts'] == 557
    assert finite['pair_count'] == cont['full_pairs'] == 154846
    assert cont['cross_link_pairs'] == 105219
    assert cont['same_link_pairs_require_finite_baseline'] == 49627
    assert len(inp['poses']) == finite['pose_count'] == len(finite['coverage'])
    assert len(inp['segments']) == cont['segment_count'] == len(cont['coverage'])
    n = cont['segment_count']
    for p, c in zip(inp['poses'], finite['coverage']):
        assert p['label'] == c['pose'] and p['time_s'] == c['time_s']
        assert c['pairs'] == c['aabb_separated_at_least3mm'] + c['exact_or_relative_cache_pairs'] == 154846
    for i, (s, c) in enumerate(zip(inp['segments'], cont['coverage'])):
        assert c['index'] == i and c['start_s'] == s['start_s'] and c['end_s'] == s['end_s']
        assert c['requested_cross_link_pairs'] == 105219
        assert c['certified_at_least2p2mm'] + c['not_certified2p2mm'] == 105219
        assert c['certified_positive_separation_at_least0p0001mm'] + c['contact_or_penetration_or_unproven'] == 105219
    assert {pair(r) for r in finite['positive_pairs']} == {pair(r) for r in old['finite_raw_positive_pair_union']}
    assert {pair(r) for r in cont['positive_pairs']} == {pair(r) for r in old['remaining_raw_cross_positive_pairs']}
    narrow = {pair(r) for r in cont['below2p2_or_unproven_pairs']}
    assert narrow == {pair(r) for r in old['remaining_below2p2_or_unproven_pairs']}
    assert len(narrow) == 72
    assert all(r['failed_segments'] == n for r in cont['below2p2_or_unproven_pairs'])
    assert all(c['not_certified2p2mm'] == 72 and c['contact_or_penetration_or_unproven'] == 34 for c in cont['coverage'])
    assert all(abs(s['q_HOME_delta_deg']['neck_pitch']) < 1e-12 for s in ref['samples'])
    for r in finite['positive_pairs']:
        hit = r['first']
        if pair(r) not in {pair(x) for x in cont['positive_pairs']}:
            assert by[hit['a']]['link_frame'] == by[hit['b']]['link_frame']
    six = read('work/r19-walking-simulation/review/six_walking_penetrations/adjudication.json')
    targeted = [r['pair'] for r in six['rows']]
    targeted.extend([[r['name'], 'R20_left_hip_rail_offset'] for r in sel['items']
                     if r['link_frame'] != by['R20_left_hip_rail_offset']['link_frame']])
    assert all(frozenset(p) not in narrow for p in targeted)
    bind(str(Path(__file__).resolve().relative_to(ROOT)))
    result = dict(
        status='REFERENCE_FULL_CAD_COVERAGE_RECONCILED_WITH_UNRESOLVED_LEGACY_INTERFACES',
        review_passed=True, all_assembly_clearances_qualified=False,
        manufacturing_approved=False, physical_approved=False,
        trajectory=inp['trajectory'], trajectory_sha256=inp['trajectory_sha256'],
        assembly_parts=557, finite_pose_count=finite['pose_count'],
        segment_count=n, cross_link_pairs=105219, cross_link_pair_segments=n*105219,
        raw_finite_pair_count=len(finite['positive_pairs']),
        remaining_below2p2_or_unproven_pair_count=72,
        remaining_material_contact_or_unproven_pair_count=34,
        no_new_raw_positive_or_unresolved_pair_identities=True,
        original_six_gait_pairs_and_all_hip_rail_cross_pairs_certified_2p2mm=True,
        neck_source_STEP_zero_from_R20_and_relative_reference_pose_unchanged=True,
        limits=['The source scanner retains passed=false for whole-assembly clearance; this review does not exempt the 72 narrow or unresolved pairs.',
                'Same-link geometry is constant; its inherited material-contact findings remain explicit.',
                'The two neck raw mesh residues retain their original STEP zero-volume adjudication and fixed relative neck angle.',
                'This reference-path review is separate from actual numerical trajectory, floor, loading, tolerances and flexible-cable checks.'],
        sources=SOURCES)
    for p, h in SOURCES.items():
        assert sha(ROOT / p) == h
    resultpath.parent.mkdir(parents=True, exist_ok=True)
    resultpath.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('REFERENCE_REVIEW', n, finite['pose_count'], len(SOURCES), sha(resultpath))

if __name__ == '__main__':
    main()
