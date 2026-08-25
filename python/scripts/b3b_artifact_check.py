import pandas as pd
f = pd.read_csv("outputs/cpp/cpp_nearest_water_hilbert_countywide_bbox.csv",
                dtype={"property_id": "string"})
print("rows", len(f), "unique", f.property_id.nunique())
print("nulls", int(f.isna().sum().sum()))
d = f.cpp_nearest_water_distance_m
print("range", d.min(), d.max(), "in [0,20000):", bool((d >= 0).all() and (d < 20000).all()))
z = f[d == 0.0]
print("exact zeros", len(z), "all waterbody:",
      set(z.cpp_nearest_water_feature_class.unique()) == {"waterbody"})
for c in ("distance_crs", "algorithm", "region_mode", "seed_mode", "verification_mode"):
    print(c, f[c].unique().tolist())
print("mean seed probes", f.cpp_seed_probes.mean(), "max", f.cpp_seed_probes.max())
