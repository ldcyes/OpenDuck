"""Merge four complete original-solver runs without dropping any segment/pair.

This is record reconciliation, never a replacement collision algorithm. The
whole-assembly passed=false and all unresolved pairs remain in the result.
"""
from pathlib import Path
from copy import deepcopy
import hashlib,itertools,json,math
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'reference_4steps_v3'/'reference_4steps_v3_continuous.json'
AUDIT=HERE/'merge_audit.json'
SOURCES={}

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def rel(path):return str(path.relative_to(ROOT))
def bind(path,expected=None):
    path=Path(path);path=path if path.is_absolute() else ROOT/path
    name=rel(path)
    if name in SOURCES:
        h=SOURCES[name]
    else:h=sha(path);SOURCES[name]=h
    assert expected is None or h==expected,('SOURCE_CHANGED',name,expected,h)
    return path

def read(path,expected=None):
    path=bind(path,expected);d=json.loads(path.read_text())
    for p,h in d.get('sources',{}).items():bind(p,h)
    return d

def verify_partition(original,manifest,chunks):
    segments=original['segments'];seen=[]
    assert len(segments)==manifest['segment_count']==582
    assert len(chunks)==len(manifest['chunks'])==4
    for record,data in zip(manifest['chunks'],chunks):
        ids=record['global_segment_indices']
        assert ids==data['original_global_segment_indices']
        assert data['partition_index']==record['chunk']
        assert data['parent_segment_count']==len(segments)
        assert len(ids)==len(data['segments'])
        assert all(type(i)is int and 0<=i<len(segments) for i in ids)
        assert ids==sorted(set(ids))
        assert all(data['segments'][j]==segments[i] for j,i in enumerate(ids)),('SEGMENT_CHANGED',record['chunk'])
        for field in ['trajectory','trajectory_sha256','source_sample_count','sample_scalar_path_max_error_deg']:
            assert data[field]==original[field],('PARENT_METADATA_CHANGED',field)
        seen.extend(ids)
    assert sorted(seen)==list(range(len(segments))), 'PARTITION_MISSING_OR_DUPLICATE'
    return segments

def check_count(v,limit=105219):
    assert type(v)is int and 0<=v<=limit,('INVALID_COUNT',v)

def verify_coverage(report,ids,segments):
    assert report['assembly_parts']==557 and report['full_pairs']==154846
    assert report['cross_link_pairs']==105219 and report['same_link_pairs_require_finite_baseline']==49627
    assert report['segment_count']==len(ids)==len(report['coverage'])
    assert report['passed']is False and report['physical_approved']is False
    mapped=[]
    for local,(idx,c) in enumerate(zip(ids,report['coverage'])):
        assert type(c['index'])is int and c['index']==local
        assert c['start_s']==segments[idx]['start_s'] and c['end_s']==segments[idx]['end_s']
        assert c['requested_cross_link_pairs']==105219
        for name in ['certified_at_least2p2mm','not_certified2p2mm','certified_positive_separation_at_least0p0001mm','contact_or_penetration_or_unproven']:
            check_count(c[name])
        assert c['certified_at_least2p2mm']+c['not_certified2p2mm']==105219
        assert c['certified_positive_separation_at_least0p0001mm']+c['contact_or_penetration_or_unproven']==105219
        mapped.append(dict(c,index=idx))
    return mapped

def main():
    assert not OUT.exists() and not AUDIT.exists(),'FROZEN_OUTPUT_ALREADY_EXISTS'
    manifest=read(HERE/'partition_index.json')
    original=read(manifest['original_input'],manifest['original_input_sha256'])
    chunks=[read(r['input'],r['input_sha256']) for r in manifest['chunks']]
    segments=verify_partition(original,manifest,chunks)
    source_ids={s['id']:i for i,s in enumerate(segments)};assert len(source_ids)==len(segments)
    selection=read('work/r20-walking-fix/assembly_final/assembly_selection.json')
    by={r['name']:r for r in selection['items']};pairs=list(itertools.combinations(by,2));pair_ids={p:i for i,p in enumerate(pairs)}
    assert len(by)==557 and len(pairs)==154846
    jnames=[r['joint']for r in selection['joints']]
    def segment_index(s,allowed):
        i=source_ids[s['id']]
        assert i in allowed and s==segments[i],('EVIDENCE_SEGMENT_CHANGED',s['id'])
        return i
    def checkq(q,s,u):
        assert math.isfinite(u) and 0<=u<=1
        assert set(q)==set(jnames)
        for n in jnames:
            actual=q[n];expected=s['q0'].get(n,0)+u*(s['q1'].get(n,0)-s['q0'].get(n,0))
            assert math.isfinite(actual) and abs(actual-expected)<=1e-12,('EVIDENCE_Q_CHANGED',s['id'],n)
    def checkpair(a,b):
        assert (a,b)in pair_ids and by[a]['link_frame']!=by[b]['link_frame'],('BAD_CROSS_PAIR',a,b)
        return (a,b)
    def checkrow(row,allowed):
        p=checkpair(row['a'],row['b']);i=segment_index(row['segment'],allowed)
        checkq(row['q_HOME_delta_deg'],row['segment'],row['parameter_u'])
        assert row['link_a']==by[p[0]]['link_frame'] and row['link_b']==by[p[1]]['link_frame']
        assert row['relative_static_same_link']is False and row['common_mm3']>1e-9
        return p,i
    countaudit=read(HERE/'cache_identity_audit.json')
    assert countaudit['segment_count']==len(segments)
    assert [r['index']for r in countaudit['segments']]==list(range(len(segments)))
    covered=[];failures={};positives={};reports=[];source_core=None;chunk_paths={r['input']for r in manifest['chunks']}
    for record in manifest['chunks']:
        k=record['chunk'];ids=record['global_segment_indices'];allowed=set(ids)
        path=HERE.parent/record['label']/(record['label']+'_continuous.json');report=read(path)
        assert report['label']==record['label']
        assert report['sources'][record['input']]==record['input_sha256']
        core={p:h for p,h in report['sources'].items()if p not in chunk_paths}
        if source_core is None:source_core=core
        else:assert core==source_core,('WORKER_GEOMETRY_OR_ALGORITHM_SOURCES_DIFFER',k)
        assert report['unique_pair_segment_certificates']==countaudit['chunks'][k]['unique_pair_segment_certificates']
        assert countaudit['chunks'][k]['chunk']==k
        covered.extend(verify_coverage(report,ids,segments))
        observed=set();failed_count=0
        for f in report['below2p2_or_unproven_pairs']:
            p=checkpair(f['a'],f['b']);assert p not in observed;observed.add(p)
            first=segment_index(f['first_segment'],allowed)
            assert type(f['failed_segments'])is int and 0<f['failed_segments']<=len(ids)
            assert math.isfinite(f['minimum_observed_gap_mm'])and f['minimum_observed_gap_mm']>=0
            assert math.isfinite(f['maximum_observed_common_mm3'])and f['maximum_observed_common_mm3']>=0
            result=f['first_result'];assert result['certificate']['passed']is False
            for visit in result['visited']:checkq(visit['q'],f['first_segment'],visit['u'])
            failed_count+=f['failed_segments']
            if p not in failures:failures[p]=deepcopy(f)
            else:
                old=failures[p]
                if first<source_ids[old['first_segment']['id']]:old['first_segment']=deepcopy(f['first_segment']);old['first_result']=deepcopy(f['first_result'])
                old['failed_segments']+=f['failed_segments']
                old['minimum_observed_gap_mm']=min(old['minimum_observed_gap_mm'],f['minimum_observed_gap_mm'])
                old['maximum_observed_common_mm3']=max(old['maximum_observed_common_mm3'],f['maximum_observed_common_mm3'])
        assert failed_count==sum(r['not_certified2p2mm']for r in report['coverage']),('PAIR_SEGMENT_COUNT_NOT_CONSERVED',k)
        observedpos=set()
        for r in report['positive_pairs']:
            p,first=checkrow(r['first'],allowed);pmax,maximum=checkrow(r['maximum'],allowed)
            assert p==pmax and p not in observedpos and p in observed
            assert first<=maximum and r['maximum']['common_mm3']>=r['first']['common_mm3']
            observedpos.add(p)
            if p not in positives:positives[p]=deepcopy(r)
            else:
                old=positives[p]
                if first<source_ids[old['first']['segment']['id']]:old['first']=deepcopy(r['first'])
                newv=r['maximum']['common_mm3'];oldv=old['maximum']['common_mm3']
                if newv>oldv or(newv==oldv and maximum<source_ids[old['maximum']['segment']['id']]):old['maximum']=deepcopy(r['maximum'])
        reports.append(dict(chunk=k,path=rel(path),sha256=SOURCES[rel(path)],segments=len(ids),requested_pair_segments=len(ids)*105219,unique_pair_segment_certificates=report['unique_pair_segment_certificates']))
    covered.sort(key=lambda r:r['index']);assert [r['index']for r in covered]==list(range(len(segments)))
    assert sum(f['failed_segments']for f in failures.values())==sum(r['not_certified2p2mm']for r in covered)
    for f in failures.values():assert f['failed_segments']<=len(segments)
    fs=sorted(failures.values(),key=lambda r:(source_ids[r['first_segment']['id']],pair_ids[(r['a'],r['b'])]))
    ps=sorted(positives.values(),key=lambda r:(source_ids[r['first']['segment']['id']],pair_ids[(r['first']['a'],r['first']['b'])]))
    bind(Path(__file__))
    # Sources are verified again after all computations; no cached recheck.
    for p,h in SOURCES.items():assert sha(ROOT/p)==h,('SOURCE_CHANGED_DURING_MERGE',p)
    audit=dict(status='EXACT_582_SEGMENT_FULL_CROSS_PAIR_PARTITION_MERGE_VERIFIED',review_passed=True,geometry_clearance_pass_claim=False,segment_count=len(segments),cross_link_pairs=105219,requested_pair_segments=len(segments)*105219,segment_objects_exact_original_match=True,all_global_indices_once=True,all_q_time_id_metadata_unchanged=True,all_worker_geometry_and_algorithm_source_maps_identical=True,all_pair_and_per_segment_counts_conserved=True,evidence_q_reconstructed_from_original_segments=True,source_sets_verified_before_and_after=True,coverage_order='Original 0..581 order; no cycle request omitted.',worker_reports=reports,unique_pair_segment_certificates=countaudit['unique_pair_segment_certificates'],sum_worker_unique_certificates=countaudit['sum_worker_unique_certificates'],below2p2_or_unproven_pair_count=len(fs),positive_raw_pair_count=len(ps),sources=SOURCES.copy())
    AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');bind(AUDIT)
    template=json.loads((ROOT/reports[0]['path']).read_text())
    merged=dict(template,label='reference_4steps_v3',segment_count=len(segments),coverage=covered,positive_pairs=ps,below2p2_or_unproven_pairs=fs,unique_pair_segment_certificates=countaudit['unique_pair_segment_certificates'],sources=SOURCES.copy(),partition_merge_audit=rel(AUDIT),partition_merge_audit_sha256=SOURCES[rel(AUDIT)])
    assert merged['passed']is False and merged['physical_approved']is False
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(merged,ensure_ascii=False,indent=2)+'\n')
    print('MERGED_FROZEN',rel(OUT),sha(OUT),'segments',len(segments),'pairs',105219,'narrow',len(fs),'positive',len(ps),flush=True)
    print('MERGE_AUDIT',rel(AUDIT),sha(AUDIT),flush=True)

if __name__=='__main__':main()
