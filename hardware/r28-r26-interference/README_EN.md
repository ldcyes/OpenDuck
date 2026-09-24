# OpenDuck R28: R26 assembly interference review

[简体中文](README.md) · [R26 assembly](../r26-cover-first/README_EN.md) · [R27 four-step replay](../r27-walk-replay/README_EN.md)

[Download evidence ZIP](https://github.com/ldcyes/OpenDuck/releases/download/r28-r26-interference-20260925/R28-R26-interference-evidence.zip) · [SHA256](https://github.com/ldcyes/OpenDuck/releases/download/r28-r26-interference-20260925/SHA256SUMS.txt)

The two new R26 thigh covers were checked directly against the recorded 9,773 numerical integration intervals (195.44175 s). The R26 selection contains 1,224 installed geometry entries; 31 flexible neck-harness entries are excluded from rigid-body testing, leaving 1,193 rigid entries. **No new rigid penetration was found for the covers along this nominal trajectory. This does not approve fabrication or physical walking.**

| Check | Result |
|---|---|
| New covers versus other rigid entries | 2,383 pairs: 2,345 moving and 38 invariant |
| Continuous intervals | All 9,773 intervals covered for every moving pair; zero unresolved dynamic penetrations |
| Smallest conservative moving-pair clearance bound | **0.015113 mm**, for the right thigh cover versus the left ankle motor. This falls below the 2.2 mm target and does not establish a manufacturing tolerance margin. |
| Six fixed seating contacts | Each cover meets its own CNC bridge saddle and F1/F2 OD7 washers. Native STEP Boolean intersection volume is **0 mm³** for all six; tiny mesh intersections are numerical error. |
| Old-to-old pairs | The prior R25 ledger of 46,170 dynamic pairs and 110 named invariant contacts is inherited; old-to-old geometry was not recomputed in this direct check. |

**Existing real interference remains:** the R25 lower head shell intersects the R12 mouth carrier when opening. A 0.25° sweep first found intersection at **8.75°** (about **0.1225 mm³**); at 25° it reaches about **218.58 mm³**. The recorded four-step mouth command stays near zero (−0.00154° to +0.00264°), so this gait does not exercise the conflict. Full mouth travel requires a geometry or limit correction and another check.

The trajectory was integrated for R21 at 4.195094 kg; the R26 estimate is 4.443060 kg, and R26 dynamics have not been recomputed. The 0.015 mm bound applies to nominal triangulated rigid geometry, without print tolerance, fastener eccentricity, load deformation, flexible harness motion, ground contact or bearing play. This finding is limited to **new nominal rigid intersections on the checked trajectory**.

[Reviewed summary](verification/direct_review.json) · [interval result](verification/result.json) · [pair index](verification/pair_index.json) · [mouth sweep](verification/mouth_interference.json) · [inputs and checkers](sources)

Reproduction needs the original R26, R25 and R21 engineering geometry and motion sources in their recorded `work/` layout. Source SHA256 bindings are retained. No physical power-on, load or walking test was performed.
