"""Bind R26's 31 free neck wires to their actual route evidence.

This is an engineering envelope audit, not an elastic-cable simulation.  The
R21 gait interval record encloses its numerical integration states; it does
not enclose an as-built robot or arbitrary unmodelled wire sag.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "work/r18-leg-hip-covers/review"))
from motion_core import link_chain, transforms  # noqa: E402

HERE = Path(__file__).resolve().parent
R25 = ROOT / "work/r25-bottom-head-entry"
R26 = ROOT / "work/r26-cover-first"
FAMILY = R25 / "flex/compact_bundle_family"
INTERVALS = ROOT / "work/r21-reduced-sway/dynamics/full_v3/nominal/interval_joint_bounds.json"
CASES = (1, 3, 4, 6, 8, 13, 16, 17, 18)
TARGET_HARD_PART_GAP_MM = 2.2


def read(path: Path):
    return json.loads(path.read_text())


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(item):
    return (item["name"], item.get("mesh_sha256", item.get("sha256_STL")),
            item.get("step_sha256", item.get("sha256_STEP")), item.get("link_frame", item.get("link")))


def box_corners(bounds):
    lo, hi = np.asarray(bounds, dtype=float)
    return np.asarray([[x, y, z] for x in (lo[0], hi[0])
                       for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])


def wire_route_envelope(rows):
    """A deliberately loose analytic AABB containing every line/circular arc."""
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for row in rows:
        pad = row["outer_diameter_max_mm"] / 2
        for seg in row["segments"]:
            if seg["type"] == "line":
                points = np.asarray([seg["start"], seg["end"]], dtype=float)
            elif seg["type"] == "arc":
                center = np.asarray(seg["center"], dtype=float)
                radius = float(seg["radius_mm"])
                points = np.asarray([center - radius, center + radius])
            else:
                raise ValueError(("UNKNOWN_SEGMENT", seg["type"]))
            lo = np.minimum(lo, points.min(axis=0) - pad)
            hi = np.maximum(hi, points.max(axis=0) + pad)
    return lo, hi


def cover_radius_terms(joints, link, corners):
    chain = link_chain(joints, link)
    pivots = [np.asarray(j["pivot_trunk_mm"], dtype=float) for j in chain]
    radius = float(np.linalg.norm(corners - pivots[-1], axis=1).max())
    terms = []
    for index in range(len(chain) - 1, -1, -1):
        if index < len(chain) - 1:
            radius += float(np.linalg.norm(pivots[index + 1] - pivots[index]))
        terms.append((chain[index]["joint"], radius))
    return terms


def main():
    s25_path, s26_path = R25 / "assembly_selection.json", R26 / "assembly_selection.json"
    old, new, bounds = read(s25_path), read(s26_path), read(INTERVALS)
    sources = {str(p.relative_to(ROOT)): digest(p) for p in (s25_path, s26_path, INTERVALS)}
    assert old["joints"] == new["joints"], "R26_JOINTS_CHANGED"
    old_by = {p["name"]: p for p in old["items"]}
    new_by = {p["name"]: p for p in new["items"]}
    wires = [p for p in new["items"] if p.get("link") == "MULTI_LINK_FLEX_HARNESS"]
    assert len(wires) == 31 and len({p["name"] for p in wires}) == 31
    assert all(p["name"] in old_by and binding(p) == binding(old_by[p["name"]]) for p in wires)
    for p in wires:
        source = ROOT / p["mesh"]
        assert digest(source) == p["mesh_sha256"], (p["name"], "MESH_HASH_MISMATCH")
        source = ROOT / p["step"]
        assert digest(source) == p["step_sha256"], (p["name"], "STEP_HASH_MISMATCH")
    selected = read(R25 / "flex/compact_bundle_home/manifest.json")
    assert {binding(x) for x in selected["parts"]} == {binding(x) for x in wires}
    sources[str((R25 / "flex/compact_bundle_home/manifest.json").relative_to(ROOT))] = digest(R25 / "flex/compact_bundle_home/manifest.json")

    all_rows = []
    checked_body_pairs = 0
    worst_gap = (math.inf, None, None, None)
    case_rows = []
    for index in CASES:
        route_path = FAMILY / f"case_{index:02}.json"
        body_path = FAMILY / f"case_{index:02}_bodies.json"
        route, body = read(route_path), read(body_path)
        for path in (route_path, body_path):
            sources[str(path.relative_to(ROOT))] = digest(path)
        assert len(route["rows"]) == 31 and {r["port"] for r in route["rows"]} == {w["name"].removeprefix("R25_NECK_FREE_") for w in wires}
        assert not route["failures"] and not route["possible_overlap_count"]
        assert not body["intersections"] and not body["errors"]
        checked_body_pairs += body["tested_pairs"]
        all_rows.extend(route["rows"])
        pair = min(route["pairs"], key=lambda p: p["certified_arc_distance_lower_mm"])
        gap = pair["certified_arc_distance_lower_mm"]
        if gap < worst_gap[0]:
            worst_gap = (gap, index, pair["a"], pair["b"])
        case_rows.append({"index": index, "q_HOME_delta_deg": route["q"],
                          "wire_pair_gap_lower_mm": gap,
                          "wire_body_pairs_screened": body["tested_pairs"]})
    wire_min, wire_max = wire_route_envelope(all_rows)

    covers = [p for p in new["items"] if p["name"] in ("R26_L_thigh_short_cover", "R26_R_thigh_short_cover")]
    assert len(covers) == 2
    assert len(bounds["intervals"]) == 9773
    maximum_cover_z = -math.inf
    cover_rows = []
    for cover in covers:
        corners = box_corners(cover["bounds_mm"])
        terms = cover_radius_terms(new["joints"], cover["link"], corners)
        maximum = -math.inf
        maximum_bound = 0.0
        for interval in bounds["intervals"]:
            q0 = interval["q_start_HOME_deg"]
            tf = transforms(new["joints"], q0)[cover["link"]]
            top_at_start = float((corners @ tf[:3, :3].T + tf[:3, 3])[:, 2].max())
            # Triangle inequality over the joint chain.  Every numerical
            # integration q is inside the recorded per-interval joint bounds.
            move = 0.0
            for joint, radius in terms:
                qmin = interval["q_min_HOME_deg"][joint]
                qmax = interval["q_max_HOME_deg"][joint]
                delta = max(abs(qmin - q0[joint]), abs(qmax - q0[joint]))
                move += 2 * radius * math.sin(math.radians(min(180.0, delta)) / 2)
            maximum = max(maximum, top_at_start + move)
            maximum_bound = max(maximum_bound, move)
        maximum_cover_z = max(maximum_cover_z, maximum)
        cover_rows.append({"name": cover["name"], "maximum_z_mm_continuous_numerical_interval_bound": maximum,
                           "maximum_per_interval_motion_bound_mm": maximum_bound})
    vertical_gap = float(wire_min[2] - maximum_cover_z)
    assert vertical_gap > TARGET_HARD_PART_GAP_MM, "NEW_COVER_TO_9_POSE_WIRE_ENVELOPE_GAP_NOT_PROVEN"
    assert checked_body_pairs == 17131
    assert abs(worst_gap[0] - 0.01610514040248456) < 1e-9
    out = {
        "status": "R26_NEW_COVERS_CLEAR_OF_CONDITIONAL_9_POSE_NECK_WIRE_ENVELOPE;_FLEX_MANUFACTURING_NOT_QUALIFIED",
        "R26_flexible_wire_count": len(wires),
        "R26_wire_geometry_identical_to_R25": True,
        "R26_joint_table_identical_to_R25": True,
        "nine_pose_route_case_count": len(case_rows),
        "nine_pose_body_pairs_screened_in_R25": checked_body_pairs,
        "nine_pose_minimum_nominal_wire_pair_gap_lower_mm": worst_gap[0],
        "worst_wire_pair": {"case_index": worst_gap[1], "a": worst_gap[2], "b": worst_gap[3]},
        "nine_pose_wire_arc_envelope_with_max_OD_mm": [wire_min.tolist(), wire_max.tolist()],
        "R26_cover_finite_gait_interval_count": len(bounds["intervals"]),
        "cover_rows": cover_rows,
        "conditional_minimum_vertical_gap_to_new_covers_mm": vertical_gap,
        "hard_part_clearance_target_mm": TARGET_HARD_PART_GAP_MM,
        "conditional_new_cover_gap_target_met": True,
        "case_rows": case_rows,
        "source_sha256": sources,
        "limits": [
            "The nine feasible cable shapes are separate kinematic references; no continuous elastic transition or real wire sag is proven.",
            "The R21 gait interval q(t) is a numerical trace, not a recalculated R26 gait or hardware trajectory.",
            "Only the two new R26 thigh covers are added to the prior R25 wire-body audit; previously retained moving body-to-wire combinations are not newly proven here.",
            "The 0.0161 mm S19-S25 nominal gap cannot absorb independently installed wire placement errors and is not a manufacturing clearance.",
            "No harness manufacturing or physical acceptance is granted.",
        ],
        "manufacturing_approved": False,
        "physical_approved": False,
    }
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "r26_flex_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in ("status", "R26_flexible_wire_count", "nine_pose_body_pairs_screened_in_R25", "worst_wire_pair", "conditional_minimum_vertical_gap_to_new_covers_mm")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
