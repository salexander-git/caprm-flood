# Errata

Discrepancies between the submitted report and this repository, found by
re-checking every published figure against the artifact that carries it. The
check was run after submission; the report was not revised.

Recorded here rather than corrected in place, because the report is a submitted
document and the repository is the live record. Where the two disagree, the
artifact governs.

The full re-check is in [`docs/evidence_index.md`](evidence_index.md), which
maps each claim to the file and field that establishes it. Everything not
listed below reconciled exactly.

---

## 1. The exact path's per-property cost, Section VIII

**The report states** (Surrogate Feasibility → Inference Cost): "The exact path
costs 35.9 microseconds per property amortized across the countywide batch."
The surrogate's 16–18× advantage is computed against that denominator.

**No artifact carries 35.9.** The figure is produced by no committed code:
neither `caprm.c4_analysis` nor `analyze_c4_inference.py` computes an
exact-path baseline, and `c4_inference_analysis.json` contains no such field. It
appears to be a conversation-side calculation, which is the practice the
project's own analysis rule exists to prevent — every derived number is
supposed to be computed in a script, with a test, and nowhere else.

**What the artifacts do carry**, from
[`b6_benchmark_tables.md`](../outputs/validation/b6_benchmark_tables.md),
segment hierarchy at countywide under original-geometry verification:

```text
34.099 us/property     invocation A   (search 0.205, verification 33.894)
36.004 us/property     invocation B   (search 0.216, verification 35.788)
37.856 us/property     invocation C
```

The three differ by invocation, which is the dispersion the protocol expects and
requires be named. 35.9 sits between A and B and matches none of them; the
closest stored value, 35.788, is invocation B's *verification-only* column
rather than a total.

**Effect on the report's conclusion: none.** The surrogate's advantage is a
factor of roughly sixteen to eighteen against any of the three, and the report's
qualitative claim — that the advantage is a batching advantage rather than a
latency advantage — rests on the batch and thread sweep, not on this
denominator.

**Correct form of the statement.** Quote a single invocation by name, as the
protocol requires: *the exact path costs 34.099 µs/property at countywide under
original-geometry verification, invocation `ladder`*.

**A second reading of the same sentence.** "The exact path" is ambiguous between
the C++ nearest-water query and the whole Python pipeline that produces the
index value the surrogate predicts. Those are different quantities by a large
factor, and only the second is the like-for-like comparison. The pipeline figure
was not available when the report was written; it is now — see
`docs/c4_inference_tables.md` and `outputs/validation/c4_pipeline_cost.json`.

## 2. The bibliography is not in the repository

`docs/report_draft.txt` closes with `\bibliography{caprm_flood}`. No
`caprm_flood.bib` exists here. The only `.bib` files in the tree belong to the
unmodified IEEE capstone template.

Consequences:

- The tracked LaTeX body does not compile standalone. It is also missing its
  preamble — the file opens with a comment block of preamble additions to paste
  after `\documentclass`, and carries no `\begin{document}`. It is the body,
  and it is tracked as a text record of the prose, not as a build input. The
  compiled PDF is the authoritative document.
- **The 23 citation keys cannot be checked against their sources from this
  repository.** They are, in full:

```text
abdullah2021mcda      chengu2025mcda        geopandas2026sjoin    nssl2026floods
allafta2021gis        fema2026fast          kraska2018learned     nysgis2026parcels
boost2026rtree        fema2026hazus         monroe2023hmp         pandey2018spatial
                      fema2026msc           moon2001hilbert       roberts2017cv
                      fema2026nfhl                                shapely2026predicates
                      fema2026nri                                 shapely2026strtree
                      fema2026oneinch                             tancik2020fourier
                                                                  usgcrp2023nca5
```

- **`fema2026fast` is known-suspect.** It supports the sentence "Hazus
  flood-model methodology is implemented in FAST to swiftly analyze
  building-level flood risk" (`docs/report_draft.txt:209`). A FEMA Hazus URL
  stands in for the Flood Assessment Structure Tool, which is a related but
  distinct product. The entry needs replacing with the FAST documentation
  itself.
- Entries in the group later than `kraska2018learned` were not verified against
  their sources before submission. Nothing in the repository depends on any of
  them; the exposure is confined to the report's Related Work section.

## 3. Documentation currency at submission

The report's Section IX states that "the canonical project documentation
currently lags the implementation." It did, and it still does — deliberately.

The three documents under `docs/canon/` are a working record of what was
believed, planned, and decided at each point in development, including
predictions later refuted. Rewriting them to match the finished state would
destroy the property that makes them worth keeping. Each now opens with a
currency notice stating what it is current through and tabulating the claims
that have since changed. The largest was the test count: the canon says 575,
the report said 653, and the suite is now 656.

## 4. Claims that reconciled exactly

Checked and confirmed against artifacts, listed so the scope of the audit is
visible rather than implied: the workload counts (267,362 / 8,572 / 1,063,159 /
1,189,589); the scoring policy and all four weights; the variance decomposition;
the sensitivity verdict and its worst-case scenario; the audit's
49/1/0 and the content of its one warning; five-rung cross-implementation
agreement including the six split-mode cells at 10K and 100K; the maximum
absolute error in both verification modes; the FEMA tie share (262,297 of
267,362, 98.11 percent); the resolve-descent entry counts and seed-quality
statistics; and the surrogate's non-separability from a constant predictor
together with the refuted registered prediction.

The report's test count of 653 was correct at submission. The suite is now 656:
three tests were added afterwards, covering the analysis step that produces the
pipeline-cost table. Every count stated in this repository is the current one.
