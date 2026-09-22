from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).parent
sys.path[:0]=[str(ROOT/'work/r3-mechanics/python-deps'),str(ROOT/'work/r13-electronics/mechanics')]
import common as c
import numpy as np
S=json.loads((O/'candidate_selection.json').read_text());items={p['name']:p for p in S['items']};H=json.loads((O/'candidate_check.json').read_text());cache={};rows=[]
def solid(n):
 if n not in cache:
  p=items[n];cache[n]=c.tf(c.read(ROOT/p['step']),p['R'],p['t_mm'])
 return cache[n]
for r in H['hits']:
 a,b=r['a'],r['b'];classification=None;native=None
 if a.endswith('PEEK_comb_housing') and '_retainer_'in b and b.endswith('M2x6'):classification='M2 thread engagement, retained diameters'
 if a.endswith('M2_nut')and b.endswith('M2x18'):classification='M2 thread engagement, retained diameters'
 if 'power_pair_band_'in a and 'power_pair_knot_'in b:classification='Same lacing loop and zero-extra-mass knot envelope'
 if a=='R25_lower_head_shell_bottom_entry' and b.endswith('M3_DIN934_nut'):classification='Unchanged inherited nut-seat STL roundoff; local shell unchanged outside bottom aperture'
 if items[a].get('step')and items[b].get('step') and classification is None:
  native=abs(c.volume(c.common(solid(a),solid(b))))
  if native<1e-7:classification='Native STEP zero volume; triangulation seating artifact'
 rows.append(dict(**r,native_STEP_intersection_mm3=native,classification=classification))
 print(rows[-1],flush=True)
report=dict(sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in [O/'candidate_selection.json',O/'candidate_check.json',Path(__file__)]},status='NATIVE_CONTACT_REVIEW',rows=rows,unresolved=[r for r in rows if not r['classification']],physical_approved=False,manufacturing_approved=False)
(O/'native_contact_review.json').write_text(json.dumps(report,indent=2)+'\n')
