# Milestone 3 Results Summary

## Generated Outputs

| Output | Path | SHA-256 |
| --- | --- | --- |
| Terrain evidence | outputs/evidence/property_terrain_evidence_countywide.csv | e7768c538b41639032af176bd789bec76137c29348bc9be931ca7b4c44e5d3de |
| Exposure index | outputs/index/property_exposure_index_countywide.csv | 3cae2e830a5867bee4d51a36f1c5c04f05ee0a6a26d64dace27da75d3c4911b0 |

## Terrain Evidence

| Metric | Value |
| --- | --- |
| Property count | 267362 |
| Unique property IDs | 267362 |
| Minimum elevation m | 75.000 |
| Maximum elevation m | 296.309 |
| Mean elevation m | 143.197 |
| Median elevation m | 146.828 |
| Minimum relative elevation m | -20.669 |
| Maximum relative elevation m | 30.149 |
| Mean relative elevation m | 0.247 |
| Median relative elevation m | 0.175 |
| Missing slope count | 0 |
| Mean slope degrees | 1.906 |
| Median slope degrees | 1.234 |

Slope is preserved as terrain evidence and does not enter the exposure index.

## Preliminary Exposure Index

| Metric | Value |
| --- | --- |
| Property count | 267362 |
| Unique property IDs | 267362 |
| Minimum exposure index | 7.915 |
| Maximum exposure index | 99.929 |
| Mean exposure index | 34.632 |
| Median exposure index | 33.728 |
| Minimum exposure percentile | 0.000 |
| Maximum exposure percentile | 100.000 |

## Scoring Policy

- Policy version: `preliminary_exposure_index_v2`
- Weights are default: True

| Component | Weight | Mean score | Variance share | Spearman vs index |
| --- | --- | --- | --- | --- |
| fema | 0.400 | 11.580 | 0.168 | 0.235 |
| water | 0.350 | 50.000 | 0.653 | 0.893 |
| terrain_absolute | 0.150 | 50.000 | 0.135 | 0.431 |
| terrain_relative | 0.100 | 50.000 | 0.043 | 0.167 |

Nominal weight and measured influence differ because the components do not have equal spread. The percentile components are uniform by construction, while the FEMA component is concentrated on a small number of values.

variance_share is Cov(w_i * C_i, I) / Var(I). Shares sum to 1.0 exactly by linearity of covariance and do not assume the components are uncorrelated. Nominal weight and measured influence diverge when components have unequal spread.

## Interpretation Boundary

- Terrain: Terrain evidence is property-centroid evidence derived from a projected DEM. It is not a hydrologic simulation, finished flood probability estimate, or loss model.
- Exposure index: The exposure index is a preliminary relative ranking built from validated evidence components. It is not a flood-probability model, hydrologic simulation, actuarial model, insurance-pricing tool, or loss estimate.
