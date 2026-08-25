// Unit tests for the segment-BVH nearest-water program.
//
// Includes water_distance_segment_bvh.cpp with its main suppressed so the
// anonymous-namespace functions (segment split, SegmentBvh, the query, and the
// reused kernel) are directly callable. Covers the three behaviors called out
// in the B1b/B1c task:
//
//   1. split distance-invariance;
//   2. polygon interior-zero;
//   3. tie-break on water_feature_id;
//
// plus a randomized field-for-field check of the segment-BVH query against an
// in-test brute-force reference over the same features, at two split caps.

#define CAPRM_SEGMENT_BVH_NO_MAIN
#include "../../cpp/spatial_core/src/water_distance_segment_bvh.cpp"

#include <cassert>
#include <cstdio>
#include <limits>
#include <random>


namespace {

int g_checks = 0;
int g_failures = 0;

void check(bool condition, const std::string& message) {
    ++g_checks;
    if (!condition) {
        ++g_failures;
        std::printf("  FAIL: %s\n", message.c_str());
    }
}

void check_close(
    double actual,
    double expected,
    double tolerance,
    const std::string& message
) {
    ++g_checks;
    const double error = std::abs(actual - expected);
    if (!(error <= tolerance)) {
        ++g_failures;
        std::printf(
            "  FAIL: %s (actual=%.17g expected=%.17g abs_err=%.3g)\n",
            message.c_str(), actual, expected, error
        );
    }
}


// A brute-force reference over an explicit feature vector, replicating the exact
// selection logic of write_brute_force_results (kernel-identical tie loop).
struct ReferenceResult {
    int feature_index = -1;
    double distance = std::numeric_limits<double>::infinity();
    int tie_count = 0;
};

ReferenceResult brute_force_reference(
    const Point& point,
    const std::vector<WaterFeature>& features,
    double tie_tolerance_meters
) {
    ReferenceResult result;

    for (const WaterFeature& feature : features) {
        const DistanceResult candidate = distance_to_feature(point, feature);

        if (candidate.distance < result.distance - tie_tolerance_meters) {
            result.distance = candidate.distance;
            result.feature_index = feature.water_feature_index;
            result.tie_count = 1;
            continue;
        }

        if (
            std::abs(candidate.distance - result.distance)
            <= tie_tolerance_meters
        ) {
            ++result.tie_count;
            if (
                result.feature_index < 0
                || feature.water_feature_id
                    < features[
                        static_cast<std::size_t>(result.feature_index)
                    ].water_feature_id
            ) {
                result.distance = candidate.distance;
                result.feature_index = feature.water_feature_index;
            }
        }
    }

    return result;
}


WaterFeature make_line(
    int index,
    const std::string& id,
    const std::vector<Point>& vertices
) {
    WaterFeature feature;
    feature.water_feature_index = index;
    feature.water_feature_id = id;
    feature.water_feature_class = "flowline";
    feature.water_feature_type = "channel";
    feature.source_feature_id = "src:" + id;
    feature.source_object_id = index;
    feature.source_name = id;
    feature.geometry_kind = "line";
    Ring ring;
    ring.vertices = vertices;
    feature.parts[0][0] = ring;
    return feature;
}


// A single-ring (no holes) polygon waterbody. The caller supplies a closed ring.
WaterFeature make_polygon(
    int index,
    const std::string& id,
    const std::vector<Point>& ring_vertices
) {
    WaterFeature feature;
    feature.water_feature_index = index;
    feature.water_feature_id = id;
    feature.water_feature_class = "waterbody";
    feature.water_feature_type = "lake";
    feature.source_feature_id = "src:" + id;
    feature.source_object_id = index;
    feature.source_name = id;
    feature.geometry_kind = "polygon";
    Ring ring;
    ring.vertices = ring_vertices;
    feature.parts[0][0] = ring;
    return feature;
}


std::vector<Point> closed_square(
    double min_x,
    double min_y,
    double side
) {
    const double max_x = min_x + side;
    const double max_y = min_y + side;
    return {
        {min_x, min_y},
        {max_x, min_y},
        {max_x, max_y},
        {min_x, max_y},
        {min_x, min_y},
    };
}


SegmentNearestResult query(
    const Point& point,
    const std::vector<WaterFeature>& features,
    double cap
) {
    SplitStatistics statistics;
    const std::vector<SegmentLeaf> segments =
        build_split_segments(features, cap, statistics);
    const PartExteriorBounds part_exterior_bounds =
        build_part_exterior_bounds(features);
    SegmentBvh index(segments, features);

    std::vector<char> is_candidate(features.size(), 0);
    std::vector<double> best_split(
        features.size(),
        std::numeric_limits<double>::infinity()
    );

    // OriginalGeometry is this suite's subject. These tests predate the
    // verification-mode fork and assert against unsplit geometry throughout:
    // distance-invariance under splitting, polygon interior-zero, and the
    // tie-break. SplitGeometry is covered by
    // test_water_segment_bvh_verify_modes.cpp, which exercises both modes.
    return find_nearest_segment_bvh(
        point,
        features,
        index,
        part_exterior_bounds,
        is_candidate,
        best_split,
        VerificationMode::OriginalGeometry,
        DEFAULT_TIE_TOLERANCE_METERS
    );
}


// ---------------------------------------------------------------------------

void test_split_piece_count() {
    std::printf("test_split_piece_count\n");
    check(split_piece_count(6000.0, 100.0) == 60, "6000/100 -> 60 pieces");
    check(split_piece_count(5748.24, 100.0) == 58, "5748.24/100 -> 58 pieces");
    check(split_piece_count(100.0, 100.0) == 1, "exactly cap -> 1 piece");
    check(split_piece_count(50.0, 100.0) == 1, "below cap -> 1 piece");
    check(split_piece_count(250.0, 100.0) == 3, "250/100 -> 3 pieces");
    check(split_piece_count(6000.0, 0.0) == 1, "cap 0 disables split");
    check(split_piece_count(6000.0, -1.0) == 1, "negative cap disables split");
}


void test_split_distance_invariance() {
    std::printf("test_split_distance_invariance\n");

    std::mt19937_64 rng(12345);
    // UTM-magnitude coordinates so any floating error is realistic.
    std::uniform_real_distribution<double> x_dist(270000.0, 300000.0);
    std::uniform_real_distribution<double> y_dist(4770000.0, 4800000.0);

    double worst_error = 0.0;

    for (int trial = 0; trial < 20000; ++trial) {
        const Point a{x_dist(rng), y_dist(rng)};
        const Point b{x_dist(rng), y_dist(rng)};
        const Point p{x_dist(rng), y_dist(rng)};

        const double original_sq =
            point_segment_distance_squared(p, a, b);

        std::vector<SegmentLeaf> leaves;
        SplitStatistics statistics;
        statistics.max_segment_length_cap_m = 100.0;
        append_split_segments(a, b, 0, 100.0, leaves, statistics);

        double split_min_sq = std::numeric_limits<double>::infinity();
        Point previous_end = a;
        bool contiguous = true;
        bool collinear = true;

        for (std::size_t i = 0; i < leaves.size(); ++i) {
            const SegmentLeaf& leaf = leaves[i];

            split_min_sq = std::min(
                split_min_sq,
                point_segment_distance_squared(p, leaf.start, leaf.end)
            );

            // Contiguity: each sub-segment starts where the previous ended.
            if (leaf.start.x != previous_end.x
                || leaf.start.y != previous_end.y) {
                contiguous = false;
            }
            previous_end = leaf.end;

            // Collinearity of the interior split point with A..B.
            const double cross =
                (leaf.start.x - a.x) * (b.y - a.y)
                - (leaf.start.y - a.y) * (b.x - a.x);
            // Scale-relative tolerance for the cross product.
            if (std::abs(cross) > 1e-3) {
                collinear = false;
            }
        }

        check(contiguous, "sub-segments are contiguous");
        check(collinear, "interior split points are collinear");
        check(
            leaves.back().end.x == b.x && leaves.back().end.y == b.y,
            "last sub-segment ends at B"
        );

        const double original = std::sqrt(original_sq);
        const double split = std::sqrt(split_min_sq);
        worst_error = std::max(worst_error, std::abs(original - split));

        check_close(
            split, original, 1e-6,
            "min split distance equals original point-segment distance"
        );
    }

    std::printf(
        "  worst split-vs-original abs error over 20000 trials: %.3g m\n",
        worst_error
    );
}


void test_interior_zero() {
    std::printf("test_interior_zero\n");

    std::vector<WaterFeature> features;
    // A flowline far away so it never competes with the polygon interior.
    features.push_back(make_line(
        0, "flow:far",
        {{260000.0, 4760000.0}, {260500.0, 4760000.0}}
    ));
    // A 100 m square waterbody.
    features.push_back(make_polygon(
        1, "body:square",
        closed_square(283000.0, 4781000.0, 100.0)
    ));

    // Strictly interior point.
    const SegmentNearestResult interior =
        query({283050.0, 4781050.0}, features, 100.0);
    check(interior.feature_index == 1, "interior selects the polygon");
    check_close(interior.distance, 0.0, 0.0, "interior distance is exactly 0");

    // Point exactly on an edge (bottom edge midpoint).
    const SegmentNearestResult on_edge =
        query({283050.0, 4781000.0}, features, 100.0);
    check(on_edge.feature_index == 1, "on-boundary selects the polygon");
    check_close(on_edge.distance, 0.0, 0.0, "on-boundary distance is exactly 0");

    // Point outside near the right edge: distance equals boundary distance,
    // and must match the reference exactly.
    const Point outside{283130.0, 4781050.0};  // 30 m right of the square
    const SegmentNearestResult exterior = query(outside, features, 100.0);
    const ReferenceResult reference =
        brute_force_reference(outside, features, DEFAULT_TIE_TOLERANCE_METERS);
    check(exterior.feature_index == reference.feature_index,
          "exterior feature matches reference");
    check_close(exterior.distance, reference.distance, 0.0,
                "exterior distance matches reference exactly");
    check_close(exterior.distance, 30.0, 1e-9, "exterior distance is ~30 m");
}


void test_tie_break() {
    std::printf("test_tie_break\n");

    // Query point with two waterbody squares at equal boundary distance,
    // mirrored in x so the distances are bit-for-bit equal. The lexicographically
    // smaller water_feature_id must be selected, tie_count == 2.
    const double px = 285000.0;
    const double py = 4785000.0;

    std::vector<WaterFeature> features;
    // Left square: right edge 10 m left of P.
    features.push_back(make_polygon(
        0, "body:zzz",
        closed_square(px - 10.0 - 100.0, py - 50.0, 100.0)
    ));
    // Right square: left edge 10 m right of P (mirror geometry).
    features.push_back(make_polygon(
        1, "body:aaa",
        closed_square(px + 10.0, py - 50.0, 100.0)
    ));

    const SegmentNearestResult result = query({px, py}, features, 100.0);
    const ReferenceResult reference =
        brute_force_reference({px, py}, features, DEFAULT_TIE_TOLERANCE_METERS);

    check_close(result.distance, 10.0, 1e-9, "tie distance is 10 m");
    check(result.tie_count == 2, "tie_count is 2");
    check(
        features[static_cast<std::size_t>(result.feature_index)]
            .water_feature_id == "body:aaa",
        "lexicographically smallest id wins"
    );
    check(result.feature_index == reference.feature_index,
          "tie selection matches reference");
    check(result.tie_count == reference.tie_count,
          "tie_count matches reference");
}


void test_field_for_field_random() {
    std::printf("test_field_for_field_random\n");

    std::vector<WaterFeature> features;
    // A long flowline with a single 6000 m segment (exceeds the real max L).
    features.push_back(make_line(
        0, "flow:long",
        {{280000.0, 4780000.0}, {286000.0, 4780000.0}}
    ));
    // A poly-line flowline with several segments.
    features.push_back(make_line(
        1, "flow:zig",
        {
            {281000.0, 4782000.0},
            {281500.0, 4782300.0},
            {282000.0, 4782100.0},
            {282600.0, 4782800.0},
        }
    ));
    // Two waterbody squares.
    features.push_back(make_polygon(
        2, "body:one", closed_square(283000.0, 4781000.0, 150.0)
    ));
    features.push_back(make_polygon(
        3, "body:two", closed_square(284000.0, 4783000.0, 400.0)
    ));

    std::mt19937_64 rng(98765);
    std::uniform_real_distribution<double> x_dist(279000.0, 287000.0);
    std::uniform_real_distribution<double> y_dist(4779000.0, 4784000.0);

    const double caps[] = {100.0, 1e12};  // split on / split off

    for (double cap : caps) {
        int mismatches = 0;
        double worst_error = 0.0;

        for (int trial = 0; trial < 50000; ++trial) {
            const Point p{x_dist(rng), y_dist(rng)};

            const SegmentNearestResult got = query(p, features, cap);
            const ReferenceResult reference =
                brute_force_reference(
                    p, features, DEFAULT_TIE_TOLERANCE_METERS
                );

            const bool feature_ok =
                got.feature_index == reference.feature_index;
            const bool tie_ok = got.tie_count == reference.tie_count;
            const double error = std::abs(got.distance - reference.distance);
            worst_error = std::max(worst_error, error);
            const bool distance_ok = error == 0.0;  // byte-identical expected

            if (!feature_ok || !tie_ok || !distance_ok) {
                ++mismatches;
                if (mismatches <= 5) {
                    std::printf(
                        "  MISMATCH cap=%.3g p=(%.3f,%.3f) "
                        "feat %d/%d tie %d/%d dist_err %.3g\n",
                        cap, p.x, p.y,
                        got.feature_index, reference.feature_index,
                        got.tie_count, reference.tie_count, error
                    );
                }
            }
        }

        check(mismatches == 0,
              "segment_bvh matches reference field-for-field (cap="
              + std::to_string(cap) + ")");
        std::printf(
            "  cap=%.3g: %d mismatches over 50000 trials, worst dist error %.3g m\n",
            cap, mismatches, worst_error
        );
    }
}


}  // namespace


int main() {
    test_split_piece_count();
    test_split_distance_invariance();
    test_interior_zero();
    test_tie_break();
    test_field_for_field_random();

    std::printf(
        "\n%d checks, %d failures\n", g_checks, g_failures
    );
    return g_failures == 0 ? 0 : 1;
}