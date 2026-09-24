"""Freeze R27 replay sources, reports, documentation and release attachments."""
from pathlib import Path
import json,hashlib,shutil,zipfile,re,subprocess
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent;VIS=OUT/'visual'
REPO=ROOT/'work/openduck-publish/repository';DEST=REPO/'hardware/r27-walk-replay';PUB=OUT/'publication';AS=PUB/'assets';AS.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())
a=load(OUT/'analysis.json');b=load(VIS/'readback.json');idx=load(VIS/'build_index.json')
assert a['status']=='R26_FOUR_STEP_KINEMATIC_REPLAY_AND_INHERITED_RIGID_COLLISION_DELTA_CHECKED'
assert b['status']=='R27_R26_ALL_9774_MOTION_KEYS_AND_FULL_1224_PART_FK_READBACK_PASS'
assert sha(VIS/'OpenDuck_R27_R26_四步运动回放.blend')==b['blend_sha256']
for rel,h in idx['source_hashes'].items():assert sha(ROOT/rel)==h
srcs=[OUT/'analyze_walk.py',OUT/'package.py',VIS/'blender_actual_helpers_r27.py',VIS/'build_walk.py',VIS/'render_walk.py',VIS/'verify_walk.py']
for p in srcs:assert p.is_file()
assets=[('OpenDuck-R27-R26-four-step-replay.blend',VIS/'OpenDuck_R27_R26_四步运动回放.blend'),('OpenDuck-R27-R26-four-step-preview.mp4',VIS/'OpenDuck_R27_R26_four_step_preview.mp4')]
for name,p in assets:assert p.is_file() and p.stat().st_size>100000
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(assets[1][1])]))
vs=next(x for x in probe['streams']if x['codec_type']=='video')
assert vs['nb_frames']=='96' and abs(float(probe['format']['duration'])-8)<.001
mapping=[]
def cp(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);assert sha(src)==sha(dst)
 mapping.append(dict(source=str(src.relative_to(ROOT)),target=str(dst.relative_to(REPO)),sha256=sha(src)))
cp(OUT/'analysis.json',DEST/'verification/analysis.json');cp(VIS/'readback.json',DEST/'verification/readback.json')
cp(VIS/'build_index.json',DEST/'verification/build_index.json')
for src in srcs:cp(src,DEST/'sources'/src.name)
poster=DEST/'images/mid-walk.jpg';poster.parent.mkdir(exist_ok=True)
Image.open(VIS/'frames/preview_001.png').convert('RGB').save(poster,quality=89)
(DEST/'source-mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
# Every new repository-local Markdown target must exist.
for p in [DEST/'README.md',DEST/'README_EN.md',REPO/'README.md',REPO/'README_EN.md']:
 for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text()):
  if '://' in target or target.startswith('#'):continue
  assert (p.parent/target.split('#')[0]).exists(),(p,target)
zip_path=AS/'R27-walk-replay-evidence.zip'
files=[OUT/'analysis.json',VIS/'readback.json',VIS/'build_index.json',ROOT/'work/r21-reduced-sway/dynamics/full_v3/nominal/dynamic_trace_for_CAD.json',ROOT/'work/r21-reduced-sway/dynamics/full_v3/nominal/interval_joint_bounds.json',ROOT/'work/r25-bottom-head-entry/motion/rigid_final/result.json',ROOT/'work/r25-bottom-head-entry/motion/rigid_final/pair_index.json',ROOT/'work/r25-bottom-head-entry/motion_contact_review.json',ROOT/'work/r26-cover-first/mechanics/geometry_checks.json',ROOT/'work/r26-cover-first/verification.json',*srcs,DEST/'README.md',DEST/'README_EN.md']
entry=[]
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in files:
  name=str(p.relative_to(ROOT));z.write(p,name);entry.append(dict(path=name,size=p.stat().st_size,sha256=sha(p)))
 z.writestr('PACKAGE_INDEX.json',json.dumps(entry,ensure_ascii=False,indent=2)+'\n')
 z.writestr('START_HERE.md','R27 replays R21 saved free-base motion on complete R26 geometry. Open standalone Blender and scene 07 for individual parts and all keys. Video is ~24.4x preview. R26 dynamics and flexible-wire motion are unqualified. Full source workspace is required to re-run scripts. No physical-motion approval.\n')
with zipfile.ZipFile(zip_path) as z:
 assert z.testzip() is None
 for e in entry:assert hashlib.sha256(z.read(e['path'])).hexdigest()==e['sha256']
for name,p in assets:shutil.copy2(p,AS/name)
allassets=[AS/assets[0][0],AS/assets[1][0],zip_path]
(AS/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.name}\n'for p in allassets))
summary=dict(status='R27_LOCAL_DELIVERY_VERIFIED',assets=[dict(name=p.name,size=p.stat().st_size,sha256=sha(p))for p in [*allassets,AS/'SHA256SUMS.txt']],zip_entries=len(entry),video_frames=96,video_duration_s=float(probe['format']['duration']),source_mapping_count=len(mapping),physical_approved=False,manufacturing_approved=False)
(PUB/'delivery.json').write_text(json.dumps(summary,indent=2)+'\n')
(PUB/'release_notes.md').write_text('Replays all 9,774 saved R21 integrated free-base poses over 195.44 seconds on the complete 1,224-part R26 assembly. Includes standalone animated Blender, a four-step ~24.4× preview video and source-bound engineering evidence. Both shorter R26 thigh covers are native subsets of their old parts: the prior interval ledger covered 57 dynamic pairs per cover with no unresolved dynamic penetration. R26 mass is 247.97 g above the R21 dynamics model, so this is a geometric motion replay rather than a new dynamics qualification. Flexible neck wiring and physical walking remain unqualified. See https://github.com/ldcyes/OpenDuck/tree/main/hardware/r27-walk-replay .\n')
print(json.dumps(summary,indent=2))
