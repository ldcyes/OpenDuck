from pathlib import Path
import pcbnew as p,json,sys,shutil,math
R=Path(__file__).parent;ROOT=R.parents[2];N='Microduck_Entry_5V_R22';mm=p.FromMM;v=lambda a:p.VECTOR2I(mm(a[0]),mm(a[1]))
b=p.LoadBoard(str(R/(N+'.kicad_pcb')));nets={n.GetNetname():n for n in b.GetNetInfo().NetsByNetcode().values()};layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu]
d=json.loads((R/('seed_routes.json' if 'seed'in sys.argv else 'routes.json')).read_text())
for row in d['segments']:
 t=p.PCB_TRACK(b);t.SetStart(v(row['a']));t.SetEnd(v(row['b']));t.SetWidth(mm(row['width']));t.SetLayer(layers[row['layer']]);t.SetNet(nets[row['net']]);b.Add(t)
for row in d['vias']:
 t=p.PCB_VIA(b);t.SetPosition(v(row['pos']));t.SetWidth(mm(row['diameter']));t.SetDrill(mm(row['drill']));t.SetLayerPair(p.F_Cu,p.B_Cu);t.SetViaType(p.VIATYPE_THROUGH);t.SetNet(nets[row['net']]);b.Add(t)
if 'seed'not in sys.argv:
 # Local power pours follow real routed paths; In1 remains the GND reference plane.
 # These are additive copper shapes, never reductions of the clearance rules.
 power=['BAT_MON','LOGIC_VIN','MOBILE_5V','BENCH_5V','SYSTEM_5V']
 def poly_shape(points):
  result=p.SHAPE_POLY_SET();result.NewOutline()
  for pt in points:result.Append(v(pt))
  return result
 def capsule(a,c,r):
  dx,dy=c[0]-a[0],c[1]-a[1];ang=math.atan2(dy,dx)
  pts=[]
  for ctr,start in [(c,ang-math.pi/2),(a,ang+math.pi/2)]:
   for j in range(9):theta=start+j*math.pi/8;pts.append([ctr[0]+r*math.cos(theta),ctr[1]+r*math.sin(theta)])
  return poly_shape(pts)
 for name in power:
  for li in [0,2,3]:
   combined=p.SHAPE_POLY_SET()
   for row in d['segments']:
    if row['net']==name and row['layer']==li and row['width']<3:
     combined.BooleanAdd(capsule(row['a'],row['b'],.8 if li!=2 else 1.1))
   if name=='BENCH_5V'and li==2:
    for a,c in [([32,13],[29,15]),([29,15],[27.5,22]),([27.5,22],[28.6,27.4])]:combined.BooleanAdd(capsule(a,c,1.0))
   if name=='MOBILE_5V'and li==3:combined.BooleanAdd(poly_shape([[14.65,27.8],[16.6,27.8],[16.6,32.95],[14.65,32.95]]))
   if not combined.OutlineCount():continue
   for oi in range(combined.OutlineCount()):
    z=p.ZONE(b);z.SetLayer(layers[li]);z.SetNet(nets[name]);z.SetAssignedPriority(10);z.SetLocalClearance(mm(.205));z.SetPadConnection(p.ZONE_CONNECTION_FULL);z.SetMinThickness(mm(.15));z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)
    z.Outline().AddOutline(combined.COutline(oi))
    for hi in range(combined.HoleCount(oi)):z.Outline().AddHole(combined.CHole(oi,hi),0)
    b.Add(z)
 for layer in layers:
  z=p.ZONE(b);z.SetLayer(layer);z.SetNet(nets['GND']);z.SetLocalClearance(mm(.205));z.SetPadConnection(p.ZONE_CONNECTION_FULL);z.SetThermalReliefGap(mm(.25));z.SetThermalReliefSpokeWidth(mm(.3));z.SetMinThickness(mm(.15));z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)
  poly=z.Outline();poly.NewOutline()
  for point in [[.25,.25],[51.75,.25],[51.75,41.75],[.25,41.75]]:poly.Append(int(mm(point[0])),int(mm(point[1])))
  b.Add(z)
 b.BuildConnectivity()
 p.ZONE_FILLER(b).Fill(b.Zones())
out=R/'verification/seed.kicad_pcb' if 'seed'in sys.argv else R/(N+'.kicad_pcb');p.SaveBoard(str(out),b)
shutil.copyfile(ROOT/'work/r13-electronics/inherited/Entry_5V_R8/Microduck_Entry_5V_R8.kicad_pro',out.with_suffix('.kicad_pro'))
print('Saved',out,len(d['segments']),'tracks',len(d['vias']),'vias')

if 'seed'not in sys.argv:
 b=p.LoadBoard(str(out));b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
 shutil.copyfile(ROOT/'work/r13-electronics/inherited/Entry_5V_R8/Microduck_Entry_5V_R8.kicad_pro',out.with_suffix('.kicad_pro'))
