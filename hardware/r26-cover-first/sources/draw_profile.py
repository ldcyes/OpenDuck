"""Dimensioned contour comparison from exported mesh, not a styling mockup."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'work/r12-motion/python-deps'),str(ROOT/'work/rk-mechanics/python-deps')]
import numpy as np
import trimesh
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.spatial import ConvexHull
M=json.loads((OUT/'mechanics/manifest.json').read_text())
G=json.loads((OUT/'mechanics/geometry_checks.json').read_text())
A=json.loads((ROOT/'work/r25-bottom-head-entry/assembly_selection.json').read_text())
old={p['name']:p for p in A['items']}
B=np.array([[1,0,0],[0,.08718932367607021,.9961917595708684],[0,.9961917595708684,-.08718932367607021]])
fig,ax=plt.subplots(figsize=(7.5,8.5))
fig.subplots_adjust(left=.12,right=.97,top=.90,bottom=.15)
part=M['parts'][0];before=old[part['replaces'][0]]
for p,color,label,style in [(before,'#747b84','R25 original','--'),(part,'#147b94','R26 shorter cover','-')]:
    mesh=trimesh.load(ROOT/p['mesh'],force='mesh',process=p.get('mesh_load_process',True))
    points=np.asarray(mesh.vertices)@B
    # External contour is convex; circular holes are drawn separately below.
    hull=ConvexHull(points[:,:2]);v=points[hull.vertices,:2];v=np.vstack([v,v[0]])
    ax.plot(v[:,0],v[:,1],color=color,linestyle=style,lw=2,label=label)
    if p is part:ax.fill(v[:,0],v[:,1],color=color,alpha=.12)
for row in part['interfaces']:
    x,y=row['centre_uv_mm']
    ax.add_patch(plt.Circle((x,y),1.35,fill=False,color='#202830',lw=1.5))
    ax.add_patch(plt.Circle((x,y),4.5,fill=False,color='#202830',lw=.7))
    ax.plot(x,y,'+',color='#202830',ms=9)
    ax.annotate(f"F{row['index']}  edge {row['centre_to_outer_edge_mm']:.2f} mm",(x,y),
                xytext=(x+12,y+3),fontsize=10,arrowprops=dict(arrowstyle='-',color='#59616c'))
row=G['parts'][0]
ax.set_title('OpenDuck R26 · A / thigh-cover profile\nMounting holes and installed plane unchanged',fontsize=13)
ax.set_xlabel('Cover local U (mm)');ax.set_ylabel('Cover local V (mm)')
ax.set_aspect('equal');ax.grid(alpha=.18);ax.legend(loc='upper right',fontsize=10)
fig.text(.04,.025,f"Wall: 2.0 mm | Lower rim: knee −10.0 mm | Vertical exposure +{row['vertical_exposure_gain_mm']:.2f} mm\nDesign candidate. Mesh projection for review; STEP and 3MF govern geometry. Left shown; right mirrored.",fontsize=9)
fig.savefig(OUT/'profile-comparison.png',dpi=180,bbox_inches='tight')
fig.savefig(OUT/'R26-cover-profile.pdf',bbox_inches='tight')
plt.close(fig)
print('PROFILE_EXPORTED',row['vertical_exposure_gain_mm'])
