# Cross-terrain benchmark of constructive axial-map selection

**Both complementary methods produced valid, smaller maps than strict backward on all seven settlements with complete exact records.** The archived frozen Algorithm D runs completed independently in two and exhausted their winding-repair budget in five. The planned 36-settlement, six-seed comparison remains incomplete because 29 settlements lack the immutable batch payloads required for a matched run.

## 1. Experimental design

The fixed cohort contains six terrains and seeds 40–45, for 36 settlements and 144 evaluation slots. Seven settlements have reproducible inputs. These comprise every terrain at seed 40, plus Flat 41. The ledger accounts for all slots. It keeps reproduced maps, bounded search failures, missing-input cases and publication-only baseline entries distinct.

## 2. Corrected settlement geometry and topology

The tar and existing directories were inspected against the published lineage. All 84 record manifests and outputs for the seven restorable cases matched the archived hashes. Those files were already present and no existing files were overwritten. The other 29 settlements lack 348 immutable files. All 36 have published corrected baseline results and vector maps. A case journal, map export or movement summary cannot supply the exact missing settlement, topology, candidate and incidence payloads. Reconstructing settlements from their configurations would create an unverified lineage, so the published baseline geometry was retained.

The seven materialised cases reuse exact building and open-space identities, numbered polygons, certified intervals, strict convex incidence and doorway ordering. Required winding rank spans 6–24. Strict region counts span 205–292. Converging Valleys 40 has 184 excluded open cells, the largest value in this subset.

[Input verification and missing file inventory](inputs.json) · [Source and configuration hashes](lineage.json) · [Published baseline summaries for all 36 cases](published-backward.csv)

## 3. Frozen algorithms

Strict backward and D use the archived runs on the restored exact inputs. Valid archived selections were independently certified again. D's original backbone size, geometry, completion and exchange parameters were preserved. The two C methods use the same archived complementary pair score and exact occupied-block support. The shortest certified interval repairs each uncovered strict region in order. Other remaining defects use the existing bounded completion procedure. The two methods then use shortest-first or sheaf-priority reduction and the same frozen bounded exchanges. All C deletion and exchange decisions use exact dynamic winding, with independent full face certification of each result. The runs use neither fixed witness protection nor a surviving same-sheaf substitute requirement.

The catalogue is complete-link on the shared repaired complementary start, using fixed geometric and incidence thresholds and distinct selection anchors. It is computed before C-S or C-H makes a deletion. On Flat 40 it reproduced all 91 historical sheaves and both archived final candidate sets. The prior Flat 40 catalogue and outcomes remain separately archived.

[Frozen settings and selection code hashes](protocol.json)

## 4. Structural completion

| Method | Independently certified valid maps | Bounded search failures | Other 29 cases |
|---|---:|---:|---|
| Strict backward | 7 | 0 | Published baseline only |
| D | 2 | 5 | Missing exact input |
| C-S | 7 | 0 | Missing exact input |
| C-H | 7 | 0 | Missing exact input |

No evaluated map used archived-map fallback. The five D failures were winding completion budget failures, not geometric infeasibility. Their partial maps are preserved. The same settlements have valid strict and C outputs. All independently certified maps meet exact clearance, strict region and doorway incidence, intersection connectivity, full winding rank and complete reachability under both route definitions.

## 5. Axial-map economy

| Settlement | Strict backward | D | C-S | C-H |
|---|---:|---:|---:|---:|
| Flat 40 | 44 | 33 | 34 | 34 |
| Flat 41 | 44 | Winding budget | 32 | 32 |
| Hill 40 | 45 | Winding budget | 35 | 34 |
| Ridge 40 | 45 | Winding budget | 27 | 27 |
| Shoulder 40 | 32 | Winding budget | 26 | 26 |
| Twin Peaks 40 | 41 | 27 | 26 | 26 |
| Converging Valleys 40 | 23 | Winding budget | 17 | 17 |

The median matched reduction from strict backward was ten lines for C-S and eleven for C-H. The two methods tied on six case counts, and C-H kept one fewer line on Hill 40. D kept one fewer line than C on Flat 40 and one more on Twin Peaks 40. The exact sample supports economy of complementary preselection across the recovered cases.

## 6. Angular movement

Routing uses zero angular entry and exit cost with exact doorway-region incidence. Both C methods lowered mean angular cost against strict backward in all seven cases. Their mean improvements were 0.351 for C-S and 0.349 for C-H. In the matched C-H minus C-S comparison, the median difference was −0.00216 and the range was −0.00506 to +0.02265. C-H won four cases, tied two and lost on Shoulder 40. D had the better mean on Flat 40, while both C maps were better on Twin Peaks 40.

## 7. Metric movement

Metric routing uses the certified finite regional connector graph and feasible projections and endpoints, with no nearest-line cap. C-H lowered mean metric distance against strict backward in all seven cases. C-S improved six and was about 0.08 units worse on Flat 40. Relative to C-S, C-H's median difference was −0.00219 and its range was −0.447 to +0.027. D had the lowest mean metric cost in both settlements where it completed independently. This comparison is conditioned on D succeeding.

The reduced routing construction uses the active union of selected maps and the strict control. The Flat 40 audit reproduced all 4,950 angular and metric costs for both C maps, with a maximum absolute deviation of 1.85e−13. Full per-doorway arrays, all requested distribution statistics and worst pairs are in each materialised settlement's movement record.

## 8. Computation

Complementary preselection reduced the raw starting inventory by a mean 57.0% across the seven cases. It took a mean 2.16 seconds to construct, with a mean 7.00 seconds for repair and 2.63 seconds for the shared catalogue. Median recorded selection-phase time was 16.34 seconds for C-S and 11.12 for C-H, including shared preselection, repair and catalogue time. The maximum was 37.91 and 31.14 seconds, respectively. Exact independent certification time is recorded separately. The case ledger and records give deletion and exchange costs, dynamic winding calls and process RSS.

Three workers processed separate cases. Within each, C-S ran before C-H, sharing loaded data and caches. The C-H times were lower in this run. Fixed order and shared caches make that a descriptive comparison rather than an isolated speed effect. D and strict times were measured during earlier archived runs, and some archived phase timings are unavailable. Their runtime figures are not directly comparable with these measurements. The earlier controlled Flat 40 comparison isolates a speed benefit there. This recovered subset shows a smaller search inventory in every case, but has no new matched unrestricted full-pool arm from which to infer an end-to-end speed benefit on all terrains.

[Execution conditions](execution.json) · [Routing equality audit](routing-network-audit.json)

## 9. Topographies and seeds

The benchmark has one reproduced seed per terrain except Flat, and only two Flat seeds. It supports within-settlement comparisons and does not establish stable terrain rankings or robustness across seeds 42–45. Terrain-level output includes explicit missing cases. Effect sizes, signed paired differences and leave-one-out mean ranges are available for the observed sample. Confidence intervals for the intended cohort would be misleading with this archival availability pattern. The separately labelled published strict-backward ranges show the spread over all six seeds per terrain without treating the unpublished method combinations as observed. [Published baseline seed ranges](published-seed-summary.json)

## 10. Circulation and corridor geometry

Final C line count is strongly associated with the number of independent occupied-block classes in this subset. Descriptive Spearman correlations are 0.955 for C-S and 0.982 for C-H, versus 0.288 and 0.327 with certified candidate count. Complementary vertex count and sheaf count also track final counts. These associations come from seven observations and covary with strict regions and geometry. They do not isolate terrain or winding as a causal effect.

[Per-settlement morphology](morphology.csv) · [Paired comparisons](paired-comparisons.csv) · [Status, terrain and matched summaries](statistics.json)

## 11. Scientific assessment and limitations

The recovered cases support complementary preselection as a practical way to build economical, structurally complete maps. C-S and C-H were equally reliable here. C-H has the strongest observed balance of economy, angular and metric performance, and measured construction time, with small trade-offs relative to C-S. D has good metric results when it succeeds, but the five winding failures prevent a claim of consistent superiority. Circulation complexity is the strongest measured association with C line count. Broader computational advantage, terrain preference and seed robustness remain open until the other 29 exact case payloads can be recovered.

[All 144 evaluation entries](evaluations.csv) · [Numbered atlas](numbered-cross-terrain-atlas.pdf) · [Individual PDFs and PNGs](visual-index.json) · [Matched summary plots](summary-comparison.pdf)

The numbered atlas contains 136 vector pages with individual 3,000-pixel PNG exports. All 36 settlements appear, with archive-only pages and missing-input notices for the 29 unavailable cases. All seven routing replays matched the saved result arrays within 2.27e-13. The 29 focused regression tests passed both before and after the benchmark.

[Seven-case route replay](routing-replay-7.json) · [Settings and source checksum receipt](reproducibility.json) · [Output checksums](sha256.json)
