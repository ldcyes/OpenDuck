"""Whole-source-material finite or continuous review of an explicit R20 candidate.

Input JSON: {poses:[{q:{joint:degrees},label:...,time_s:...}],
segments:[{q0:...,q1:...,start_s:...,end_s:...}],sources:{path:sha256}}.
No geometry or part category is exempted merely by being static or adjacent.
"""
from pathlib import Path
import sys,itertools,json,argparse
ROOT=Path(__file__).resolve().parents[3]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'work/r19-walking-simulation/geometry')]
import check_walking as previous
import numpy as np
import trimesh,manifold3d as md
BASE='work/r18-leg-hip-covers/legs/reference_design/candidate_v8/motion_diagnostic/diagnostic_selection.json'

def new_context(selection,manifest):
 ctx=previous.dc.load_context(selection,manifest,baseline_path=BASE);sources=ctx['sources'];sources.bind(__file__)
 override=sources.json('work/r19-walking-simulation/review/xc330_analysis/override_manifest.json')
 for p,h in override['sources'].items():sources.bind(p,h)
 for o in override['overrides']:
  row=ctx['by'][o['name']]
  if row['mesh_sha256']!=o['original_mesh_sha256']or row['R']!=o['original_R']or row['t_mm']!=o['original_t_mm']or row['link_frame']!=o['original_link_frame']:raise ValueError(('XC330_RETAINED_BINDING_CHANGED',o['name']))
  mesh=trimesh.load(sources.bind(o['analysis_mesh'],o['analysis_mesh_sha256']),force='mesh');V=np.ascontiguousarray(np.asarray(mesh.vertices)@np.asarray(row['R']).T+row['t_mm'],dtype=np.float64)
  # The native binding needs writable contiguous input while copying the mesh.
  solid=md.Manifold(md.Mesh64(V,np.ascontiguousarray(mesh.faces,dtype=np.uint64)))
  if solid.status()!=md.Error.NoError or solid.volume()<=0:raise ValueError(('INVALID_DERIVED_XC330',o['name']))
  V.flags.writeable=False
  b=np.array([V.min(0),V.max(0)]);ctx['objects'][o['name']]=dict(vertices=V,solid=solid,bounds=b,corners=np.array(list(itertools.product(*zip(b[0],b[1])))))
 if any(o['solid']is None for o in ctx['objects'].values()):raise ValueError('UNRESOLVED_NEW_OR_RETAINED_MATERIAL')
 ctx['pairs']=list(itertools.combinations(ctx['by'],2))
 ctx['analysis_override']=dict(override,status='SAME_THREE_RETAINED_XC330_ANALYSIS_SOURCES_EXPLICITLY_REBOUND_TO_R20_SELECTION',review_selection=selection,review_selection_sha256=previous.dc.sha(ROOT/selection))
 sources.verify();return ctx

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--label',required=True);ap.add_argument('--selection');ap.add_argument('--manifest');ap.add_argument('--mode',choices=['finite','continuous','both'],default='finite');a=ap.parse_args()
 if bool(a.selection)!=bool(a.manifest):raise ValueError('SELECTION_AND_DELTA_MANIFEST_BOTH_REQUIRED')
 out=Path(__file__).resolve().parent/a.label;out.mkdir(parents=True,exist_ok=True);previous.OUT=out
 ctx=new_context(a.selection,a.manifest)if a.selection else previous.context();ctx['sources'].bind(__file__)
 data=ctx['sources'].json(a.input)
 for p,h in data.get('sources',{}).items():ctx['sources'].bind(p,h)
 scanner=previous.Scan(ctx)
 if a.mode in ['finite','both']:scanner.finite(data['poses'],a.label)
 if a.mode in ['continuous','both']:scanner.continuous(data['segments'],a.label)
if __name__=='__main__':main()
