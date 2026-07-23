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
// Correctness properties (see docs/caprm_flood_code_reconstruction.md, the
// B1b/B1c task notes, and the completion record):
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

    std::uint64_t node_visits = 0;
    std::uint64_t candidate_feature_checks = 0;
    std::uint64_t segment_checks = 0;
    std::uint64_t segment_box_tests = 0;
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
                    candidate_features.push_back(segment.feature_index);
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


// Phase 2: run the exact brute-force tie loop over the candidate features. This
// is the same selection logic as write_brute_force_results, restricted to the
// candidate set; distance_to_feature (unchanged) supplies interior-zero and the
// exact per-feature distance, so the result is byte-identical to the reference.
SegmentNearestResult find_nearest_segment_bvh(
    const Point& point,
    const std::vector<WaterFeature>& features,
    const SegmentBvh& index,
    std::vector<char>& feature_is_candidate_scratch,
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
        result
    );

    double best_distance = std::numeric_limits<double>::infinity();
    int best_feature_index = -1;
    int tie_count = 0;

    for (const int feature_index : candidate_features) {
        // Reset the scratch flag so the buffer is clean for the next property.
        feature_is_candidate_scratch[
            static_cast<std::size_t>(feature_index)
        ] = 0;

        const WaterFeature& feature =
            features[static_cast<std::size_t>(feature_index)];

        const DistanceResult candidate =
            distance_to_feature(point, feature);

        ++result.candidate_feature_checks;
        result.segment_checks += candidate.segment_checks;

        if (candidate.distance < best_distance - tie_tolerance_meters) {
            best_distance = candidate.distance;
            best_feature_index = feature_index;
            tie_count = 1;
            continue;
        }

        if (
            std::abs(candidate.distance - best_distance)
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
                best_distance = candidate.distance;
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
    const std::string& distance_crs,
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
        << "distance_crs,"
        << "algorithm\n";

    output << std::setprecision(17);

    std::uint64_t total_node_visits = 0;
    std::uint64_t total_candidate_checks = 0;
    std::uint64_t total_segment_checks = 0;
    std::uint64_t total_segment_box_tests = 0;

    // One reusable scratch buffer of candidate flags, cleared per property
    // inside the phase-2 loop. Avoids reallocating per query.
    std::vector<char> feature_is_candidate(features.size(), 0);

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
                feature_is_candidate,
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
            << csv_escape(distance_crs) << ",segment_bvh\n";

        total_node_visits += nearest.node_visits;
        total_candidate_checks += nearest.candidate_feature_checks;
        total_segment_checks += nearest.segment_checks;
        total_segment_box_tests += nearest.segment_box_tests;

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
        << total_segment_box_tests / property_count << "\n";
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
    if (argc < 5 || argc > 7) {
        std::cerr
            << "Usage:\n"
            << "  water_distance_segment_bvh.exe "
            << "<properties_csv> "
            << "<features_csv> "
            << "<vertices_csv> "
            << "<output_csv> "
            << "[distance_crs] "
            << "[max_segment_length_m]\n";

        return 1;
    }

    const std::string properties_path = argv[1];
    const std::string features_path = argv[2];
    const std::string vertices_path = argv[3];
    const std::string output_path = argv[4];

    const std::string distance_crs = argc >= 6 ? argv[5] : "EPSG:26918";

    double max_segment_length_m = DEFAULT_MAX_SEGMENT_LENGTH_METERS;

    if (argc == 7) {
        max_segment_length_m = parse_cap_argument(argv[6]);
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
            << "BVH nodes: " << index.node_count() << "\n"
            << "Input loading seconds: " << load_seconds << "\n"
            << "Index construction seconds: " << index_seconds << "\n";

        write_segment_bvh_results(
            output_path,
            properties,
            features,
            index,
            distance_crs,
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