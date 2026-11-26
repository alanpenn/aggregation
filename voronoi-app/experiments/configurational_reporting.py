"""Vector atlas and descriptive exports for the matched configurational pilot."""

import csv
from itertools import combinations

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import numpy as np

from experiments.flat40_configurational import coordinates


KINDS = ("axial", "segment", "angular", "metric", "convex")
LABELS = {"axial": "Axial hops", "segment": "Segment hops", "angular": "Angular segments",
          "metric": "Metric segments", "convex": "Maximal convex"}
CHOICE = ("gini", "top_5_share", "top_10_share", "max_over_mean", "zero_fraction")


def name(case):
    return case.replace("converging_valleys", "Converging Valleys").replace("_", " ").replace("-", " ").title()


def base(ax, case, title):
    for part in case.accessible.geoms if case.accessible.geom_type == "MultiPolygon" else (case.accessible,):
        ax.fill(*part.exterior.xy, color="#eaf4f6", linewidth=.4, edgecolor="#7d9297", zorder=0)
        for ring in part.interiors:
            ax.fill(*ring.xy, color="white", linewidth=.3, edgecolor="#9babad", zorder=1)
    ax.add_collection(PolyCollection([list(p.exterior.coords) for p in case.buildings],
                                     facecolors="#c7c2be", edgecolors="#89837e", linewidths=.22, zorder=2))
    x0,y0,x1,y1 = case.inventory["study_boundary"]
    ax.set(xlim=(x0,x1), ylim=(y0,y1), aspect="equal", title=title)
    ax.set_axis_off()


def mapper(values):
    low, high = min(values), max(values)
    return ScalarMappable(norm=Normalize(low, high if high > low else low + 1), cmap="viridis")


def text_page(pdf, title, paragraphs):
    fig = plt.figure(figsize=(12, 8), layout="constrained")
    fig.suptitle(title, fontsize=19, x=.07, ha="left")
    y = .84
    for paragraph in paragraphs:
        fig.text(.07, y, paragraph, fontsize=12, va="top", linespacing=1.55)
        y -= .08 + .034 * paragraph.count("\n")
    finish(pdf, fig)


def finish(pdf, fig):
    pdf.savefig(fig)
    plt.close(fig)


def audit_page(pdf, audit):
    fig, panels = plt.subplots(2, 2, figsize=(11, 8), layout="constrained")
    axes = panels.flat
    fields = [(("measures", "mean_depth", "mean"), "Mean angular depth (degrees)"),
              (("measures", "integration", "mean"), "Mean angular integration"),
              (("intelligibility", "r"), "Intelligibility"),
              (("choice_concentration", "gini"), "Choice Gini")]
    for ax, (path, title) in zip(axes, fields):
        for i, key in enumerate(("historical", "continuous")):
            values = []
            for label in audit:
                entry = audit[label][key]
                for part in path:
                    entry = entry[part]
                values.append(entry)
            ax.bar(np.arange(len(audit)) + (i-.5)*.34, values, width=.34, label=key.title())
        ax.set(xticks=range(len(audit)), xticklabels=list(audit), title=title)
    axes[0].legend()
    fig.suptitle("Flat 40 · Historical adjacency and continuous traversal")
    finish(pdf, fig)


def terrain_maps(pdf, cases, matched, terrain):
    fig, axes = plt.subplots(2, 3, figsize=(12, 8), layout="constrained")
    for ax, key in zip(axes.flat, matched):
        base(ax, cases[key], name(key))
    fig.suptitle("Verified seed 40 accessible components and buildings · common 100 × 100 canvas")
    finish(pdf, fig)
    for kind in ("axial", "angular"):
        for metric in ("integration", "choice"):
            fig, axes = plt.subplots(2, 3, figsize=(12, 9), layout="constrained")
            scale = mapper([r[metric] for key in matched for r in terrain[key][kind][1].values()])
            for ax, key in zip(axes.flat, matched):
                base(ax, cases[key], name(key))
                graph, rows = terrain[key][kind]
                ax.add_collection(LineCollection([coordinates(graph.nodes[i]["points"]) for i in graph],
                                                 colors=[scale.to_rgba(rows[i][metric]) for i in graph],
                                                 linewidths=1.25, zorder=4))
            fig.suptitle(f"Matched seed 40 · {LABELS[kind]} · {metric.title()}")
            fig.colorbar(scale, ax=list(axes.flat), shrink=.6, orientation="horizontal")
            finish(pdf, fig)


def convex_maps(pdf, case, convex, spatial):
    graph, rows = convex
    fig, axes = plt.subplots(2, 3, figsize=(12, 9), layout="constrained")
    geoms = [coordinates(graph.nodes[i]["points"]) for i in graph]
    centres = np.asarray([np.mean(vertices, axis=0) for vertices in geoms])
    for (a, b, c), metric in zip(axes, ("integration", "choice")):
        scale = mapper([row[metric] for row in rows.values()])
        colours = [scale.to_rgba(rows[i][metric]) for i in graph]
        base(a, case, f"{metric.title()} footprints")
        base(b, case, f"{metric.title()} polygon scores")
        base(c, case, f"{metric.title()} sampled overlay")
        a.add_collection(PolyCollection(geoms, facecolors=colours, edgecolors=colours,
                                        alpha=.14, linewidths=.35, zorder=4))
        b.scatter(*centres.T, c=colours, s=8, zorder=4)
        points = [r for r in spatial["samples"] if r["scores"]["convex"][metric] is not None]
        c.scatter(*np.asarray([r["point"] for r in points], dtype=float).T,
                  c=[scale.to_rgba(r["scores"]["convex"][metric]) for r in points], marker="s", s=9, zorder=4)
        fig.colorbar(scale, ax=[a,b,c], shrink=.65, orientation="horizontal")
    fig.suptitle("Flat 40 · Certified maximal convex spaces · comparable covers unavailable elsewhere")
    finish(pdf, fig)


def distributions(pdf, data, summaries, matched):
    for kind in KINDS:
        keys = ("flat40-31-H",) if kind == "convex" else matched
        fig, axes = plt.subplots(2, 3, figsize=(13, 8), layout="constrained")
        for row, metric in zip(axes, ("integration", "choice")):
            values = {k: np.sort([r[metric] for r in data[k][kind][1].values()]) for k in keys}
            bins = np.histogram_bin_edges(np.concatenate(list(values.values())), bins=20)
            for key, series in values.items():
                row[0].hist(series, bins=bins, weights=np.ones(len(series))/len(series),
                            histtype="step", label=name(key))
                row[1].step(series, np.arange(1, len(series)+1)/len(series), where="post")
                if metric == "integration":
                    kind_rows = data[key][kind][1]
                    row[2].scatter([r["connectivity"] for r in kind_rows.values()],
                                   [r[metric] for r in kind_rows.values()], s=7, alpha=.48)
                else:
                    row[2].plot(np.r_[0, np.arange(1, len(series)+1)/len(series)],
                                np.r_[0, np.cumsum(series)/series.sum()] if series.sum()
                                else np.zeros(len(series)+1))
            row[0].set(title=f"{metric.title()} histogram", ylabel="Fraction of nodes")
            row[1].set(title=f"{metric.title()} ECDF", ylabel="Cumulative fraction")
        axes[0,0].legend(fontsize=7)
        axes[0,2].set(title="Intelligibility", xlabel="Degree", ylabel="Integration")
        axes[1,2].plot((0,1),(0,1), color="#aaaaaa", linestyle="--")
        axes[1,2].set(title="Choice concentration", xlabel="Fraction of elements", ylabel="Cumulative choice share")
        fig.suptitle(LABELS[kind])
        finish(pdf, fig)


def spatial_page(pdf, case, spatial):
    fig, axes = plt.subplots(2, 3, figsize=(12, 9), layout="constrained")
    for panel, metric in zip(axes, ("integration", "choice")):
        for ax, kind in zip(panel, ("axial", "segment", "convex")):
            data = [r for r in spatial["samples"] if r["scores"][kind][metric] is not None]
            scale = mapper([r["scores"][kind][metric] for r in data])
            base(ax, case, f"{kind.title()} {metric}")
            ax.scatter(*np.asarray([r["point"] for r in data], dtype=float).T, s=10, marker="s",
                       c=[scale.to_rgba(r["scores"][kind][metric]) for r in data], zorder=4)
            fig.colorbar(scale, ax=ax, shrink=.8, orientation="horizontal")
    fig.suptitle("Flat 40 · Common sampled locations, representation-specific colour scales")
    finish(pdf, fig)


def fixtures_page(pdf, fixtures):
    descriptions = {"straight": "Straight chain · zero turn", "corner": "Right angle · 90°",
                    "tee": "T-junction · 0° and 90°", "cross": "Crossroads · 0° and 90°",
                    "loop": "Rectangle · two opposite routes", "unequal_length_tie": "Equal angular, different length",
                    "same_junction": "Teleportation excluded", "reversal": "Physical U-turn · 180°"}
    fig, axes = plt.subplots(2, 4, figsize=(13, 6), layout="constrained")
    for ax, (key, result) in zip(axes.flat, fixtures.items()):
        for row in result["angular"]["geometry"]:
            x,y = zip(*row)
            ax.plot(x,y, color="#256685", marker="o", lw=2)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_title(descriptions[key], fontsize=10)
        ax.set_axis_off()
    fig.suptitle("Directed traversal fixtures · independent exhaustive route checks")
    finish(pdf, fig)


def comparison_plots(pdf, summaries, matched):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    for ax, field in zip(axes.flat, ("intelligibility", "gini", "top_10_share", "dispersion")):
        for kind in KINDS[:-1]:
            values = []
            for key in matched:
                s = summaries[key][kind]
                if field == "intelligibility":
                    value = s["intelligibility"]["r"]
                elif field == "dispersion":
                    value = s["measures"]["integration"]["iqr"]
                else:
                    value = s["choice_concentration"][field]
                values.append(value)
            ax.plot(range(len(matched)), values, marker="o", label=LABELS[kind])
        ax.set(xticks=range(len(matched)), xticklabels=[name(k).replace(" 40","") for k in matched],
               title=field.replace("_"," ").title())
        ax.tick_params(axis="x", labelrotation=18)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("Six matched seed 40 settlements · one observation per terrain")
    finish(pdf, fig)


def report(out, cases, matched, summaries, audit, seed, spatial, routes):
    lines = ["# Six-terrain configurational pilot", "",
             "## A–B. Angular audit and corrected Flat 40 reference", "",
             "The historical model assigns deflections to edges of an undirected segment adjacency graph. A shortest walk has no arrival heading, so two consecutive edges can reuse the same junction without travelling the intervening segment. The three-arm fixture yields 28.072486° along such an adjacency walk and 151.927513° in the continuous model. A physical reversal uses a 180° endpoint transition and traverses the segment back. The directed model passed independent exhaustive state-path and path-multiplicity comparisons, including an equal-angle pair where the labelled metric tie-break removes one route.", "",
             "Topological degree, hop depth, integration, choice and intelligibility reproduced the frozen pilot. The historical angular implementation also replayed without discrepancy. The correction retains the same segment elements and degree; it changes the set of admissible angular paths. Its centrality counts all tied optimal routes between physical segment midpoints, with both endpoint orientations free.", "",
             "| Reference | Depth old → continuous (°) | Integration old → continuous | Mean choice old → continuous | Intelligibility old → continuous | Choice Gini old → continuous | Top-10 overlap |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for label, row in audit.items():
        old, new = row["historical"], row["continuous"]
        fields = [" → ".join(f"{x['measures'][m]['mean']:.5f}" for x in (old,new)) for m in ("mean_depth","integration","choice")]
        fields += [" → ".join(f"{x['intelligibility']['r']:.5f}" for x in (old,new)),
                   " → ".join(f"{x['choice_concentration']['gini']:.5f}" for x in (old,new))]
        lines.append(f"| {label} | " + " | ".join(fields) + f" | {row['top10_overlap']}/10 |")
    for label, row in audit.items():
        counts = row["pair_counts"]
        old_top, new_top = row["top10_historical"], row["top10_continuous"]
        old_highest, new_highest = old_top[0]["id"], new_top[0]["id"]
        entrants = sorted({item["id"] for item in new_top} - {item["id"] for item in old_top})
        lead = (f"Atom {new_highest} remains highest-choice." if old_highest == new_highest
                else f"The highest-choice atom changes from {old_highest} to {new_highest}.")
        lines.append(f"\n{label} changed {counts.get('higher',0)+counts.get('lower',0):,} angular pair costs "
                     f"({counts.get('higher',0):,} higher, {counts.get('lower',0):,} lower). "
                     f"{lead} New top-ten atoms are {entrants}.")
    lines += ["", "Archived doorway routes are a different, terminal-specific check. Mean angular costs are "
              f"{routes['31-H']['angular']:.5f} and {routes['29-H']['angular']:.5f} for 31-H and 29-H respectively.",
              "", "## C–D. Comparable inputs", "",
              "Six corrected settlements share seed 40, 100 buildings, a 100 × 100 study canvas, a 500-point Voronoi generator and the same facewise aggregation settings. The archived Valley terrain is Converging Valleys. Its verified main accessible component is much smaller than the others. The controlled axial and segment comparison uses the same archived C-H procedure throughout, including Flat's 34-H historical control. The certified Flat 31-H and 29-H remain the method reference and sensitivity pair. Flat 41 is the sole supplementary C-H seed. The remaining 29 cases have no archived C-H inventory in the benchmark. Their source stage files are present on the shared drive and are audited separately under the archived strict-backward method.", "",
              "| Case | Accessible area | Occupied area | Candidates | C-H lines | Archived regional polygons | Certified maximal polygons |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for key, case in cases.items():
        x = case.inventory
        lines.append(f"| {name(key)} | {x['accessible_area']:.2f} | {x['occupied_area']:.2f} | "
                     f"{x['certified_candidates']} | {x['archived_CH_lines']} | {x['archived_regional_representation']} | "
                     f"{x['maximal_convex'] or 'Unavailable'} |")
    lines += ["", "Individual areas in the table are numerical summaries of saved WKB. Exact axial endpoints and overlaps are retained in the graph exports. The archived regional polygons are the earlier coverage representation. A verified complete globally maximal cover is available only for Flat 40, so there is no six-terrain maximal-convex comparison.",
              "", "## E–G. Matched configurational contrasts", "",
              "| Terrain | Axial depth / r | Segment-hop depth / r | Angular depth (°) / r | Metric depth / r | Angular choice Gini | Angular choice top 10% |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for key in matched:
        grid = summaries[key]
        values = [f"{grid[k]['measures']['mean_depth']['mean']:.3f} / {grid[k]['intelligibility']['r']:.3f}" for k in KINDS[:-1]]
        choice = grid["angular"]["choice_concentration"]
        lines.append(f"| {name(key)} | " + " | ".join(values) +
                     f" | {choice['gini']:.3f} | {choice['top_10_share']:.1%} |")
    for kind in ("axial","angular"):
        richest = max(matched, key=lambda c: summaries[c][kind]["choice_concentration"]["gini"])
        broadest = max(matched, key=lambda c: summaries[c][kind]["measures"]["integration"]["iqr"])
        lines.append(f"\n{LABELS[kind]} show the greatest observed choice Gini in {name(richest)} "
                     f"and its largest integration IQR in {name(broadest)}.")
    convex = summaries["flat40-31-H"]["convex"]
    lines += ["", f"Flat 40's shared convex graph has {convex['nodes']} nodes and {convex['edges']:,} edges, "
              f"mean depth {convex['measures']['mean_depth']['mean']:.3f}, and intelligibility "
              f"{convex['intelligibility']['r']:.3f}. Exact cover multiplicity areas are exported with the sampled overlay.",
              "", "Integration is reach fraction times inverse one-plus-depth. Degree is the physical adjacency degree even under angular or metric travel. Choice excludes endpoints and distributes equal-path credit. Clustering is unweighted physical clustering. The graph summaries include component sizes, diameters, degree distributions, node dispersion and locations of high-choice elements. Raw depth and integration retain their representation-specific units and meaning.",
              "", "## H. Seed sensitivity", ""]
    for kind in ("axial","segment","angular","metric"):
        row = seed[f"{kind}/intelligibility"]
        lines.append(f"- {LABELS[kind]} intelligibility spans {row['matched_terrain_range']:.3f} across six seed-40 cases. "
                     f"Flat 40 versus Flat 41 changes by {row['flat_absolute_seed_difference']:.3f}.")
    lines += ["", "Two Flat seeds provide one within-terrain contrast for C-H. Each other terrain has a single independently realised settlement in that cohort. The separate strict-backward seed audit keeps the selection method fixed across the wider cohort. The observed ranges are descriptive and cannot separate seed, terrain and settlement morphology effects.",
              "", "## I. Spatial relationships", "",
              f"The Flat 40 lattice supplies {len(spatial['samples'])} accessible locations and "
              f"{spatial['all_three_count']} with all three representations present. Nearest line and segment assignments "
              "and polygon coverage were evaluated with rational predicates. The sampled fields use axial hop scores, "
              "continuous angular segment scores and convex hop scores."]
    for metric in ("integration","choice"):
        scores = spatial["pearson"]
        formatted = [f"{a}–{b} {scores[f'{metric}:{a}:{b}']:.3f}" for a,b in combinations(("axial","segment","convex"),2)]
        lines.append(f"\n{metric.title()} field Pearson r is " + ", ".join(formatted) + ".")
    lines += ["", "These correlations describe spatial co-location at the specified lattice and radius. They can vary with sampling scale, decision to average covering polygons, and line proximity thresholds.",
              "", "## J. Remaining evidence", "",
              "A controlled maximal-convex comparison requires five separately checkpointed exhaustive covers with certificates for their own accessible domains. Further C-H seed inference requires reduced inventories beyond the seven saved cases. The present contrasts combine topography, changes in accessible area and building/open-space morphology mediated by aggregation.",
              "", "[Vector atlas](atlas.pdf) · [Frozen definitions](configuration.json) · [Source inventory](source-inventory.json) · "
              "[Verified hashes](verified-hashes.json) · [Metrics](statistics.json) · [Comparison CSV](terrain-comparison.csv) · "
              "[Angular fixtures](angular-fixtures.json) · [Angular audit](flat40-angular-audit.json) · "
              "[Spatial overlay](flat40-spatial-overlay.json) · [Runtime](runtime.json)"]
    (out/"report.md").write_text("\n".join(lines)+"\n")


def exports(out, cases, matched, terrain, reference, summaries, audit, seed, spatial, fixtures, routes):
    with (out/"terrain-comparison.csv").open("w", newline="") as stream:
        columns = ["case", "role", "representation", "nodes", "edges", "components", "mean_degree",
                   "mean_depth", "mean_integration", "integration_iqr", "mean_choice",
                   "intelligibility", "observations", "pearson_defined", "clustering", "diameter", *CHOICE]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for key, row in summaries.items():
            role = "matched" if key in matched else "supplementary seed" if key in cases else "Flat 40 reference"
            for kind, s in row.items():
                writer.writerow(dict(case=key, role=role, representation=kind, nodes=s["nodes"], edges=s["edges"],
                    components=len(s["components"]), mean_degree=s["measures"]["connectivity"]["mean"],
                    mean_depth=s["measures"]["mean_depth"]["mean"], mean_integration=s["measures"]["integration"]["mean"],
                    integration_iqr=s["measures"]["integration"]["iqr"], mean_choice=s["measures"]["choice"]["mean"],
                    intelligibility=s["intelligibility"]["r"], observations=s["intelligibility"]["observations"],
                    pearson_defined=s["intelligibility"]["defined"], clustering=s["mean_unweighted_local_clustering"],
                    diameter=s["diameter"], **s["choice_concentration"]))
    data = terrain | {"flat40-31-H": reference["31-H"]}
    with PdfPages(out/"atlas.pdf") as pdf:
        cohort_rows = [f"{name(k):24}    {cases[k].inventory['accessible_area']:8.2f} units² accessible    "
                       f"{cases[k].inventory['archived_CH_lines']:2} axial lines    "
                       f"{'596 certified maximal polygons' if k=='flat-40' else 'maximal cover unavailable'}" for k in matched]
        text_page(pdf, "Source inventory and comparability", [
            "All six cases use seed 40, 100 buildings, a 100 × 100 canvas and the same corrected facewise aggregation.",
            "\n".join(cohort_rows), "Flat 41 provides one additional C-H observation. The remaining 29 lack archived C-H inventories."])
        fixtures_page(pdf, fixtures)
        audit_page(pdf, audit)
        terrain_maps(pdf, cases, matched, terrain)
        convex_maps(pdf, cases["flat-40"], reference["31-H"]["convex"], spatial)
        comparison_plots(pdf, summaries, matched)
        distributions(pdf, data, summaries, matched)
        spatial_page(pdf, cases["flat-40"], spatial)
        text_page(pdf, "Scope of the observed differences", [
            "Continuous angular paths join matching endpoints and retain all optimal directed ties.",
            "The matched axial comparison uses the same historical C-H procedure for all terrains.",
            "Five terrains lack independently certified complete maximal convex covers.",
            "Valley differs in accessible-component area as well as local configuration.",
            "One settlement per terrain and two Flat seeds support descriptive contrasts."])
    report(out, cases, matched, summaries, audit, seed, spatial, routes)
