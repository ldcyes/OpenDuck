"""Publish the R21 update and standalone viewer; preserve the R13.7 CAD base."""
from pathlib import Path
import hashlib, json, shutil, zipfile

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
OUT = ROOT / 'outputs/Microduck_R13_8_减摆步态与PCB复核'
ZIP = ROOT / 'outputs/R13_8_减摆步态更新包.zip'

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        while b := f.read(1024 * 1024): h.update(b)
    return h.hexdigest()

def save(p, d):
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2)+'\n')

def main():
    review = json.loads((WORK / 'final_review_index.json').read_text())
    assert review['review_checks_passed'] and review['all_four_numerical_cases_passed']
    assert review['actual_amplitude_improved_in_both_metrics']
    assert not review['physical_approved'] and not review['manufacturing_approved']
    assert not OUT.exists() and not ZIP.exists(), 'NEVER_OVERWRITE_PUBLISHED_RELEASE'
    sources = dict(review['sources'])
    for rel in ['work/r21-reduced-sway/报告.md', 'work/r21-reduced-sway/publish_update.py']:
        assert rel in sources and sources[rel] == sha(ROOT/rel), ('UNREVIEWED_DELIVERY_CHANGE', rel)
    # The final index cannot contain its own hash; all other release inputs,
    # including this publisher and the finished guide, are already reviewed.
    own_index = 'work/r21-reduced-sway/final_review_index.json'
    assert own_index not in sources
    sources[own_index] = sha(ROOT/own_index)
    for rel, h in sources.items(): assert sha(ROOT / rel) == h, ('SOURCE_CHANGED', rel)
    baseline = json.loads((WORK / 'baseline_snapshot.json').read_text())
    for r in baseline['protected_files']: assert sha(ROOT / r['path']) == r['sha256']
    OUT.mkdir(parents=True)
    copied = []
    def copy(src, dest, expected=None):
        src = Path(src); src = src if src.is_absolute() else ROOT / src
        h = sha(src)
        assert expected is None or h == expected
        p = OUT / dest; p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, p); assert sha(p) == h
        copied.append(dict(path=str(dest), source_path=str(src.relative_to(ROOT)), sha256=h, bytes=p.stat().st_size))
    prefix = 'work/r21-reduced-sway/'
    for rel, h in sorted(sources.items()):
        if rel.startswith(prefix): copy(rel, Path('工程更新') / rel, h)
    base_manifest_path = ROOT / 'outputs/Microduck_R13_7_步态与头部安装修订/文件清单与检查状态.json'
    base_manifest = json.loads(base_manifest_path.read_text())
    base_zip = ROOT/'outputs/R13_7_结构与步态修复.zip'
    with zipfile.ZipFile(base_zip) as old:
        assert old.read('文件清单与检查状态.json') == base_manifest_path.read_bytes()
    base_files = {r['source_path']: r['sha256'] for r in base_manifest['files']
                  if r.get('source_path') and r['path'].startswith('工程快照/')}
    external, additional = {}, {}
    for rel, h in sorted(sources.items()):
        if rel.startswith(prefix): continue
        if base_files.get(rel) == h:
            external[rel] = h
        elif rel == 'outputs/R13_7_结构与步态修复.zip':
            assert h == '0b5ed578dc9d2d43d7bb3aa78a9e9a32e8c9faec918b9f390a2e8d2aa97835e3'
        else:
            # Newly created evidence outside R21 or a dependency absent from
            # the old package must accompany this update at its actual path.
            copy(rel, Path('工程更新') / rel, h)
            additional[rel] = h
    with zipfile.ZipFile(base_zip) as old:
        for rel, h in external.items():
            assert hashlib.sha256(old.read('工程快照/'+rel)).hexdigest() == h, ('BASE_MEMBER_MISMATCH',rel)
    save(OUT / '沿用基线文件索引.json', dict(
        description='These unchanged dependencies are kept in the existing R13.7 source base. The new Blender viewer is self-contained. For script reproduction merge this package 工程更新 with the R13.7 工程快照 at a shared workspace root.',
        base_archive='outputs/R13_7_结构与步态修复.zip',
        base_archive_sha256='0b5ed578dc9d2d43d7bb3aa78a9e9a32e8c9faec918b9f390a2e8d2aa97835e3',
        base_manifest_sha256=sha(base_manifest_path),
        unchanged_sources=external, extra_dependencies_in_this_update=additional))
    copy(WORK / '报告.md', Path('00_减摆结果与查看说明.md'))
    for row in review['public_artifacts']:
        copy(row['path'], Path(row['destination']), row['sha256'])
    readme = ('本包是 R13.7 的步态与检查更新，结构件、PCB板形、安装接口和电机能力参数沿用同一冻结基线。\n\n'
              '模型文件可直接打开，已内含完整零件与实际运动；无需先解压旧包才能查看。\n'
              '复算脚本需要旧 R13.7 包的“工程快照”，再把本包“工程更新”全部内容（含work与outputs目录）合并到同一根目录。'
              '沿用文件逐项列在“沿用基线文件索引.json”，新文件逐项列在“文件清单与检查状态.json”。数值库/Blender运行时需按工程记录安装。\n\n'
              'PCB独立检查包：PCB_功能_DRC与尺寸复核_2026-09-13.zip，内含全部12种原生板图、原理图、BOM和两轮检查。'
              '本次没有生成缩小后的PCB或替换制造文件。\n\n'
              '已完成的是慢速数值仿真检查；不是正常步速、硬件低电量、热、强度或实物行走合格证。'
              '准备站姿过渡另列候选，不随完整四步的数值结果一并放行。\n')
    (OUT / '01_更新包使用说明.txt').write_text(readme)
    for p in [OUT/'沿用基线文件索引.json', OUT/'01_更新包使用说明.txt']:
        copied.append(dict(path=p.name, sha256=sha(p), bytes=p.stat().st_size))
    save(OUT / '文件清单与检查状态.json', dict(
        status='R21_REDUCED_SWAY_NUMERICAL_UPDATE_WITH_UNCHANGED_R13_7_CAD_BASE',
        physical_approved=False, manufacturing_approved=False,
        normal_speed_walking_qualified=False, all_assembly_clearances_qualified=False,
        viewer_self_contained=True, native_CAD_base_required_for_script_reproduction=True,
        actual_amplitude_improved_in_both_metrics=True,
        predeclared_sway_targets_met=review['predeclared_sway_targets_met'],
        files=copied))
    with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(OUT.rglob('*')):
            if p.is_file(): z.write(p, p.relative_to(OUT))
    with zipfile.ZipFile(ZIP) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(copied)+1
        assert set(z.namelist()) == {r['path'] for r in copied} | {'文件清单与检查状态.json'}
        for r in copied: assert hashlib.sha256(z.read(r['path'])).hexdigest() == r['sha256']
    for rel, h in sources.items(): assert sha(ROOT / rel) == h
    for r in baseline['protected_files']: assert sha(ROOT / r['path']) == r['sha256']
    result = dict(passed=True, archive=str(ZIP.relative_to(ROOT)), archive_sha256=sha(ZIP),
                  archive_bytes=ZIP.stat().st_size, member_count=len(copied)+1,
                  source_files_verified=len(sources), protected_R20_files_unchanged=len(baseline['protected_files']),
                  public_folder=str(OUT.relative_to(ROOT)), all_copied_hashes_and_zip_crc_passed=True,
                  base_dependency_index_sha256=sha(OUT/'沿用基线文件索引.json'))
    save(WORK / '交付文件验证.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
