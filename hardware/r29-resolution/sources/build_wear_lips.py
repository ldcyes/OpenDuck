"""R29 candidate: replace the four power-wire PEEK films with 1.5 mm exit lips.

The 6061 metal and its load path are bit-for-bit unchanged. This extends the
existing film only toward the free conductor, across the sharp metal exit.
"""

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
GEOM = HERE / "geometry"
GEOM.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "work/r13-electronics/mechanics"))
import common as c  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def box(lo, hi):
    return c.box((np.asarray(lo) + np.asarray(hi)) / 2, np.asarray(hi) - np.asarray(lo))


assembly_path = ROOT / "work/r26-cover-first/assembly_selection.json"
contract_path = ROOT / "work/r25-bottom-head-entry/flex/endpoint_contract.json"
assembly = json.loads(assembly_path.read_text())
contract = json.loads(contract_path.read_text())
selected = {p["name"]: p for p in assembly["items"]}
parts = []
for side in ("upper", "lower"):
    anchor = contract["anchors"][side]
    ports = [p for p in anchor["ports"] if p["id"] in ("P5", "P6")]
    assert len(ports) == 2
    E = np.mean([p["free_exit_mm"] for p in ports], axis=0)
    U = np.array([1., 0., 0.])
    T = -np.asarray(anchor["free_tangent"], dtype=float)
    V = np.cross(U, T)
    R = np.array([U, T, V]).T
    assert abs(np.linalg.det(R) - 1) < 1e-8
    for port in ports:
        old_name = ("R25" if side == "upper" else "R23") + f"_neck_{side}_{port['id']}_PEEK_film"
        old = selected[old_name]
        x = float(port["free_exit_mm"][0] - E[0])
        # Original film is an open semicircular R1.00..R1.25 strip on
        # y(local)=0..12. Increase only the free-exit end to -1.5.
        outer = c.cylinder([x, 5.25, 0], 1.25, 13.5, [0, 1, 0])
        inner = c.cylinder([x, 5.25, 0], 1., 13.7, [0, 1, 0])
        strip = c.common(c.cut(outer, inner), box([x - 1.3, -1.6, -1.3],
                                                  [x + 1.3, 12.1, 0]))
        shape = c.tf(strip, R, E)
        old_shape = c.tf(c.read(ROOT / old["step"]), old["R"], old["t_mm"])
        removed_from_old = abs(c.volume(c.cut(old_shape, shape)))
        assert removed_from_old < 1e-6, (old_name, removed_from_old)
        added = abs(c.volume(c.cut(shape, old_shape)))
        assert added > 0.5, (old_name, added)
        name = f"R29_neck_{side}_{port['id']}_PEEK_exit_lip"
        result = c.export(name, shape, GEOM, "unfilled PEEK formed wear film", 1.3,
                          "jaw_soft" if side == "upper" else "trunk_base",
                          "R1.00..R1.25 split semicircle; original 12 mm bearing retained; 1.5 mm free-exit lip shields the 6061 edge. No adhesive or new metal subtraction. Deburr film free edge with a 0.05-0.10 mm edge break; verify on first article.")
        result.update(step=str((GEOM / result["STEP"]).relative_to(ROOT)),
                      mesh=str((GEOM / result["STL"]).relative_to(ROOT)),
                      R=np.eye(3).tolist(), t_mm=[0, 0, 0],
                      link_frame="jaw_soft" if side == "upper" else "trunk_base",
                      kind="PEEK_exit_wear_lip_candidate", reference_only=False,
                      replaces=[old_name], original_12mm_film_removed_mm3=removed_from_old,
                      added_lip_volume_mm3=added, free_exit_extension_mm=1.5,
                      original_bridge_6061_unchanged=True,
                      manufacturing_approved=False, physical_approved=False)
        readback = c.properties(c.read(ROOT / result["step"]))
        assert readback["valid_BRep"] and readback["solid_count"] == 1
        result["STEP_readback_verified"] = True
        parts.append(result)
manifest = dict(status="R29_PEEK_EXIT_LIP_CANDIDATE_PENDING_FULL_ASSEMBLY_AND_PHYSICAL_REVIEW",
                parts=parts, replaces=[p["replaces"][0] for p in parts],
                same_6061_bridge_STEP_sha256={n: selected[n]["step_sha256"] for n in (
                    "R25_neck_upper_6061_bottom_bridge",
                    "R23_neck_lower_6061_with_power_pair_P5_entry_slot_reinforced")},
                sources={str(p.relative_to(ROOT)): sha(p) for p in (assembly_path, contract_path)},
                limits=["PEEK film axial capture remains by the original lacing/retention process; do not assume adhesive strength.",
                        "The overhanging lip and wire/guide motion require first-article abrasion testing.",
                        "The film is a replacement part, never stacked with the original film."],
                manufacturing_approved=False, physical_approved=False)
(HERE / "wear_lip_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print([(p["name"], p["added_lip_volume_mm3"]) for p in parts])
