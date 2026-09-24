# OpenDuck R26: cover-first option A

[简体中文](README.md) · [Blender](https://github.com/ldcyes/OpenDuck/releases/download/r26-cover-first-20260924/OpenDuck-R26-cover-first.blend) · [ZIP](https://github.com/ldcyes/OpenDuck/releases/download/r26-cover-first-20260924/R26-cover-first-design.zip) · [SHA256](https://github.com/ldcyes/OpenDuck/releases/download/r26-cover-first-20260924/SHA256SUMS.txt)

Two shorter thigh covers improve the knee/lower-leg outline while retaining leg lengths, all 15 joint definitions, actuators, mounting brackets and fasteners. **Engineering candidate; no prototype or physical acceptance.**

![Same-scale thigh-cover comparison](images/04-leg-comparison.jpg)

The lower rim changes from about 27.23 mm below the knee axis to 10.00 mm, exposing approximately **17.23 mm** more vertical space. The 2 mm main wall, both mounting holes, locating pockets and OD9 washer pads are retained. Minimum hole-centre-to-outer-edge distance is **8.056 mm**. These dimensions do not replace physical load qualification.

## Files and assembly

- [3MF printing masters](print), [native STEP](step), [millimetre STL](stl), [profile drawing](documents/R26-cover-profile.pdf). Import STL in millimetres without automatic scaling. The indexed 3MF is the printing master.
- The complete Blender file opens independently. Scene 01 contains R26; 02/03 show same-scale comparisons; 04/05 retain R25 head details; 06 is the original R25 reference. It contains 1224 assembly geometry entries and 17 hidden service references, not a manufacturing BOM count. Individual parts can be selected/hidden in Outliner.
- Replace only `R18P_L/R_thigh_photo_triangle`. With the robot supported and powered off, remove the two M2.5×8 screws and OD7 washers on each cover, disengage the cover outward from its locating spigots, and install the new cover on the unchanged bracket. Refit original washers/screws. Fastener torque, printed fit and clamp load remain first-article acceptance items.
- The ZIP is an incremental engineering package layered onto the original R23/R24/R25 workspace. Programs live under `work/r26-cover-first/`. The standalone Blender, STEP and 3MF files can be opened without that workspace.

## Verification and limitations

Native STEP checks, independent-process reimport and independent mesh checks are recorded. An initial cross-process coplanar-Boolean failure was corrected in the clipping-tool construction; the final checks do not relax the volume threshold to hide it. The new solids are valid and connected; exported meshes are closed and consistently oriented. Complete R7 mounting support regions, OD9 pads and locating-pocket surroundings lose no material.

Each new cover was screened against all other 1223 selected geometry entries; 12 near pairs received detailed checks. Named seating contacts are recorded individually. Four fastener access checks cover a 3 mm diameter shaft extending 35 mm outward at final cover installation; real handles, hand access and bit fit are not physically certified.

The new native solids are subsets of the old covers, with unchanged link transforms and unchanged surrounding parts. Therefore they cannot introduce a new rigid intersection at the same joint pose. This is a **continuous-pose collision-delta argument**, not proof that existing robot conflicts, load deflection, manufacturing tolerances or flexible-wire motion are resolved. All 1222 retained records and 15 joint records remain identical. A fresh Blender process checks component sources, transforms and replacement meshes.

Estimated mass falls by **4.420 g** to **4.443060 kg**. HOME COM changes by (+0.0337, -0.0016, +0.1428) mm. This uses material density, not measured weight, and does not qualify balance or dynamics. HOME height remains approximately 570.393 mm.

No 4 mm lateral inset is applied: original spigot engagement is only 0.8 mm, and moving the cover would require a bridge and screw-stack redesign. The original installed plane is retained.

The separately authorized permanent head-opening closure remains pending; this R26 retains the R25 head shell. The prior mouth/lower-shell conflict beginning around 8.75°, harness tolerance/pose limits, low-battery sustained torque, thermal/endurance and physical walking acceptance remain open. No new actuator purchase qualification, trained policy or hardware-motion approval is issued.

[Native geometry/export checks](verification/geometry_checks.json) · [Assembly and access/collision-delta checks](verification/verification.json) · [Mass/COM](verification/mass_delta.json) · [Blender readback](verification/Blender-readback.json) · [Source programs](sources)

![Profile and preserved fixings](images/profile-comparison.png)
