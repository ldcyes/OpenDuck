"""Report actual R21 amplitude change without weakening the fixed targets."""
from pathlib import Path
import sys,json,hashlib,argparse
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;E=OUT.parent/'evidence'
sys.path.insert(0,str(E))
from sway_metrics import world_metrics,compare_actual,tracking_diagnostics
ap=argparse.ArgumentParser();ap.add_argument('folder');ap.add_argument('--reference');a=ap.parse_args();folder=Path(a.folder).resolve();assert folder.is_relative_to(OUT)
sources={}
def read(p,h=None):
 p=Path(p).resolve();actual=hashlib.sha256(p.read_bytes()).hexdigest()
 if h:assert h==actual
 sources[str(p.relative_to(ROOT))]=actual;return json.loads(p.read_text())
contract=read(E/'metrics_contract.json','6fc77c713dbdc692caf2d34c120da8de5e666172f07ca80305a191440b47af71');baseline=read(E/'r20_fixed_marker_baseline.json');trace=read(folder/'dynamic_trace_for_CAD.json');acceptance=read(folder/'acceptance.json')
candidate=world_metrics(trace,contract);change=compare_actual(baseline['actual'],candidate,contract);positive=change['actual_roll_reduction_fraction']>0 and change['actual_head_marker_Y_reduction_fraction']>0
status='PREDECLARED_SWAY_TARGETS_MET'if change['both_sway_targets_met']else'POSITIVE_AMPLITUDE_IMPROVEMENT_BELOW_PREDECLARED_TARGETS'if positive else'NO_TWO_METRIC_AMPLITUDE_IMPROVEMENT_DEMONSTRATED'
reference_tracking=tracking_diagnostics(trace,read(a.reference),contract)if a.reference else None
for p in [Path(__file__),E/'sway_metrics.py']:sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
result=dict(status=status,physical_approved=False,actual_baseline=baseline['actual'],actual_candidate=candidate,amplitude_comparison=change,dynamic_criteria_status=acceptance['status'],dynamic_criteria_checks=acceptance['checks'],reference_tracking_diagnostics=reference_tracking,limits=['40percent roll/30percent markerY remain the original optimization targets even when smaller positive progress is delivered.','Amplitude improvement does not replace full four-step/stability/torque/slip or actual CAD collision checks.','Initial numeric pose assignment does not prove a connected physical setup motion.','World amplitudes use saved actual numerical poses; rendering camera/offsets are excluded.'],sources=sources)
(folder/'sway_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=status,comparison=change,dynamic_criteria_status=acceptance['status']),ensure_ascii=False))
