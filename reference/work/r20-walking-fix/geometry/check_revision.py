"""Explicit changed-material x whole-assembly review against a frozen R20 selection.

Unchanged pair results may be reused only with exact geometry/link/frame matches
and an identically source-bound trajectory. This file does not itself approve
that composition or turn named nominal contacts into free clearance.
"""
from pathlib import Path
import sys,argparse,json
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from check_candidate_v2 import previous,new_context

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--selection',required=True);ap.add_argument('--manifest',required=True);ap.add_argument('--prior-selection',required=True);ap.add_argument('--input',required=True);ap.add_argument('--label',required=True);a=ap.parse_args()
 ctx=new_context(a.selection,a.manifest);src=ctx['sources'];src.bind(__file__);old=src.json(a.prior_selection);before={r['name']:r for r in old['items']};after=ctx['by']
 if old['joints']!=ctx['sel']['joints']:raise ValueError('KINEMATIC_CHAIN_CHANGED_CANNOT_REUSE_UNCHANGED_PAIRS')
 fields=['mesh_sha256','R','t_mm','link_frame','geometry_scale']
 changed=[n for n in after if n not in before or any(after[n].get(k)!=before[n].get(k)for k in fields)];removed=sorted(set(before)-set(after));retained=sorted(set(after)-set(changed))
 if not changed:raise ValueError('NO_CHANGED_MATERIAL')
 allpairs=ctx['pairs'];ctx['pairs']=[(x,y)for x,y in allpairs if x in changed or y in changed];data=src.json(a.input)
 for p,h in data['sources'].items():src.bind(p,h)
 out=HERE/a.label;out.mkdir(exist_ok=True);previous.OUT=out;scanner=previous.Scan(ctx)
 info=dict(status='EXPLICIT_GEOMETRY_DIFF_NOT_AN_ASSEMBLY_PASS',changed_material_names=changed,removed_names=removed,unchanged_geometry_link_frame_names=retained,whole_pair_count=len(allpairs),revised_pair_count=len(ctx['pairs']),unchanged_pair_count=len(allpairs)-len(ctx['pairs']),geometry_comparison_fields=fields,prior_selection=a.prior_selection,current_selection=a.selection,input=a.input,sources=src.entries.copy())
 (out/'revision_scope.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
 scanner.finite(data['poses'],a.label);scanner.continuous(data['segments'],a.label)
if __name__=='__main__':main()
