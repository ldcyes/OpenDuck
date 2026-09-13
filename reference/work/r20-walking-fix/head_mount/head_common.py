"""R20 head-only source binding; all frozen R18/R19 files remain read-only."""
from pathlib import Path
import sys, json, hashlib, math, itertools, copy
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'work/r13-electronics/mechanics'), str(ROOT/'work/r12-motion/python-deps'), str(ROOT/'work/rk-mechanics/python-deps')]
import common as c
import numpy as np
import trimesh, manifold3d as md
from OCP.BRepTools import BRepTools
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.StlAPI import StlAPI_Writer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID

SOURCES = {}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p): return str(Path(p).resolve().relative_to(ROOT))
def bind(p, h=None):
    p = Path(p); p = p if p.is_absolute() else ROOT/p
    a = sha(p)
    if h is not None: assert a == h, (rel(p), 'SOURCE_CHANGED')
    SOURCES[rel(p)] = a
    return p
def load(p): return json.loads(bind(p).read_text())
def dump(p, o):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')

SEL_PATH='work/r18-leg-hip-covers/legs/reference_design/candidate_v8/motion_diagnostic/diagnostic_selection.json'
SEL=load(SEL_PATH); BY={r['name']:r for r in SEL['items']}
R9=load('work/r9-appearance/r9_selected_component_layout.json')
R9BY={r['name']:r for r in R9['parts']}
SHIFT=np.array([138.34454072117805,-2.347290277481079,237.5042672753334])
HOLES=[(21.65270972251892,264.5042672753334),(21.65270972251892,297.5042672753334),(-26.29729027748108,264.4842672753334),(-26.29729027748108,297.4842672753334)]
FEET=[(55.,yy+sy,222.) for yy in [HOLES[0][0],HOLES[2][0]] for sy in [-5.,5.]]
REMOVED=['R11_CM4_front_clamp_bar_1','R11_CM4_front_clamp_bar_2']
SHAPES={}
def source_shape(name):
    if name not in SHAPES:
        r=BY[name]
        if r.get('step'):
            s=c.tf(c.read(bind(r['step'],r['step_sha256'])),r['R'],r['t_mm'])
        else:
            q=R9BY[name.removeprefix('R10_')]
            assert q['mesh_sha256']==r['mesh_sha256']
            bind(q['mesh'],q['mesh_sha256']);bind(r['mesh'],r['mesh_sha256'])
            s=c.tf(c.read(bind(q['source'],q['source_sha256'])),q['oldtrunk_R'],q['oldtrunk_t_mm'])
            s=c.tf(s,r['R'],r['t_mm'])
        assert c.properties(s)['valid_BRep'], name
        SHAPES[name]=s
    return SHAPES[name]

def mesh_solid(path,R=None,t=None):
    m=trimesh.load(path,force='mesh',process=True)
    if R is not None: m.vertices=np.asarray(m.vertices)@np.asarray(R).T+np.asarray(t)
    s=md.Manifold(md.Mesh64(np.asarray(m.vertices,np.float64),np.asarray(m.faces,np.uint64)))
    assert s.status()==md.Error.NoError,(str(path),s.status())
    return m,s

def export(name,s,folder='CAD',material='A2 stainless purchased nominal reference',density=7.93,notes=''):
    d=OUT/folder
    q=c.export(name,s,d,material,density,'jaw_soft',notes)
    # Remove cached inherited tessellation before independently writing this new part.
    reread=c.read(d/q['STEP']); BRepTools.Clean_s(reread)
    BRepMesh_IncrementalMesh(reread,.012,False,.06,False).Perform()
    stl=d/q['STL']; writer=StlAPI_Writer();writer.ASCIIMode=False;assert writer.Write(reread,str(stl))
    m,solid=mesh_solid(stl)
    assert m.is_watertight and m.is_winding_consistent and m.volume>0
    err=abs(solid.volume()-q['volume_mm3'])
    assert err/max(q['volume_mm3'],1e-9)<.003,(name,err)
    q.update(mesh=rel(stl),mesh_sha256=sha(stl),step=rel(d/q['STEP']),step_sha256=sha(d/q['STEP']),
             mesh_closed_positive=True,mesh_volume_mm3=float(solid.volume()),mesh_vs_STEP_abs_volume_error_mm3=err,
             mesh_bbox_mm=m.bounds.tolist(),mesh_vs_STEP_bbox_max_abs_mm=float(np.max(np.abs(m.bounds-np.array(q['bounds_mm'])))))
    return q

def hex_prism(center,across_flats,length,axis='X'):
    r=across_flats/math.sqrt(3)
    pts=[]
    for axial in [-length/2,length/2]:
        for k in range(6):
            a=math.radians(30+k*60)
            v=np.array([axial,r*math.cos(a),r*math.sin(a)])
            if axis=='Z':v=v[[1,2,0]]
            pts.append(v+center)
    return c.convex_solid(pts)

def hardware(axis,underhead,d,L,head_d,head_h,hex_af,socket_depth,nut_af,nut_h,washer_d,washer_t,grip,name):
    """axis +X or -Z; grip is substrate distance, excluding washers/nut."""
    v=np.array([1.,0,0]) if axis=='X' else np.array([0.,0,-1.])
    ax='X' if axis=='X' else 'Z'
    U=np.array(underhead)
    shaft=c.cylinder(U+v*L/2,d/2,L,v)
    head=c.cylinder(U-v*head_h/2,head_d/2,head_h,v)
    screw=c.union(shaft,head)
    socket=hex_prism(U-v*(head_h-socket_depth/2),hex_af,socket_depth+.001,ax)
    screw=c.cut(screw,socket)
    washer_ID=d+.2
    def ring(center):return c.cut(c.cylinder(center,washer_d/2,washer_t,v),c.cylinder(center,washer_ID/2,washer_t+1,v))
    first=ring(U+v*washer_t/2)
    parts=[('screw',screw),('front_washer' if axis=='X' else 'top_washer',first)]
    nut_front=U+v*(washer_t+grip)
    if axis=='X':
        parts.append(('rear_washer',ring(nut_front+v*washer_t/2)))
        nut_front+=v*washer_t
    nut=hex_prism(nut_front+v*nut_h/2,nut_af,nut_h,ax)
    # Thread root envelope only: the controlled screw/nut nominal thread overlap is separately audited.
    nut=c.cut(nut,c.cylinder(nut_front+v*nut_h/2,(d-.4)/2,nut_h+1,v))
    parts.append(('nut',nut))
    return [(name+'_'+k,s) for k,s in parts],dict(axis=v.tolist(),under_head_mm=U.tolist(),nut_front_mm=nut_front.tolist(),nut_back_mm=(nut_front+v*nut_h).tolist(),tip_mm=(U+v*L).tolist(),nominal_protrusion_mm=L-washer_t-grip-(washer_t if axis=='X' else 0)-nut_h)
