"""Review the actual four-step improvement without changing its failed stretch goals."""
from pathlib import Path
import argparse, hashlib, json, sys

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
SOURCES = {}
NEW_JSON = []

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        while b := f.read(1024*1024): h.update(b)
    return h.hexdigest()

def bind(path, expected=None):
    p = Path(path); p = p if p.is_absolute() else ROOT / p
    rel = str(p.relative_to(ROOT))
    # Shared evidence repeats the same source hundreds of times. Hash each
    # source on first binding, then check every source freshly again before
    # writing the review. Expected-digest conflicts still fail immediately.
    h = SOURCES[rel] if rel in SOURCES else sha(p)
    assert expected is None or h == expected, ('SOURCE_CHANGED', rel, expected, h)
    assert rel not in SOURCES or SOURCES[rel] == h
    if rel not in SOURCES and rel.startswith('work/r21-reduced-sway/') and p.suffix == '.json':
        NEW_JSON.append(p)
    SOURCES[rel] = h
    return p

def refs(node):
    if isinstance(node, dict):
        if isinstance(node.get('path'), str) and isinstance(node.get('sha256'), str):
            bind(node['path'], node['sha256'])
        for k, v in node.items():
            if isinstance(v, str) and len(v) == 64 and (ROOT/k).is_file(): bind(k, v)
            elif isinstance(v, (dict, list)): refs(v)
    elif isinstance(node, list):
        for v in node: refs(v)

FIELDS = ['sources', 'source_hashes', 'files', 'outputs', 'canonical', 'cases', 'inputs', 'verified_sources', 'primary_files', 'checked_reports']

def read(path):
    d = json.loads(bind(path).read_text())
    for k in FIELDS:
        if k in d: refs(d[k])
    return d

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--reference-review', required=True)
    ap.add_argument('--artifacts', required=True); ap.add_argument('--preflight',action='store_true'); args = ap.parse_args()
    selection_path = 'work/r20-walking-fix/assembly_final/assembly_selection.json'
    sel = read(selection_path)
    assert len(sel['items']) == 557 and abs(sel['nominal_mass_kg']-4.1950935502695295)<1e-12
    contract_path = 'work/r20-walking-fix/dynamics/release_v4/verified_models/model_contract_contact4.json'
    contract = read(contract_path)
    assert contract['joints'] == sel['joints'] and abs(contract['mass_kg']-sel['nominal_mass_kg'])<1e-12
    assert SOURCES[contract_path] == '2fdcdd4d4f24594692a2e48eb7b8880ff190228a84131265bca1190b4765c240'
    ref_path = 'work/r21-reduced-sway/gait/trajectory_4steps_v3.json'
    ref = read(ref_path)
    assert SOURCES[ref_path] == '9ae29d7be2dd7e211482bfb13ba49b2234e4ecaf782c945b46b9a944b41a7d5d'
    gait = read(WORK/'gait/final_delivery_index.json')
    math = read(WORK/'gait/math_review_4steps_v3.json')
    stat = read(WORK/'evidence/independent_static/full_4steps_v3.json')
    loads = read(WORK/'gait/load_shares_4steps_v3.json')
    assert len(ref['samples']) == math['sample_count'] == stat['all_reference_samples'] == 8399
    assert math['segment_count'] == gait['summary']['moving_and_hold_segments'] == 582
    assert math['max_actual_sole_target_point_error_mm'] < .01
    assert stat['maximum_single_support_utilization'] < .85002
    assert stat['minimum_single_support_COP_margin_mm'] > 8-1e-6
    assert loads['summary']['maximum_static_allocated_utilization'] < .85002
    assert loads['summary']['minimum_loaded_double_contact_COP_margin_mm'] > 2-.001
    reference_review = read(args.reference_review)
    assert reference_review['review_passed'] and reference_review['segment_count'] == 582
    assert reference_review['remaining_below2p2_or_unproven_pair_count'] == 72
    dyn = read(WORK/'dynamics/final_delivery_index.json')
    assert SOURCES['work/r21-reduced-sway/dynamics/final_delivery_index.json'] == '870eea3b312d8aff62fb53ba9fcfb5c997413e1c4766c81f52a3a67f33970852'
    cases = {}
    for case in ['nominal','half_timestep','friction_0p5','contact9']:
        folder = WORK/'dynamics/full_v3'/case
        acceptance = read(folder/'acceptance.json')
        report = read(folder/'report.json')
        contact = read(folder/'actual_contact_supplement.json')
        assert acceptance['status'] == 'SIMULATION_THRESHOLDS_MET'
        assert len(acceptance['checks']) == 10 and all(acceptance['checks'].values())
        assert report['status'] == 'COMPLETED'
        assert contact['force_threshold_N'] == 2 and contact['all_actual_loaded_groups_within_original_3mm_slip_limit']
        assert all(f['maximum_loaded_group_polygon_XY_displacement_mm'] <= 3 for f in contact['feet'].values())
        cases[case] = dict(acceptance=acceptance, report_summary={k:v for k,v in report.items() if k not in ['sources','files']}, actual_contact=contact)
    run = WORK/'dynamics/full_v3/nominal'
    trace = read(run/'dynamic_trace_for_CAD.json')
    assert len(trace['samples']) == 9774
    assert SOURCES[str((run/'dynamic_trace_for_CAD.json').relative_to(ROOT))] == '524b29651e786bb9ef1608693a349df3e1e059f9b523fe4f5abc20e7647ba240'
    bounds = read(run/'interval_joint_bounds.json')
    assert bounds['interval_count'] == 9773 and bounds['total_integration_steps'] == 781767
    boxes = read(WORK/'geometry/actual_4steps_v3/numerical_state_box_check.json')
    anchors = read(WORK/'geometry/actual_4steps_v3_anchors/actual_anchor_adjudication.json')
    coverage = read(WORK/'geometry/actual_4steps_v3_coverage/independent_actual_geometry_review.json')
    assert coverage['ledger_has_no_overlap_or_unreported_coverage_gap']
    assert coverage['trace_interval_endpoint_bindings_exact'] and coverage['no_unnamed_actual_raw_positive']
    assert coverage['unresolved_pairs_are_not_automatically_exempted']
    assert boxes['pair_interval_requests'] == 105219*9773 == 1028305287
    assert boxes['certified_material_pair_intervals'] + boxes['unresolved_pair_intervals'] == boxes['pair_interval_requests']
    assert len(boxes['unresolved_pairs']) == 34 and len(boxes['raw_positive_actual_anchors']) == 4
    assert not anchors['unclassified_or_positive_original_material']
    floors = {}
    for label, count in [('reference_4steps_v3_floor',8399),('actual_4steps_v3_floor',9774)]:
        floor = read(WORK/f'geometry/{label}/index.json')
        summary = floor['summary'][label]
        assert summary['sample_count'] == count
        assert all(r['penetrating_part_count']==0 for r in summary['category_summary'] if r['category']!='TPU_designed_contact')
        floors[label] = summary
    metrics = read(run/'sway_comparison.json')
    stats = read(run/'sway_extended_statistics.json')
    sys.path.insert(0,str(WORK/'evidence'))
    from sway_metrics import world_metrics, compare_actual
    mc = read(WORK/'evidence/metrics_contract.json')
    bm = read(WORK/'evidence/r20_fixed_marker_baseline.json')
    actual = world_metrics(trace, mc)
    comparison = compare_actual(bm['actual'], actual, mc)
    assert comparison == metrics['amplitude_comparison']
    assert comparison['actual_roll_reduction_fraction'] > 0 and comparison['actual_head_marker_Y_reduction_fraction'] > 0
    assert not comparison['both_sway_targets_met']
    assert mc['targets']['minimum_actual_roll_reduction_fraction'] == .4
    assert mc['targets']['minimum_actual_head_marker_Y_reduction_fraction'] == .3
    if args.preflight:
        for rel,h in SOURCES.items(): assert sha(ROOT/rel) == h
        print('NONVISUAL_REVIEW_PREFLIGHT_PASSED_NO_RELEASE_INDEX_WRITTEN',len(SOURCES))
        return
    visual = read(WORK/'visual/visual_delivery_index.json')
    va = read(WORK/'visual/release_v3/readback.json')
    assert va['passed'] and va['purpose'] == 'FINAL_FOUR_STEP'
    assert va['metrics_from_full_raw_original_samples'] and va['full_trace_sway_comparison'] == comparison
    assert va['unchanged_R20_scenes'] == ['01_完整装配_557件_静态','02_头部安装_旧与新对照','03_实际自由积分_四步行走']
    assert len(va['avatars']) == len(va['all_key_checks']) == 5
    for avatar in va['avatars']:
        assert len(avatar['pose_checks']) >= 12
        assert all(p['parts']==557 and p['max_world_matrix_abs_error']<1e-5 for p in avatar['pose_checks'])
    key_counts = {k['avatar']:k['all_saved_samples'] for k in va['all_key_checks']}
    assert key_counts['candidate_full'] == key_counts['same_time_candidate'] == 9774
    assert key_counts['same_time_baseline'] == key_counts['same_phase_baseline'] == 8744
    assert key_counts['same_phase_candidate'] >= 9774
    for k in va['all_key_checks']:
        assert len(k['all_key_checks']) == 67 and all(c['count']==k['all_saved_samples'] for c in k['all_key_checks'])
    prepared = read(WORK/'visual/release_v3/prepared_visual_inputs.json')
    assert prepared['purpose'] == 'FINAL_FOUR_STEP'
    assert prepared['candidate']['trace_path'] == str((run/'dynamic_trace_for_CAD.json').relative_to(ROOT))
    assert prepared['candidate']['trace_sha256'] == SOURCES[prepared['candidate']['trace_path']]
    assert prepared['metrics']['candidate']['sample_count'] == 9774
    assert prepared['full_trace_sway_comparison'] == comparison
    public = read(args.artifacts)['artifacts']
    for row in public: bind(row['path'],row['sha256'])
    public_blends = [row for row in public if row['path'].endswith('.blend')]
    assert len(public_blends) == 1 and public_blends[0]['sha256'] == va['source_blend_sha256']
    pcb = read(WORK/'pcb_review/publication_verification.json')
    assert pcb['status'] == 'PASS_COPY_HASH_ARCHIVE_CRC_MEMBERS_AND_PROTECTED_SOURCES'
    bind(pcb['archive'],pcb['archive_sha256'])
    assert any(row['path']==pcb['archive'] and row['sha256']==pcb['archive_sha256'] for row in public)
    for p in [WORK/'evidence/pending_electronics_mass_audit.json', WORK/'baseline_snapshot.json',
              WORK/'gait/减摆步态说明.md', WORK/'publish_update.py', WORK/'write_report.py', WORK/'update_current_state.py', WORK/'报告.md', Path(__file__)]:
        bind(p)
    # Traverse only the declared evidence graph inside this update. Frozen R20
    # historical reports retain their own explicitly adjudicated source versions.
    visited = set()
    while NEW_JSON:
        p = NEW_JSON.pop()
        if p in visited: continue
        visited.add(p); d = json.loads(p.read_text())
        if isinstance(d,dict):
            for k in FIELDS:
                if k in d: refs(d[k])
    baseline = json.loads((WORK/'baseline_snapshot.json').read_text())
    for row in baseline['protected_files']: assert sha(ROOT/row['path']) == row['sha256']
    for rel,h in SOURCES.items(): assert sha(ROOT/rel) == h
    result = dict(
        status='R21_ACTUAL_SLOW_FOUR_STEP_AMPLITUDE_IMPROVEMENT_WITH_EXPLICIT_LIMITS',
        review_checks_passed=True, physical_approved=False, manufacturing_approved=False,
        normal_speed_walking_qualified=False, all_assembly_clearances_qualified=False,
        actual_amplitude_improved_in_both_metrics=True,
        predeclared_sway_targets_met=comparison['both_sway_targets_met'],
        all_four_numerical_cases_passed=True, assembly_parts=557, nominal_mass_kg=sel['nominal_mass_kg'],
        selection_path=selection_path, selection_sha256=SOURCES[selection_path],
        reference_path=ref_path, reference_sha256=SOURCES[ref_path],
        reference_cross_link_pair_segments=reference_review['cross_link_pair_segments'],
        reference_remaining_narrow_or_unproven_pairs=72,
        actual_interval_count=9773, actual_integration_steps=781767,
        actual_pair_interval_requests=boxes['pair_interval_requests'],
        actual_material_certified_pair_intervals=boxes['certified_material_pair_intervals'],
        actual_remaining_unresolved_pair_count=34,
        sway_comparison=comparison, actual_world_metrics=actual['metrics'],
        static_maximum_allocated_utilization=loads['summary']['maximum_static_allocated_utilization'],
        static_minimum_double_COP_margin_mm=loads['summary']['minimum_loaded_double_contact_COP_margin_mm'],
        floor_checks=floors, public_artifacts=public,
        protected_R20_files_unchanged=len(baseline['protected_files']),
        PCB_review_delivered_with_original_geometry=True,
        limits=['Original 40% roll / 30% head lateral optimization goals remain unmet; the measured improvements are reported without moving thresholds.',
                'Slow four-step motion from the checked prepared stance only; automatic HOME-to-stance entry remains a separate candidate.',
                'Whole-CAD actual geometry review covers nominal numerical integrator states and their joint-space boxes. Sensitivity runs have dynamics checks, not separate complete CAD proofs.',
                'The 72 reference narrow/unproven and 34 actual nominal-interface/reference pairs remain explicit. No blanket all-assembly clearance or physical-fit approval.',
                'TPU contact penetration is numerical, not tested compression. Tolerances, flex harnesses, thermal behavior, motor low-voltage continuous capability and real walking are unqualified.',
                'Six self-designed PCBs, U2D2 and camera still need full installation definitions. Their estimated mass allocations already exist and must not be double-counted.',
                'No smaller PCB or modified manufacturing geometry was produced in the PCB assessment.'],
        source_count=len(SOURCES), sources=SOURCES)
    (WORK/'final_review_index.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('R21_FINAL_REVIEW_PASSED',len(SOURCES),sha(WORK/'final_review_index.json'))

if __name__ == '__main__': main()
