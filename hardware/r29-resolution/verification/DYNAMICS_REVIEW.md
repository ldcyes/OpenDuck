# R26 / R29 mass-rebound walking review

**Engineering result: walking acceptance is blocked.** The original four-step gait completes the predeclared *numerical* checks with the R26 and R29 masses only because the simulator permits 0.08 Nm at the mouth joint. The active runtime and structural guard is 0.05 Nm, exceeded throughout all four R29 walks even while the mouth is closed. The 15% assumed leg-motor torque margin also fails. There is no prototype or low-battery sustained-torque qualification.

## Exact configuration

- R26 baseline model: 4.443059766833 kg. R29 selected model: **4.442728967589 kg**, HOME center of mass **[2.925636, −1.627056, 25.124310] mm** in the project assembly frame.
- The R29 shell is `work/r29-mouth-relief/mechanics_10deg/R29_lower_head_shell_mouth_10deg_3mm.ply`, SHA-256 `a498871307dd3cb4fab6493529b748d02d31e2311a8489179fbd15450c0f19e3`. It replaces the R25 lower shell once. The four PEEK exit lips replace four older films once, with net mass **+0.006892 g**. The 31 free head-harness sections remain paired 50/50 rigid mass surrogates, not flexible cables.
- Body inertias are recomputed from the selected mass rows. Five randomized articulated poses give row-summed world COM versus MuJoCo COM errors below **2.3×10⁻¹⁵ m**. Joint pivots, force caps and foot-contact arrays match the frozen original model. Material densities and purchased-component masses remain engineering estimates.
- The selected 0–10° mouth cap is an independent firmware/geometry constraint. This four-step trace holds the mouth close to HOME; it does not test the full mouth movement during walking.

## Four complete final-model runs

The predeclared checks require ≥2 forward steps per foot, ≥15 mm net forward travel per foot, root and joint tracking errors ≤3°, stance-outline slip ≤3 mm, saturation ≤20 ms, and peak swing-sole clearance ≥2 mm. All four cases meet only those frozen numerical thresholds under the inconsistent 0.08 Nm simulated mouth cap. They do **not** pass the active 0.05 Nm mouth structural guard. Each run has a continuously integrated free base and lasts **195.442 s**; this is an extremely slow diagnostic, not a normal walking-speed test.

| R29 case | dt / friction / sole contact | Worst joint torque | Assumed cap use | Loaded foot slip L / R | Body roll peak-to-peak |
| --- | --- | ---: | ---: | ---: | ---: |
| Nominal | 0.25 ms / 0.8 / 4 | left hip roll 0.859552 Nm | 95.51% | 0.940 / 0.646 mm | 33.382° |
| Half timestep | 0.125 ms / 0.8 / 4 | left hip roll 0.835505 Nm | 92.83% | 0.926 / 0.635 mm | 33.383° |
| Low friction | 0.25 ms / 0.5 / 4 | left hip roll 0.859514 Nm | 95.50% | 0.934 / 0.646 mm | 33.382° |
| Contact partition | 0.25 ms / 0.8 / 9 | right hip roll 0.838900 Nm | 93.21% | 0.576 / 0.295 mm | 33.301° |

The R26 mass baseline also passes all four numerical checks. Its worst case is nominal left hip roll **0.859966 Nm**. The R29 nominal change reduces that modeled peak by only **0.000414 Nm**. Body roll remains essentially the R21 result of **33.369°**; this rebind is not a lateral-sway improvement.

The previous 0.9 Nm hip-roll and 1.35 Nm hip-pitch/knee caps are **unmeasured engineering targets**. Across all four R29 cases, measured continuous capacity at the specified low-voltage/temperature/duration would need to be at least **1.011237 Nm left hip roll**, **0.986941 Nm right hip roll**, **1.448551 Nm right knee**, and **1.445806 Nm left hip pitch** to retain 15% peak headroom in this model. The 10.30–10.35 V, 40°C, 7200 s actuator bench test has **not run**. A purchased motor's stall rating does not establish any of these sustained values.


## Active mouth structural guard: hard blocker

The published runtime source `work/openduck-publish/repository/software/r8/rk_runtime/microduck_rk/motion_limits.py` fixes `MOUTH_STRUCTURAL_TORQUE_NM = 0.05`, while the R20/R29 simulation model leaves the mouth-actuator cap at **0.08 Nm**. The simulated mouth peaks for the four final cases are **0.058760, 0.058370, 0.058761, and 0.059250 Nm**; RMS is about **0.056672 Nm** in every case. All **9,774** saved samples in each case exceed 0.05 Nm, despite actual mouth angles staying within about ±0.004° of closed. This is a continuous holding load, not a short gait impulse.

A level-base HOME calculation from the selected model requires **−0.056119 Nm** just to hold the mouth closed; at 10° it still requires **−0.051982 Nm**. The moving mouth assembly is 90.652 g, with its center 63.104 mm forward of the +Y hinge. The revised lower-head shell is on the parent link and therefore does not cause this mouth-axis gravity moment. A passive closing assist would need to offset at least **0.009251 Nm** at the observed worst case merely to meet the hard guard, or **0.016751 Nm** for an 85%-of-guard design target, before manufacturing, spring-rate, position, temperature and motion margins. Those numbers are sizing targets, not an approved spring. The remedy requires a source-bound CAD installation, retained 0–10° clearance, rated torque over angle, and four-case rerun with the **0.05 Nm** active cap. Increasing the software guard is not an authorized shortcut. The direct evidence is `mouth_structural_guard_audit.json`.

## Planned swing contact audit

The acceptance check tests *peak* swing clearance; it does not assert zero contact throughout the named swing interval. The saved 20 ms samples show transient normal loads during lift-off and landing. In all four R29 cases, every >2 N contact sample lies in the first or last 10% of planned swing, while the central 20–80% has zero sampled contact force. The longest nominal loaded transfer run lasts **0.96 s**; the nominal maximum force is **7.592 N** and the sampled normal impulse reaches **7.814 N·s** per planned swing. During such >2 N runs, foot-center motion is at most **0.179 mm** nominal (**0.182 mm** over all cases). Thus the saved trace does not show mid-swing drag, but this is a **post-hoc diagnostic** and does not exclude a brief event between 20 ms samples. A future explicit acceptance criterion could require >2 N contact only in the outer 10% of planned swing and ≤0.5 mm loaded foot-center movement; it must be declared before the next design-validation run.

## Gait changes considered

At R26 mass, 1.3× retiming, a modified double-support load target, and 3 mm/5 mm rightward lateral-COM waypoints were integrated. None reached the 15% assumed-cap margin while retaining the four-step contact checks. The best 5 mm shift still used **93.01%** of the 0.9 Nm hip-roll target. That modified path is **not selected**; the final R29 runs retain the original, already CAD-reviewed gait. A larger motor or further sway retune requires separate CAD, balance, thermal, and battery checks.

## Model-limited balance observation

In all four selected-model runs, saved root height remains about **250.6–259.8 mm** and maximum absolute root tilt is about **18.3°**. After the initialized t=0 sample, every saved frame retains at least one foot with ≥2 N normal load; no numerical fall occurs. These are 20 ms sampled observations, not a support-polygon, capture-point, disturbance-recovery, or physical balance margin. `stability_sample_audit.json` preserves the source-bound values.

## Replay and limits

The nominal CAD replay is `R29_final_nominal/dynamic_trace_for_CAD.json` (SHA-256 `18c88537f29bdc1f58752ca969612dc5b06b51fd656afd9e1129b2e5d231e0c5`). It has 9,774 time-ordered samples with all 15 joint angles and a 4×4 base transform. `R29_final_nominal/interval_joint_bounds.json` encloses joint values at all **781,767 numerical integration endpoints** in 9,773 successive 20 ms intervals; a separate rigid-body CAD collision pass is still required. These bounds do not account for manufacturing tolerances or flexible cable movement.

MuJoCo retains the original R20 foot-contact shape; the changed covers and shell are not its collision bodies. The model omits actuator voltage sag and heat, backlash/compliance, harness bending, real friction variation, falls caused by control latency, and physical endurance. Numerical threshold success must not be marked as manufacturing or walking acceptance, particularly while the active mouth structural guard is violated.

Machine-readable evidence is in `R29_dynamics_validation.json`; transfer contact timing is in `swing_contact_audit.json`. Both bind their input artifacts by SHA-256.
