"""Bind exact control phases to complete actual traces, disclosing endpoint rounding."""
from pathlib import Path
import sys,json,hashlib,argparse,copy
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));from comparison_timeline import ActualSeries,phase_mapping
ap=argparse.ArgumentParser();ap.add_argument('--reference-map',required=True);ap.add_argument('--candidate-trace',required=True);ap.add_argument('--candidate-sha',required=True);ap.add_argument('--output-dir',required=True);args=ap.parse_args()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();sources={}
def read(path,h=None):
 p=ROOT/path;actual=sha(p)
 if h:assert actual==h,str(p)
 sources[path]=actual;return json.loads(p.read_text())
r=read(args.reference_map);assert r['status']=='REFERENCE_PHASE_PAIRING_ONLY_WAITING_COMPLETE_ACTUAL_TRACE'
for p,h in r['sources'].items():assert sha(ROOT/p)==h,p;sources[p]=h
baseline_path='work/r20-walking-fix/dynamics/release_v4/runs/nominal/dynamic_trace_for_CAD.json';baseline_sha='5d9104173386da8d4e04a4929a6cd9d98260aadf87aedf09cb42c82c9b5b0282'
base=read(baseline_path,baseline_sha);candidate=read(args.candidate_trace,args.candidate_sha);series=[ActualSeries(base),ActualSeries(candidate)]
expected={row['name']for row in r['rows']}
for trace in [base,candidate]:assert expected<={s.get('phase')for s in trace['samples']},'Complete reference phase coverage not observed in actual trace'
rows=copy.deepcopy(r['rows']);adjustments={}
for k,ss in zip(['baseline_s','candidate_s'],series):
 reference_end=rows[-1][k][1];actual_end=float(ss.times[-1]);difference=actual_end-reference_end
 assert abs(difference)<=.0005,'Actual trace ended far from the reference; incomplete or mismatched integration'
 assert rows[-1][k][0]<actual_end
 rows[-1][k][1]=actual_end
 adjustments[k]=dict(reference_end_s=reference_end,actual_end_s=actual_end,actual_minus_reference_s=difference,handling='Only final display interval ends at saved actual time; internal exact controller boundaries unchanged; no physics extrapolation.')
phase_mapping(rows,series[0].times[-1],series[1].times[-1])
sources[str(Path(__file__).relative_to(ROOT))]=sha(__file__)
result=dict(status='DISPLAY_MAP_REAL_TRACE_BOUNDED_CONTROLLER_PHASES',rows=rows,semantics=r['semantics'],endpoint_adjustments=adjustments,baseline_trace=dict(path=baseline_path,sha256=baseline_sha),candidate_trace=dict(path=args.candidate_trace,sha256=args.candidate_sha),physical_approved=False,sources=sources)
out=ROOT/args.output_dir;assert out.is_relative_to(HERE);out.mkdir(parents=True,exist_ok=True);p=out/'actual_phase_mapping.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(p,sha(p))
