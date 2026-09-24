# R26 Cover-First Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development. User approved A and its published design on 2026-09-24; proceed with implementation and review without asking the same design question again.

**Goal:** Deliver two shorter thigh covers with preserved mounting interfaces, verified geometry and a complete R26 assembly.

**Architecture:** Preserve R25 immutable inputs. Build native STEP intersections from the existing rounded-triangle construction, verify subset and interfaces, then select precisely two replacements in the assembly. Separate native-CAD creation from integration/readback and documentation.

**Tech Stack:** Python, OCP, NumPy, trimesh/manifold3d, Blender 4.5, existing indexed 3MF/PLY exporter.

## Task 1 — Native covers and manufacturing files

Files: create `work/r26-cover-first/build_covers.py`, `work/r26-cover-first/mechanics/manifest.json`, native/print files and `work/r26-cover-first/mechanics/geometry_checks.json`.

- [x] Read R25 assembly and verify both cover STEP hashes; load original triangle parameters from R18 candidate_v3 shape manifest and candidate_v8 fixing contract. Read only, never execute old builders because they allocate new historical revisions.
- [x] Build a rounded-triangle clipping solid in the existing local cover basis. Raise the bottom corner toward the interior; intersect with each original STEP. Target world lower edge at knee Z minus10 mm, preserve circle radius and 2 mm plate thickness. Preserve all material within R7 mm of both fixed-hole axes; if target conflicts, reduce trimming until retained.
- [x] Compute BRep validity, one solid, positive volume, `new minus old` and `(old minus new) intersect interface_zone` (target <=1e-6 mm3; investigate rather than suppress discrepancies). Record exact hole-center-to-new-boundary distances with >=7 mm target.
- [x] Export STEP, precision STL, indexed PLY and millimetre3MF via existing `mesh_print_export.export_indexed`. Read all formats back, check closure, orientation, connectedness and volume/bounds tolerances; verify mesh with manifold3d.
- [x] Record material density0.93 g/cm3, new mass/COM and exact replacement names. No motor, joint, support or fastener moves. Evaluate4mm lateral inset as interface mismatch and retain position if bridge must be redesigned; record this decision.

Run `python3 work/r26-cover-first/build_covers.py`. Expected: two valid solid exports, all interface/subset checks pass. A failed meaningful geometry check must be fixed before integration.

## Task 2 — Assembly, collision delta and mass

Files: create `work/r26-cover-first/integrate_verify.py`, `assembly_selection.json`, `verification.json`, `mass_delta.json`.

- [x] Replace only the two named covers and assert all other source records/coordinates and 15 joint records are unchanged. Clear inherited obsolete per-revision selection counts and record R25 parent explicitly.
- [x] Independently check subset with mesh booleans and native source checks from Task1, including STEP neighbour checks for false positive tessellation contacts.
- [x] Check new HOME covers against every selected R25 installed item; classify named seating surfaces and actual penetrations, no blanket exemption. Recheck source shell removal corridor and actual screw/washer access for the cover mounting stage; name absent parts and limit grip/handle claims.
- [x] Use new-solid subset and invariant transforms to prove no added rigid collisions for any common joint pose; do not claim old assembly collision issues resolved or new physical dynamics passed. Existing interfaces untouched implies no added obstruction along identical original assembly paths, with scope limited to those paths.
- [x] Bind old cover mass to R23 retained mass ledger, remove once, add new mass once; update R25 aggregate HOME mass/moment. Report estimate and no dynamics approval.

Run `python3 work/r26-cover-first/integrate_verify.py`. Expected: exact two-cover delta, untouched joints, no unresolved added collisions, explicit existing limitations.

## Task 3 — Complete Blender and orthographic comparison

Files: create `work/r26-cover-first/build_viewer.py`, `verify_viewer.py`, `visual/OpenDuck_R26_cover_first.blend`, images and readback JSON.

- [x] Load hash-verified R25 standalone blend. Copy main assembly scene with original materials and matrices. Import two PLY replacements in millimetres, preserve same link binding and native-to-scene shift. Keep prior head detail scenes, correctly labelled as retained R25 content.
- [x] Create same-camera, same-scale old/new orthographic side and front views. Expose only complete R26 by default and retain a separate labelled comparison scene; avoid duplicated physical parts in one assembly.
- [x] Save .blend and open in a fresh process. Check part count, unique IDs, source hashes, all matrices, replacement vertex coordinates and original transforms unchanged within0.0001 mm. Read back dimensions; camera frame must contain full robot.

Run `work/tools/blender/blender --background --factory-startup --python work/r26-cover-first/build_viewer.py` then same command with `verify_viewer.py`. Expected: independently openable assembly and passing readback.

## Task 4 — Review and publish

Files: `work/r26-cover-first/README.md`, `README_EN.md`, delivery verification and archive; repository `hardware/r26-cover-first/` and bilingual homepage links.

- [x] Review spec compliance, then implementation quality and numerical limits; resolve material findings.
- [x] Write actual edge change, exported file instructions, installation order, invariant motor/leg dimensions, mass delta and unqualified items. Preserve left-head-closure pending status and old mouth conflict; never call them fixed.
- [x] Package source, parts, manifests and reports with relative workspace paths. Publish complete standalone Blender separately using existing GitHub release pattern. Generate SHA256 after files are final.
- [x] Validate all new local links and run repository `python3 tools/verify_publication.py`; keep removed angled homepage images absent. Commit exact changed paths, push without force, attach release files, verify remote asset hashes/size metadata. Record if upload is blocked instead of claiming it completed.

## Execution evidence

- Native and separate-process STEP/interface/export checks passed. Initial cross-process Boolean defect reproduced as a negative control and fixed by extending the clipping tool, without tolerance relaxation.
- Integration passed: 1222 retained records, 15 unchanged joints, 12 near pairs and 4 external tool corridors.
- Blender fresh readback passed; maximum retained geometry displacement 0.000056081 mm < 0.0001 mm. Three complete camera frames checked.
- Independent specification and quality reviews approved. Local package checks: 118 links, archive re-read and source hashes. Repository check: 722 files, 12 native boards and 12 schematics passed.
- Remote publication verification is recorded separately after upload.

Published R26 prerelease: https://github.com/ldcyes/OpenDuck/releases/tag/r26-cover-first-20260924 . Remote tree checked against all 31 changed files; all three asset digests and sizes matched; downloaded checksum bytes matched. Release commit `aec5c5a3312b8f147bbc5a967a52e356f232d30c`. Evidence: `provenance/r26-upload-verification.json`.
