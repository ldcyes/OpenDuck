"""Apply one mouth-shell and four PEEK film replacements to R26, with no stack-up."""
from pathlib import Path
import argparse
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'work/r26-cover-first/assembly_selection.json'
DEFAULT_MOUTH = ROOT / 'work/r29-mouth-relief/assembly_patch_10deg.json'
LIPS = ROOT / 'work/r29-closure/harness/r26_selection_patch.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mouth-patch', type=Path, default=DEFAULT_MOUTH)
    args = parser.parse_args()
    mouth_path = args.mouth_patch.resolve()
    base, mouth, lips = load(BASE), load(mouth_path), load(LIPS)
    assert len(base['items']) == 1224 and len(base['joints']) == 15
    assert mouth['source_selection_sha256'] == lips['base_selection_sha256'] == sha(BASE)
    assert mouth['source_selection'] == lips['base_selection'] == str(BASE.relative_to(ROOT))
    assert len(lips['remove_names']) == len(lips['insert_items']) == 4
    changes = {mouth['remove_name']: copy.deepcopy(mouth['add_item'])}
    for item in lips['insert_items']:
        assert len(item['replaces']) == 1
        original = item['replaces'][0]
        assert original in lips['remove_names'] and original not in changes
        changes[original] = copy.deepcopy(item)
    assert len(changes) == 5
    original = {item['name']: item for item in base['items']}
    assert set(changes).issubset(original)
    for old_name, item in changes.items():
        old = original[old_name]
        assert item['name'] != old_name
        assert item['R'] == old['R'] and item['t_mm'] == old['t_mm']
        assert item['link_frame'] == old['link_frame']
        assert item.get('replaces') == [old_name]
        for field, digest in [('mesh', 'mesh_sha256'), ('manufacturing_master', 'manufacturing_master_sha256'),
                              ('step', 'step_sha256')]:
            if item.get(field) and item.get(digest):
                assert sha(ROOT / item[field]) == item[digest], (item['name'], field)
        item['is_new'] = True
        item['input_group'] = 'R29_R26_clearance_revision'
        item['physical_approved'] = False
        item['manufacturing_approved'] = False
    installed = [changes.get(item['name'], item) for item in base['items']]
    names = [item['name'] for item in installed]
    assert len(installed) == len(set(names)) == 1224
    assert sum(item['link_frame'] == 'MULTI_LINK_FLEX_HARNESS' for item in installed) == 31
    new_names = [item['name'] for item in changes.values()]
    mouth_delta = float(changes[mouth['remove_name']]['mass_from_CAD_g'] -
                        original[mouth['remove_name']]['mass_from_CAD_g'])
    film_delta = sum(float(changes[n]['mass_from_CAD_g'] - original[n]['mass_from_CAD_g'])
                     for n in lips['remove_names'])
    assert abs(film_delta - lips['mass_delta_g']) < 1e-7
    out = copy.deepcopy(base)
    out.update(status='R29_R26_FIVE_PART_CLEARANCE_CANDIDATE', items=installed,
               parent_selection=str(BASE.relative_to(ROOT)), parent_selection_sha256=sha(BASE),
               new_part_names=base['new_part_names'] + new_names,
               revision_replacements={v['name']: k for k, v in changes.items()},
               revision_mass_delta_g=mouth_delta + film_delta,
               mouth_operational_range_deg=mouth['add_item'].get('mouth_operating_range_deg'),
               physical_approved=False, manufacturing_approved=False,
               revision_sources={str(p.relative_to(ROOT)): sha(p) for p in [BASE, mouth_path, LIPS, Path(__file__)]})
    target = OUT / 'assembly_selection.json'
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=out['status'], item_count=len(installed), replaced=out['revision_replacements'],
                          revision_mass_delta_g=out['revision_mass_delta_g'],
                          output=str(target.relative_to(ROOT))), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
