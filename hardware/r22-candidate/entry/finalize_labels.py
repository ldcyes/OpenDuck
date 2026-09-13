"""Readable polarity/ref labels beside eight power solder terminals."""
from pathlib import Path
import pcbnew as p,shutil
R=Path(__file__).parent;f=R/'Microduck_Entry_5V_R22.kicad_pcb';b=p.LoadBoard(str(f))
labels=[('W1+',5,4.9),('W2-',9.5,16),('W3+',24,13),('W4-',24,21),('W5+',32,9),('W6-',32,23.8),('W7+',40,9),('W8-',44.5,20),('ENTRY R22',12.5,3)]
for t in list(b.GetDrawings()):
 if isinstance(t,p.PCB_TEXT)and t.GetText()in [q[0]for q in labels]:b.Remove(t)
for label,x,y in labels:
 t=p.PCB_TEXT(b);t.SetText(label);t.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));t.SetTextSize(p.VECTOR2I(p.FromMM(.8),p.FromMM(.8)));t.SetTextThickness(p.FromMM(.12));t.SetLayer(p.F_SilkS);b.Add(t)
p.SaveBoard(str(f),b);shutil.copyfile(R.parents[2]/'work/r13-electronics/inherited/Entry_5V_R8/Microduck_Entry_5V_R8.kicad_pro',f.with_suffix('.kicad_pro'))
