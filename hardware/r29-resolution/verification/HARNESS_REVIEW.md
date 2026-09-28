# R26 31-wire neck harness: delta audit and release gates

The R26 thigh-cover change does not introduce a new nominal clash with the
31 selected flexible neck wires. It does **not** qualify the harness for
manufacture or walking. The free wires are elastic bodies, while the R26
rigid checker omitted them. This review binds the selected geometry and
separates deliberate insulation/guide contact from uncontrolled pinching.

## Recomputed evidence

- [`audit_r26_flex.py`](audit_r26_flex.py) compares the R26 and R25 selected
  STEP/STL hashes and joint tables. All 31 free wires are identical. It
  rechecks the nine R25 route cases (HOME and the two single-axis endpoints
  of neck pitch ±10°, head pitch ±15°, yaw ±30° and roll ±10°): 17,131
  wire/body near pairs, no reported positive-volume intersection. Those are
  nine distinct mathematically fitted routes, not a continuously deforming
  cable simulation.
- For those nine route shapes, a deliberately oversized analytic envelope
  covering every line, circular arc, and maximum insulation OD has a lowest
  point at **z = 72.142 mm** in the trunk frame. The two R26 thigh covers
  reach no higher than **z = 20.287 mm** over all 9,773 recorded numerical
  walking intervals, using joint-range displacement bounds. Their conditional
  vertical separation is **51.855 mm**, exceeding the 2.2 mm hard-part
  design target. This remains conditional on real wires staying inside the
  modelled envelope; a loose, sagging harness has not been simulated.
- The closest nominal wire pair in the nine poses is **S19/S25, 0.0161 mm**
  at head pitch −15°. Individually insulated wires in a controlled bundle
  may touch, so the value is not itself a metal collision. It cannot serve
  as manufacturing tolerance or proof that loose wires will not rub.

The source hashes, case-by-case numbers and envelope are in
[`r26_flex_audit.json`](r26_flex_audit.json). Guide proximity is separately
recomputed in [`guide_near_clearance.json`](guide_near_clearance.json).

## Pinch/abrasion classification

| Pair family | Smallest nominal mesh gap | Intended function | Release disposition |
|---|---:|---|---|
| Free wire to its own fixed tail | 0 mm at the conductor junction | Continuity of the same lead | Intended mate; inspect insulation transition and strain relief |
| P5/P6 to installed VMQ liner | 0 mm at the guide | Compliant grip | Intended contact; verify compression, retention and insulation condition on first article |
| P5/P6 to PEEK film, upper/lower | 0.110/0.110 mm | Replaceable wear barrier near power-wire exit | Very small as-modelled gap; assembled film coverage and no pinching are unproven |
| Signal wire to upper/lower PEEK comb | 0.161/0.161 mm | Channelled guidance | Intended proximity; channel finish/size and wire OD require as-built measurement |
| P5/P6 to upper/lower 6061 bridge | 0.360/0.360 mm | Structural bridge, **not** a contact surface | No nominal intersection, but metal abrasion margin is too small to inherit production approval |
| Free wire to new R26 thigh covers | ≥51.855 mm conditional vertical bound | No contact intended | R26 cover delta cleared for the modelled route and recorded gait only |

Existing retention hardware is the **upper and lower PEEK comb housings,
VMQ inserts, PEEK retainers, P5/P6 PEEK films and PTFE lacing bands** in the
selected R25/R26 assembly. These parts must remain in the build; removing
one invalidates the clearance and strain-relief argument. The free span is
not yet contained by a common sleeve. A nominal 14 mm common braid cannot
be slipped over the selected HOME layout: at z = 150 mm, one sampled point
per wire already spans **55.161 mm center to center**. See
[`sleeve_feasibility.json`](sleeve_feasibility.json). A compact common sleeve
requires a full route, clip and guide redesign with new CAD/body checks.
Adding individual tubing at the 0.110 mm PEEK-film gap would also consume
the existing nominal space, so it is not a safe drop-in fix.

A local S25 +0.5 mm x adjustment near the S19/S25 gap was tested, not
selected. Although it opened that pair to 0.213 mm, it overlapped S24 and
changed the route length by 0.164 mm; larger shifts violated the 25 mm bend
geometry. [`s25_probe.json`](s25_probe.json) records this failed diagnostic.
The correction must coordinate neighbouring conductors and maintain all
31 endpoint/length/radius constraints.

## Design and first-article gate

Before issuing a manufacturing release, solve all **81 combined endpoint
poses** (three values for each of the four head/neck axes) with the same
31 cut lengths, both clamps, the finished guide/bridge meshes, and the
repaired mouth travel. Validate continuous transitions on the commanded
head and walking trajectories using a cable model with measured bending and
torsional stiffness, self-contact and friction. The nine existing independent
fits cannot be interpolated as a physical cable solution. Model maximum OD,
actual clamp positions and worst measured assembly variation. Resolve any
uncontrolled rigid-metal contact by rerouting or increasing a replaceable
PEEK liner/bridge relief, then rerun the interference check. Do not simply
whitelist a zero-gap pair.

For the first built unit, measure each finished comb slot, PEEK film,
bridge edge and wire maximum OD; deburr all 6061/PEEK edges and photograph
liner coverage. Number-check and measure all 31 conductors against the
selected R25 cut-length table. On a supported, current-limited bench, move neck pitch to
±10°, head pitch to ±15°, yaw to ±30° and roll to ±10°, then exercise
all 81 combined endpoint poses and continuous transitions at the intended
speed. Inspect in situ with a borescope: no wire may touch bare 6061 or a
fastener edge, enter a pinch line or pull taut; the minimum visible metal
separation target is **0.2 mm** at every reachable pose. PEEK/VMQ contact is
allowed only at the intended guide/retainer locations with no extrusion,
cut, flat spot or slippage. Keep the existing **≥25 mm free-wire bend
radius** design requirement unless the actual selected wire datasheet is
more restrictive.

Apply the already specified retention test: **5 N to each conductor,
never more than 5 N total simultaneously**, with **≤0.2 mm slip** and no
insulation damage. Continuously monitor all 31 circuits during motion; a
single open/intermittent event fails. Run an initial 10,000 full-range
head-motion cycles, inspecting guide exits, PEEK film and 6061 witness
points at intervals and afterwards. This is a qualification screen, not a
service-life claim. Record post-cycle continuity, resistance and insulation
condition against pre-cycle measurements. Repeat with the gait playback and
camera/mouth wiring active after the mouth collision is fixed. Any abrasion
or pinch requires a revised physical route or guide and a new CAD audit.

**Current gate:** R26 thigh-cover-to-modelled-wire clearance is closed;
combined-pose cable deformation, guide tolerances and fatigue are open.
No physical harness, manufactured guide measurements or loaded walking test
exists, so this review cannot approve the 31 flexible wires for production.
