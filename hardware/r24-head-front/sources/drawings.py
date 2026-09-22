"""Dimensioned engineering PDF from final source sections, not a print-scale template."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'work/rk-mechanics/python-deps'))
import trimesh,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import fontManager
fontManager.addfont('/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf');plt.rcParams.update({'font.family':['DejaVu Sans','Droid Sans Fallback'],'axes.unicode_minus':False,'font.size':10})
m=json.loads((O/'manifest.json').read_text());d=m['design'];mass=json.loads((O/'mass_delta.json').read_text());detail=json.loads((O/'detail_checks.json').read_text())
face=trimesh.load(ROOT/m['parts'][0]['mesh'],force='mesh',process=False)
with PdfPages(O/'R24_前盖尺寸与装配.pdf')as pdf:
 fig,ax=plt.subplots(figsize=(11.7,8.3));fig.subplots_adjust(left=.08,right=.94,top=.85,bottom=.33)
 sec=face.section(plane_normal=[1,0,0],plane_origin=[134,0,0])
 for line in sec.discrete:ax.plot(line[:,1],line[:,2],color='#28465c',lw=.9)
 for k,(y,z) in enumerate(d['face_mount_yz_mm'],1):ax.plot(y,z,'r+');ax.annotate(f'F{k} ({y}, {z})',(y,z),xytext=(4,5),textcoords='offset points',fontsize=8)
 cy,cz=d['eye_axis_yz_mm'];ax.plot(cy,cz,'k+');ax.add_patch(plt.Circle((cy,cz),33,fill=False,color='black',ls='--'));ax.text(cy,cz+35,'眼圈外径 66 / 前开口约28',ha='center')
 ax.set(xlabel='Y / mm',ylabel='Z / mm',aspect='equal',xlim=(-102,102),ylim=(221,323));ax.grid(alpha=.2)
 fig.suptitle('R24 摄像头前盖 · 原型轮廓 / 安装尺寸\n工程设计候选；单位mm；坐标为 trunk HOME，非1:1打印模板',fontsize=16)
 fig.text(.08,.23,'前盖基板 X132.625–135.025，厚2.40；原型X134截面内缩0.35，下沿Z227.50，并按前向拆卸通道局部让位1.0。\nF1–F4：沿X的Ø2.40通孔，M2×10；四个安装耳随新版上头壳整体打印，禁止作为独立贴块粘接。\n镜头轴线 Y−0.19194 / Z269.007；眼圈4孔位于轴心的Y±29、Z±29，Ø2.40，M2×8。\n孔心和非圆轮廓以配套3MF为准；打印主文件保留mm和索引拓扑，勿将参考器件当作打印件。',fontsize=11,linespacing=1.7,va='top')
 pdf.savefig(fig);fig.savefig(O/'front_dimensions.png',dpi=130);plt.close(fig)
 fig,ax=plt.subplots(figsize=(11.7,8.3));fig.subplots_adjust(left=.08,right=.94,top=.85,bottom=.43)
 for p,color in zip(m['parts'][:5],['#c2a36c','#333333','#aaaaaa','#279875','#28526b']):
  if 'top_head' in p['name']:continue
  q=trimesh.load(ROOT/p['mesh'],force='mesh',process=p.get('mesh_load_process',True));sec=q.section(plane_normal=[0,1,0],plane_origin=[0,cy,0])
  if sec:
   for line in sec.discrete:ax.plot(line[:,0],line[:,2],color=color,lw=1)
 ax.set(aspect='equal',xlim=(118,157),ylim=(232,308),xlabel='X / mm（朝前）',ylabel='Z / mm');ax.grid(alpha=.2)
 for i,(x,label) in enumerate([(129,'后座 X129'),(135.1,'PCB X135.1'),(149.025,'眼圈 X149.025'),(151.1,'镜头 X151.1')]):
  ax.axvline(x,color='#456',ls=':',lw=.5);ax.annotate(label,(x,302-10*i),xytext=(162,302-10*i),fontsize=9,va='center',annotation_clip=False,arrowprops=dict(arrowstyle='-',lw=.6))
 fig.suptitle('相机和眼圈剖面 / 安装堆叠',fontsize=16)
 fig.text(.07,.34,'沿用 OS05A10 5MP USB Camera(A)，SKU33123；包络来自厂商尺寸图，非精确供应商CAD。\n板25±0.2 ×25±0.2，孔距21，4×Ø2；镜头Ø14；总深22.1±0.2，镜头至PCB正面16±0.2。\n后座至PCB名义6.1，独立最差公差±0.4；须确认背面四个支承区没有元件/焊点。\n4×M1.6×14：从PCB正面插入，后侧垫片OD4/ID1.8/t0.3、AF3.2/t1.3螺母。\n眼圈：M2×8，后侧垫片OD5/ID2.2/t0.3、AF4/t1.6螺母。禁止靠拧紧螺钉强行拉平PCB。\n原设计无镜头保护玻璃；96°对角视场按50°半角、入口瞳后退4mm包络检查，须用实际画面复核。',fontsize=11,linespacing=1.7,va='top')
 pdf.savefig(fig);plt.close(fig)
 fig=plt.figure(figsize=(11.7,8.3));fig.suptitle('装配顺序与首件验收 / 设计边界',fontsize=16)
 text='1. 打印3件：前盖、黑色眼圈、新版上头壳。优先PA12 SLS；外观喷涂不得堵孔或减小装配缝。\n2. 在裸上头壳装入4个M2螺母，槽沿朝头中心方向侧装；再装回保留的头部组件。\n3. 在拆下的前盖上装相机：检查4个背面支承区、螺钉长度及无压件，再装眼圈。\n4. 连接USB后将总成装入头壳，用4×M2×10固定；拆卸应先断电、松4颗面盖螺钉、断开USB。\n5. 使用尺寸匹配的工具。正面工具轴已检查：M2 Ø3mm / 相机螺钉Ø2.4mm，长35mm。\n6. 首件测孔距/孔径、基板厚度和下沿间隙，消除毛刺；名义下沿间隙详见静态检查；前向拆卸通道按壳体投影局部让位1mm。\n7. 待核：真实相机插头/线缆朝向与弯曲半径、背部支承平整度、入口瞳位置、完整拆装过程。\n\n打印控制建议（须由加工方确认能力）：孔距±0.15，板厚±0.15，轮廓±0.25mm；配合孔后处理。\n建议下沿实物最小间隙≥0.8mm；嘴部全程无接触，并实测其他旧接口，不以渲染图代替干装。\n材料密度PA12 0.93g/cm³/五金7.9g/cm³用于估重；未据此给出夹紧扭矩或载荷批准。\n\n新增几何对指定嘴部0–25°范围连续下界≥4.74mm（名义模型，非软件允许角/实物公差承诺）。\n记录步态29970动态配对已完成区间几何检查；旧壳/嘴约1.4mm及R23未闭合项继续保留。\n完整驱动、训练、质量调整后的行走验证、相机线束动态检查及制造放行不包含在本次前盖批准中。'
 fig.text(.065,.87,text,va='top',fontsize=11,linespacing=1.9);pdf.savefig(fig);plt.close(fig)
print('PDF3pages',O/'R24_前盖尺寸与装配.pdf')
