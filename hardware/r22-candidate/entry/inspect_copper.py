from pathlib import Path
import pcbnew as p,json
R=Path(__file__).parent;b=p.LoadBoard(str(R/'Microduck_Entry_5V_R22.kicad_pcb'));out={'polys':[],'points':[]};layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu]
def contour(c):return [[p.ToMM(c.CPoint(i).x),p.ToMM(c.CPoint(i).y)]for i in range(c.PointCount())]
for z in b.Zones():
 for l in layers:
  if not z.IsOnLayer(l):continue
  ps=z.GetFilledPolysList(l)
  for i in range(ps.OutlineCount()):out['polys'].append(dict(net=z.GetNetname(),layer=l,outer=contour(ps.COutline(i)),holes=[contour(ps.CHole(i,j))for j in range(ps.HoleCount(i))]))
for fp in b.GetFootprints():
 for pd in fp.Pads():
  if pd.GetNetname():out['points'].append(dict(name=fp.GetReference()+'.'+pd.GetNumber(),net=pd.GetNetname(),x=p.ToMM(pd.GetPosition().x),y=p.ToMM(pd.GetPosition().y),layers=[l for l in layers if pd.IsOnLayer(l)]))
for t in b.GetTracks():
 if isinstance(t,p.PCB_VIA):out['points'].append(dict(name='via',net=t.GetNetname(),x=p.ToMM(t.GetPosition().x),y=p.ToMM(t.GetPosition().y),layers=layers))
(R/'verification/copper_polygons.json').write_text(json.dumps(out));print('filled copper polygons',len(out['polys']))
