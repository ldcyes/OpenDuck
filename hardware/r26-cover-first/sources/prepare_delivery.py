"""Freeze checked geometry, bilingual documents and release candidates."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
from urllib.parse import unquote
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
REPO=ROOT/'work/openduck-publish/repository';DEST=REPO/'hardware/r26-cover-first'
PUB=OUT/'publication';ASSETS=PUB/'assets';ASSETS.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
geom=read(OUT/'mechanics/geometry_checks.json');v=read(OUT/'verification.json')
rb=read(OUT/'visual/readback.json');mass=read(OUT/'mass_delta.json');manifest=read(OUT/'mechanics/manifest.json')
assert not v['errors'] and rb['status']=='R26_COMPLETE_MODEL_READBACK_PASS'
assert geom['status']=='PASS_NATIVE_COVER_AND_EXPORT_CHECKS'
verified={}
for report in [geom,v,read(OUT/'visual/build_index.json')]:
    for path,h in report['sources'].items():assert sha(ROOT/path)==h,path;verified[path]=h
assert sha(OUT/'visual/OpenDuck_R26_cover_first.blend')==rb['blend_sha256']
assert sha(OUT/'visual/build_index.json')==rb['build_index_sha256']
assert sha(OUT/'verify_viewer.py')==rb['verifier_sha256']
for name,h in rb['renders'].items():assert sha(OUT/'visual'/name)==h
for p in manifest['parts']:
    for key,hkey in [('step','step_sha256'),('mesh','mesh_sha256'),('stl','sha256_STL'),('manufacturing_file','manufacturing_sha256')]:
        assert sha(ROOT/p[key])==p[hkey];verified[p[key]]=p[hkey]
gain=geom['parts'][0]['vertical_exposure_gain_mm'];edge=min(x['centre_to_outer_edge_mm'] for r in geom['parts'] for x in r['interfaces'])
tag='r26-cover-first-20260924';url='https://github.com/ldcyes/OpenDuck/releases';release=url+'/tag/'+tag
base=url+'/download/'+tag
common_links=f'[Blender]({base}/OpenDuck-R26-cover-first.blend) · [ZIP]({base}/R26-cover-first-design.zip) · [SHA256]({base}/SHA256SUMS.txt)'
zh=f'''# OpenDuck R26：A方案大腿覆盖件

[English](README_EN.md) · {common_links}

按已选A方案，缩短两侧大腿罩下缘，保持实际腿长、15个关节、商品电机、支架及固定五金的位置。**工程候选，未制造或实物验收。**

![大腿覆盖件同尺度对比](images/04-leg-comparison.jpg)

下缘从膝轴下约27.23 mm收至10.00 mm，恢复约**{gain:.2f} mm**垂直露出量。2 mm主壁、两个安装孔、定位沉孔和OD9垫圈承压台保留；固定孔中心到新外缘最小**{edge:.3f} mm**。新零件是原覆盖件的实体子集，四处工具外伸通道已检查。此处不将孔边距和主壁数值称为已通过实物受载验证。

## 下载与装配

- [两件打印主文件3MF](print)、[原生STEP](step)、[STL毫米](stl)、[轮廓尺寸PDF](documents/R26-cover-profile.pdf)。3MF是打印主文件；STEP用于原生实体核对。STL没有内置单位，导入必须选毫米，禁止自动缩放。
- 完整Blender可独立打开：场景01完整R26，02/03为同尺度新旧比较，04/05保留R25头部细节，06保留原R25参考。完整装配仍有{rb['part_count']}项几何和{rb['service_count']}项隐藏服务参考，不能等同制造BOM零件数。Outliner可逐件选择、隐藏PCB、电机和结构。
- 装配仅替换原`R18P_L/R_thigh_photo_triangle`两件。既有支架不拆改；在无载台架、断电状态下，先卸外侧两颗M2.5×8螺钉与OD7垫圈，再沿各侧向外法线脱离定位凸台。新罩对准原定位点，依原顺序放回垫圈和螺钉。实际紧固扭矩、打印孔径/收缩与夹持力仍须首件确认；不在本次新增未经来源验证的紧固扭矩。
- ZIP是工程增量：叠加R23/R24/R25完整工程到相同根目录；执行入口位于`work/r26-cover-first/`。单独Blender和本目录的STEP/3MF不依赖旧工程才能打开。

## 已完成的检查

- 新旧原生实体、STEP在独立进程读取后的差分，以及独立网格核对均有记录。共面构造首次暴露出跨进程布尔异常，现已通过仅修改裁切工具消除；重新读取原始STEP后验证，未通过放宽体积阈值绕过。
- 两个新件原生实体有效、单实体；导出网格闭合、定向一致。完整固定支承R7区域、OD9承压台及沉孔区域均无丢失材料。打印格式回读与体积/包络误差有逐项记录。
- 对每个新罩筛查全部其它{v['static_all_selected_items_tested_per_cover']}项所选几何，精查{v['static_near_pairs']}个邻近配对。名义安装面接触按具体配对记录。工具通道是最终装盖阶段直径3 mm、外伸35 mm的杆部空间；不包含真实手柄、握持或批头配合的实物认证。
- 两盖原生实体子集、其所属连杆变换不变，其它部件不变，因此在相同关节姿态下不会新增刚体相交。这是连续姿态的**碰撞增量证明**，不是整机旧冲突已消除，也不代表载荷变形、制造公差、实际线束运动或真实步态通过。
- {v['retained_part_records_identical']}项保留装配记录及{v['joint_records_identical']}个关节记录未变。完整Blender另经新进程回读，核对真实来源、坐标与替换关系。

## 质量、侧向内收与边界

两盖合计减重约**{-mass['delta_mass_g']:.3f} g**；整机工程估计质量**{mass['mass_kg']:.6f} kg**。HOME重心变化约({mass['delta_COM_HOME_mm'][0]:+.4f}, {mass['delta_COM_HOME_mm'][1]:+.4f}, {mass['delta_COM_HOME_mm'][2]:+.4f}) mm。原质量账扣除两盖一次，新盖计入一次。这是材料密度估计，不是称重结果；不据此宣称动态平衡改善。

本次没有实施4 mm侧向内收：原定位凸台只进入0.8 mm，直接内移会改变支承面及螺钉堆叠，需要另做桥架结构。保持原安装面完成下缘优化，不增加连杆力臂或整体高度。模型HOME高约{rb['HOME_height_mm']:.3f} mm；不同站姿高度随关节角变化。

头部左侧开孔永久闭合B方案仍待独立实施，本R26仍保留R25头壳，不能据新腿图认为头孔已封。R25旧下壳与嘴部约8.75°起的冲突、线束离散姿态/公差限制、低电量持续扭矩、热、续航与实物行走未验收项继续保留。**不发布新电机采购定型、训练权重或装机运动许可。**

## 证据

[原生几何与打印回读](verification/geometry_checks.json) · [整机与工具/碰撞增量](verification/verification.json) · [质量重心](verification/mass_delta.json) · [Blender回读](verification/Blender-readback.json) · [制造及验证源程序](sources)

![新轮廓与固定孔](images/profile-comparison.png)
'''
en=f'''# OpenDuck R26: cover-first option A

[简体中文](README.md) · {common_links}

Two shorter thigh covers improve the knee/lower-leg outline while retaining leg lengths, all 15 joint definitions, actuators, mounting brackets and fasteners. **Engineering candidate; no prototype or physical acceptance.**

![Same-scale thigh-cover comparison](images/04-leg-comparison.jpg)

The lower rim changes from about 27.23 mm below the knee axis to 10.00 mm, exposing approximately **{gain:.2f} mm** more vertical space. The 2 mm main wall, both mounting holes, locating pockets and OD9 washer pads are retained. Minimum hole-centre-to-outer-edge distance is **{edge:.3f} mm**. These dimensions do not replace physical load qualification.

## Files and assembly

- [3MF printing masters](print), [native STEP](step), [millimetre STL](stl), [profile drawing](documents/R26-cover-profile.pdf). Import STL in millimetres without automatic scaling. The indexed 3MF is the printing master.
- The complete Blender file opens independently. Scene 01 contains R26; 02/03 show same-scale comparisons; 04/05 retain R25 head details; 06 is the original R25 reference. It contains {rb['part_count']} assembly geometry entries and {rb['service_count']} hidden service references, not a manufacturing BOM count. Individual parts can be selected/hidden in Outliner.
- Replace only `R18P_L/R_thigh_photo_triangle`. With the robot supported and powered off, remove the two M2.5×8 screws and OD7 washers on each cover, disengage the cover outward from its locating spigots, and install the new cover on the unchanged bracket. Refit original washers/screws. Fastener torque, printed fit and clamp load remain first-article acceptance items.
- The ZIP is an incremental engineering package layered onto the original R23/R24/R25 workspace. Programs live under `work/r26-cover-first/`. The standalone Blender, STEP and 3MF files can be opened without that workspace.

## Verification and limitations

Native STEP checks, independent-process reimport and independent mesh checks are recorded. An initial cross-process coplanar-Boolean failure was corrected in the clipping-tool construction; the final checks do not relax the volume threshold to hide it. The new solids are valid and connected; exported meshes are closed and consistently oriented. Complete R7 mounting support regions, OD9 pads and locating-pocket surroundings lose no material.

Each new cover was screened against all other {v['static_all_selected_items_tested_per_cover']} selected geometry entries; {v['static_near_pairs']} near pairs received detailed checks. Named seating contacts are recorded individually. Four fastener access checks cover a 3 mm diameter shaft extending 35 mm outward at final cover installation; real handles, hand access and bit fit are not physically certified.

The new native solids are subsets of the old covers, with unchanged link transforms and unchanged surrounding parts. Therefore they cannot introduce a new rigid intersection at the same joint pose. This is a **continuous-pose collision-delta argument**, not proof that existing robot conflicts, load deflection, manufacturing tolerances or flexible-wire motion are resolved. All {v['retained_part_records_identical']} retained records and {v['joint_records_identical']} joint records remain identical. A fresh Blender process checks component sources, transforms and replacement meshes.

Estimated mass falls by **{-mass['delta_mass_g']:.3f} g** to **{mass['mass_kg']:.6f} kg**. HOME COM changes by ({mass['delta_COM_HOME_mm'][0]:+.4f}, {mass['delta_COM_HOME_mm'][1]:+.4f}, {mass['delta_COM_HOME_mm'][2]:+.4f}) mm. This uses material density, not measured weight, and does not qualify balance or dynamics. HOME height remains approximately {rb['HOME_height_mm']:.3f} mm.

No 4 mm lateral inset is applied: original spigot engagement is only 0.8 mm, and moving the cover would require a bridge and screw-stack redesign. The original installed plane is retained.

The separately authorized permanent head-opening closure remains pending; this R26 retains the R25 head shell. The prior mouth/lower-shell conflict beginning around 8.75°, harness tolerance/pose limits, low-battery sustained torque, thermal/endurance and physical walking acceptance remain open. No new actuator purchase qualification, trained policy or hardware-motion approval is issued.

[Native geometry/export checks](verification/geometry_checks.json) · [Assembly and access/collision-delta checks](verification/verification.json) · [Mass/COM](verification/mass_delta.json) · [Blender readback](verification/Blender-readback.json) · [Source programs](sources)

![Profile and preserved fixings](images/profile-comparison.png)
'''
# Write identical overview documents beside work files and repository artifacts.
DEST.mkdir(parents=True,exist_ok=True)
for name,text in [('README.md',zh),('README_EN.md',en)]:
    (DEST/name).write_text(text)
    local=text.replace('(README_EN.md)', '(README_EN.md)').replace('(images/04-leg-comparison.jpg)', '(visual/04-leg-comparison.png)').replace('(images/profile-comparison.png)', '(profile-comparison.png)').replace('(documents/R26-cover-profile.pdf)', '(R26-cover-profile.pdf)')
    for folder in ['print','step','stl','verification','sources']:
        local=local.replace(']('+folder, ']('+ 'https://github.com/ldcyes/OpenDuck/tree/main/hardware/r26-cover-first/'+folder)
    (OUT/name).write_text(local)
mapping=[]
def cp(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
    assert sha(src)==sha(dst)
    mapping.append(dict(source=str(src.relative_to(ROOT)),target=str(dst.relative_to(REPO)),sha256=sha(src)))
for p in manifest['parts']:
    for key,folder in [('step','step'),('stl','stl'),('manufacturing_file','print')]:cp(ROOT/p[key],DEST/folder/Path(p[key]).name)
for name in ['01-front','02-side','03-full-comparison','04-leg-comparison']:
    target=DEST/'images'/f'{name}.jpg';target.parent.mkdir(exist_ok=True)
    Image.open(OUT/'visual'/f'{name}.png').convert('RGB').save(target,quality=90)
cp(OUT/'profile-comparison.png',DEST/'images/profile-comparison.png')
cp(OUT/'R26-cover-profile.pdf',DEST/'documents/R26-cover-profile.pdf')
for src,name in [(OUT/'mechanics/geometry_checks.json','geometry_checks.json'),(OUT/'mechanics/manifest.json','manufacturing-manifest.json'),
    (OUT/'verification.json','verification.json'),(OUT/'mass_delta.json','mass_delta.json'),(OUT/'visual/readback.json','Blender-readback.json')]:cp(src,DEST/'verification'/name)
for p in OUT.glob('*.py'):cp(p,DEST/'sources'/p.name)
(DEST/'source-mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')

zhroot=REPO/'README.md';text=zhroot.read_text()
text=re.sub(r'\*\*本次更新：.*?\*\*',f'**本次更新：[R26 A方案大腿覆盖件](hardware/r26-cover-first/README.md) · [完整Blender与工程下载]({release})。**',text,count=1)
hero='![OpenDuck R26 正交正视](hardware/r26-cover-first/images/01-front.jpg)\n\n'
if hero not in text:text=text.replace('![头部摄像头前盖特写]',hero+'![头部摄像头前盖特写]',1)
text=text.replace('沿用R25：31根头部导线改为底部接入','31根头部导线改为底部接入').replace('31根头部导线改为底部接入','沿用R25：31根头部导线改为底部接入',1)
text=text.replace('已测量现有装配并比较三种方案；尚未替换制造模型、电机BOM或批准步态。','前期比较三种方案，现已采用A修改覆盖件；电机和腿长不变，实物步态未验收。')
zhroot.write_text(text)
enroot=REPO/'README_EN.md';text=enroot.read_text()
text=re.sub(r'\*\*Latest assembly:.*?\*\*',f'**Latest assembly: [R26 cover-first option A](hardware/r26-cover-first/README_EN.md) · [Complete Blender and engineering downloads]({release}).**',text,count=1)
hero='![OpenDuck R26 orthographic front view](hardware/r26-cover-first/images/01-front.jpg)\n\n'
if hero not in text:text=text.replace('![Head camera front cover]',hero+'![Head camera front cover]',1)
text=text.replace('This review measures the existing assembly and compares alternatives; it does not introduce a qualified longer-leg assembly or a new actuator BOM.','The earlier review compares alternatives. R26 now implements option A with shorter covers; leg lengths and actuator selection remain unchanged.')
enroot.write_text(text)
for name,line in [('README.md','后续：用户已采用A，实施与验证见[R26覆盖件](../../hardware/r26-cover-first/README.md)。下文保留为改动前的方案分析。'),('README_EN.md','Follow-up: option A is now implemented in [R26](../../hardware/r26-cover-first/README_EN.md). The study below remains the pre-change comparison.')]:
    path=REPO/'docs/proportion-study-20260924'/name;s=path.read_text()
    if line not in s:s=s.replace('\n','\n\n'+line+'\n',1);path.write_text(s)

errors=[];count=0
for path in [zhroot,enroot,DEST/'README.md',DEST/'README_EN.md',REPO/'docs/proportion-study-20260924/README.md',REPO/'docs/proportion-study-20260924/README_EN.md']:
    for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',path.read_text()):
        if '://' in target or target.startswith('#'):continue
        count+=1
        if not (path.parent/unquote(target.split('#')[0])).exists():errors.append(str(path)+': '+target)
assert not errors,errors
assert '同阶段装配对照.png' not in zhroot.read_text()
assert '01-complete-assembly.png' not in zhroot.read_text()

files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix not in ['.blend','.blend1','.pyc','.log'] and not any(t in p.parts for t in ['publication','__pycache__'])]
archive=ASSETS/'R26-cover-first-design.zip';entries=[]
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(files):
        name=str(p.relative_to(ROOT));raw=p.read_bytes();z.writestr(name,raw)
        entries.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    z.writestr('PACKAGE_INDEX.json',json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
    z.writestr('START_HERE.md','R26 A cover-first incremental design. Layer over full R23/R24/R25 workspace. Select only mechanics/manifest.json parts and assembly_selection.json. Diagnostics/pre_fix contains a rejected geometry regression, NEVER print/install it. Standalone complete Blender is a separate asset. Repository-style README links resolve at hardware/r26-cover-first in GitHub; local sources live under work/r26-cover-first. Not manufacturing or motion approved.\n')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for r in entries:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256']
cp_blend=ASSETS/'OpenDuck-R26-cover-first.blend';shutil.copy2(OUT/'visual/OpenDuck_R26_cover_first.blend',cp_blend)
assets=[dict(name=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in [archive,cp_blend]]
(ASSETS/'SHA256SUMS.txt').write_text(''.join(a['sha256']+'  '+a['name']+'\n' for a in assets))
summary=dict(status='LOCAL_R26_DELIVERY_VERIFIED',tag=tag,assets=assets,archive_entries=len(entries),local_links_checked=count,
    verification_files=verified,errors=[],physical_approved=False,manufacturing_approved=False)
(PUB/'delivery_verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(PUB/'release_notes.md').write_text(f'Implements approved option A: two shorter thigh covers, with {gain:.2f} mm less extension below the knee. Leg lengths, joint axes and actuator sizes remain unchanged.\n\nIncludes complete standalone Blender, STEP/STL/3MF files, native/mesh checks, independent Blender readback and bilingual engineering notes. Estimated mass delta {mass["delta_mass_g"]:.3f} g.\n\nEngineering prerelease only. Existing head-opening closure, mouth conflict, low-battery sustained torque and physical walking qualification remain pending. See [engineering notes](https://github.com/ldcyes/OpenDuck/tree/main/hardware/r26-cover-first).\n')
print(json.dumps({k:summary[k] for k in ['status','tag','assets','archive_entries','local_links_checked']},indent=2))
