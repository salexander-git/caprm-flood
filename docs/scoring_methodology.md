# Scoring Methodology

**Status:** preliminary
**Scoring policy version:** `preliminary_exposure_index_v2`
**Written:** 2026-07-16
**Roadmap chunks:** A1 reconstruction, A2 hardening, A3 sensitivity, A4 audit

---

## Purpose and standing

This document records what the scoring layer does, including its limitations.

Every statement traces to one of two places:

- **Source:** `python/caprm/scoring.py`, `python/caprm/sensitivity.py`.
- **Measured:** a generated artifact, cited by file.

Sections marked **⚠ Limitation** record behavior that is understood and
accepted. Sections marked **⚠ Open** record work that remains.

Measured values come from a countywide run on 2026-07-16 against:

```text
evidence  sha256 4e0d27e14b30aba4c2afb350b9c58d6b4384f951db7252831c29df8487bd75f2
terrain   sha256 e7768c538b41639032af176bd789bec76137c29348bc9be931ca7b4c44e5d3de
index     sha256 3cae2e830a5867bee4d51a36f1c5c04f05ee0a6a26d64dace27da75d3c4911b0
```

Supporting artifacts:

```text
outputs/validation/property_exposure_index_countywide_manifest.json
outputs/validation/scoring_inputs_summary.json
outputs/validation/component_correlation_summary.json
outputs/validation/scoring_sensitivity_manifest.json
outputs/validation/milestone3_audit.json
```

---

## 1. Position in the pipeline

Scoring is **downstream** of evidence extraction and does not modify it.

```text
property_flood_evidence_countywide.csv     (FEMA + water evidence, Milestone 2)
property_terrain_evidence_countywide.csv   (terrain evidence, Milestone 3)
                    │
                    ▼
          caprm.scoring.build_exposure_index
                    │
                    ▼
property_exposure_index_countywide.csv     (derived index)
```

`build_exposure_index` operates on copies of both inputs and its output
columns are entirely derived. No code path writes back into an evidence
table.

---

## 2. The four components

The index has **four components, each with one declared weight**. There are
no nested or internal sub-weights.

$$
I_i = \sum_{k} w_k \cdot C_{k,i}
\qquad \sum_k w_k = 1, \quad w_k \geq 0
$$

| Component | Raw evidence | Normalization | Direction | Weight |
|---|---|---|---|---:|
| `fema` | `fema_zone`, `matched_fema_polygon` | absolute lookup | higher severity ⇒ higher | 0.40 |
| `water` | `nearest_water_distance_m` | percentile rank | nearer ⇒ higher | 0.35 |
| `terrain_absolute` | `terrain_elevation_m` | percentile rank | lower ⇒ higher | 0.15 |
| `terrain_relative` | `terrain_relative_elevation_m` | percentile rank | lower ⇒ higher | 0.10 |

Expanded:

$$
I_i = 0.40\,C_{\text{fema},i}
    + 0.35\,\text{pct}(-d_i)
    + 0.15\,\text{pct}(-e_i)
    + 0.10\,\text{pct}(-r_i)
$$

where $d_i$ is nearest-water distance in meters, $e_i$ is elevation in
meters, and $r_i$ is relative elevation in meters.

**These four weights plus the two evidence tables are sufficient to
reproduce the index.** The manifest records them, so a third party can
recompute the result without reading source code. That property is a
requirement, not a convenience, and `audit_milestone3_products.py` verifies
it against the stored artifact on every run.

### Provenance of the weights

The values were inherited from the retired v1 policy, which applied 0.25 to
a terrain component split internally 0.60 absolute / 0.40 relative:

```text
0.25 × 0.60 = 0.15    terrain_absolute
0.25 × 0.40 = 0.10    terrain_relative
```

Scoring is linear, so the flat and nested forms are algebraically
identical. Verified across the countywide workload at a maximum absolute
difference of `5.0e-13`, and locked by
`test_flat_weights_reproduce_legacy_nested_policy`.

**Why the nesting was removed.** The sub-weights were absent from
`DEFAULT_WEIGHTS`, unchecked by `validate_weights`, and absent from every
manifest. The consequence was not cosmetic: **the manifest could not
reproduce the score.** A reader with the manifest and both evidence tables
still had to open `scoring.py` to find the missing constants.

> **⚠ Open — the weights are a judgement call.**
> No source, manifest, or document justifies 0.40 / 0.35 / 0.15 / 0.10.
> They are not learned, not calibrated, and not derived from any external
> reference. Section 12 measures how much the ranking depends on them.

---

## 3. Inputs consumed

### From the FEMA/water evidence table

| Column | Used for |
|---|---|
| `property_id` | join key, validation |
| `matched_fema_polygon` | FEMA component |
| `fema_zone` | FEMA component |
| `is_sfha` | **validation only — does not score** |
| `nearest_water_distance_m` | water component |
| `distance_crs` | CRS gate |

The evidence table has 24 columns; scoring reads 6.

### From the terrain evidence table

| Column | Used for |
|---|---|
| `property_id` | join key, validation |
| `terrain_elevation_m` | terrain_absolute component |
| `terrain_relative_elevation_m` | terrain_relative component |
| `terrain_crs` | CRS gate |

`terrain_slope_degrees` is **not required**. Slope is extracted and
preserved as terrain evidence but does not enter any component, so
requiring it would reject a terrain table over a column scoring never
reads.

> **⚠ Open — slope is unused evidence.**
> Whether slope should have a component is a methodology question, not a
> defect. The directionality is not obvious: steep slope implies runoff,
> flat implies ponding. Deferred rather than guessed.

### Measured input domain

**FEMA zone × SFHA, countywide:**

```text
matched   X    not SFHA   262,297
matched   AE   SFHA         4,226
matched   A    SFHA           408
matched   AO   SFHA           388
matched   VE   SFHA            39
unmatched      no zone          4
                          -------
                          267,362
```

Exactly five mapped zone values occur. SFHA status is perfectly determined
by zone in this dataset: every matched non-X zone is SFHA; X never is. This
is a property of the current data, **not** a guarantee of the FEMA schema.

**Nearest-water distance:** 0.0 – 2,630.235 m; mean 506.411; median
325.346; 0 nulls; 266 properties at exactly 0.0 (inside a waterbody).

**Terrain elevation:** 75.000 – 296.309 m; mean 143.197; median 146.828;
0 nulls.

**Terrain relative elevation:** −20.669 – +30.149 m; mean 0.247; median
0.175; 0 nulls.

**CRS:** `distance_crs` and `terrain_crs` each contain exactly one distinct
value, `EPSG:26918`.

---

## 4. Preconditions

`build_exposure_index` raises before computing any score unless all hold:

| Check | Failure |
|---|---|
| Required columns present in both tables | `ValueError` listing missing columns |
| `property_id` non-null and unique in both | `ValueError` |
| `set(distance_crs) == {"EPSG:26918"}` | `ValueError: Evidence distance CRS mismatch` |
| `set(terrain_crs) == {"EPSG:26918"}` | `ValueError: Terrain CRS mismatch` |
| Inner join is one-to-one | merge validation error |
| `len(merged) == len(evidence)` | `ValueError: Scoring merge lost property rows` |
| No property is SFHA without a polygon match | `ValueError` |
| Every matched zone appears in `FEMA_ZONE_SCORES` | `ValueError` |
| Every output column within `[0, 100]` | `RuntimeError` |

### Missing-value policy

**There is no imputation anywhere in the scoring layer.** Every missing,
non-finite, or unparseable input raises.

---

## 5. The percentile transform

Three of the four components are built on one function.

$$
\text{pct}(v_i) = \frac{\text{rank}_{\text{avg}}(s_i)}{n} \times 100
\qquad
s_i = \begin{cases}
v_i & \text{higher} \Rightarrow \text{higher exposure} \\
-v_i & \text{otherwise}
\end{cases}
$$

**Properties:**

- **Range** $(0, 100]$. The minimum attainable score is $100/n$, not 0.
  Countywide: `0.00037402473051518164`.
- **Ties** receive the mean of the ranks they span. Deterministic and
  order-independent.
- **Mean** fixed at $\frac{n+1}{2n} \times 100$ by construction. Countywide:
  `50.00018701236526` — measured identically for all three percentile
  components.
- **Standard deviation** fixed at $\approx 100/\sqrt{12} = 28.8675$, the
  standard deviation of a uniform distribution. Measured `28.8675674` for
  all three.
- **Direction by negation**, not by reversing the rank.

> **⚠ Limitation — rank-preserving, magnitude-destroying.**
> Only the ordering of the input survives. A property 5 m from a stream and
> one 50 m away may sit at adjacent percentiles.

> **⚠ Limitation — distribution dependence.**
> Percentile scores are computed over the rows supplied. Scoring a subset
> yields different scores for the same property. The index is meaningful
> only for the full countywide workload, and values are not comparable
> across workloads or NFHL vintages.

> **⚠ Limitation — silent degenerate branch.**
> A component whose input has one unique value returns a constant 50.0 for
> every property. Unreachable at countywide scale. Tested; deliberate — a
> constant input carries no ranking information, and the midpoint is more
> honest than asserting an ordering.

---

## 6. Component: FEMA

**Absolute, not distribution-dependent.** A zone maps to the same score
regardless of what other properties are present. This is the only component
with that property.

```python
FEMA_ZONE_SCORES = {"X": 10.0, "AO": 80.0, "A": 90.0, "AE": 95.0, "VE": 100.0}
UNMATCHED_FEMA_SCORE = 0.0
```

| Zone | Score | Meaning | Count |
|---|---:|---|---:|
| `VE` | 100.0 | Coastal high hazard, wave action | 39 |
| `AE` | 95.0 | 1% annual chance, base flood elevation determined | 4,226 |
| `A` | 90.0 | 1% annual chance, no BFE determined | 408 |
| `AO` | 80.0 | Shallow flooding, 1–3 ft sheet flow | 388 |
| `X` | 10.0 | Outside the 0.2% annual chance floodplain | 262,297 |
| *(unmatched)* | 0.0 | No polygon contains the point | 4 |

**Mean:** `11.580179681480539`. **Standard deviation:** `11.391420439036462`.

### Unrecognized zones raise

A matched property carrying any zone absent from `FEMA_ZONE_SCORES` raises,
reporting the observed zones and example property IDs.

**Why raise rather than default.** A silent default would score an
unmapped-but-real zone at 0.0 — *below* zone X's 10.0 — inverting the
severity ordering with no error. A `0.2 PCT ANNUAL CHANCE FLOOD HAZARD`
zone would rank as less exposed than a property outside the floodplain
entirely. A future NFHL vintage or another county could introduce `AH`,
`AR`, `A99`, or `D` at any time.

### `is_sfha` is validated, not scored

Special Flood Hazard Area status is implied by the zone, so scoring both
would double-count one signal. It is still required, and enforces one
invariant: **a property cannot be SFHA without matching a flood-hazard
polygon.** That is a FEMA invariant, not a property of one dataset.

The v1 policy applied `is_sfha & score < 80 → 90` as an override. It was
**unreachable**: all 5,061 SFHA properties already score ≥ 80 from zone
alone. Removed rather than left as dead, untested code.

---

## 7. Component: Water

**Pure rank inversion.** No threshold, no decay curve, no cap.

$$
C_{\text{water},i} = \frac{\text{rank}_{\text{avg}}(-d_i)}{n} \times 100
$$

Raises on non-finite or negative distances.

**Measured:** mean `50.00018701236526`; std `28.8675674297175`; min
`0.000374`; max `99.950442`. The 266 properties at distance 0.0 share the
top tied rank.

---

## 8. Components: Terrain

Two independent components, scored separately.

$$
C_{\text{terrain\_absolute},i} = \text{pct}(-e_i)
\qquad
C_{\text{terrain\_relative},i} = \text{pct}(-r_i)
$$

`terrain_relative_elevation_m = terrain_elevation_m −
terrain_local_mean_elevation_m`, where the local mean is taken over a square
window of half-width `ceil(90 m / pixel size)`. Positive means the property
sits above its immediate surroundings. Measured mean `+0.247 m` —
consistent with construction on locally higher ground.

**Why two components and not one.** Absolute elevation measures position in
the county; relative elevation measures position within the immediate
neighbourhood. Measured Spearman between them: **−0.006**. Statistically
independent.

They are grouped as one evidence family because they derive from the same
DEM, which is a **provenance** relationship. A scoring weight expresses what
a component *means*, which is a different question. Sharing a source raster
is not a reason to share a weight budget.

---

## 9. Component redundancy — measured

Rank correlation between all four components, countywide:

| | fema | water | terrain_abs | terrain_rel |
|---|---:|---:|---:|---:|
| **fema** | 1.000 | 0.152 | −0.004 | 0.087 |
| **water** | 0.152 | 1.000 | 0.102 | −0.069 |
| **terrain_abs** | −0.004 | 0.102 | 1.000 | −0.006 |
| **terrain_rel** | 0.087 | −0.069 | −0.006 | 1.000 |

**Largest pairwise correlation: 0.152.** The components are near-orthogonal.
No component duplicates another.

This was measured specifically to test whether low absolute elevation was
shadowing water distance — the county's elevation floor is 75.0 m and Lake
Ontario sits at ~74.2 m, so low absolute elevation substantially means *near
the lake*, and the lake is a waterbody in the hydrography cache. **It is
not:** `water ↔ terrain_absolute` is 0.102. Water distance is local —
nearest of 5,600 flowlines and 2,972 waterbodies — so it does not track
regional elevation.

**Tail dependence exceeds global correlation.** In the top decile,
`water ↔ terrain_relative` overlap is 23.8% against ~10% expected by chance,
despite a global correlation of −0.069. Physically plausible: properties
near water usually sit on raised banks, but the extreme cases sit in
depressions near water — the floodplain signature. The relationship is
non-monotonic, so rank correlation alone would miss it.

---

## 10. The composite is rounded before ranking

```python
COMPOSITE_DECIMALS = 9
```

The composite is rounded to 9 decimal places before it is stored or ranked.

**Why.** Under any percentile-based weighting the composite lies on a
lattice. Each percentile component is $\text{rank} \times 100/n$ with ranks
in half steps, so with the default weights:

$$
I = 0.40\,C_{\text{fema}} + \frac{100}{n}\left(0.35 r_w + 0.15 r_{ta} + 0.10 r_{tr}\right)
$$

and the bracket is $0.05 \times (7 r_w + 3 r_{ta} + 2 r_{tr})$ — a multiple
of $2.5/n$, about **9.4e-6** countywide. Distinct rank triples collide on
that lattice constantly: many properties have **mathematically identical
composites**.

Float arithmetic separates a colliding pair by around `1e-14`, depending on
operation order. Ranking the unrounded value therefore:

1. imposes an ordering on properties tied in substance, sourced from
   rounding order rather than evidence — the same category of error as
   percentile-ranking the FEMA component to manufacture spread, which this
   project rejects;
2. breaks reproducibility, because writing the index at 12 decimal places
   re-merges the pair, so **the stored percentile could not be recomputed
   from the stored index**.

Measured before the fix: recomputing the percentile from the stored index
disagreed by up to `1.066e-02` percentile points — about 28.5 ranks,
implying a tie group of roughly 58 properties split by float noise.

**Why 9 decimals.** The lattice spacing is `9.4e-6`. Rounding at `1e-9` sits
four orders of magnitude below the smallest distinction the lattice can
express and five above float noise. It merges only values tied in substance.
The constant has a derivation rather than being a guess.

`caprm.sensitivity.score_scenarios` applies the same rounding, so every
scenario ranking is built on the same rule as the baseline and remains
comparable to it.

Locked by `test_percentile_reproduces_from_the_stored_index` and verified
against the stored artifact by `audit_milestone3_products.py`.

---

## 11. Composite, ranking, and output

### Verification against the artifact

**Measured index:** min `7.914598933`, max `99.929084911`, mean
`34.63218408001099`, median `33.7284299935`, std `13.063711939924076`.

Independent recomputation from the evidence tables agrees with the shipped
artifact to `5.0e-10`, which is the half-ulp of `round(9)` — bounded by
construction, not by float noise.

### Bounds

All component and composite columns are checked against `[0, 100]`; a
violation raises `RuntimeError`. **No clipping occurs** — out of range is
treated as a bug, not corrected. The bounds hold structurally: a convex
combination of values in `[0, 100]` cannot leave `[0, 100]`.

### Percentile and ordering

$P_i = \text{pct}(I_i)$, not inverted. Measured min
`0.00037402473051518164`, max `100.0`. Ties receive equal percentiles.
**There is no integer rank column.**

Output is sorted by `property_id` with a stable sort — **not** by score — so
ordering is deterministic and independent of input row order.

### Output schema

```text
property_id
fema_component_0_100
water_component_0_100
terrain_absolute_component_0_100
terrain_relative_component_0_100
exposure_index_0_100
exposure_percentile
scoring_policy_version
```

Written with `float_format="%.12f"`. 267,362 rows, 267,362 unique IDs.

> **⚠ Open — the index retains no evidence.**
> The output carries no `fema_zone`, no `nearest_water_distance_m`, no
> elevation. Explaining one property's score requires a manual three-way
> join. An `explain_property.py` tool is planned; it preserves the
> evidence/scoring separation rather than duplicating evidence into a
> derived product.

---

## 12. Nominal weight is not influence

Weight alone does not determine how much a component moves the ranking.
Influence scales with **weight × spread**, and the components do not have
equal spread.

| Component | Weight | Std | Variance share | Spearman vs index |
|---|---:|---:|---:|---:|
| `water` | 0.35 | 28.868 | **0.653** | 0.893 |
| `fema` | 0.40 | 11.391 | **0.168** | 0.235 |
| `terrain_absolute` | 0.15 | 28.868 | **0.135** | 0.431 |
| `terrain_relative` | 0.10 | 28.868 | **0.043** | 0.167 |

Shares sum to 1.0000000000000006.

**Water carries 35% of the weight and 65% of the variance. FEMA carries 40%
of the weight and 17%.**

### Why

The three percentile components are uniform by construction, so their
standard deviation is pinned at $100/\sqrt{12} = 28.87$. The FEMA component
is a lumpy near-constant: **262,297 of 267,362 properties (98.1%) are tied
at 10.0**, giving a standard deviation of 11.39, under half.

FEMA's 90th-percentile threshold is therefore **10.0**, which selects
267,358 properties — 99.998% of the county. **The FEMA component cannot
define a top decile.** It discriminates only at the 1.9% level.

### Why this is not a defect

**FEMA adds a constant 4.0 to 98.1% of properties, and constants do not
affect ranking.** Its actual role is to identify the 1.9% it has information
about and move them decisively: an AE property receives
`0.40 × (95 − 10) = +34` on a composite whose standard deviation is 13.06 —
**+2.6 standard deviations**.

The low rank correlation is not measuring a weighting error. It measures the
fact that **FEMA says "zone X" for 98% of the county and genuinely has
nothing further to say about them**. The component reports that faithfully.
Water and terrain then rank the properties FEMA is silent on.

**Rejected alternative:** percentile-ranking the FEMA component to give it
comparable spread. That would smear 262,297 identical zone-X properties
across ranks 0–98, inventing distinctions the source data does not contain.

### Method

`variance_share` is $\text{Cov}(w_k C_k, I) / \text{Var}(I)$. By linearity
of covariance, $\sum_k \text{Cov}(w_k C_k, I) = \text{Var}(I)$, so the
shares sum to exactly 1.0 **without assuming the components are
uncorrelated**. This matters: an orthogonality-assuming estimate predicts
water 0.681 and fema 0.139, wrong in both directions because FEMA
correlates +0.152 with water and terrain_relative correlates −0.069 with it.

Spearman is computed as the Pearson correlation of ranks, which is the
definition when ties are present. This avoids adding scipy for one
statistic, and avoids a pandas asymmetry:
`DataFrame.corr(method="spearman")` uses an internal implementation while
`Series.corr(method="spearman")` requires scipy.

---

## 13. Sensitivity — measured

**Verdict: moderately sensitive.**

40 scenarios: 1 baseline, 1 equal-weighted, 8 single-component
emphasized/deemphasized (×2 / ×0.5, renormalized), 2 terrain-family, 24
seeded Dirichlet perturbations around the baseline, and 4 reference corners.

| Measure | Value | Scenario |
|---|---:|---|
| Minimum Spearman vs baseline | **0.875** | `equal` |
| Median Spearman vs baseline | 0.996 | |
| Minimum top-decile overlap | **0.761** | `equal` |
| Median top-decile overlap | 0.946 | |
| Maximum percentile shift | 47.5 | |
| Median of median percentile shift | 1.56 | |

### Declared thresholds

| Verdict | Min Spearman | Min top-decile overlap |
|---|---:|---:|
| stable | 0.95 | 0.80 |
| moderately sensitive | 0.85 | 0.60 |

Declared in `caprm.sensitivity` **before any result was measured**. They are
a judgement call with no external standard. Choosing them after inspecting
the output would make the verdict unfalsifiable.

The verdict is driven by the **worst** plausible scenario, not the average.
An index that survives most reweightings but collapses under one plausible
reweighting is not stable.

### The metrics discriminate

| | Spearman | top-decile overlap |
|---|---|---|
| reference corners | 0.167 – 0.893 | ≥ 0.289 |
| plausible scenarios | 0.875 – ~1.0 | ≥ 0.761 |

This calibration is why the numbers above can be interpreted at all. Three
of four components are percentile ranks, and reweighting a linear sum of
rank variables tends to preserve order — so a high correlation could have
been an artifact of the design rather than a finding. **It is not.** The
corners span a wide range, so the metric can tell configurations apart.

### The baseline is substantially a water ranking

**`water_only` correlates 0.893 with the baseline. `equal` correlates
0.875.**

Putting 100% of the weight on water alone reproduces the baseline ranking
**better** than weighting all four components equally.

This follows directly from water's 65% variance share: the baseline already
*is* substantially a water ranking. Equal weighting cuts water to 25% and
promotes `terrain_relative` — which correlates 0.167 with the baseline
ranking — from 0.10 to 0.25. That moves more mass than going all-in on
water.

The honest characterization is that the index is **a water-proximity
ranking with a decisive FEMA correction on the 1.9% of properties FEMA has
information about**, adjusted by terrain. It should not be described as
though all four components contribute comparably.

### The verdict hinges on one scenario

Every other plausible scenario — all 24 perturbations, all 8
single-component reweightings, both terrain-family scenarios — sits near
0.996. **`equal` alone drags the verdict down.** This is not general
instability; it is one specific, explainable sensitivity: *the index is
stable unless you stop privileging water.*

`equal` stays in the family. "Weight everything the same because I don't
want to assume" is the most obvious default a reviewer would reach for.

### The extremes never move; the middle churns

| | percentile range across 36 plausible scenarios |
|---|---|
| top-ranked properties | **0.0004** |
| bottom-ranked properties | 0.02 – 0.25 |
| median property | **18.0** |
| 77.6% of properties | > 10 points |
| 25.8% of properties | > 25 points |
| worst property | 63.0 |

All 20 most-unstable properties have a baseline percentile between **59 and
66** — dead middle. They swing from roughly the 16th to the 80th percentile
depending on weights. The top of the ranking is immovable to four decimal
places.

**This is the most defensible property of the index.** A VE-zone property
sitting in water at low elevation is top-ranked under every weighting.
Weight choice matters only for properties with genuinely mixed evidence —
high on one component, low on another — which is exactly where it *should*
matter.

**One-line summary: the index reliably identifies the extremes; the middle
ordering depends on weighting assumptions.**

---

## 14. Assumptions and limitations

1. **Rank is a sufficient proxy for exposure** in three of four components.
   Magnitude is discarded.
2. **The FEMA lookup values** (10/80/90/95/100) express relative severity on
   a scale commensurable with percentile ranks. Neither the values nor the
   commensurability is externally justified.
3. **The weights are undocumented judgement calls.** Section 13 measures how
   much the ranking depends on them.
4. **Linear additive combination** assumes components substitute for one
   another: a high FEMA score can be offset by a low water score. No
   interaction terms, no minimum-threshold logic.
5. **Centroid representation.** The index describes a property point, not a
   parcel or structure. A centroid can fall outside a hazard polygon while
   part of the parcel intersects it.
6. **Study-area relative.** The index ranks properties within Monroe County
   under one weighting configuration. It is not calibrated flood
   probability, expected loss, insurance pricing, or actuarial risk.

### Validation status

**Established:**

- Composite arithmetic reproduces the artifact to `5.0e-10`.
- The four-weight model reproduces the retired nested policy exactly.
- The stored percentile reproduces from the stored index.
- Percentile component means and standard deviations match their closed
  forms.
- Every component's directionality is tested.
- Determinism and row-order independence are tested.
- Non-default weights reach the composite and are reported correctly.
- Unrecognized zones, SFHA-without-match, negative distances, non-finite
  values, CRS mismatches, row loss, and duplicate IDs all raise.
- Variance shares sum to 1.0.
- Components are near-orthogonal (max pairwise |ρ| = 0.152).
- Rank stability measured across 40 weight scenarios with declared
  thresholds and metric calibration.
- All four products describe the same 267,362 properties; manifests agree
  with the artifacts on disk.

**Not established:**

- Whether the weights are defensible. Sensitivity measures how much the
  ranking depends on them; it does not establish that they are right.
- Whether the four components are the right components.
- Whether the index corresponds to any real-world flood outcome. **No
  validation against observed flooding has been attempted, and none is
  planned.**

---

## 15. Reproducing

```powershell
.\.venv\Scripts\python.exe python\scripts\build_exposure_index.py
.\.venv\Scripts\python.exe python\scripts\summarize_milestone3_results.py
.\.venv\Scripts\python.exe python\scripts\analyze_scoring_sensitivity.py
.\.venv\Scripts\python.exe python\scripts\summarize_component_correlation.py
.\.venv\Scripts\python.exe python\scripts\summarize_scoring_inputs.py
.\.venv\Scripts\python.exe python\scripts\audit_milestone3_products.py
.\.venv\Scripts\python.exe -m pytest -q
```

The audit exits nonzero on any failure.