"""Serial fixed-seed replay into a separate sibling directory."""
from pathlib import Path
import argparse,json,hashlib,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();group=ap.add_mutually_exclusive_group(required=True);group.add_argument('--index',type=int,choices=range(81));group.add_argument('--all',action='store_true');args=ap.parse_args();manifest=json.loads((HERE/'rerun_manifest.json').read_text());out=HERE.with_name('combined81-rerun');out.mkdir(exist_ok=True)
 for name in ['bootstrap.py','refine_bending.py','solve_family.py','audit_bodies.py']:
  p=HERE/name;assert sha(p)==manifest['source_hashes'][str(p.relative_to(ROOT))];shutil.copyfile(p,out/name)
 assert sha(HERE/'selection_snapshot.json')==manifest['selection_sha256'];shutil.copyfile(HERE/'selection_snapshot.json',out/'selection_snapshot.json')
 meshes=json.loads((HERE/'rigid_mesh_hashes.json').read_text())['mesh_files'];assert all(sha(ROOT/name)==h for name,h in meshes.items()),'Rigid mesh inputs changed'
 for r in manifest['cases']:
  if args.index is not None and r['index']!=args.index:continue
  for suffix in [f'case_{r["index"]:02}.json',f'case_{r["index"]:02}_bodies.json',f'failure_{r["index"]:02}.json']:(out/'cases'/suffix).unlink(missing_ok=True)
  seed=ROOT/r['seed'];assert sha(seed)==r['seed_sha256'];command=[sys.executable,str(out/'solve_family.py'),'--index',str(r['index']),'--seed-file',str(seed),'--iterations',str(r['iterations']),'--stages',str(r['stages'])]
  with (out/f'replay_{r["index"]:02}.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
  route=out/'cases'/f'case_{r["index"]:02}.json'
  if route.exists():subprocess.run([sys.executable,str(out/'audit_bodies.py'),'--input',str(route)],check=True)
  print('REPLAY_FINISHED',r['index'],'ROUTE' if route.exists() else 'UNRESOLVED',flush=True)
if __name__=='__main__':main()
