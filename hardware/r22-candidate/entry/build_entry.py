"""R22 Entry physical redesign. Inherit authoritative R13 schematic and footprints verbatim.
All outputs remain below this directory; source inputs are read only.
"""
from pathlib import Path
import pcbnew as p, json, shutil, hashlib, re, math
R=Path(__file__).resolve().parent
ROOT=R.parents[2]; SRC=ROOT/'work/r13-electronics/inherited/Entry_5V_R8'
N='Microduck_Entry_5V_R22'; OLD='Microduck_Entry_5V_R8'
mm=p.FromMM; v=lambda x,y:p.VECTOR2I(mm(x),mm(y))
for sub in ['assembly','verification','preview']: (R/sub).mkdir(exist_ok=True)
for ext in ['kicad_sch','kicad_pro']: shutil.copyfile(SRC/(OLD+'.'+ext),R/(N+'.'+ext))
for f in ['Microduck_Entry_R8.kicad_sym','fp-lib-table','sym-lib-table']:shutil.copyfile(SRC/f,R/f)
shutil.copytree(SRC/'footprints',R/'footprints',dirs_exist_ok=True)
(R/(N+'.kicad_dru')).write_text('(version 1)\n# Source project dimensions remain unchanged. These rules only tighten them.\n(rule "2oz absolute fabrication spacing" (constraint clearance (min 0.16mm)))\n(rule "New traces minimum width" (condition "A.Type == \'Track\'") (constraint track_width (min 0.20mm)))\n(rule "Zone copper separation" (condition "A.Type == \'Zone\' || B.Type == \'Zone\'") (constraint clearance (min 0.205mm)))\n')
def strip_root_geometry(text):
 spans=[]; depth=0; quoted=False;escape=False;start=None
 for i,c in enumerate(text):
  if escape:escape=False;continue
  if c=='\\' and quoted:escape=True;continue
  if c=='"':quoted=not quoted;continue
  if quoted:continue
  if c=='(':
   if depth==1:start=i
   depth+=1
  elif c==')':
   depth-=1
   if depth==1 and start is not None:
    key=text[start+1:].split(None,1)[0]
    if key in ['segment','via','zone'] or key.startswith('gr_'):spans.append((start,i+1))
 for a,z in reversed(spans):text=text[:a]+text[z:]
 return text
(R/'verification/native_unrouted.kicad_pcb').write_text(strip_root_geometry((SRC/(OLD+'.kicad_pcb')).read_text()))
b=p.LoadBoard(str(R/'verification/native_unrouted.kicad_pcb'))
b.SetCopperLayerCount(4)
# Host clearance review authorized matching SH top-entry headers at the frozen XY.
# Preserve every numbered contact/net and the same SHR housing/SSH terminal family.
vertical={'J3':2,'J5':8,'J6':3,'J7':3,'J8':5}
libpath=ROOT/'work/tools/kicad/AppDir/share/kicad/footprints/Connector_JST.pretty'
for ref,count in vertical.items():
 oldfp=next(fp for fp in b.GetFootprints()if fp.GetReference()==ref)
 name=f'JST_SH_BM{count:02d}B-SRSS-TB_1x{count:02d}-1MP_P1.00mm_Vertical'
 shutil.copyfile(libpath/(name+'.kicad_mod'),R/'footprints/Connector_JST.pretty'/(name+'.kicad_mod'))
 newfp=p.FootprintLoad(str(R/'footprints/Connector_JST.pretty'),name)
 newfp.SetReference(ref);newfp.SetValue(oldfp.GetValue());newfp.SetFPID(p.LIB_ID('Connector_JST',name));newfp.SetPath(oldfp.GetPath())
 newfp.SetField('MPN',f'BM{count:02d}B-SRSS-TB(LF)(SN)');newfp.GetField('MPN').SetVisible(False);newfp.SetField('Datasheet','https://www.jst-mfg.com/product/pdf/eng/eSH.pdf');newfp.GetField('Datasheet').SetVisible(False)
 oldnets={pd.GetNumber():pd.GetNet()for pd in oldfp.Pads()if pd.GetNetname()}
 for pd in newfp.Pads():
  if pd.GetNumber()in oldnets:pd.SetNet(oldnets[pd.GetNumber()])
  pd.SetLocalZoneConnection(p.ZONE_CONNECTION_FULL)
 b.Remove(oldfp);b.Add(newfp)
pos={
'W1':(5,9,0),'RS1':(14,9,0),'W3':(24,9,0),'W2':(5,16,0),'W4':(24,17,0),
'W5':(32,13,0),'W6':(32,20,0),'W7':(40,13,0),'W8':(40,20,0),
'U3':(16,27,0),'C9':(7,22,0),'C10':(7,25.5,0),'C11':(4,32,0),
'C12':(13,35,0),'C13':(18,35,0),'C14':(22,35,0),'C15':(28,35,0),
'R10':(18,19,0),'C8':(18,21,0),'R11':(16,22,0),'R12':(10,22,0),'F1':(26.5,25,270),
'U1':(14,16,0),'R1':(10,20,0),'R2':(13.2,20,0),'C1':(9,28,0),'C2':(18,19,0),
'U4':(33,27,0),'C16':(38,25,0),'C17':(33,30,0),'C18':(39,31,0),'R13':(32,31.5,0),'R14':(36,30,0),
'J5':(33.4,4,180),'J8':(44,4,180),'J4':(48,14,90),'J1':(48,24.5,90),'J2':(48,31.5,90),
'J3':(43.5,38,0),'J6':(35.5,38,0),'J7':(27.5,38,0),
'U2':(41,7,0),'R3':(30,8,0),'R4':(29.5,5,0),'R5':(26.5,21.5,0),
'R6':(44,25,0),'R7':(44,28,0),'R8':(44,35,0),'C3':(40,24.5,0),'C4':(40,27,0),'C5':(36,33,0),
'R9':(35,5,0),'C6':(35,7,0),'C7':(45,10,0),
'H1':(3,3,0),'H2':(23,3,0),'H3':(3,39,0),'H4':(49,39,0)}
assert len(pos)==58
fps={}
for fp in b.GetFootprints():
 ref=fp.GetReference(); fp.SetPosition(v(*pos[ref][:2])); fp.SetOrientationDegrees(pos[ref][2])
 if ref in ['C14','C15']:fp.Flip(fp.GetPosition(),False)
 fp.Reference().SetVisible(False);fp.Value().SetVisible(False)
 fps[ref]=fp
 if ref in ['U1','U2']:
  # TI DGS0010A example layout: 10x1.45x0.30, row-center span 4.4, pitch0.5.
  # Package body/fab/courtyard and physical pin numbering are unchanged.
  for pd in fp.Pads():
   point=pd.GetPosition();dx=p.ToMM(point.x)-pos[ref][0]
   pd.SetPosition(v(pos[ref][0]+math.copysign(2.2,dx),p.ToMM(point.y)));pd.SetSize(v(1.45,.30));pd.SetRoundRectCornerRadius(mm(.05))
  fp.SetFPID(p.LIB_ID('Microduck_Entry_R8','TI_DGS0010A_Manufacturer_1p45x0p30'))
 # Actual Ø6 mm solder land plus 0.5 mm process allowance on both sides.
 if ref.startswith('W'):
  for layer in [p.F_CrtYd,p.B_CrtYd]:
   for a,c in [((-3.5,-3.5),(3.5,-3.5)),((3.5,-3.5),(3.5,3.5)),((3.5,3.5),(-3.5,3.5)),((-3.5,3.5),(-3.5,-3.5))]:
    sh=p.PCB_SHAPE(fp);sh.SetShape(p.SHAPE_T_SEGMENT);sh.SetStart(v(pos[ref][0]+a[0],pos[ref][1]+a[1]));sh.SetEnd(v(pos[ref][0]+c[0],pos[ref][1]+c[1]));sh.SetLayer(layer);sh.SetWidth(mm(.05));fp.Add(sh)
p.FootprintSave(str(R/'footprints/Microduck_Entry_R8.pretty'),fps['W1'])
p.FootprintSave(str(R/'footprints/Microduck_Entry_R8.pretty'),fps['U1'])
sch=R/(N+'.kicad_sch');sch.write_text(sch.read_text().replace('Package_SO:MSOP-10_3x3mm_P0.5mm','Microduck_Entry_R8:TI_DGS0010A_Manufacturer_1p45x0p30'))
text=sch.read_text();spans=[];depth=0;quoted=False;escape=False;start=None
for i,c in enumerate(text):
 if escape:escape=False;continue
 if c=='\\'and quoted:escape=True;continue
 if c=='"':quoted=not quoted;continue
 if quoted:continue
 if c=='(':
  if depth==1:start=i
  depth+=1
 elif c==')':
  depth-=1
  if depth==1 and start is not None and text[start+1:].split(None,1)[0]=='symbol':spans.append((start,i+1))
for a,z in reversed(spans):
 block=text[a:z]
 for ref,count in vertical.items():
  if re.search(r'\(property\s+"Reference"\s+"'+ref+'"',block):
   block=block.replace(f'SM{count:02d}B-SRSS-TB(LF)(SN)',f'BM{count:02d}B-SRSS-TB(LF)(SN)').replace(f'JST_SH_SM{count:02d}B-SRSS-TB_1x{count:02d}-1MP_P1.00mm_Horizontal',f'JST_SH_BM{count:02d}B-SRSS-TB_1x{count:02d}-1MP_P1.00mm_Vertical')
 text=text[:a]+block+text[z:]
sch.write_text(text)
W=52;H=42
for a,c in [((0,0),(W,0)),((W,0),(W,H)),((W,H),(0,H)),((0,H),(0,0))]:
 sh=p.PCB_SHAPE();sh.SetShape(p.SHAPE_T_SEGMENT);sh.SetStart(v(*a));sh.SetEnd(v(*c));sh.SetLayer(p.Edge_Cuts);sh.SetWidth(mm(.05));b.Add(sh)
ds=b.GetDesignSettings();ds.SetAuxOrigin(v(0,H));ds.SetBoardThickness(mm(1.6))
pads=[]
for fp in b.GetFootprints():
 for pd in fp.Pads():
  if not(pd.IsOnLayer(p.F_Cu) or pd.IsOnLayer(p.B_Cu)):continue
  xy=pd.GetPosition();size=pd.GetSize(); sx,sy=p.ToMM(size.x),p.ToMM(size.y)
  if round(pd.GetOrientationDegrees())%180:sx,sy=sy,sx
  thru=pd.GetAttribute() in [p.PAD_ATTRIB_PTH,p.PAD_ATTRIB_NPTH]
  pads.append(dict(ref=fp.GetReference(),pin=pd.GetNumber(),net=pd.GetNetname() or None,x=p.ToMM(xy.x),y=p.ToMM(xy.y),sx=sx,sy=sy,through=thru,drill=p.ToMM(pd.GetDrillSize().x),shape=int(pd.GetShape()),layers=[0,1,2,3] if thru else ([0] if pd.IsOnLayer(p.F_Cu) else [3])))
(R/'pads.json').write_text(json.dumps(pads,indent=2))
(R/'placement.json').write_text(json.dumps(pos,indent=2))
(R/'config.json').write_text(json.dumps(dict(W=W,H=H,TH=1.6,NAME=N)))
p.SaveBoard(str(R/(N+'.kicad_pcb')),b)
# Replace the native two-layer stack block with a symmetric four-layer proposal.
f=R/(N+'.kicad_pcb');s=f.read_text(); start=s.index('(stackup');depth=0;end=start
for i in range(start,len(s)):
 if s[i]=='(':depth+=1
 elif s[i]==')':
  depth-=1
  if depth==0:end=i+1;break
stack='''(stackup
 (layer "F.SilkS" (type "Top Silk Screen")) (layer "F.Paste" (type "Top Solder Paste"))
 (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
 (layer "F.Cu" (type "copper") (thickness 0.07))
 (layer "dielectric 1" (type "prepreg") (thickness 0.185) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "In1.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 2" (type "core") (thickness 1.00) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "In2.Cu" (type "copper") (thickness 0.035))
 (layer "dielectric 3" (type "prepreg") (thickness 0.185) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
 (layer "B.Cu" (type "copper") (thickness 0.07))
 (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
 (layer "B.Paste" (type "Bottom Solder Paste")) (layer "B.SilkS" (type "Bottom Silk Screen"))
 (copper_finish "ENIG") (dielectric_constraints no))'''
s=s[:start]+stack+s[end:];f.write_text(s)
shutil.copyfile(SRC/(OLD+'.kicad_pro'),R/(N+'.kicad_pro'))
print('Native R13 58-footprint placement inherited; 52x42 mm four layers; unrouted.')
