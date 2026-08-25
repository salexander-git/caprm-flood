// Segment-level BVH nearest-water program.
//
// Follows the same extension pattern as water_distance_indexed.cpp: it
// #includes the brute-force translation unit (with its main renamed) to reuse
// the exact geometry kernel, IO, tie rule, and distance_to_feature. The only
// new machinery here is:
//
//   1. a distance-exact segment split that caps segment length before indexing;
//   2. a bounding-volume hierarchy over the (split) segment boxes;
//   3. a best-first query that reduces the candidate feature set, after which
//      the UNCHANGED distance_to_feature produces the reported answer.
//
// Correctness properties (see docs/benchmark_results.md and the B1 entries in
// docs/canon/CAPRM_Flood_Current_Status.md):
//
//   - Splitting is used ONLY to build BVH leaf boxes. Reported distances come
//     from distance_to_feature over ORIGINAL geometry, so a reported value is
//     byte-identical to the brute-force / Feature-BVH / Python reference. This
//     is why "splitting a segment at a point on it does not change any
//     point-to-segment distance" holds trivially: split geometry never enters
//     the distance calculation, only the search bounds.
//
//   - A sub-segment box is contained in its parent segment box, so splitting
//     can only tighten bounds (more pruning), never drop a true candidate: the
//     sub-segment containing a feature's closest point still competes at the
//     final threshold, so that feature is still visited.
//
//   - Interior-zero (a point inside a waterbody polygon is distance 0) is
//     preserved WITHOUT a separate containment index, under the USGS 3DHP
//     non-overlap invariant: waterbodies partition water area and islands are
//     holes of the same feature, so the nearest boundary segment to an interior
//     point belongs to the containing polygon itself. That polygon is therefore
//     always a candidate, and distance_to_feature returns its exact 0.0. The
//     countywide field-for-field comparison against the Python oracle validates
//     this on the real data.
//
// ---------------------------------------------------------------------------
// Milestone 4, chunk B2: verification modes
// ---------------------------------------------------------------------------
//
// Phase 1 (index traversal) costs roughly 35 node and box operations per
// property. Phase 2 (exact verification) costs thousands of segment checks,
// because distance_to_feature rescans each candidate feature's entire original
// geometry. B2 exposes the verification strategy as a runtime flag so the cost
// of exactness over extended objects can be measured rather than asserted:
//
//   original  reported distance comes from distance_to_feature over ORIGINAL
//             geometry. Byte-identical to the reference. This is the B1
//             behaviour and remains the DEFAULT.
//
//   split     reported distance comes from the per-candidate minimum over the
//             SPLIT sub-segments already examined during phase 1, so no feature
//             geometry is rescanned for distance.
//
// Why "split" does NOT collapse verification for polygons. Interior-zero is not
// a distance result; it is the parity of a ray-crossing count over the ring
// vertices (see evaluate_ring in the brute-force translation unit). Split
// geometry can supply the boundary distance but cannot supply the inside/outside
// predicate, so polygon candidates still require a ring walk. The saving under
// "split" is therefore bounded by the LINE-candidate share of verification, and
// that share is measured directly by the cpp_line_segment_checks /
// cpp_polygon_segment_checks decomposition emitted under "original".
//
// Containment bounding-box pre-filter (exact, not an approximation). A point
// inside a polygon part must lie inside that part's exterior-ring bounding box.
// The converse is false, so a point outside the box is definitively outside the
// part and its ring walk can be skipped entirely. Parts whose box does contain
// the point still get the full exact crossing test. The filter's hit rate is a
// measured quantity (cpp_containment_parts_tested vs
// cpp_containment_parts_skipped), not an assumption.
//
// Exactness of the "split" mode, stated so it can be checked rather than
// trusted. Phase 1 prunes on best_boundary_distance + tie_tolerance, and
// best_boundary_distance is monotonically nonincreasing. Any feature whose true
// split-geometry minimum d satisfies d <= best_final + tie_tolerance has a
// minimizing sub-segment whose box lower bound is <= d, so that box competes at
// every point during the traversal and its enclosing nodes are popped before the
// queue terminates. The recorded per-candidate minimum therefore equals the true
// split minimum for every feature that can win or tie; for features outside the
// tie window the recorded value may be an overestimate, and an overestimate
// cannot enter the window. tie_count is preserved on the same argument. This is
// an argument, not a measurement: the countywide comparison is what validates it.
//
// Known hazard, deliberately not hidden. Split endpoints are linear
// interpolations, so a sub-segment distance differs from the parent segment
// distance by roughly one ULP at UTM 18N magnitudes (~1e-9 m). That is the same
// order as BOUNDARY_EPSILON_METERS (1e-9), so a point lying within about a
// nanometre of a boundary could be classified on-boundary under "original" and
// not under "split". The sweep harness reports the minimum NONZERO countywide
// distance so this hazard can be settled with a number instead of an argument.

#define main caprm_bruteforce_program_main
#include "water_distance_bruteforce.cpp"
#undef main

#include <cmath>
#include <numeric>
#include <queue>
#include <unordered_map>


namespace {

constexpr std::size_t SEGMENT_BVH_LEAF_SIZE = 8;
constexpr double DEFAULT_MAX_SEGMENT_LENGTH_METERS = 100.0;


// Which geometry supplies the reported distance during phase-2 verification.
// OriginalGeometry is the B1 behaviour and the default.
enum class VerificationMode {
    OriginalGeometry,
    SplitGeometry,
};


const char* verification_mode_name(VerificationMode mode) {
    return mode == VerificationMode::SplitGeometry
        ? "split"
        : "original";
}


// ---------------------------------------------------------------------------
// Axis-aligned bounds (mirrors the Feature-BVH helpers, kept local so this
// translation unit does not depend on water_distance_indexed.cpp).
// ---------------------------------------------------------------------------

struct Bounds {
    double min_x = std::numeric_limits<double>::infinity();
    double min_y = std::numeric_limits<double>::infinity();
    double max_x = -std::numeric_limits<double>::infinity();
    double max_y = -std::numeric_limits<double>::infinity();
};


void expand_bounds(Bounds& bounds, const Point& point) {
    bounds.min_x = std::min(bounds.min_x, point.x);
    bounds.min_y = std::min(bounds.min_y, point.y);
    bounds.max_x = std::max(bounds.max_x, point.x);
    bounds.max_y = std::max(bounds.max_y, point.y);
}


void expand_bounds(Bounds& destination, const Bounds& source) {
    destination.min_x = std::min(destination.min_x, source.min_x);
    destination.min_y = std::min(destination.min_y, source.min_y);
    destination.max_x = std::max(destination.max_x, source.max_x);
    destination.max_y = std::max(destination.max_y, source.max_y);
}


double bounds_distance_squared(
    const Point& point,
    const Bounds& bounds
) {
    double delta_x = 0.0;

    if (point.x < bounds.min_x) {
        delta_x = bounds.min_x - point.x;
    } else if (point.x > bounds.max_x) {
        delta_x = point.x - bounds.max_x;
    }

    double delta_y = 0.0;

    if (point.y < bounds.min_y) {
        delta_y = bounds.min_y - point.y;
    } else if (point.y > bounds.max_y) {
        delta_y = point.y - bounds.max_y;
    }

    return delta_x * delta_x + delta_y * delta_y;
}


double bounds_center_x(const Bounds& bounds) {
    return (bounds.min_x + bounds.max_x) / 2.0;
}


double bounds_center_y(const Bounds& bounds) {
    return (bounds.min_y + bounds.max_y) / 2.0;
}


// Closed containment test. Used only as a NECESSARY condition for polygon
// membership: a point outside the box is definitively outside the ring, while a
// point inside the box still requires the exact crossing test.
bool bounds_contains_point(const Bounds& bounds, const Point& point) {
    return point.x >= bounds.min_x
        && point.x <= bounds.max_x
        && point.y >= bounds.min_y
        && point.y <= bounds.max_y;
}


// ---------------------------------------------------------------------------
// Distance-exact segment split.
// ---------------------------------------------------------------------------

struct SegmentLeaf {
    Point start;
    Point end;
    int feature_index = -1;
};


struct SplitStatistics {
    std::uint64_t original_segments = 0;
    std::uint64_t split_segments = 0;
    double max_original_length_m = 0.0;
    double max_split_length_m = 0.0;
    double max_segment_length_cap_m = 0.0;
};


double segment_length(const Point& start, const Point& end) {
    const double delta_x = end.x - start.x;
    const double delta_y = end.y - start.y;
    return std::sqrt(delta_x * delta_x + delta_y * delta_y);
}


// Number of equal pieces an original segment is divided into so that no piece
// exceeds the cap. A cap <= 0 disables splitting (one piece).
std::uint64_t split_piece_count(double length, double cap) {
    if (cap <= 0.0 || length <= cap || !std::isfinite(length)) {
        return 1;
    }

    const double pieces = std::ceil(length / cap);

    if (!std::isfinite(pieces) || pieces < 1.0) {
        return 1;
    }

    return static_cast<std::uint64_t>(pieces);
}


// Append the sub-segments of [start, end] to `leaves`, each carrying
// feature_index. Interior split points are linear interpolations; because they
// lie on the original segment, min over the sub-segments of the point-segment
// distance equals the point-segment distance to the original (exactly, up to
// the ~1 ULP representation of the interpolated point). Split geometry is used
// only for BVH bounds, so this residual never reaches a reported distance.
void append_split_segments(
    const Point& start,
    const Point& end,
    int feature_index,
    double cap,
    std::vector<SegmentLeaf>& leaves,
    SplitStatistics& statistics
) {
    const double length = segment_length(start, end);

    ++statistics.original_segments;
    statistics.max_original_length_m =
        std::max(statistics.max_original_length_m, length);

    const std::uint64_t pieces = split_piece_count(length, cap);

    if (pieces <= 1) {
        leaves.push_back(SegmentLeaf{start, end, feature_index});
        ++statistics.split_segments;
        statistics.max_split_length_m =
            std::max(statistics.max_split_length_m, length);
        return;
    }

    const double delta_x = end.x - start.x;
    const double delta_y = end.y - start.y;
    const double step = 1.0 / static_cast<double>(pieces);

    Point previous = start;

    for (std::uint64_t piece = 1; piece <= pieces; ++piece) {
        Point next;

        if (piece == pieces) {
            next = end;
        } else {
            const double fraction =
                static_cast<double>(piece) * step;
            next.x = start.x + fraction * delta_x;
            next.y = start.y + fraction * delta_y;
        }

        leaves.push_back(
            SegmentLeaf{previous, next, feature_index}
        );

        ++statistics.split_segments;
        statistics.max_split_length_m = std::max(
            statistics.max_split_length_m,
            segment_length(previous, next)
        );

        previous = next;
    }
}


std::vector<SegmentLeaf> build_split_segments(
    const std::vector<WaterFeature>& features,
    double cap,
    SplitStatistics& statistics
) {
    std::vector<SegmentLeaf> leaves;
    statistics = SplitStatistics{};
    statistics.max_segment_length_cap_m = cap;

    for (
        std::size_t feature_index = 0;
        feature_index < features.size();
        ++feature_index
    ) {
        const WaterFeature& feature = features[feature_index];

        for (const auto& part_entry : feature.parts) {
            for (const auto& ring_entry : part_entry.second) {
                const std::vector<Point>& vertices =
                    ring_entry.second.vertices;

                for (
                    std::size_t vertex = 1;
                    vertex < vertices.size();
                    ++vertex
                ) {
                    append_split_segments(
                        vertices[vertex - 1],
                        vertices[vertex],
                        static_cast<int>(feature_index),
                        cap,
                        leaves,
                        statistics
                    );
                }
            }
        }
    }

    if (leaves.empty()) {
        throw std::runtime_error(
            "No water segments were produced for the BVH."
        );
    }

    return leaves;
}


// ---------------------------------------------------------------------------
// Segment BVH (median split over segment-box centers).
// ---------------------------------------------------------------------------

struct SegmentBvhNode {
    Bounds bounds;
    std::size_t begin = 0;
    std::size_t end = 0;
    int left_child = -1;
    int right_child = -1;

    bool is_leaf() const {
        return left_child < 0 && right_child < 0;
    }
};


class SegmentBvh {
public:
    SegmentBvh(
        const std::vector<SegmentLeaf>& segments,
        const std::vector<WaterFeature>& features
    )
        : segments_(segments), features_(features) {
        if (segments_.empty()) {
            throw std::invalid_argument(
                "Cannot build a BVH for an empty segment set."
            );
        }

        segment_bounds_.reserve(segments_.size());

        for (const SegmentLeaf& segment : segments_) {
            Bounds bounds;
            expand_bounds(bounds, segment.start);
            expand_bounds(bounds, segment.end);
            segment_bounds_.push_back(bounds);
        }

        segment_order_.resize(segments_.size());
        std::iota(segment_order_.begin(), segment_order_.end(), 0);

        nodes_.reserve(segments_.size() * 2);
        root_index_ = build_node(0, segment_order_.size());
    }

    int root_index() const {
        return root_index_;
    }

    const SegmentBvhNode& node(int index) const {
        return nodes_.at(static_cast<std::size_t>(index));
    }

    std::size_t segment_index_at(std::size_t position) const {
        return static_cast<std::size_t>(segment_order_.at(position));
    }

    const SegmentLeaf& segment(std::size_t segment_index) const {
        return segments_.at(segment_index);
    }

    const Bounds& segment_bounds(std::size_t segment_index) const {
        return segment_bounds_.at(segment_index);
    }

    std::size_t node_count() const {
        return nodes_.size();
    }

    std::size_t segment_count() const {
        return segments_.size();
    }

    // Resident size of the index payload, computed from container element
    // counts rather than measured from the process. It counts the leaf array,
    // the precomputed per-entry bounds, the permutation, and the node array.
    // It deliberately excludes the WaterFeature geometry, which is input rather
    // than index.
    std::size_t index_bytes() const {
        return segments_.size() * sizeof(SegmentLeaf)
            + segment_bounds_.size() * sizeof(Bounds)
            + segment_order_.size() * sizeof(int)
            + nodes_.size() * sizeof(SegmentBvhNode);
    }

private:
    const std::vector<SegmentLeaf>& segments_;
    const std::vector<WaterFeature>& features_;

    std::vector<Bounds> segment_bounds_;
    std::vector<int> segment_order_;
    std::vector<SegmentBvhNode> nodes_;

    int root_index_ = -1;

    // Deterministic tie-break for the median split: segment-box center, then
    // parent water_feature_id, then original segment position. This keeps the
    // tree construction stable and independent of input ordering quirks.
    bool order_before(int left_index, int right_index, bool split_on_x) const {
        const Bounds& left_bounds =
            segment_bounds_[static_cast<std::size_t>(left_index)];
        const Bounds& right_bounds =
            segment_bounds_[static_cast<std::size_t>(right_index)];

        const double left_center = split_on_x
            ? bounds_center_x(left_bounds)
            : bounds_center_y(left_bounds);
        const double right_center = split_on_x
            ? bounds_center_x(right_bounds)
            : bounds_center_y(right_bounds);

        if (left_center != right_center) {
            return left_center < right_center;
        }

        const SegmentLeaf& left_segment =
            segments_[static_cast<std::size_t>(left_index)];
        const SegmentLeaf& right_segment =
            segments_[static_cast<std::size_t>(right_index)];

        const std::string& left_id =
            features_[static_cast<std::size_t>(left_segment.feature_index)]
                .water_feature_id;
        const std::string& right_id =
            features_[static_cast<std::size_t>(right_segment.feature_index)]
                .water_feature_id;

        if (left_id != right_id) {
            return left_id < right_id;
        }

        return left_index < right_index;
    }

    int build_node(std::size_t begin, std::size_t end) {
        if (begin >= end) {
            throw std::runtime_error(
                "Attempted to build an empty BVH node."
            );
        }

        Bounds node_bounds;
        double minimum_center_x = std::numeric_limits<double>::infinity();
        double minimum_center_y = std::numeric_limits<double>::infinity();
        double maximum_center_x = -std::numeric_limits<double>::infinity();
        double maximum_center_y = -std::numeric_limits<double>::infinity();

        for (std::size_t position = begin; position < end; ++position) {
            const int segment_index = segment_order_[position];
            const Bounds& bounds =
                segment_bounds_[static_cast<std::size_t>(segment_index)];

            expand_bounds(node_bounds, bounds);

            const double center_x = bounds_center_x(bounds);
            const double center_y = bounds_center_y(bounds);

            minimum_center_x = std::min(minimum_center_x, center_x);
            minimum_center_y = std::min(minimum_center_y, center_y);
            maximum_center_x = std::max(maximum_center_x, center_x);
            maximum_center_y = std::max(maximum_center_y, center_y);
        }

        const int node_index = static_cast<int>(nodes_.size());
        nodes_.push_back(SegmentBvhNode{node_bounds, begin, end, -1, -1});

        const std::size_t segment_count = end - begin;

        if (segment_count <= SEGMENT_BVH_LEAF_SIZE) {
            return node_index;
        }

        const double x_extent = maximum_center_x - minimum_center_x;
        const double y_extent = maximum_center_y - minimum_center_y;
        const bool split_on_x = x_extent >= y_extent;

        const std::size_t middle = begin + segment_count / 2;

        std::nth_element(
            segment_order_.begin() + static_cast<std::ptrdiff_t>(begin),
            segment_order_.begin() + static_cast<std::ptrdiff_t>(middle),
            segment_order_.begin() + static_cast<std::ptrdiff_t>(end),
            [this, split_on_x](int left_index, int right_index) {
                return order_before(left_index, right_index, split_on_x);
            }
        );

        const int left_child = build_node(begin, middle);
        const int right_child = build_node(middle, end);

        nodes_[static_cast<std::size_t>(node_index)].left_child = left_child;
        nodes_[static_cast<std::size_t>(node_index)].right_child = right_child;

        return node_index;
    }
};


// ---------------------------------------------------------------------------
// Containment support for the "split" verification mode.
//
// Under "original" the crossing test lives inside evaluate_ring and is fused
// with the distance loop. Under "split" the distance comes from the index, so
// the crossing test has to be available on its own. The crossing predicate below
// is character-for-character the same expression evaluate_ring uses, and the
// exterior / hole / part precedence is the same as distance_to_polygon_feature.
// The brute-force kernel itself is NOT modified.
// ---------------------------------------------------------------------------

// feature_index -> part_index -> exterior-ring bounds. Empty for line features.
using PartExteriorBounds = std::vector<std::map<int, Bounds>>;


PartExteriorBounds build_part_exterior_bounds(
    const std::vector<WaterFeature>& features
) {
    PartExteriorBounds all_bounds(features.size());

    for (
        std::size_t feature_index = 0;
        feature_index < features.size();
        ++feature_index
    ) {
        const WaterFeature& feature = features[feature_index];

        if (feature.geometry_kind == "line") {
            continue;
        }

        for (const auto& part_entry : feature.parts) {
            const auto& rings = part_entry.second;
            const auto exterior = rings.find(0);

            if (exterior == rings.end()) {
                continue;
            }

            Bounds bounds;

            for (const Point& vertex : exterior->second.vertices) {
                expand_bounds(bounds, vertex);
            }

            all_bounds[feature_index][part_entry.first] = bounds;
        }
    }

    return all_bounds;
}


struct ContainmentResult {
    bool inside = false;
    std::uint64_t ring_checks = 0;
    std::uint64_t parts_tested = 0;
    std::uint64_t parts_skipped = 0;
};


// Crossing parity over one ring. Mirrors evaluate_ring's predicate exactly,
// without the distance arithmetic.
bool ring_contains_point(
    const Point& point,
    const Ring& ring,
    std::uint64_t& ring_checks
) {
    bool inside = false;

    for (
        std::size_t index = 1;
        index < ring.vertices.size();
        ++index
    ) {
        const Point& start = ring.vertices[index - 1];
        const Point& end = ring.vertices[index];

        ++ring_checks;

        const bool crosses =
            ((start.y > point.y) != (end.y > point.y))
            && (
                point.x
                < (
                    (end.x - start.x)
                    * (point.y - start.y)
                    / (end.y - start.y)
                    + start.x
                )
            );

        if (crosses) {
            inside = !inside;
        }
    }

    return inside;
}


// Exact polygon membership with the bounding-box pre-filter applied per part.
// A part whose exterior-ring box excludes the point cannot contain it, so its
// rings are never walked; that rejection is counted, not silently skipped.
ContainmentResult polygon_contains_point(
    const Point& point,
    const WaterFeature& feature,
    const std::map<int, Bounds>& part_exterior_bounds
) {
    ContainmentResult result;

    for (const auto& part_entry : feature.parts) {
        const auto bounds_entry =
            part_exterior_bounds.find(part_entry.first);

        if (
            bounds_entry != part_exterior_bounds.end()
            && !bounds_contains_point(bounds_entry->second, point)
        ) {
            ++result.parts_skipped;
            continue;
        }

        ++result.parts_tested;

        const auto& rings = part_entry.second;
        const auto exterior = rings.find(0);

        if (exterior == rings.end()) {
            continue;
        }

        const bool inside_exterior = ring_contains_point(
            point,
            exterior->second,
            result.ring_checks
        );

        if (!inside_exterior) {
            continue;
        }

        bool inside_hole = false;

        for (const auto& ring_entry : rings) {
            if (ring_entry.first == 0) {
                continue;
            }

            if (
                ring_contains_point(
                    point,
                    ring_entry.second,
                    result.ring_checks
                )
            ) {
                inside_hole = true;
            }
        }

        if (!inside_hole) {
            result.inside = true;
            return result;
        }
    }

    return result;
}


// ---------------------------------------------------------------------------
// Query.
// ---------------------------------------------------------------------------

struct QueueEntry {
    double lower_bound_squared = 0.0;
    int node_index = -1;
};


struct QueueEntryGreater {
    bool operator()(const QueueEntry& left, const QueueEntry& right) const {
        if (left.lower_bound_squared != right.lower_bound_squared) {
            return left.lower_bound_squared > right.lower_bound_squared;
        }

        return left.node_index > right.node_index;
    }
};


bool lower_bound_can_compete(
    double lower_bound_squared,
    double best_distance,
    double tie_tolerance_meters
) {
    if (!std::isfinite(best_distance)) {
        return true;
    }

    const double threshold = best_distance + tie_tolerance_meters;
    return lower_bound_squared <= threshold * threshold;
}


struct SegmentNearestResult {
    int feature_index = -1;
    double distance = std::numeric_limits<double>::infinity();
    int tie_count = 0;

    // Search side (phase 1).
    std::uint64_t node_visits = 0;
    std::uint64_t segment_box_tests = 0;

    // Verification side (phase 2).
    std::uint64_t candidate_feature_checks = 0;

    // Total phase-2 per-segment geometry work, whatever its kind. Under
    // "original" this is the sum of the two decomposition counters below; under
    // "split" it is the containment ring walk, because no distance work is done
    // over feature geometry at all.
    std::uint64_t segment_checks = 0;

    // Decomposition of "original"-mode verification by candidate geometry kind.
    // This is what bounds the achievable saving of "split" mode, and it is
    // measured under "original" so the bound precedes the conclusion.
    std::uint64_t line_segment_checks = 0;
    std::uint64_t polygon_segment_checks = 0;

    // Ring segments walked purely for the inside/outside predicate. Zero under
    // "original", where the crossing test is fused into the distance loop.
    std::uint64_t containment_ring_checks = 0;
    std::uint64_t containment_parts_tested = 0;
    std::uint64_t containment_parts_skipped = 0;
};


// Phase 1: best-first traversal of the segment BVH. Establishes the nearest
// boundary distance and the set of candidate features (every feature with a
// sub-segment whose box competes at the final best + tie_tolerance threshold).
void collect_candidate_features(
    const Point& point,
    const SegmentBvh& index,
    double tie_tolerance_meters,
    std::vector<int>& candidate_features,
    std::vector<char>& feature_is_candidate,
    std::vector<double>& feature_best_split_distance,
    SegmentNearestResult& result
) {
    std::priority_queue<
        QueueEntry,
        std::vector<QueueEntry>,
        QueueEntryGreater
    > queue;

    double best_boundary_distance = std::numeric_limits<double>::infinity();

    queue.push(
        QueueEntry{
            bounds_distance_squared(point, index.node(index.root_index()).bounds),
            index.root_index()
        }
    );

    while (!queue.empty()) {
        const QueueEntry entry = queue.top();
        queue.pop();

        if (
            !lower_bound_can_compete(
                entry.lower_bound_squared,
                best_boundary_distance,
                tie_tolerance_meters
            )
        ) {
            break;
        }

        ++result.node_visits;

        const SegmentBvhNode& node = index.node(entry.node_index);

        if (node.is_leaf()) {
            for (
                std::size_t position = node.begin;
                position < node.end;
                ++position
            ) {
                const std::size_t segment_index =
                    index.segment_index_at(position);

                const double segment_lower_bound =
                    bounds_distance_squared(
                        point,
                        index.segment_bounds(segment_index)
                    );

                if (
                    !lower_bound_can_compete(
                        segment_lower_bound,
                        best_boundary_distance,
                        tie_tolerance_meters
                    )
                ) {
                    continue;
                }

                ++result.segment_box_tests;

                const SegmentLeaf& segment = index.segment(segment_index);

                const double distance_squared =
                    point_segment_distance_squared(
                        point,
                        segment.start,
                        segment.end
                    );

                const double distance = std::sqrt(distance_squared);

                if (distance < best_boundary_distance) {
                    best_boundary_distance = distance;
                }

                const std::size_t feature_index =
                    static_cast<std::size_t>(segment.feature_index);

                if (!feature_is_candidate[feature_index]) {
                    feature_is_candidate[feature_index] = 1;
                    feature_best_split_distance[feature_index] = distance;
                    candidate_features.push_back(segment.feature_index);
                } else if (
                    distance
                    < feature_best_split_distance[feature_index]
                ) {
                    feature_best_split_distance[feature_index] = distance;
                }
            }

            continue;
        }

        const SegmentBvhNode& left = index.node(node.left_child);
        const double left_lower_bound =
            bounds_distance_squared(point, left.bounds);

        if (
            lower_bound_can_compete(
                left_lower_bound,
                best_boundary_distance,
                tie_tolerance_meters
            )
        ) {
            queue.push(QueueEntry{left_lower_bound, node.left_child});
        }

        const SegmentBvhNode& right = index.node(node.right_child);
        const double right_lower_bound =
            bounds_distance_squared(point, right.bounds);

        if (
            lower_bound_can_compete(
                right_lower_bound,
                best_boundary_distance,
                tie_tolerance_meters
            )
        ) {
            queue.push(QueueEntry{right_lower_bound, node.right_child});
        }
    }
}


// Phase 2: run the exact brute-force tie loop over the candidate features.
//
// The SELECTION logic is unchanged from write_brute_force_results, restricted to
// the candidate set. Only the source of each candidate's distance depends on the
// verification mode:
//
//   OriginalGeometry  distance_to_feature over original geometry (unchanged
//                     kernel), so the result is byte-identical to the reference.
//
//   SplitGeometry     the phase-1 minimum over split sub-segments, plus an exact
//                     containment test for polygon candidates because a split
//                     segment cannot express interior-zero.
SegmentNearestResult find_nearest_segment_bvh(
    const Point& point,
    const std::vector<WaterFeature>& features,
    const SegmentBvh& index,
    const PartExteriorBounds& part_exterior_bounds,
    std::vector<char>& feature_is_candidate_scratch,
    std::vector<double>& feature_best_split_distance_scratch,
    VerificationMode verification_mode,
    double tie_tolerance_meters
) {
    SegmentNearestResult result;

    std::vector<int> candidate_features;
    candidate_features.reserve(64);

    collect_candidate_features(
        point,
        index,
        tie_tolerance_meters,
        candidate_features,
        feature_is_candidate_scratch,
        feature_best_split_distance_scratch,
        result
    );

    double best_distance = std::numeric_limits<double>::infinity();
    int best_feature_index = -1;
    int tie_count = 0;

    for (const int feature_index : candidate_features) {
        const std::size_t feature_position =
            static_cast<std::size_t>(feature_index);

        // Reset the scratch buffers so they are clean for the next property.
        feature_is_candidate_scratch[feature_position] = 0;

        const double split_distance =
            feature_best_split_distance_scratch[feature_position];

        feature_best_split_distance_scratch[feature_position] =
            std::numeric_limits<double>::infinity();

        const WaterFeature& feature = features[feature_position];

        ++result.candidate_feature_checks;

        double candidate_distance =
            std::numeric_limits<double>::infinity();

        if (verification_mode == VerificationMode::OriginalGeometry) {
            const DistanceResult candidate =
                distance_to_feature(point, feature);

            candidate_distance = candidate.distance;
            result.segment_checks += candidate.segment_checks;

            if (feature.geometry_kind == "line") {
                result.line_segment_checks += candidate.segment_checks;
            } else {
                result.polygon_segment_checks += candidate.segment_checks;
            }
        } else {
            candidate_distance = split_distance;

            if (feature.geometry_kind != "line") {
                // On-boundary is decided from the split minimum here, because
                // recomputing it over original geometry would reintroduce the
                // scan this mode exists to avoid. See the hazard note in the
                // file header: the split perturbation is the same order as
                // BOUNDARY_EPSILON_METERS.
                if (candidate_distance <= BOUNDARY_EPSILON_METERS) {
                    candidate_distance = 0.0;
                } else {
                    const ContainmentResult containment =
                        polygon_contains_point(
                            point,
                            feature,
                            part_exterior_bounds[feature_position]
                        );

                    result.containment_ring_checks +=
                        containment.ring_checks;
                    result.containment_parts_tested +=
                        containment.parts_tested;
                    result.containment_parts_skipped +=
                        containment.parts_skipped;
                    result.segment_checks += containment.ring_checks;

                    if (containment.inside) {
                        candidate_distance = 0.0;
                    }
                }
            }
        }

        if (candidate_distance < best_distance - tie_tolerance_meters) {
            best_distance = candidate_distance;
            best_feature_index = feature_index;
            tie_count = 1;
            continue;
        }

        if (
            std::abs(candidate_distance - best_distance)
            <= tie_tolerance_meters
        ) {
            ++tie_count;

            if (
                best_feature_index < 0
                || feature.water_feature_id
                    < features[
                        static_cast<std::size_t>(best_feature_index)
                    ].water_feature_id
            ) {
                best_distance = candidate_distance;
                best_feature_index = feature_index;
            }
        }
    }

    if (best_feature_index < 0) {
        throw std::runtime_error(
            "The segment BVH did not return a nearest feature."
        );
    }

    result.feature_index = best_feature_index;
    result.distance = best_distance;
    result.tie_count = tie_count;

    return result;
}


[[maybe_unused]] void write_segment_bvh_results(
    const std::string& output_path,
    const std::vector<PropertyPoint>& properties,
    const std::vector<WaterFeature>& features,
    const SegmentBvh& index,
    const PartExteriorBounds& part_exterior_bounds,
    const std::string& distance_crs,
    VerificationMode verification_mode,
    double tie_tolerance_meters
) {
    const std::filesystem::path filesystem_path(output_path);

    if (!filesystem_path.parent_path().empty()) {
        std::filesystem::create_directories(filesystem_path.parent_path());
    }

    std::ofstream output(output_path);

    if (!output) {
        throw std::runtime_error(
            "Could not open output file: " + output_path
        );
    }

    output
        << "property_id,"
        << "cpp_nearest_water_distance_m,"
        << "cpp_nearest_water_feature_id,"
        << "cpp_nearest_water_feature_class,"
        << "cpp_nearest_water_feature_type,"
        << "cpp_nearest_water_source_id,"
        << "cpp_nearest_water_source_object_id,"
        << "cpp_nearest_water_name,"
        << "cpp_nearest_water_tie_count,"
        << "cpp_segment_checks,"
        << "cpp_candidate_feature_checks,"
        << "cpp_index_node_visits,"
        << "cpp_segment_box_tests,"
        << "cpp_line_segment_checks,"
        << "cpp_polygon_segment_checks,"
        << "cpp_containment_ring_checks,"
        << "cpp_containment_parts_tested,"
        << "cpp_containment_parts_skipped,"
        << "distance_crs,"
        << "verification_mode,"
        << "algorithm\n";

    output << std::setprecision(17);

    std::uint64_t total_node_visits = 0;
    std::uint64_t total_candidate_checks = 0;
    std::uint64_t total_segment_checks = 0;
    std::uint64_t total_segment_box_tests = 0;
    std::uint64_t total_line_segment_checks = 0;
    std::uint64_t total_polygon_segment_checks = 0;
    std::uint64_t total_containment_ring_checks = 0;
    std::uint64_t total_containment_parts_tested = 0;
    std::uint64_t total_containment_parts_skipped = 0;

    // Reusable scratch buffers, cleared per property inside the phase-2 loop.
    // Avoids reallocating per query.
    std::vector<char> feature_is_candidate(features.size(), 0);

    std::vector<double> feature_best_split_distance(
        features.size(),
        std::numeric_limits<double>::infinity()
    );

    const auto computation_start = std::chrono::steady_clock::now();

    for (
        std::size_t property_index = 0;
        property_index < properties.size();
        ++property_index
    ) {
        const PropertyPoint& property = properties[property_index];

        const SegmentNearestResult nearest =
            find_nearest_segment_bvh(
                property.point,
                features,
                index,
                part_exterior_bounds,
                feature_is_candidate,
                feature_best_split_distance,
                verification_mode,
                tie_tolerance_meters
            );

        const WaterFeature& selected =
            features[static_cast<std::size_t>(nearest.feature_index)];

        output
            << csv_escape(property.property_id) << ","
            << nearest.distance << ","
            << csv_escape(selected.water_feature_id) << ","
            << csv_escape(selected.water_feature_class) << ","
            << csv_escape(selected.water_feature_type) << ","
            << csv_escape(selected.source_feature_id) << ","
            << selected.source_object_id << ","
            << csv_escape(selected.source_name) << ","
            << nearest.tie_count << ","
            << nearest.segment_checks << ","
            << nearest.candidate_feature_checks << ","
            << nearest.node_visits << ","
            << nearest.segment_box_tests << ","
            << nearest.line_segment_checks << ","
            << nearest.polygon_segment_checks << ","
            << nearest.containment_ring_checks << ","
            << nearest.containment_parts_tested << ","
            << nearest.containment_parts_skipped << ","
            << csv_escape(distance_crs) << ","
            << verification_mode_name(verification_mode)
            << ",segment_bvh\n";

        total_node_visits += nearest.node_visits;
        total_candidate_checks += nearest.candidate_feature_checks;
        total_segment_checks += nearest.segment_checks;
        total_segment_box_tests += nearest.segment_box_tests;
        total_line_segment_checks += nearest.line_segment_checks;
        total_polygon_segment_checks += nearest.polygon_segment_checks;
        total_containment_ring_checks += nearest.containment_ring_checks;
        total_containment_parts_tested +=
            nearest.containment_parts_tested;
        total_containment_parts_skipped +=
            nearest.containment_parts_skipped;

        if (
            (property_index + 1) % 100 == 0
            || property_index + 1 == properties.size()
        ) {
            std::cout
                << "Processed " << (property_index + 1)
                << "/" << properties.size() << " properties\n";
        }
    }

    const auto computation_end = std::chrono::steady_clock::now();

    const double elapsed_seconds =
        std::chrono::duration<double>(
            computation_end - computation_start
        ).count();

    const double property_count =
        static_cast<double>(properties.size());

    std::cout
        << std::fixed << std::setprecision(6)
        << "Segment-BVH computation seconds: " << elapsed_seconds << "\n"
        << "Properties per second: "
        << property_count / elapsed_seconds << "\n"
        << "Total index node visits: " << total_node_visits << "\n"
        << "Average node visits per property: "
        << total_node_visits / property_count << "\n"
        << "Total candidate feature checks: " << total_candidate_checks << "\n"
        << "Average candidate features per property: "
        << total_candidate_checks / property_count << "\n"
        << "Total segment checks: " << total_segment_checks << "\n"
        << "Average segment checks per property: "
        << total_segment_checks / property_count << "\n"
        << "Total segment box tests: " << total_segment_box_tests << "\n"
        << "Average segment box tests per property: "
        << total_segment_box_tests / property_count << "\n"
        << "Total line candidate segment checks: "
        << total_line_segment_checks << "\n"
        << "Average line candidate segment checks per property: "
        << total_line_segment_checks / property_count << "\n"
        << "Total polygon candidate segment checks: "
        << total_polygon_segment_checks << "\n"
        << "Average polygon candidate segment checks per property: "
        << total_polygon_segment_checks / property_count << "\n"
        << "Total containment ring checks: "
        << total_containment_ring_checks << "\n"
        << "Average containment ring checks per property: "
        << total_containment_ring_checks / property_count << "\n"
        << "Total containment parts tested: "
        << total_containment_parts_tested << "\n"
        << "Total containment parts skipped: "
        << total_containment_parts_skipped << "\n";
}


[[maybe_unused]] VerificationMode parse_verification_mode(
    const std::string& raw_value
) {
    if (raw_value == "original") {
        return VerificationMode::OriginalGeometry;
    }

    if (raw_value == "split") {
        return VerificationMode::SplitGeometry;
    }

    throw std::runtime_error(
        "Invalid verification_mode (expected 'original' or 'split'): "
        + raw_value
    );
}


[[maybe_unused]] double parse_cap_argument(const std::string& raw_value) {
    std::size_t consumed = 0;
    double parsed = 0.0;

    try {
        parsed = std::stod(raw_value, &consumed);
    } catch (const std::exception&) {
        throw std::runtime_error(
            "Invalid max_segment_length_m: " + raw_value
        );
    }

    if (consumed != raw_value.size() || !std::isfinite(parsed)) {
        throw std::runtime_error(
            "Invalid max_segment_length_m: " + raw_value
        );
    }

    return parsed;
}


}  // namespace


#ifndef CAPRM_SEGMENT_BVH_NO_MAIN

int main(int argc, char* argv[]) {
    if (argc < 5 || argc > 8) {
        std::cerr
            << "Usage:\n"
            << "  water_distance_segment_bvh.exe "
            << "<properties_csv> "
            << "<features_csv> "
            << "<vertices_csv> "
            << "<output_csv> "
            << "[distance_crs] "
            << "[max_segment_length_m] "
            << "[verification_mode]\n"
            << "\n"
            << "  max_segment_length_m  entry-extent cap in metres; "
            << "<= 0 disables splitting (default "
            << DEFAULT_MAX_SEGMENT_LENGTH_METERS << ")\n"
            << "  verification_mode     'original' (default) or 'split'\n";

        return 1;
    }

    const std::string properties_path = argv[1];
    const std::string features_path = argv[2];
    const std::string vertices_path = argv[3];
    const std::string output_path = argv[4];

    const std::string distance_crs = argc >= 6 ? argv[5] : "EPSG:26918";

    double max_segment_length_m = DEFAULT_MAX_SEGMENT_LENGTH_METERS;

    if (argc >= 7) {
        max_segment_length_m = parse_cap_argument(argv[6]);
    }

    VerificationMode verification_mode =
        VerificationMode::OriginalGeometry;

    if (argc == 8) {
        verification_mode = parse_verification_mode(argv[7]);
    }

    try {
        const auto load_start = std::chrono::steady_clock::now();

        const std::vector<PropertyPoint> properties =
            read_properties(properties_path);

        std::vector<WaterFeature> features =
            read_feature_metadata(features_path);

        const std::uint64_t vertex_count =
            read_vertices(vertices_path, features);

        const std::uint64_t segment_count = validate_geometry(features);

        const auto load_end = std::chrono::steady_clock::now();

        const auto index_start = std::chrono::steady_clock::now();

        SplitStatistics split_statistics;
        const std::vector<SegmentLeaf> segments =
            build_split_segments(
                features,
                max_segment_length_m,
                split_statistics
            );

        const SegmentBvh index(segments, features);

        const PartExteriorBounds part_exterior_bounds =
            build_part_exterior_bounds(features);

        const auto index_end = std::chrono::steady_clock::now();

        const double load_seconds =
            std::chrono::duration<double>(load_end - load_start).count();
        const double index_seconds =
            std::chrono::duration<double>(index_end - index_start).count();

        std::cout
            << "Properties: " << properties.size() << "\n"
            << "Water features: " << features.size() << "\n"
            << "Vertices: " << vertex_count << "\n"
            << "Segments (kernel count): " << segment_count << "\n"
            << "Original segments (split input): "
            << split_statistics.original_segments << "\n"
            << "Split segments (BVH leaves): "
            << split_statistics.split_segments << "\n"
            << "Added segments: "
            << (split_statistics.split_segments
                - split_statistics.original_segments) << "\n"
            << "Max segment length cap (m): "
            << std::fixed << std::setprecision(6)
            << split_statistics.max_segment_length_cap_m << "\n"
            << "Max original segment length (m): "
            << split_statistics.max_original_length_m << "\n"
            << "Max split segment length (m): "
            << split_statistics.max_split_length_m << "\n"
            << "Index entries: " << index.segment_count() << "\n"
            << "Index bytes: " << index.index_bytes() << "\n"
            << "Max entry extent (m): "
            << split_statistics.max_split_length_m << "\n"
            << "BVH nodes: " << index.node_count() << "\n"
            << "Verification mode: "
            << verification_mode_name(verification_mode) << "\n"
            << "Input loading seconds: " << load_seconds << "\n"
            << "Index construction seconds: " << index_seconds << "\n";

        write_segment_bvh_results(
            output_path,
            properties,
            features,
            index,
            part_exterior_bounds,
            distance_crs,
            verification_mode,
            DEFAULT_TIE_TOLERANCE_METERS
        );

        std::cout
            << "Wrote segment-BVH C++ output to " << output_path << "\n";
    } catch (const std::exception& exception) {
        std::cerr << "Error: " << exception.what() << "\n";
        return 1;
    }

    return 0;
}

#endif  // CAPRM_SEGMENT_BVH_NO_MAIN