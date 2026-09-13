"""Run established source-material checks into R21 only, with R20 CAD frozen."""
from pathlib import Path
import sys, argparse, json, re
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'work/r20-walking-fix/geometry'))
from check_candidate_v2 import new_context,previous
import check_interval_bounds as interval_check
SELECTION='work/r20-walking-fix/assembly_final/assembly_selection.json'
MANIFEST='work/r20-walking-fix/assembly_final/candidate_manifest.json'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True)
    ap.add_argument('--mode',choices=['finite','continuous','both','actual_boxes'],required=True)
    ap.add_argument('--label',required=True);a=ap.parse_args()
    assert re.fullmatch('[a-z0-9_]+',a.label),'R21_LOCAL_LABEL_REQUIRED'
    out=HERE/a.label;out.mkdir(parents=True,exist_ok=True)
    ctx=new_context(SELECTION,MANIFEST);ctx['sources'].bind(__file__)
    data=ctx['sources'].json(a.input)
    for path,h in data.get('sources',{}).items():ctx['sources'].bind(path,h)
    previous.OUT=out;scanner=previous.Scan(ctx)
    if a.mode=='actual_boxes':
        ctx['sources'].bind(interval_check.__file__)
        result=interval_check.scan(data,scanner)
        (out/'numerical_state_box_check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print('ACTUAL_BOXES',result['interval_count'],'RAW',len(result['raw_positive_actual_anchors']),
              'UNRESOLVED',len(result['unresolved_pairs']),flush=True)
    else:
        if a.mode in ['finite','both']:scanner.finite(data['poses'],a.label)
        if a.mode in ['continuous','both']:scanner.continuous(data['segments'],a.label)
    ctx['sources'].verify()

if __name__=='__main__':main()
