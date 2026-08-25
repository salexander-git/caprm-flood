# Scoring Sensitivity Summary

- Scoring policy: `preliminary_exposure_index_v2`
- Properties: 267362
- Scenarios evaluated: 40 (35 plausible, 4 reference corners)

## Verdict

**MODERATELY SENSITIVE**

The verdict is driven by the worst plausible scenario, not the average. An index that survives most reweightings but collapses under one plausible reweighting is not stable.

| Measure | Value | Scenario |
| --- | --- | --- |
| Minimum Spearman vs baseline | 0.8750 | equal |
| Median Spearman vs baseline | 0.9963 |  |
| Minimum top-decile overlap | 0.7614 | equal |
| Median top-decile overlap | 0.9455 |  |
| Maximum percentile shift | 47.4667 |  |
| Median of median percentile shift | 1.5596 |  |

## Declared thresholds

Declared in caprm.sensitivity before any result was measured. They are a judgement call with no external standard.

| Verdict | Minimum Spearman | Minimum top-decile overlap |
| --- | --- | --- |
| stable | 0.9500 | 0.8000 |
| moderately_sensitive | 0.8500 | 0.6000 |

## Metric calibration

Reference corners place all weight on one component. They are not proposed configurations. They establish what a genuinely different weighting does to these metrics, without which a high correlation among plausible scenarios cannot be interpreted.

| Measure | Value |
| --- | --- |
| Minimum reference-corner Spearman | 0.1674 |
| Maximum reference-corner Spearman | 0.8933 |
| Minimum reference-corner top-decile overlap | 0.2895 |

## Scenarios

| Scenario | Family | w(fema) | w(water) | w(terrain_absolute) | w(terrain_relative) | Spearman | Top decile | Top 5% | Median shift | Max shift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | baseline | 0.4000 | 0.3500 | 0.1500 | 0.1000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |
| perturbation_000 | perturbation | 0.3444 | 0.3671 | 0.1910 | 0.0975 | 0.9974 | 0.9417 | 0.9509 | 1.5170 | 16.3636 |
| perturbation_001 | perturbation | 0.4354 | 0.3021 | 0.1627 | 0.0998 | 0.9963 | 0.9581 | 0.9636 | 1.7291 | 8.0830 |
| perturbation_002 | perturbation | 0.4107 | 0.3909 | 0.1222 | 0.0763 | 0.9932 | 0.9322 | 0.9531 | 2.1217 | 9.8402 |
| perturbation_003 | perturbation | 0.4045 | 0.3544 | 0.1304 | 0.1106 | 0.9986 | 0.9455 | 0.9627 | 1.0604 | 4.2852 |
| perturbation_004 | perturbation | 0.4322 | 0.3498 | 0.1391 | 0.0789 | 0.9985 | 0.9603 | 0.9654 | 1.0847 | 6.1247 |
| perturbation_005 | perturbation | 0.4887 | 0.3208 | 0.1088 | 0.0817 | 0.9973 | 0.9537 | 0.9650 | 1.5596 | 11.5854 |
| perturbation_006 | perturbation | 0.4292 | 0.3035 | 0.1547 | 0.1126 | 0.9962 | 0.9521 | 0.9580 | 1.5320 | 8.8509 |
| perturbation_007 | perturbation | 0.3841 | 0.3811 | 0.1344 | 0.1004 | 0.9981 | 0.9596 | 0.9738 | 1.3207 | 5.7375 |
| perturbation_008 | perturbation | 0.3659 | 0.3514 | 0.1155 | 0.1672 | 0.9839 | 0.8327 | 0.8826 | 3.6093 | 14.5200 |
| perturbation_009 | perturbation | 0.3782 | 0.3892 | 0.1399 | 0.0927 | 0.9979 | 0.9619 | 0.9697 | 1.2109 | 8.7234 |
| perturbation_010 | perturbation | 0.3755 | 0.3444 | 0.1584 | 0.1217 | 0.9983 | 0.9580 | 0.9651 | 1.1613 | 5.8434 |
| perturbation_011 | perturbation | 0.3861 | 0.3818 | 0.1497 | 0.0824 | 0.9980 | 0.9526 | 0.9613 | 1.2644 | 7.2666 |
| perturbation_012 | perturbation | 0.4208 | 0.3436 | 0.1438 | 0.0918 | 0.9999 | 0.9883 | 0.9871 | 0.3314 | 4.6177 |
| perturbation_013 | perturbation | 0.3919 | 0.3850 | 0.1314 | 0.0917 | 0.9970 | 0.9556 | 0.9681 | 1.5174 | 6.5413 |
| perturbation_014 | perturbation | 0.3869 | 0.3801 | 0.1182 | 0.1148 | 0.9955 | 0.9090 | 0.9385 | 2.1215 | 6.6404 |
| perturbation_015 | perturbation | 0.4531 | 0.3039 | 0.1301 | 0.1128 | 0.9976 | 0.9343 | 0.9474 | 1.5344 | 9.7059 |
| perturbation_016 | perturbation | 0.4050 | 0.3806 | 0.1270 | 0.0874 | 0.9963 | 0.9513 | 0.9663 | 1.6536 | 7.1652 |
| perturbation_017 | perturbation | 0.4616 | 0.3220 | 0.1423 | 0.0741 | 0.9989 | 0.9512 | 0.9583 | 1.0432 | 9.6618 |
| perturbation_018 | perturbation | 0.4445 | 0.3119 | 0.1347 | 0.1089 | 0.9987 | 0.9523 | 0.9600 | 1.1359 | 8.7526 |
| perturbation_019 | perturbation | 0.3944 | 0.3438 | 0.1854 | 0.0764 | 0.9951 | 0.9167 | 0.9363 | 1.8357 | 8.3714 |
| perturbation_020 | perturbation | 0.3965 | 0.3549 | 0.1534 | 0.0952 | 0.9999 | 0.9846 | 0.9871 | 0.3247 | 1.6442 |
| perturbation_021 | perturbation | 0.4373 | 0.3180 | 0.1367 | 0.1080 | 0.9990 | 0.9586 | 0.9640 | 0.9718 | 7.8362 |
| perturbation_022 | perturbation | 0.3705 | 0.4325 | 0.1147 | 0.0822 | 0.9884 | 0.9050 | 0.9340 | 2.9484 | 14.7074 |
| perturbation_023 | perturbation | 0.4145 | 0.3168 | 0.1846 | 0.0841 | 0.9936 | 0.9263 | 0.9492 | 2.4610 | 8.2297 |
| fema_only | reference_corner | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.2348 | 0.9947 | 0.9676 | 24.0535 | 55.9894 |
| terrain_absolute_only | reference_corner | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.4310 | 0.4251 | 0.3343 | 23.0100 | 97.4185 |
| terrain_relative_only | reference_corner | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.1674 | 0.2895 | 0.2513 | 27.4572 | 98.8547 |
| water_only | reference_corner | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.8933 | 0.5893 | 0.4970 | 8.8015 | 85.1535 |
| equal | structured | 0.2500 | 0.2500 | 0.2500 | 0.2500 | 0.8750 | 0.7614 | 0.7875 | 9.0631 | 47.4667 |
| fema_deemphasized | structured | 0.2500 | 0.4375 | 0.1875 | 0.1250 | 0.9989 | 0.9752 | 0.9411 | 0.0116 | 42.5543 |
| fema_emphasized | structured | 0.5714 | 0.2500 | 0.1071 | 0.0714 | 1.0000 | 0.9990 | 0.9877 | 0.0000 | 12.4098 |
| terrain_absolute_deemphasized | structured | 0.4324 | 0.3784 | 0.0811 | 0.1081 | 0.9847 | 0.8397 | 0.8756 | 4.0223 | 11.5478 |
| terrain_absolute_emphasized | structured | 0.3478 | 0.3043 | 0.2609 | 0.0870 | 0.9617 | 0.8538 | 0.8862 | 6.1061 | 20.3090 |
| terrain_family_deemphasized | structured | 0.4571 | 0.4000 | 0.0857 | 0.0571 | 0.9779 | 0.8673 | 0.9099 | 3.9884 | 17.1154 |
| terrain_family_emphasized | structured | 0.3200 | 0.2800 | 0.2400 | 0.1600 | 0.9496 | 0.8507 | 0.8812 | 5.8142 | 29.3695 |
| terrain_relative_deemphasized | structured | 0.4211 | 0.3684 | 0.1579 | 0.0526 | 0.9930 | 0.8858 | 0.9072 | 2.6754 | 7.2284 |
| terrain_relative_emphasized | structured | 0.3636 | 0.3182 | 0.1364 | 0.1818 | 0.9746 | 0.8289 | 0.8833 | 4.8189 | 14.2401 |
| water_deemphasized | structured | 0.4848 | 0.2121 | 0.1818 | 0.1212 | 0.9497 | 0.8555 | 0.8906 | 5.7892 | 29.3695 |
| water_emphasized | structured | 0.2963 | 0.5185 | 0.1111 | 0.0741 | 0.9772 | 0.8563 | 0.8879 | 4.0170 | 37.3004 |

## Interpretation boundary

Sensitivity measures how far the countywide ranking moves when component weights change. It does not establish that the weights are correct, that the components are the right components, or that the index estimates flood probability. A stable ranking under reweighting means the conclusion does not hinge on the weight choice, not that the conclusion is right.
