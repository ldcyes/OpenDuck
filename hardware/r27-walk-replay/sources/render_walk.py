"""Render fixed-camera overview frames from the checked R26 replay."""
from pathlib import Path
import json,sys,math,hashlib
import bpy
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
idx=json.loads((HERE/'build_index.json').read_text());rb=json.loads((HERE/'readback.json').read_text())
blend=HERE/'OpenDuck_R27_R26_四步运动回放.blend'
assert hashlib.sha256(blend.read_bytes()).hexdigest()==rb['blend_sha256']
bpy.ops.wm.open_mainfile(filepath=str(blend));scene=bpy.data.scenes[idx['scene']];bpy.context.window.scene=scene;bpy.context.window.view_layer=scene.view_layers[0]
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=6;scene.cycles.use_denoising=True;scene.cycles.max_bounces=3;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
out=HERE/'frames';out.mkdir(exist_ok=True)
mode=sys.argv[sys.argv.index('--')+1]if '--' in sys.argv else'preview'
if mode=='preview':points=[0,idx['duration_s']/2,idx['duration_s']]
else:
 scene.render.resolution_x=576;scene.render.resolution_y=720
 points=[idx['duration_s']*i/95 for i in range(96)]
for i,t in enumerate(points):
 f=1+40*t;scene.frame_set(math.floor(f),subframe=f%1)
 scene.render.filepath=str(out/(f'preview_{i:03}.png'if mode=='preview'else f'walk_{i:04}.png'))
 bpy.ops.render.render(write_still=True,scene=scene.name)
 print('R27_FRAME',mode,i,len(points),t,flush=True)
