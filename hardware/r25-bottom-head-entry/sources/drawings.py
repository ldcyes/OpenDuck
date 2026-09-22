from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2];O=Path(__file__).parent
sys.path.insert(0,str(ROOT/'work/rk-mechanics/python-deps'))
import trimesh,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import fontManager
fontManager.addfont('/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf');plt.rcParams.update({'font.family':['DejaVu Sans','Droid Sans Fallback'],'axes.unicode_minus':False,'font.size':10})
M=json.loads((O/'mechanics/manifest.json').read_text());parts=M['parts'];by={p['name']:p for p in parts}
with PdfPages(O/'R25_头部底部入口与装配.pdf')as pdf:
 fig,ax=plt.subplots(figsize=(11.7,8.3));fig.subplots_adjust(left=.08,right=.95,top=.83,bottom=.31)
 for n,col in [('R25_lower_head_shell_bottom_entry','#657b83'),('R25_neck_upper_PEEK_comb_housing','#b58b32'),('R25_neck_upper_6061_bottom_bridge','#316a92')]:
  p=by[n];m=trimesh.load(ROOT/p['mesh'],force='mesh',process=p.get('mesh_load_process',True))
  for z in [201,206,216,222,230]:
   sec=m.section(plane_normal=[0,0,1],plane_origin=[0,0,z])
   if sec:
    for ln in sec.discrete:ax.plot(ln[:,0],ln[:,1],color=col,lw=.6)
 ax.plot(32,-68,'r+');ax.annotate('入口基准 (32, −68, 198)',(32,-68),xytext=(-30,-91),arrowprops=dict(arrowstyle='->'),fontsize=10)
 for x in [46.5,63.5]:ax.plot(x,-46,'ko');ax.annotate(f'({x}, −46)',(x,-46),xytext=(0,8 if x==63.5 else-15),textcoords='offset points',fontsize=8)
 ax.set(xlim=(-80,100),ylim=(-101,12),aspect='equal',xlabel='X / mm（朝前）',ylabel='Y / mm');ax.grid(alpha=.2)
 fig.suptitle('OpenDuck R25 · 头部底部入口\nHOME 装配毫米坐标，截面叠图；非1:1模板，制造候选未放行',fontsize=16)
 fig.text(.08,.24,'下壳主开孔：X2.5～51.5，Y−77～−56，切穿范围Z195～215；名义49×21。\n支架局部让位：X45.5～54.5，Y−73～−64.5，Z210～220；完整轮廓以3MF为准。\n上导向座宽轴+X，窄轴−Y，固定侧+Z；自由出口Z198，导向内部直线12mm。\n沿用头内鞍座2×M2孔心：X46.5/63.5，Y−46，孔距17；下夹座及其五金不移动。\n上头壳恢复原型侧面轮廓并保留R24前盖安装耳；侧面原电机工作孔保留，不作为线束入口。',va='top',fontsize=11,linespacing=1.7)
 pdf.savefig(fig);fig.savefig(O/'bottom_dimensions.png',dpi=140);plt.close(fig)
 fig=plt.figure(figsize=(11.7,8.3));fig.suptitle('R25 · 装配顺序与实物验收项目',fontsize=16)
 text='1. 采购原规格导线、M2五金与PEEK/VMQ材料；不得按早期HOME最短诊断线路剪线。\n2. 在台架上将未弯成型、未端接的31根导线穿入导向/软夹座，固定12mm夹持段。\n3. 导线仍沿+Z伸直时装紧两颗M2×6压盖螺钉，然后按源线路成型并完成端接。\n4. 在尚未连接颈部、尚未装上下头壳的头部子总成上，用M2×18固定导向座和新桥架。\n5. 用原M2鞍座五金夹紧承载梁；保留正向限位环及原M3头壳紧固件。\n6. 安装新版下头壳，将入口和桥架穿过对应开口；装新版上壳及原R24摄像头前盖。\n7. 对每根导线核对端号，测线长、最小弯曲半径及所有运动姿态下的自由余量。\n\n建议首件尺寸控制：壳体轮廓±0.25mm、孔位±0.15mm；PEEK孔/槽按旧材料合同。\n桥架为6061-T651机加工候选，标称连臂截面4×4mm、安装侧板2mm；材料及局部强度待承接方确认。\n引线夹持沿用单线5N、总束同时载荷不超过5N的验证方案，实测滑移≤0.2mm且绝缘无损。\n几何名义间距不等于制造公差裕量，特别是密集线束；须进行温升、振动、反复转头与磨损检查。\n\n新导向座/桥架/固定尾线通过指定范围的几何检查，不代表整机制造、扭矩或行走验收。\n嘴部扩展检查发现旧下头壳与嘴承载件约8.75°开始相交，R25没有批准25°整机嘴部行程。\n完整检查范围、自由线运动离散采样及未通过工况，以配套README和原始JSON为准。'
 fig.text(.07,.89,text,va='top',fontsize=11,linespacing=1.8);pdf.savefig(fig);plt.close(fig)
print('PDF2pages')
