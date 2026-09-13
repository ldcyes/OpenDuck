"""Export actual native copper shapes; source board is read-only."""
from pathlib import Path
import pcbnew as p,json,sys
R=Path(__file__).parent;ROOT=R.parents[2]
paths={'source_regen':ROOT/'work/r13-electronics/inherited/Regen_R8/Microduck_Brake_Control_R8.kicad_pcb','source_power':ROOT/'work/r13-electronics/inherited/TDK_Power_R8/Microduck_TDK_Power_R8.kicad_pcb','r22':R/'Microduck_Power_Regen_R22.kicad_pcb'}
NETS=['SERVO_BUS','GND','RG_RH_LOW','RH_LOW','RG_BRAKE_SHUNT_P','BRAKE_SHUNT_P']
def contour(c):return [[p.ToMM(c.CPoint(i).x),p.ToMM(c.CPoint(i).y)]for i in range(c.PointCount())]
for label,path in paths.items():
 b=p.LoadBoard(str(path));layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu] if label=='r22'else[p.F_Cu,p.B_Cu];out=dict(label=label,layers=layers,thickness_mm=[.07,.035,.035,.07]if label=='r22'else[.07,.07],z_mm=[0,.2375,1.2725,1.51]if label=='r22'else[0,1.51],polys=[],tracks=[],vias=[],pads=[])
 def polys(ps,net,l,kind):
  for i in range(ps.OutlineCount()):out['polys'].append(dict(net=net,layer=l,outer=contour(ps.COutline(i)),holes=[contour(ps.CHole(i,j))for j in range(ps.HoleCount(i))],kind=kind))
 for z in b.Zones():
  if z.GetNetname()not in NETS:continue
  for l in layers:
   if z.IsOnLayer(l):polys(z.GetFilledPolysList(l),z.GetNetname(),l,'zone')
 for fp in b.GetFootprints():
  for pd in fp.Pads():
   net=pd.GetNetname()
   if net not in NETS:continue
   ls=[l for l in layers if pd.IsOnLayer(l)];name=fp.GetReference()+'.'+pd.GetNumber();q=dict(net=net,name=name,xy=[p.ToMM(pd.GetPosition().x),p.ToMM(pd.GetPosition().y)],layers=ls,drill=p.ToMM(pd.GetDrillSize().x),polys=[])
   for l in ls:
    ps=pd.GetEffectivePolygon(l,p.ERROR_INSIDE);polys(ps,net,l,'pad')
    for i in range(ps.OutlineCount()):q['polys'].append(dict(layer=l,outer=contour(ps.COutline(i)),holes=[contour(ps.CHole(i,j))for j in range(ps.HoleCount(i))]))
   out['pads'].append(q)
   if q['drill']>0:out['vias'].append(dict(net=net,pos=q['xy'],drill=q['drill'],diameter=min(p.ToMM(pd.GetSize().x),p.ToMM(pd.GetSize().y)),name=name))
 for t in b.GetTracks():
  if t.GetNetname()not in NETS:continue
  if isinstance(t,p.PCB_VIA):out['vias'].append(dict(net=t.GetNetname(),pos=[p.ToMM(t.GetPosition().x),p.ToMM(t.GetPosition().y)],drill=p.ToMM(t.GetDrillValue()),diameter=p.ToMM(t.GetWidth(p.F_Cu)),name='via'))
  else:out['tracks'].append(dict(net=t.GetNetname(),a=[p.ToMM(t.GetStart().x),p.ToMM(t.GetStart().y)],b=[p.ToMM(t.GetEnd().x),p.ToMM(t.GetEnd().y)],width=p.ToMM(t.GetWidth()),layer=t.GetLayer()))
 (R/f'verification/{label}_dc_geometry.json').write_text(json.dumps(out));print(label,len(out['polys']),len(out['tracks']),len(out['vias']))
