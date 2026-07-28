// Unit tests for the B2 verification-mode fork in the segment-BVH query path.
//
// Scope. These tests do not re-validate the B1 index; tests/cpp/
// test_water_segment_bvh.cpp already does that. They validate the four things
// B2 adds:
//
//   1. "split" mode agrees with "original" mode on feature selection and
//      tie_count, and on distance to within the split-interpolation
//      perturbation, including for polygon interiors and polygon holes;
//   2. "original" mode's line/polygon decomposition sums to the total segment
//      check count, so the bound it places on "split" mode is arithmetically
//      sound;
//   3. "split" mode does no distance work over feature geometry, so its total
//      segment checks are exactly its containment ring walks;
//   4. the containment bounding-box pre-filter is a necessary-condition filter:
//      it skips parts it cannot contain the point, and never skips a part that
//      does contain it.
//
// Ground truth for every case is the unchanged brute-force kernel
// distance_to_feature, not the other index mode, so a shared error in the index
// cannot make the pair agree.
//
// Build (from the repository root, one line):
//
//   g++ -std=c++17 -O2 -Wall -Wextra -I cpp/spatial_core/src
//       tests/cpp/test_water_segment_bvh_verify_modes.cpp
//       -o cpp/spatial_core/build/test_water_segment_bvh_verify_modes.exe

#define CAPRM_SEGMENT_BVH_NO_MAIN
#include "../../cpp/spatial_core/src/water_distance_segment_bvh.cpp"

#include <cstdio>
#include <string>
#include <vector>


namespace {

std::uint64_t g_checks = 0;
std::uint64_t g_failures = 0;


void check(bool condition, const std::string& label) {
    ++g_checks;

    if (!condition) {
        ++g_failures;
        std::printf("FAIL: %s\n", label.c_str());
    }
}


void check_close(
    double left,
    double right,
    double tolerance,
    const std::string& label
) {
    ++g_checks;

    const double error = std::abs(left - right);

    if (!(error <= tolerance)) {
        ++g_failures;
        std::printf(
            "FAIL: %s (|%.17g - %.17g| = %.3e > %.3e)\n",
            label.c_str(),
            left,
            right,
            error,
            tolerance
        );
    }
}


Ring make_ring(const std::vector<Point>& vertices) {
    Ring ring;
    ring.vertices = vertices;
    return ring;
}


// A long polyline running east-west. Long enough that a 100 m cap actually
// splits it, so the split path is exercised rather than trivially bypassed.
WaterFeature make_line_feature() {
    WaterFeature feature;

    feature.water_feature_index = 0;
    feature.water_feature_id = "flowline:AAA";
    feature.water_feature_class = "flowline";
    feature.water_feature_type = "stream/river";
    feature.source_feature_id = "AAA";
    feature.source_object_id = 11;
    feature.source_name = "";
    feature.geometry_kind = "line";

    feature.parts[0][0] = make_ring(
        {
            Point{0.0, 0.0},
            Point{1500.0, 0.0},
            Point{3000.0, 400.0},
        }
    );

    return feature;
}


// A two-part polygon. Part 0 is a 2 km square with a 400 m square hole; part 1
// is a small detached square far to the east, present so the per-part bounding
// box pre-filter has something it must skip.
WaterFeature make_polygon_feature() {
    WaterFeature feature;

    feature.water_feature_index = 1;
    feature.water_feature_id = "waterbody:BBB";
    feature.water_feature_class = "waterbody";
    feature.water_feature_type = "lake/pond";
    feature.source_feature_id = "BBB";
    feature.source_object_id = 22;
    feature.source_name = "Test Lake";
    feature.geometry_kind = "polygon";

    feature.parts[0][0] = make_ring(
        {
            Point{0.0, 2000.0},
            Point{2000.0, 2000.0},
            Point{2000.0, 4000.0},
            Point{0.0, 4000.0},
            Point{0.0, 2000.0},
        }
    );

    feature.parts[0][1] = make_ring(
        {
            Point{800.0, 2800.0},
            Point{1200.0, 2800.0},
            Point{1200.0, 3200.0},
            Point{800.0, 3200.0},
            Point{800.0, 2800.0},
        }
    );

    feature.parts[1][0] = make_ring(
        {
            Point{9000.0, 2000.0},
            Point{9200.0, 2000.0},
            Point{9200.0, 2200.0},
            Point{9000.0, 2200.0},
            Point{9000.0, 2000.0},
        }
    );

    return feature;
}


struct Fixture {
    std::vector<WaterFeature> features;
    std::vector<SegmentLeaf> segments;
    SplitStatistics split_statistics;
    PartExteriorBounds part_exterior_bounds;
    std::unique_ptr<SegmentBvh> index;
};


std::unique_ptr<Fixture> build_fixture(double cap) {
    auto fixture = std::make_unique<Fixture>();

    fixture->features.push_back(make_line_feature());
    fixture->features.push_back(make_polygon_feature());

    fixture->segments = build_split_segments(
        fixture->features,
        cap,
        fixture->split_statistics
    );

    fixture->part_exterior_bounds =
        build_part_exterior_bounds(fixture->features);

    fixture->index = std::make_unique<SegmentBvh>(
        fixture->segments,
        fixture->features
    );

    return fixture;
}


SegmentNearestResult query(
    const Fixture& fixture,
    const Point& point,
    VerificationMode mode
) {
    std::vector<char> is_candidate(fixture.features.size(), 0);

    std::vector<double> best_split(
        fixture.features.size(),
        std::numeric_limits<double>::infinity()
    );

    return find_nearest_segment_bvh(
        point,
        fixture.features,
        *fixture.index,
        fixture.part_exterior_bounds,
        is_candidate,
        best_split,
        mode,
        DEFAULT_TIE_TOLERANCE_METERS
    );
}


// Independent ground truth: the unchanged brute-force kernel over every
// feature, with the same tie rule the index uses.
struct BruteForceAnswer {
    int feature_index = -1;
    double distance = std::numeric_limits<double>::infinity();
    int tie_count = 0;
};


BruteForceAnswer brute_force_answer(
    const std::vector<WaterFeature>& features,
    const Point& point
) {
    BruteForceAnswer answer;

    for (
        std::size_t feature_index = 0;
        feature_index < features.size();
        ++feature_index
    ) {
        const WaterFeature& feature = features[feature_index];

        const DistanceResult candidate =
            distance_to_feature(point, feature);

        if (
            candidate.distance
            < answer.distance - DEFAULT_TIE_TOLERANCE_METERS
        ) {
            answer.distance = candidate.distance;
            answer.feature_index = static_cast<int>(feature_index);
            answer.tie_count = 1;
            continue;
        }

        if (
            std::abs(candidate.distance - answer.distance)
            <= DEFAULT_TIE_TOLERANCE_METERS
        ) {
            ++answer.tie_count;

            if (
                answer.feature_index < 0
                || feature.water_feature_id
                    < features[
                        static_cast<std::size_t>(answer.feature_index)
                    ].water_feature_id
            ) {
                answer.distance = candidate.distance;
                answer.feature_index =
                    static_cast<int>(feature_index);
            }
        }
    }

    return answer;
}


struct NamedPoint {
    const char* label;
    Point point;
};


// Bound on the split-interpolation perturbation at these coordinate
// magnitudes. Deliberately loose relative to the 1e-6 m tie tolerance and
// deliberately far tighter than it, so a real disagreement cannot pass.
constexpr double SPLIT_PERTURBATION_BOUND_M = 1e-7;


void run_cap(double cap) {
    const std::unique_ptr<Fixture> fixture = build_fixture(cap);

    const std::vector<NamedPoint> points = {
        {"far south, nearest the flowline", Point{700.0, -900.0}},
        {"on the flowline", Point{700.0, 0.0}},
        {"between line and polygon", Point{700.0, 1400.0}},
        {"inside the polygon exterior", Point{400.0, 3000.0}},
        {"deep inside the polygon", Point{1700.0, 3800.0}},
        {"inside the polygon hole", Point{1000.0, 3000.0}},
        {"just inside the hole edge", Point{810.0, 3000.0}},
        {"north of the polygon", Point{1000.0, 4600.0}},
        {"far east, near the detached part", Point{9100.0, 1900.0}},
        {"inside the detached part", Point{9100.0, 2100.0}},
        {"far northeast of everything", Point{20000.0, 20000.0}},
    };

    for (const NamedPoint& named : points) {
        const std::string context =
            std::string(named.label)
            + " (cap "
            + std::to_string(cap)
            + ")";

        const BruteForceAnswer truth =
            brute_force_answer(fixture->features, named.point);

        const SegmentNearestResult original = query(
            *fixture,
            named.point,
            VerificationMode::OriginalGeometry
        );

        const SegmentNearestResult split = query(
            *fixture,
            named.point,
            VerificationMode::SplitGeometry
        );

        // (1) original mode is byte-identical to the brute-force kernel.
        check(
            original.feature_index == truth.feature_index,
            context + ": original feature matches brute force"
        );

        check(
            original.distance == truth.distance,
            context + ": original distance is bit-identical"
        );

        check(
            original.tie_count == truth.tie_count,
            context + ": original tie_count matches brute force"
        );

        // (2) split mode selects the same feature and the same tie count, and
        //     its distance differs only by the interpolation perturbation.
        check(
            split.feature_index == truth.feature_index,
            context + ": split feature matches brute force"
        );

        check(
            split.tie_count == truth.tie_count,
            context + ": split tie_count matches brute force"
        );

        check_close(
            split.distance,
            truth.distance,
            SPLIT_PERTURBATION_BOUND_M,
            context + ": split distance within perturbation bound"
        );

        // Interior zero must stay exactly zero, not merely small.
        if (truth.distance == 0.0) {
            check(
                split.distance == 0.0,
                context + ": split preserves exact interior zero"
            );
        }

        // (3) counter decomposition invariants.
        check(
            original.line_segment_checks
                + original.polygon_segment_checks
                == original.segment_checks,
            context + ": original decomposition sums to the total"
        );

        check(
            original.containment_ring_checks == 0
                && original.containment_parts_tested == 0
                && original.containment_parts_skipped == 0,
            context + ": original does no standalone containment work"
        );

        check(
            split.line_segment_checks == 0
                && split.polygon_segment_checks == 0,
            context + ": split does no distance work over feature geometry"
        );

        check(
            split.segment_checks == split.containment_ring_checks,
            context + ": split segment checks are exactly ring walks"
        );

        // (4) split mode can never cost more phase-2 work than original mode.
        check(
            split.segment_checks <= original.segment_checks,
            context + ": split verification does not exceed original"
        );

        // Both modes see the same candidate set and the same search cost.
        check(
            split.candidate_feature_checks
                == original.candidate_feature_checks,
            context + ": candidate sets agree"
        );

        check(
            split.node_visits == original.node_visits
                && split.segment_box_tests == original.segment_box_tests,
            context + ": search cost is mode independent"
        );
    }
}


// The pre-filter is a necessary-condition filter. Direct tests, independent of
// the query path, because a filter bug that only ever over-rejects would be
// invisible in aggregate agreement until it hit a property inside a polygon.
void run_prefilter_tests() {
    std::vector<WaterFeature> features;
    features.push_back(make_polygon_feature());

    const PartExteriorBounds part_bounds =
        build_part_exterior_bounds(features);

    check(
        part_bounds.size() == 1 && part_bounds[0].size() == 2,
        "prefilter: both polygon parts have exterior bounds"
    );

    // A point inside part 0 must never cause part 0 to be skipped. Containment
    // returns as soon as a part contains the point, matching
    // distance_to_polygon_feature's early return, so later parts are neither
    // tested nor counted as skipped.
    const ContainmentResult inside_part_zero = polygon_contains_point(
        Point{400.0, 3000.0},
        features[0],
        part_bounds[0]
    );

    check(
        inside_part_zero.inside,
        "prefilter: point inside part 0 is reported inside"
    );

    check(
        inside_part_zero.parts_tested == 1,
        "prefilter: only the containing part is walked"
    );

    check(
        inside_part_zero.parts_skipped == 0,
        "prefilter: containment returns before reaching later parts"
    );

    // A point near the detached part must skip part 0 by box rejection and
    // exactly test part 1. This is the case that proves the filter actually
    // rejects rather than passing everything through.
    const ContainmentResult near_detached = polygon_contains_point(
        Point{9100.0, 2100.0},
        features[0],
        part_bounds[0]
    );

    check(
        near_detached.inside,
        "prefilter: point inside the detached part is reported inside"
    );

    check(
        near_detached.parts_skipped == 1
            && near_detached.parts_tested == 1,
        "prefilter: the distant main part is box-rejected"
    );

    // A point inside the hole is inside the exterior ring's box and inside the
    // exterior ring, so the walk must happen and must still report outside.
    const ContainmentResult inside_hole = polygon_contains_point(
        Point{1000.0, 3000.0},
        features[0],
        part_bounds[0]
    );

    check(
        !inside_hole.inside,
        "prefilter: point inside a hole is reported outside"
    );

    check(
        inside_hole.parts_tested == 1 && inside_hole.ring_checks > 0,
        "prefilter: the hole case walks rings rather than short-circuiting"
    );

    // A point outside every part box must be rejected without any ring walk.
    const ContainmentResult far_away = polygon_contains_point(
        Point{-5000.0, -5000.0},
        features[0],
        part_bounds[0]
    );

    check(
        !far_away.inside,
        "prefilter: distant point is reported outside"
    );

    check(
        far_away.ring_checks == 0,
        "prefilter: distant point costs zero ring checks"
    );

    check(
        far_away.parts_skipped == 2 && far_away.parts_tested == 0,
        "prefilter: distant point skips every part"
    );

    // Inside the box but outside the ring: the filter must not reject it, and
    // the exact test must still say outside. This is the case a filter that
    // over-trusted the box would get wrong.
    const ContainmentResult box_only = polygon_contains_point(
        Point{2000.0, 4000.0},
        features[0],
        part_bounds[0]
    );

    check(
        !box_only.inside,
        "prefilter: corner point inside the box is still outside the ring"
    );

    check(
        box_only.parts_tested == 1,
        "prefilter: a point inside the box is always exactly tested"
    );
}


void run_split_statistics_tests() {
    const std::unique_ptr<Fixture> uncapped = build_fixture(0.0);
    const std::unique_ptr<Fixture> capped = build_fixture(100.0);

    check(
        uncapped->split_statistics.split_segments
            == uncapped->split_statistics.original_segments,
        "split: a nonpositive cap disables splitting"
    );

    check(
        capped->split_statistics.split_segments
            > capped->split_statistics.original_segments,
        "split: a 100 m cap adds entries on this fixture"
    );

    // The cap is enforced to within double rounding, not exactly: interior
    // split points are linear interpolations, so an entry can exceed the cap by
    // a relative ~1e-15. Measured overshoot on an exact-multiple edge is
    // 2.27e-13 m at a 100 m cap. This matters for B3 only in that the inflation
    // bound is cap/2 plus that residual, never cap/2 exactly.
    check(
        capped->split_statistics.max_split_length_m <= 100.0 + 1e-9,
        "split: no capped entry exceeds the cap beyond rounding"
    );

    check(
        capped->split_statistics.max_split_length_m > 99.0,
        "split: the capped extent is actually near the cap"
    );

    check(
        uncapped->split_statistics.max_original_length_m
            == capped->split_statistics.max_original_length_m,
        "split: the original extent is independent of the cap"
    );

    check(
        capped->index->index_bytes() > 0
            && capped->index->index_bytes()
                > uncapped->index->index_bytes(),
        "index_bytes: more entries report more bytes"
    );
}

}  // namespace


int main() {
    for (const double cap : {0.0, 10.0, 100.0, 1000.0}) {
        run_cap(cap);
    }

    run_prefilter_tests();
    run_split_statistics_tests();

    std::printf(
        "%llu checks, %llu failures\n",
        static_cast<unsigned long long>(g_checks),
        static_cast<unsigned long long>(g_failures)
    );

    return g_failures == 0 ? 0 : 1;
}