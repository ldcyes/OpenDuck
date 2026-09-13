"""Encode already-rendered source frames with legible, trace-bound subtitle headers.

The only image-space change is an opaque header above the robot. Its per-frame
clocks come from Blender's evaluated clock objects recorded in the render index.
This does not transform, interpolate, recrop or rescale the rendered CAD region.
"""
from pathlib import Path
import argparse, hashlib, json, math, subprocess
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'work/r21-reduced-sway/visual/release_v3'
FONT = Path('/mnt/c/Windows/Fonts/msyh.ttc')
NAMES = {'candidate_actual': 'R21_完整实际四步_约24倍速',
         'same_phase': 'R20_R21_同参考阶段_对照',
         'same_actual_time': 'R20_R21_同实际时间_对照'}
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p):
    return str(Path(p).relative_to(ROOT))
def stamp(centis):
    return f'{centis//360000}:{centis//6000%60:02d}:{centis//100%60:02d}.{centis%100:02d}'
def lines(mode, frame, total):
    t = frame['display_time_s']; c = frame['actual_clocks_s']
    metrics = ['完整实际侧倾：46.74° → 33.37°，减少 28.60%',
               '上头壳固定点横摆：257.8 → 184.0 mm，减少 28.62%',
               '原目标：侧倾减 40% / 头部减 30%，均未达到']
    if mode == 'candidate_actual':
        return ['R21 完整实际四步 · 557 件 CAD',
                f'实际时间 {t:.2f} / {total:.2f} s · 预览约 24 倍速',
                '自由根实际积分；实物行走尚未验收'] + metrics
    if mode == 'same_phase':
        return ['R20（左）与 R21（右）· 固定相机 / 相同比例',
                f'实际时钟：R20 {c["R20"]:.2f} s / R21 {c["R21"]:.2f} s',
                '按参考阶段对齐；未按真实接触事件对齐',
                'R20 时钟约 24 倍速；R21 按阶段变速；实物未验收'] + metrics
    return ['R20（左）与 R21（右）· 相同实际时间 / 相同比例',
            f'实际时钟：R20 {c["R20"]:.2f} s / R21 {c["R21"]:.2f} s',
            '共同时间 0–174.85 s；R21 全程 195.44 s 在单机视频中',
            '自由根实际积分；实物行走尚未验收'] + metrics

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--mode', choices=list(NAMES), required=True)
    ap.add_argument('--still-probe', action='store_true'); args = ap.parse_args()
    mode = args.mode; kind = 'probe' if args.still_probe else 'video'
    ip = OUT / f'{mode}_{kind}_render_index.json'; idx = json.loads(ip.read_text())
    assert idx['purpose'] == 'FINAL_FOUR_STEP'
    assert idx['all_rendered_text_inside_frustum']
    assert sha(ROOT / idx['source_blend_path']) == idx['source_blend_sha256']
    frames = idx['frames']; sources = {rel(ip): sha(ip), rel(Path(__file__)): sha(__file__)}
    assert [x['index'] for x in frames] == list(range(len(frames)))
    for f in frames:
        assert sha(ROOT / f['PNG']) == f['PNG_sha256']; sources[f['PNG']] = f['PNG_sha256']
    first = ROOT / frames[0]['PNG']; width, height = Image.open(first).size
    header_h = 180 if mode == 'candidate_actual' else 208
    font_size = 20 if mode == 'candidate_actual' else 21
    fps = 12; subtitle = OUT / f'{mode}_{kind}_清晰字幕.ass'
    text = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Header,Microsoft YaHei,{font_size},&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,20,20,14,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    captions = []
    for i, f in enumerate(frames):
        start = math.floor(i * 100 / fps); end = math.floor((i+1) * 100 / fps)
        caption = lines(mode, f, frames[-1]['display_time_s'])
        assert start / 100 <= i / fps < end / 100
        # ASS line breaks are literal backslash-N, never real newline text.
        text += f'Dialogue: 0,{stamp(start)},{stamp(end)},Header,,0,0,0,,' + r'\N'.join(caption) + '\n'
        captions.append(dict(frame_index=i,video_PTS_s=i/fps,display_time_s=f['display_time_s'],
                             actual_clocks_s=f['actual_clocks_s'],lines=caption,
                             ASS_start_centiseconds=start,ASS_end_centiseconds=end))
    subtitle.write_text(text, encoding='utf-8')
    font_dir = OUT.parent / 'render_fonts'; font_dir.mkdir(exist_ok=True)
    font_link = font_dir / FONT.name
    if not font_link.exists(): font_link.symlink_to(FONT)
    vf = f"drawbox=x=0:y=0:w=iw:h={header_h}:color=0xF5F7F8:t=fill,subtitles=filename='{subtitle}':fontsdir='{font_dir}'"
    stem = NAMES[mode] + ('_静态' if args.still_probe else '')
    target = OUT / (stem + '.mp4')
    cmd = ['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',str(fps),'-start_number','0',
           '-i',str(first.parent/'%04d.png'),'-frames:v',str(len(frames)),'-vf',vf,
           '-c:v','libx264','-preset','medium','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
    subprocess.run(cmd, check=True)
    raw = subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_entries',
             'stream=codec_name,width,height,avg_frame_rate,nb_frames,nb_read_frames,duration',
             '-of','json',str(target)], text=True)
    probe = json.loads(raw)['streams'][0]
    assert int(probe['nb_read_frames']) == len(frames) == int(probe['nb_frames'])
    assert probe['width'] == width and probe['height'] == height and probe['avg_frame_rate']=='12/1'
    assert abs(float(probe['duration']) - len(frames)/fps) < .001
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(target),'-f','null','-'],check=True)
    previews = []
    for j in sorted(set([0, min(30,len(frames)-1), len(frames)-1])):
        preview = OUT / f'{mode}_{kind}_已解码_{j:04d}.png'
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(target),'-vf',f'select=eq(n\\,{j})','-vsync','0','-frames:v','1',str(preview)],check=True)
        previews.append(dict(path=rel(preview),sha256=sha(preview),frame_index=j,
                             source_png=frames[j]['PNG'],caption=captions[j]))
    report = dict(status='PASS_ALL_VIDEO_FRAMES_DECODED_WITH_SOURCE_CLOCK_CAPTIONS',passed=True,
        mode=mode,video_path=rel(target),video_sha256=sha(target),ffprobe=probe,
        source_blend_sha256=idx['source_blend_sha256'],render_frame_count=len(frames),
        full_source_time_extent_s=[frames[0]['display_time_s'],frames[-1]['display_time_s']],
        all_input_PNG_hashes_verified=True,all_output_frames_decoded_without_error=True,
        subtitle_path=rel(subtitle),subtitle_sha256=sha(subtitle),captions=captions,previews=previews,
        header_only_overlay=dict(pixel_rectangle=[0,0,width,header_h],font='Microsoft YaHei',
            font_path=str(FONT),font_sha256=sha(FONT),font_size_px=font_size,
            CAD_rescale_crop_or_coordinate_change=False,subtitle_clocks_from='render index evaluated clocks'),
        original_blend_unchanged_after_encoding=sha(ROOT/idx['source_blend_path'])==idx['source_blend_sha256'],
        physical_approved=False,sources=sources)
    (OUT / f'{mode}_{kind}_encoding_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('VIDEO_ENCODE_DECODE_PASS',mode,len(frames),sha(target),flush=True)

if __name__ == '__main__': main()
