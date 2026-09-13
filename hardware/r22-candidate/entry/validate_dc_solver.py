from pathlib import Path
import math,json
from solve_dc_copper import solve,rho
R=Path(__file__).parent
def rect(x0,y0,x1,y1,l):return dict(net='TEST',layer=l,outer=[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],holes=[])
out=[]
for h in [.05,.025]:
 q=rect(0,0,10,1,0);d=dict(layers=[0],thickness_mm=[.07],z_mm=[0],polys=[q],tracks=[],vias=[],pads=[dict(name='S.1',polys=[rect(0,0,h,1,0)]),dict(name='T.1',polys=[rect(10-h,0,10,1,0)])]);r=solve(d,'TEST',['S.1'],['T.1'],h);expected=rho*(10-h)/(.07*1)*1000;out.append(dict(case='Uniform rectangular sheet, ideal end columns',expected_mOhm=expected,relative_error=(r['R20_mOhm']/expected-1),**r))
for count in[1,4]:
 d=dict(layers=[0,2],thickness_mm=[.07,.07],z_mm=[0,1.51],polys=[rect(0,0,2,2,0),rect(0,0,2,2,2)],tracks=[],vias=[dict(net='TEST',pos=xy,diameter=.45,drill=.2)for xy in ([[1,1]]if count==1 else[[.5,.5],[.5,1.5],[1.5,.5],[1.5,1.5]])],pads=[dict(name='S.1',polys=[rect(0,0,2,2,0)]),dict(name='T.1',polys=[rect(0,0,2,2,2)])]);r=solve(d,'TEST',['S.1'],['T.1'],.05);expected=rho*1.51/(math.pi*(.125**2-.1**2))/count*1000;out.append(dict(case=f'{count} plated barrels between equipotential layers',expected_mOhm=expected,relative_error=r['R20_mOhm']/expected-1,**r))
assert max(abs(q['relative_error'])for q in out)<1e-6
(R/'verification/dc_solver_analytic_checks.json').write_text(json.dumps(out,indent=2));print('4 analytic checks passed')
