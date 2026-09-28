# Final bounded R29 harness feasibility result

All **81 combined endpoint poses** received at least one bounded solve attempt, preserving all 31 R25 conductor identities, free-span lengths, anchor positions and guide tangents. The selected CAD and HOME geometry were not changed.

**59 poses have verified geometric route witnesses; 22 remain unresolved.** “Witness found” means the independent geometry constraints passed; it does not mean a stationary elastic equilibrium was established. The 59 include the nine frozen R25 shapes at their identical coordinates plus 50 newly fitted combined poses. Two initially failed poses were recovered from other nearby successful seeds; a third retry remained unresolved. No further optimization is pending.

For the 59 completed poses:

- 1,829 wire/pose checks passed endpoint identity, tangent/C1 continuity, frozen physical length, minimum R25 radius, wire-pair separation and nonlocal self-clearance checks.
- 111,125 nearby wire/rigid mesh pairs were screened against the frozen R29 selection, including the four new PEEK exit lips: zero intersection volumes above 1e-5 mm³ and zero mesh errors.
- Minimum wire-pair clearance lower bound: **0.0161051404 mm**. This is not manufacturing tolerance allowance.
- Maximum fixed-length residual: **0.00447669038 mm**, below the 0.005 mm numerical acceptance threshold.
- Minimum bare bridge gap: **0.360124458 mm**; no computed bridge gap below the 0.2 mm nominal target. PEEK/VMQ proximity is classified separately and does not establish wear or retention performance.
- Every body report matches its exact route and frozen selection hash. All 1,109 unique retained mesh-file hashes remain unchanged.

`summary.json` contains every pose, result, independent check and source binding. `abrasion_contacts.json` contains all near-contact classifications. `rigid_mesh_hashes.json` binds the full retained geometry. `rerun_manifest.json` binds an exact starting seed and iteration budget for each target. `solver_math_check.json` confirms the normalized bending integral against independent analytic arc integration and a finite-difference gradient check.

The bending objective is a normalized unit-EI integral of curvature squared over a restricted straight/R25-arc basis. It is not a calibrated elastic-rod model: there are no measured bending/torsional stiffnesses, friction, gravity, clamp compliance, force-balance certificate or continuous deformation proof. All 81 targets hold the mouth and other joints at 0 degrees. No manufacturing, physical harness or loaded-walking approval is granted. A bounded failure is not mathematical infeasibility and does not establish that longer wires or changed anchors are required.

## Unresolved target coordinates

Order is neck pitch, head pitch, head yaw, head roll, in degrees.

| Grid index | Target angles |
|---:|---|
| 15 | (-10, 0, 30, -10) |
| 18 | (-10, 15, -30, -10) |
| 19 | (-10, 15, -30, 0) |
| 22 | (-10, 15, 0, 0) |
| 23 | (-10, 15, 0, 10) |
| 24 | (-10, 15, 30, -10) |
| 25 | (-10, 15, 30, 0) |
| 42 | (0, 0, 30, -10) |
| 45 | (0, 15, -30, -10) |
| 46 | (0, 15, -30, 0) |
| 47 | (0, 15, -30, 10) |
| 50 | (0, 15, 0, 10) |
| 51 | (0, 15, 30, -10) |
| 52 | (0, 15, 30, 0) |
| 60 | (10, -15, 30, -10) |
| 69 | (10, 0, 30, -10) |
| 72 | (10, 15, -30, -10) |
| 73 | (10, 15, -30, 0) |
| 75 | (10, 15, 0, -10) |
| 76 | (10, 15, 0, 0) |
| 77 | (10, 15, 0, 10) |
| 78 | (10, 15, 30, -10) |

## Fixed-seed replay

From the repository root, using the recorded Python 3.10 and bundled dependency versions:

```sh
python3.10 work/r29-closure/harness/combined81/reproduce.py --index 0
python3.10 work/r29-closure/harness/combined81/reproduce.py --all
```

The replay verifies input hashes, uses each recorded seed explicitly, and writes to `work/r29-closure/harness/combined81-rerun/`. It never overwrites this evidence or selected CAD. Serial fixed-seed replay avoids the discovery scheduler's completion-order dependence. Bitwise behavior across different numerical libraries or hardware is not claimed; the independent geometric thresholds define acceptance. `evidence_freeze.json` hashes the final artifacts and retained attempt history.
