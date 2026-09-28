# R29 PEEK bridge-exit wear lips: manufacturing candidate

The four P5/P6 power-wire PEEK films have been lengthened **1.5 mm toward
the free span** at both the upper and lower neck guides. This shields the
edge of each 6061 open groove with the same replaceable PEEK material already
selected for the original 12 mm bearing. The 6061 STEP files, attachment
bores, 0.55 mm nominal support web, lacing channels and structural load path
are **unchanged**. Each new STEP contains its old film solid and adds
1.32536 mm³ at the free exit; four films change estimated mass by
**+0.006892 g**.

The section is an open semicircular strip, **inner radius 1.00 mm, outer
radius 1.25 mm, 0.25 mm nominal thickness**. The local carrier coordinate
continues from **T = −1.5 mm to T = 12 mm** instead of 0..12 mm. The
semicircle opens toward positive local V. Cut 13.5 mm long from unfilled
PEEK film, form on the R1.00 mandrel, and deburr the free edge with a
0.05–0.10 mm edge break. Inspect the formed profile and P5/P6 jacket OD.
No adhesive strength is assumed; the selected bands and frictional grip
remain the retention method and require the established 5 N/≤0.2 mm
first-article check. These four replacement films must never be stacked on
their old versions.

[`wear_lip_manifest.json`](wear_lip_manifest.json) identifies the four
replacement CAD solids. Full STEP and installed-coordinate STL live in
[`geometry/`](geometry/). [`r26_selection_patch.json`](r26_selection_patch.json)
is a source-hash-bound four-for-four assembly patch with item names, paths,
hashes, link frames and mass accounting; it has not changed the original
R26 selection in place.

The post-change checks are:

| Screen | Coverage | Result |
|---|---:|---|
| New films vs free wires | 4 × 31 × 9 = 1,116 film/wire/pose pairs; 610 exact native-CAD near checks | No positive-volume intersection; minimum P5-to-film gap 0.111 mm |
| Added lip material vs all other R26 rigid parts | 4 × 1,189 × 9 = 42,804 broad pairs; 260 near, including 20 triangulated shell pairs | No positive-volume intersection and no unresolved pairs |
| Rigid near-contact classification | 108 fixed conductors, 22 lacing, 74 PEEK/VMQ guides, 20 printed shells, 36 unchanged 6061 bridges | All added-lip intersections zero |
| 81 combined endpoint poses, 31 wires | 2,511 straight endpoint-length necessary conditions | All pass; worst extra length over chord is 78.673 mm for P6 at (+10,+15,−30,+10)° |

Evidence: [`wear_lip_wire_screen.json`](wear_lip_wire_screen.json),
[`wear_lip_rigid_delta_screen.json`](wear_lip_rigid_delta_screen.json),
[`wear_lip_contact_review.json`](wear_lip_contact_review.json), and
[`anchor81_length_screen.json`](anchor81_length_screen.json). The 81-pose
test checks only the span between moving anchors against fixed wire length.
It does **not** construct 81 cable shapes or prove bend radius, wall
clearance, fatigue, or a physical elastic equilibrium. The nine wire shapes
are independent static fits; continuous deformations and first-article
retention/abrasion remain open. Thus these films are engineering candidates,
not manufacture or loaded-walking releases.
