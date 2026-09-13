"""Recompute R20/R21 actual sway from byte-preserved published input traces."""
from pathlib import Path
import hashlib,importlib.util,json,math
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'reference/work/r21-reduced-sway'
FILES={
 'module':SRC/'evidence/sway_metrics.py',
 'contract':SRC/'evidence/metrics_contract.json',
 'baseline':ROOT/'reference/work/r20-walking-fix/dynamics/release_v4/runs/nominal/dynamic_trace_for_CAD.json',
 'candidate':SRC/'dynamics/full_v3/nominal/dynamic_trace_for_CAD.json',
}
def main():
 manifest={x['repository_path']:x for x in json.loads((ROOT/'provenance/source-manifest.json').read_text())['files']}
 for q in FILES.values():
  key=str(q.relative_to(ROOT));assert hashlib.sha256(q.read_bytes()).hexdigest()==manifest[key]['source_sha256'],key
 spec=importlib.util.spec_from_file_location('original_sway_metrics',FILES['module']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 contract=json.loads(FILES['contract'].read_text())
 baseline=m.world_metrics(json.loads(FILES['baseline'].read_text()),contract)
 candidate=m.world_metrics(json.loads(FILES['candidate'].read_text()),contract)
 result=m.compare_actual(baseline,candidate,contract)
 expected=json.loads((ROOT/'provenance/original/work/r21-reduced-sway/final_review_index.json').read_text())['sway_comparison']
 keys=['actual_roll_reduction_fraction','actual_head_marker_Y_reduction_fraction']
 matched=all(math.isclose(result[k],expected[k],rel_tol=1e-10,abs_tol=1e-10) for k in keys)
 out={'passed':matched,'scope':'Actual amplitude recomputation only; no new dynamics, geometry, hardware or manufacturing acceptance.','comparison':result,'physical_approved':False,'manufacturing_approved':False}
 print(json.dumps(out,ensure_ascii=False,indent=2));raise SystemExit(not matched)
if __name__=='__main__':main()
