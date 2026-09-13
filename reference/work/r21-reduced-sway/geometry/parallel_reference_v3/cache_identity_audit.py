"""Reconstruct original scanner cache identities, never replace material checks.

No Boolean or distance outcome is inferred here. All 582 requests still require
completed original-solver reports. This audit only prevents summing worker-local
cache counts and falsely calling their sum globally unique.
"""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/p) for p in ['work/python-deps','work/r12-motion/python-deps','work/rk-mechanics/python-deps','work/r21-reduced-sway/geometry']]
from run_material_check import new_context,previous,SELECTION,MANIFEST
import numpy as np

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def rel(p):return str(p.relative_to(ROOT))
def keyhash(keys):
    h=hashlib.sha256()
    for row in sorted(keys):h.update((repr(row)+'\n').encode())
    return h.hexdigest()

def main():
    out=HERE/'cache_identity_audit.json';assert not out.exists()
    manifest=HERE/'partition_index.json';m=json.loads(manifest.read_text())
    original=ROOT/m['original_input'];assert digest(original)==m['original_input_sha256']
    d=json.loads(original.read_text());segs=d['segments'];assert len(segs)==582
    ctx=new_context(SELECTION,MANIFEST);ctx['sources'].bind(__file__)
    ctx['sources'].bind(ROOT/'work/r21-reduced-sway/geometry/run_material_check.py')
    ctx['sources'].bind(previous.__file__)
    ctx['sources'].bind(manifest)
    ctx['sources'].bind(original,m['original_input_sha256'])
    for p,h in d['sources'].items():ctx['sources'].bind(p,h)
    scan=previous.Scan(ctx)
    assert len(scan.pairs)==154846 and int(scan.cross.sum())==105219
    groups={};rows=[];per_chunk=[];all_indices=[]
    for chunk in m['chunks']:
        p=ROOT/chunk['input'];ctx['sources'].bind(p,chunk['input_sha256'])
        data=json.loads(p.read_text());ids=chunk['global_segment_indices']
        assert ids==data['original_global_segment_indices']
        assert len(ids)==len(data['segments'])
        keys=set()
        for local,(idx,seg) in enumerate(zip(ids,data['segments'])):
            assert seg==segs[idx]
            sig=json.dumps([seg['q0'],seg['q1']],sort_keys=True,separators=(',',':'))
            if sig not in groups:
                v0,v1=scan.qv(seg['q0']),scan.qv(seg['q1'])
                dq=np.abs(v1-v0);mid=(v0+v1)/2
                ts=previous.transforms(scan.joints,dict(zip(scan.jnames,mid.tolist())))
                broad=scan.broad(scan.bounds(ts))
                movement=np.sum(scan.rho*(2*np.sin(np.radians(np.minimum(180,dq/2))/2))[None,:],axis=1)
                near=np.flatnonzero(scan.cross & ~(scan.cross & (broad-movement-1e-5>=2.2)))
                ck={(int(i),tuple(v0[scan.dep[int(i)]]),tuple(v1[scan.dep[int(i)]]))for i in near}
                groups[sig]=ck
            ck=groups[sig];keys.update(ck)
            rows.append(dict(index=idx,segment_id=seg['id'],chunk=chunk['chunk'],local_index=local,near_pair_count=len(ck)))
            all_indices.append(idx)
        per_chunk.append(dict(chunk=chunk['chunk'],unique_pair_segment_certificates=len(keys),exact_cache_key_fingerprint_sha256=keyhash(keys)))
        print('CACHE_IDENTITIES',chunk['chunk'],len(keys),'distinct_full_q',len(groups),flush=True)
    assert sorted(all_indices)==list(range(len(segs)))
    allkeys=set().union(*groups.values());ctx['sources'].verify()
    report=dict(status='EXACT_SCANNER_CACHE_IDENTITY_AUDIT_NOT_GEOMETRY_PASS',assembly_parts=len(scan.names),full_pairs=len(scan.pairs),cross_link_pairs=int(scan.cross.sum()),segment_count=len(segs),distinct_full_q0q1_signatures=len(groups),unique_pair_segment_certificates=len(allkeys),sum_worker_unique_certificates=sum(r['unique_pair_segment_certificates']for r in per_chunk),global_cache_key_fingerprint_sha256=keyhash(allkeys),chunks=per_chunk,segments=sorted(rows,key=lambda r:r['index']),sources=ctx['sources'].entries.copy(),scope='Only original broad-phase routing and post-common-ancestor cache identities are reconstructed. Every exact distance/material certificate is taken exclusively from four complete source-bound original solver outputs.')
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('CACHE_AUDIT_FROZEN',rel(out),digest(out),flush=True)

if __name__=='__main__':main()
