#define main caprm_bruteforce_program_main
#include "water_distance_bruteforce.cpp"
#undef main

#include <numeric>
#include <queue>


namespace {

constexpr std::size_t BVH_LEAF_SIZE = 8;


struct Bounds {
    double min_x =
        std::numeric_limits<double>::infinity();

    double min_y =
        std::numeric_limits<double>::infinity();

    double max_x =
        -std::numeric_limits<double>::infinity();

    double max_y =
        -std::numeric_limits<double>::infinity();
};


void expand_bounds(
    Bounds& bounds,
    const Point& point
) {
    bounds.min_x = std::min(
        bounds.min_x,
        point.x
    );

    bounds.min_y = std::min(
        bounds.min_y,
        point.y
    );

    bounds.max_x = std::max(
        bounds.max_x,
        point.x
    );

    bounds.max_y = std::max(
        bounds.max_y,
        point.y
    );
}


void expand_bounds(
    Bounds& destination,
    const Bounds& source
) {
    destination.min_x = std::min(
        destination.min_x,
        source.min_x
    );

    destination.min_y = std::min(
        destination.min_y,
        source.min_y
    );

    destination.max_x = std::max(
        destination.max_x,
        source.max_x
    );

    destination.max_y = std::max(
        destination.max_y,
        source.max_y
    );
}


bool valid_bounds(const Bounds& bounds) {
    return (
        std::isfinite(bounds.min_x)
        && std::isfinite(bounds.min_y)
        && std::isfinite(bounds.max_x)
        && std::isfinite(bounds.max_y)
        && bounds.min_x <= bounds.max_x
        && bounds.min_y <= bounds.max_y
    );
}


Bounds calculate_feature_bounds(
    const WaterFeature& feature
) {
    Bounds bounds;

    for (const auto& part_entry : feature.parts) {
        for (
            const auto& ring_entry :
            part_entry.second
        ) {
            for (
                const Point& point :
                ring_entry.second.vertices
            ) {
                expand_bounds(bounds, point);
            }
        }
    }

    if (!valid_bounds(bounds)) {
        throw std::runtime_error(
            "Could not calculate bounds for feature "
            + feature.water_feature_id
        );
    }

    return bounds;
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

    return (
        delta_x * delta_x
        + delta_y * delta_y
    );
}


double bounds_center_x(const Bounds& bounds) {
    return (
        bounds.min_x + bounds.max_x
    ) / 2.0;
}


double bounds_center_y(const Bounds& bounds) {
    return (
        bounds.min_y + bounds.max_y
    ) / 2.0;
}


struct BvhNode {
    Bounds bounds;

    std::size_t begin = 0;
    std::size_t end = 0;

    int left_child = -1;
    int right_child = -1;

    bool is_leaf() const {
        return (
            left_child < 0
            && right_child < 0
        );
    }
};


class FeatureBvh {
public:
    explicit FeatureBvh(
        const std::vector<WaterFeature>& features
    )
        : features_(features)
    {
        if (features_.empty()) {
            throw std::invalid_argument(
                "Cannot build a BVH for an empty feature set."
            );
        }

        feature_bounds_.reserve(
            features_.size()
        );

        for (
            const WaterFeature& feature :
            features_
        ) {
            feature_bounds_.push_back(
                calculate_feature_bounds(feature)
            );
        }

        feature_order_.resize(
            features_.size()
        );

        std::iota(
            feature_order_.begin(),
            feature_order_.end(),
            0
        );

        nodes_.reserve(
            features_.size() * 2
        );

        root_index_ = build_node(
            0,
            feature_order_.size()
        );
    }

    int root_index() const {
        return root_index_;
    }

    const BvhNode& node(int index) const {
        return nodes_.at(
            static_cast<std::size_t>(index)
        );
    }

    int feature_index_at(
        std::size_t position
    ) const {
        return feature_order_.at(position);
    }

    const Bounds& feature_bounds(
        int feature_index
    ) const {
        return feature_bounds_.at(
            static_cast<std::size_t>(
                feature_index
            )
        );
    }

    std::size_t node_count() const {
        return nodes_.size();
    }

private:
    const std::vector<WaterFeature>& features_;

    std::vector<Bounds> feature_bounds_;
    std::vector<int> feature_order_;
    std::vector<BvhNode> nodes_;

    int root_index_ = -1;

    int build_node(
        std::size_t begin,
        std::size_t end
    ) {
        if (begin >= end) {
            throw std::runtime_error(
                "Attempted to build an empty BVH node."
            );
        }

        Bounds node_bounds;

        double minimum_center_x =
            std::numeric_limits<double>::infinity();

        double minimum_center_y =
            std::numeric_limits<double>::infinity();

        double maximum_center_x =
            -std::numeric_limits<double>::infinity();

        double maximum_center_y =
            -std::numeric_limits<double>::infinity();

        for (
            std::size_t position = begin;
            position < end;
            ++position
        ) {
            const int feature_index =
                feature_order_[position];

            const Bounds& bounds =
                feature_bounds_[
                    static_cast<std::size_t>(
                        feature_index
                    )
                ];

            expand_bounds(
                node_bounds,
                bounds
            );

            const double center_x =
                bounds_center_x(bounds);

            const double center_y =
                bounds_center_y(bounds);

            minimum_center_x = std::min(
                minimum_center_x,
                center_x
            );

            minimum_center_y = std::min(
                minimum_center_y,
                center_y
            );

            maximum_center_x = std::max(
                maximum_center_x,
                center_x
            );

            maximum_center_y = std::max(
                maximum_center_y,
                center_y
            );
        }

        const int node_index =
            static_cast<int>(nodes_.size());

        nodes_.push_back(
            BvhNode{
                node_bounds,
                begin,
                end,
                -1,
                -1
            }
        );

        const std::size_t feature_count =
            end - begin;

        if (feature_count <= BVH_LEAF_SIZE) {
            return node_index;
        }

        const double x_extent =
            maximum_center_x - minimum_center_x;

        const double y_extent =
            maximum_center_y - minimum_center_y;

        const bool split_on_x =
            x_extent >= y_extent;

        const std::size_t middle =
            begin + feature_count / 2;

        std::nth_element(
            feature_order_.begin()
                + static_cast<std::ptrdiff_t>(begin),
            feature_order_.begin()
                + static_cast<std::ptrdiff_t>(middle),
            feature_order_.begin()
                + static_cast<std::ptrdiff_t>(end),
            [this, split_on_x](
                int left_index,
                int right_index
            ) {
                const Bounds& left_bounds =
                    feature_bounds_[
                        static_cast<std::size_t>(
                            left_index
                        )
                    ];

                const Bounds& right_bounds =
                    feature_bounds_[
                        static_cast<std::size_t>(
                            right_index
                        )
                    ];

                const double left_center =
                    split_on_x
                    ? bounds_center_x(left_bounds)
                    : bounds_center_y(left_bounds);

                const double right_center =
                    split_on_x
                    ? bounds_center_x(right_bounds)
                    : bounds_center_y(right_bounds);

                if (left_center != right_center) {
                    return left_center < right_center;
                }

                return (
                    features_[
                        static_cast<std::size_t>(
                            left_index
                        )
                    ].water_feature_id
                    <
                    features_[
                        static_cast<std::size_t>(
                            right_index
                        )
                    ].water_feature_id
                );
            }
        );

        const int left_child =
            build_node(begin, middle);

        const int right_child =
            build_node(middle, end);

        nodes_[
            static_cast<std::size_t>(node_index)
        ].left_child = left_child;

        nodes_[
            static_cast<std::size_t>(node_index)
        ].right_child = right_child;

        return node_index;
    }
};


struct QueueEntry {
    double lower_bound_squared = 0.0;
    int node_index = -1;
};


struct QueueEntryGreater {
    bool operator()(
        const QueueEntry& left,
        const QueueEntry& right
    ) const {
        if (
            left.lower_bound_squared
            != right.lower_bound_squared
        ) {
            return (
                left.lower_bound_squared
                > right.lower_bound_squared
            );
        }

        return (
            left.node_index
            > right.node_index
        );
    }
};


struct IndexedNearestResult {
    int feature_index = -1;

    double distance =
        std::numeric_limits<double>::infinity();

    int tie_count = 0;

    std::uint64_t node_visits = 0;
    std::uint64_t candidate_feature_checks = 0;
    std::uint64_t segment_checks = 0;
};


bool lower_bound_can_compete(
    double lower_bound_squared,
    double best_distance,
    double tie_tolerance_meters
) {
    if (!std::isfinite(best_distance)) {
        return true;
    }

    const double threshold =
        best_distance + tie_tolerance_meters;

    return (
        lower_bound_squared
        <= threshold * threshold
    );
}


IndexedNearestResult find_nearest_indexed(
    const Point& point,
    const std::vector<WaterFeature>& features,
    const FeatureBvh& index,
    double tie_tolerance_meters
) {
    IndexedNearestResult result;

    std::priority_queue<
        QueueEntry,
        std::vector<QueueEntry>,
        QueueEntryGreater
    > queue;

    const BvhNode& root =
        index.node(index.root_index());

    queue.push(
        QueueEntry{
            bounds_distance_squared(
                point,
                root.bounds
            ),
            index.root_index()
        }
    );

    while (!queue.empty()) {
        const QueueEntry entry = queue.top();
        queue.pop();

        if (
            !lower_bound_can_compete(
                entry.lower_bound_squared,
                result.distance,
                tie_tolerance_meters
            )
        ) {
            break;
        }

        ++result.node_visits;

        const BvhNode& node =
            index.node(entry.node_index);

        if (node.is_leaf()) {
            for (
                std::size_t position = node.begin;
                position < node.end;
                ++position
            ) {
                const int feature_index =
                    index.feature_index_at(
                        position
                    );

                const double feature_lower_bound =
                    bounds_distance_squared(
                        point,
                        index.feature_bounds(
                            feature_index
                        )
                    );

                if (
                    !lower_bound_can_compete(
                        feature_lower_bound,
                        result.distance,
                        tie_tolerance_meters
                    )
                ) {
                    continue;
                }

                ++result.candidate_feature_checks;

                const WaterFeature& feature =
                    features[
                        static_cast<std::size_t>(
                            feature_index
                        )
                    ];

                const DistanceResult candidate =
                    distance_to_feature(
                        point,
                        feature
                    );

                result.segment_checks +=
                    candidate.segment_checks;

                if (
                    candidate.distance
                    < result.distance
                        - tie_tolerance_meters
                ) {
                    result.distance =
                        candidate.distance;

                    result.feature_index =
                        feature_index;

                    result.tie_count = 1;

                    continue;
                }

                if (
                    std::abs(
                        candidate.distance
                        - result.distance
                    )
                    <= tie_tolerance_meters
                ) {
                    ++result.tie_count;

                    if (
                        result.feature_index < 0
                        || feature.water_feature_id
                            <
                            features[
                                static_cast<std::size_t>(
                                    result.feature_index
                                )
                            ].water_feature_id
                    ) {
                        result.distance =
                            candidate.distance;

                        result.feature_index =
                            feature_index;
                    }
                }
            }

            continue;
        }

        const BvhNode& left =
            index.node(node.left_child);

        const double left_lower_bound =
            bounds_distance_squared(
                point,
                left.bounds
            );

        if (
            lower_bound_can_compete(
                left_lower_bound,
                result.distance,
                tie_tolerance_meters
            )
        ) {
            queue.push(
                QueueEntry{
                    left_lower_bound,
                    node.left_child
                }
            );
        }

        const BvhNode& right =
            index.node(node.right_child);

        const double right_lower_bound =
            bounds_distance_squared(
                point,
                right.bounds
            );

        if (
            lower_bound_can_compete(
                right_lower_bound,
                result.distance,
                tie_tolerance_meters
            )
        ) {
            queue.push(
                QueueEntry{
                    right_lower_bound,
                    node.right_child
                }
            );
        }
    }

    if (result.feature_index < 0) {
        throw std::runtime_error(
            "The BVH did not return a nearest feature."
        );
    }

    return result;
}


void write_indexed_results(
    const std::string& output_path,
    const std::vector<PropertyPoint>& properties,
    const std::vector<WaterFeature>& features,
    const FeatureBvh& index,
    const std::string& distance_crs,
    double tie_tolerance_meters
) {
    const std::filesystem::path filesystem_path(
        output_path
    );

    if (!filesystem_path.parent_path().empty()) {
        std::filesystem::create_directories(
            filesystem_path.parent_path()
        );
    }

    std::ofstream output(output_path);

    if (!output) {
        throw std::runtime_error(
            "Could not open output file: "
            + output_path
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
        << "distance_crs,"
        << "algorithm\n";

    output << std::setprecision(17);

    std::uint64_t total_node_visits = 0;
    std::uint64_t total_candidate_checks = 0;
    std::uint64_t total_segment_checks = 0;

    const auto computation_start =
        std::chrono::steady_clock::now();

    for (
        std::size_t property_index = 0;
        property_index < properties.size();
        ++property_index
    ) {
        const PropertyPoint& property =
            properties[property_index];

        const IndexedNearestResult nearest =
            find_nearest_indexed(
                property.point,
                features,
                index,
                tie_tolerance_meters
            );

        const WaterFeature& selected =
            features[
                static_cast<std::size_t>(
                    nearest.feature_index
                )
            ];

        output
            << csv_escape(property.property_id)
            << ","
            << nearest.distance
            << ","
            << csv_escape(
                selected.water_feature_id
            )
            << ","
            << csv_escape(
                selected.water_feature_class
            )
            << ","
            << csv_escape(
                selected.water_feature_type
            )
            << ","
            << csv_escape(
                selected.source_feature_id
            )
            << ","
            << selected.source_object_id
            << ","
            << csv_escape(selected.source_name)
            << ","
            << nearest.tie_count
            << ","
            << nearest.segment_checks
            << ","
            << nearest.candidate_feature_checks
            << ","
            << nearest.node_visits
            << ","
            << csv_escape(distance_crs)
            << ",feature_bvh\n";

        total_node_visits +=
            nearest.node_visits;

        total_candidate_checks +=
            nearest.candidate_feature_checks;

        total_segment_checks +=
            nearest.segment_checks;

        if (
            (property_index + 1) % 100 == 0
            || property_index + 1
                == properties.size()
        ) {
            std::cout
                << "Processed "
                << (property_index + 1)
                << "/"
                << properties.size()
                << " properties\n";
        }
    }

    const auto computation_end =
        std::chrono::steady_clock::now();

    const double elapsed_seconds =
        std::chrono::duration<double>(
            computation_end - computation_start
        ).count();

    const double property_count =
        static_cast<double>(
            properties.size()
        );

    std::cout
        << std::fixed
        << std::setprecision(6)
        << "Indexed computation seconds: "
        << elapsed_seconds
        << "\n"
        << "Properties per second: "
        << property_count / elapsed_seconds
        << "\n"
        << "Total index node visits: "
        << total_node_visits
        << "\n"
        << "Average node visits per property: "
        << total_node_visits / property_count
        << "\n"
        << "Total candidate feature checks: "
        << total_candidate_checks
        << "\n"
        << "Average candidate features per property: "
        << total_candidate_checks / property_count
        << "\n"
        << "Total segment checks: "
        << total_segment_checks
        << "\n"
        << "Average segment checks per property: "
        << total_segment_checks / property_count
        << "\n";
}


}  // namespace


int main(int argc, char* argv[]) {
    if (argc != 5 && argc != 6) {
        std::cerr
            << "Usage:\n"
            << "  water_distance_indexed.exe "
            << "<properties_csv> "
            << "<features_csv> "
            << "<vertices_csv> "
            << "<output_csv> "
            << "[distance_crs]\n";

        return 1;
    }

    const std::string properties_path =
        argv[1];

    const std::string features_path =
        argv[2];

    const std::string vertices_path =
        argv[3];

    const std::string output_path =
        argv[4];

    const std::string distance_crs =
        argc == 6
        ? argv[5]
        : "EPSG:26918";

    try {
        const auto load_start =
            std::chrono::steady_clock::now();

        const std::vector<PropertyPoint> properties =
            read_properties(
                properties_path
            );

        std::vector<WaterFeature> features =
            read_feature_metadata(
                features_path
            );

        const std::uint64_t vertex_count =
            read_vertices(
                vertices_path,
                features
            );

        const std::uint64_t segment_count =
            validate_geometry(features);

        const auto load_end =
            std::chrono::steady_clock::now();

        const auto index_start =
            std::chrono::steady_clock::now();

        const FeatureBvh index(features);

        const auto index_end =
            std::chrono::steady_clock::now();

        const double load_seconds =
            std::chrono::duration<double>(
                load_end - load_start
            ).count();

        const double index_seconds =
            std::chrono::duration<double>(
                index_end - index_start
            ).count();

        std::cout
            << "Properties: "
            << properties.size()
            << "\n"
            << "Water features: "
            << features.size()
            << "\n"
            << "Vertices: "
            << vertex_count
            << "\n"
            << "Segments: "
            << segment_count
            << "\n"
            << "BVH nodes: "
            << index.node_count()
            << "\n"
            << "Input loading seconds: "
            << std::fixed
            << std::setprecision(6)
            << load_seconds
            << "\n"
            << "Index construction seconds: "
            << index_seconds
            << "\n";

        write_indexed_results(
            output_path,
            properties,
            features,
            index,
            distance_crs,
            DEFAULT_TIE_TOLERANCE_METERS
        );

        std::cout
            << "Wrote indexed C++ output to "
            << output_path
            << "\n";
    } catch (const std::exception& exception) {
        std::cerr
            << "Error: "
            << exception.what()
            << "\n";

        return 1;
    }

    return 0;
}