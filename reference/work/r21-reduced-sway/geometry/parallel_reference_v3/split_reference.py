from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[4];O=Path(__file__).resolve().parent;src=ROOT/'work/r21-reduced-sway/geometry/reference_4steps_v3_input.json';raw=src.read_bytes();D=json.loads(raw);S=D['segments'];assert len(S)==582;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();groups={}
for i,s in enumerate(S):
 sig=json.dumps([s['q0'],s['q1']],sort_keys=True,separators=(',',':'));groups.setdefault(sig,[]).append(i)
buckets=[[]for _ in range(4)]
for indices in groups.values():buckets[min(range(4),key=lambda k:len(buckets[k]))].extend(indices)
assert sorted(i for b in buckets for i in b)==list(range(582));records=[]
for k,ids in enumerate(buckets):
 ids.sort();chunk=dict(D);chunk.update(status='EXACT_FULL_CROSS_LINK_CONTINUOUS_SEGMENT_PARTITION',poses=[],segments=[S[i]for i in ids],original_global_segment_indices=ids,parent_segment_count=len(S),partition_index=k,source_geometry_grouping='All equal q0/q1 full-state signatures assigned to one chunk, retaining every original request and original id/time/q.')
 chunk['sources']={**D['sources'],str(src.relative_to(ROOT)):hashlib.sha256(raw).hexdigest(),str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))};p=O/f'chunk{k}_input.json';assert not p.exists();p.write_text(json.dumps(chunk,indent=2)+'\n');assert all(chunk['segments'][j]==S[i]for j,i in enumerate(ids));records.append(dict(chunk=k,input=str(p.relative_to(ROOT)),input_sha256=sha(p),global_segment_indices=ids,label=f'parallel_reference_v3_chunk{k}'))
p=O/'partition_index.json';assert not p.exists();p.write_text(json.dumps(dict(status='EXACT_582_SEGMENT_PARTITION_PRESERVING_DUPLICATE_CYCLE_REQUESTS',original_input=str(src.relative_to(ROOT)),original_input_sha256=hashlib.sha256(raw).hexdigest(),segment_count=len(S),distinct_full_q0q1_signatures=len(groups),chunks=records,sources={str(src.relative_to(ROOT)):hashlib.sha256(raw).hexdigest(),str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))}),indent=2)+'\n');print([(r['chunk'],len(r['global_segment_indices']))for r in records],flush=True)
