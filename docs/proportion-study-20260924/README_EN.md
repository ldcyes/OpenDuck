# Leg proportions and actuator screening — September 24, 2026

Follow-up: option A is now implemented in [R26](../../hardware/r26-cover-first/README_EN.md). The study below remains the pre-change comparison.

[中文完整分析](README.md) · [English project overview](../../README_EN.md)

**Design study only. No manufacturing geometry, actuator BOM or qualified gait has been replaced. A height of 610 mm is not a design requirement.** The previously selected permanent closure of the left head opening remains pending implementation and validation.

The source-checked R25 Blender assembly measures **570.393 mm** tall in its saved HOME pose. Applying the earlier R21 preparation joint angles gives **577.830 mm**; that is a kinematic comparison, not a new R25 balance or collision result. The hip–knee and knee–ankle axis distances are **88.599 mm** and **103.732 mm**. Their sum, **192.331 mm**, includes lateral offsets; vertical hip-to-ankle separation in HOME is only **157.400 mm**.

The thigh cover extends **27.224 mm below the knee axis**. Redrawing its lower edge to about 10 mm below that axis could expose approximately 17.2 mm more of the knee/lower-leg region without increasing joint moment arms. This is an envelope observation, not a pixel-occlusion or clearance measurement. Fasteners, edge distances, access, mounts and continuous knee motion must be checked before changing the printable part.

![Existing R25 assembly, orthographic side view](baseline-side.jpg)

[Orthographic front view](baseline-front.jpg). Both images retain the original HOME geometry.

| Alternative | Combined 3D leg-axis lengths | HOME height estimate | Same preparation-angle height estimate |
|---|---:|---:|---:|
| A — redraw covers first, recommended | 192.33 mm | 570.39 mm | 577.83 mm |
| B — extend sagittal leg-vector components by 10% | 209.23 mm | 586.13 mm | 594.30 mm |
| C — extend sagittal leg-vector components by 15% | 217.74 mm | 594.00 mm | 602.53 mm |

B/C preserve HOME lateral axis positions rather than scaling hip width. Because lateral components remain unchanged, their combined 3D lengths do not increase by exactly 10%/15%. These height estimates retain joint angles and existing motor/foot offsets. New CAD, mass, foot contacts and the final stance can change them. A real redesign must re-solve both feet and contact forces.

The actual R25 inventory has twelve XM430 actuators and three XC330 actuators, with XM430 at all ten leg joints. Commercial motor models must retain manufacturer dimensions; visually scaling a motor is not a valid substitution.

| Actuator | W × H × D | Mass | Stall torque at 11.1 V | Screening result |
|---|---|---:|---:|---|
| XM430-W350-T | 28.5 × 46.5 × 34 mm | 82 g | 3.8 N·m | Existing loaded-joint baseline; sustained capacity remains unmeasured |
| XM335-T323-T | 19 × 35 × 22 mm | 27 g | 1.03 N·m | Smaller candidate for head pitch and possibly hip yaw; not a direct substitution at loaded pitch/knee/ankle joints |
| XC330-T181-T | 20 × 34 × 26 mm | 23 g | 0.76 N·m | Retain candidate head yaw/roll and mouth uses |
| XM540-W270-T | 33.5 × 58.5 × 44 mm | 165 g | 10.0 N·m | Larger and heavier; four hip-pitch/knee replacements add 332 g before new mounts |

Manufacturer specifications checked September 24, 2026: [XM430](https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/), [XM335](https://emanual.robotis.com/docs/en/dxl/x/xm335-t323/), [XC330](https://emanual.robotis.com/docs/en/dxl/x/xc330-t181/), [XM540](https://emanual.robotis.com/docs/en/dxl/x/xm540-w270/). Stall torque does not establish sustained output. XM335/XC330 allow at most 12.0 V input, so they cannot automatically share an XM430 supply that can reach 14.8 V.

Across the earlier four R21 cases, the larger left/right hip-pitch peak is 1.175 N·m and knee RMS is 0.690 N·m. Neck-pitch RMS reaches 0.402 N·m; head pitch is lower at 0.108 N·m. These observations prioritize head pitch for smaller-actuator investigation, but the updated camera, shell and harness loads must be included. One XM430-to-XM335 substitution saves 55 g in motor mass; three save 165 g, before mount changes. None is an approved substitution.

R25's estimated **4.447479 kg** is **6.02%** above the **4.195094 kg** R21 dynamics model. A first-order mass-and-arm sensitivity calculation gives hip-pitch capacity requirements of approximately 1.465, 1.612 and 1.685 N·m for A/B/C if 15% capacity reserve is requested. This calculation is **neither inverse dynamics nor a conservative bound**. It cannot replace a new model with actual COM/inertia, contact allocation, accelerations and actuator limits. The former 1.35 N·m model limit was itself unqualified.

The next design stage should first redraw the covers, then use B if actual leg extension is still needed. It must update mounts, hardware, harnesses, mass/COM/inertia, collisions and gait together. Low-battery cyclic/sustained torque and temperature over the intended 1–2 hour duty period need applicable manufacturer data or bench measurements. No new STL/STEP, integrated Blender assembly, final actuator purchase selection or physical acceptance is claimed here.

Evidence: [per-part dimensions and input hashes](baseline_measurements.json), [candidate coordinates and sensitivity results](candidate_screen.json), [geometry measurement source](measure_baseline.py), and [screening source](compare_candidates.py). Scripts run from `work/r26-proportion-study/` within the full original engineering workspace and need the R25 assembly, R21 records and R11 kinematics; this Git repository alone does not contain every dependency. The [Chinese analysis](README.md) specifies the reproduction commands and remaining checks, including the existing mouth/lower-shell conflict.
