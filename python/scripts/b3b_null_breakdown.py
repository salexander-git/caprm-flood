import pandas as pd
f = pd.read_csv("outputs/cpp/cpp_nearest_water_hilbert_countywide_bbox.csv",
                dtype={"property_id": "string"})
n = f.isna().sum()
print("columns with nulls:")
print(n[n > 0].to_string())
required = ["property_id", "cpp_nearest_water_distance_m", "cpp_nearest_water_feature_id",
            "cpp_nearest_water_feature_class", "cpp_nearest_water_feature_type",
            "cpp_nearest_water_source_id", "cpp_nearest_water_source_object_id",
            "cpp_nearest_water_tie_count", "cpp_segment_checks", "distance_crs", "algorithm"]
print("nulls in required cols:", int(f[required].isna().sum().sum()))
print("empty names:", int(f.cpp_nearest_water_name.isna().sum()))
