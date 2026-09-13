"""Verify the curated publication without running hardware or simulation code."""
from pathlib import Path
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--assets',type=Path);args=p.parse_args()
 files=json.loads((ROOT/'provenance/source-manifest.json').read_text())['files'];errors=[]
 for item in files:
  q=ROOT/item['repository_path']
  if not q.is_file() or digest(q)!=item['published_sha256']:errors.append(str(q.relative_to(ROOT)))
 native=ROOT/'hardware/kicad'; boards=list(native.glob('*/*.kicad_pcb'));schematics=list(native.glob('*/*.kicad_sch'))
 if len(boards)!=12 or len(schematics)!=12:errors.append('Expected 12 boards and 12 schematics')
 for board in boards:
  if not board.with_suffix('.kicad_pro').is_file() or not board.with_suffix('.kicad_sch').is_file():errors.append(str(board))
 for table in [*native.glob('*/fp-lib-table'),*native.glob('*/sym-lib-table')]:
  for uri in re.findall(r'\(uri "([^"]+)"\)',table.read_text()):
   q=Path(uri.replace('${KIPRJMOD}',str(table.parent)))
   if not q.exists():errors.append(f'{table.relative_to(ROOT)}: unresolved library {uri}')
 checked_assets=0
 if args.assets:
  for a in json.loads((ROOT/'release-assets.json').read_text())['assets']:
   q=args.assets/a['name']
   if not q.is_file() or q.stat().st_size!=a['bytes'] or digest(q)!=a['sha256']:errors.append(a['name'])
   checked_assets+=1
 print(json.dumps({'passed':not errors,'copied_files_checked':len(files),'native_board_types':len(boards),'native_schematics':len(schematics),'release_assets_checked':checked_assets,'errors':errors},ensure_ascii=False,indent=2))
 raise SystemExit(bool(errors))
if __name__=='__main__':main()
