#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>


namespace {

constexpr double BOUNDARY_EPSILON_METERS = 1e-9;
constexpr double DEFAULT_TIE_TOLERANCE_METERS = 1e-6;


struct Point {
    double x = 0.0;
    double y = 0.0;
};


struct PropertyPoint {
    int sample_order = -1;
    std::string property_id;
    Point point;
};


struct Ring {
    std::vector<Point> vertices;
};


struct WaterFeature {
    int water_feature_index = -1;

    std::string water_feature_id;
    std::string water_feature_class;
    std::string water_feature_type;
    std::string source_feature_id;
    long long source_object_id = -1;
    std::string source_name;
    std::string geometry_kind;

    // part_index -> ring_index -> ring
    std::map<int, std::map<int, Ring>> parts;
};


struct RingEvaluation {
    bool inside = false;
    bool on_boundary = false;
    double minimum_distance_squared =
        std::numeric_limits<double>::infinity();
    std::uint64_t segment_checks = 0;
};


struct DistanceResult {
    double distance = std::numeric_limits<double>::infinity();
    std::uint64_t segment_checks = 0;
};


using HeaderMap = std::map<std::string, std::size_t>;


std::string trim(const std::string& value) {
    std::size_t start = 0;

    while (
        start < value.size()
        && std::isspace(
            static_cast<unsigned char>(value[start])
        )
    ) {
        ++start;
    }

    std::size_t end = value.size();

    while (
        end > start
        && std::isspace(
            static_cast<unsigned char>(value[end - 1])
        )
    ) {
        --end;
    }

    return value.substr(start, end - start);
}


void remove_utf8_bom(std::string& value) {
    if (
        value.size() >= 3
        && static_cast<unsigned char>(value[0]) == 0xEF
        && static_cast<unsigned char>(value[1]) == 0xBB
        && static_cast<unsigned char>(value[2]) == 0xBF
    ) {
        value.erase(0, 3);
    }
}


std::vector<std::string> parse_csv_record(
    const std::string& line,
    std::size_t line_number
) {
    std::vector<std::string> fields;
    std::string field;
    bool inside_quotes = false;

    for (std::size_t index = 0; index < line.size(); ++index) {
        const char character = line[index];

        if (character == '"') {
            if (inside_quotes) {
                if (
                    index + 1 < line.size()
                    && line[index + 1] == '"'
                ) {
                    field.push_back('"');
                    ++index;
                } else {
                    inside_quotes = false;
                }
            } else {
                if (!field.empty()) {
                    throw std::runtime_error(
                        "Unexpected quote in CSV field at line "
                        + std::to_string(line_number)
                    );
                }

                inside_quotes = true;
            }

            continue;
        }

        if (character == ',' && !inside_quotes) {
            fields.push_back(field);
            field.clear();
            continue;
        }

        field.push_back(character);
    }

    if (inside_quotes) {
        throw std::runtime_error(
            "Unclosed quoted CSV field at line "
            + std::to_string(line_number)
        );
    }

    fields.push_back(field);
    return fields;
}


HeaderMap read_header(
    std::ifstream& input,
    const std::string& path
) {
    std::string line;

    if (!std::getline(input, line)) {
        throw std::runtime_error(
            "CSV file is empty: " + path
        );
    }

    auto fields = parse_csv_record(line, 1);

    if (fields.empty()) {
        throw std::runtime_error(
            "CSV header is empty: " + path
        );
    }

    remove_utf8_bom(fields[0]);

    HeaderMap header;

    for (
        std::size_t index = 0;
        index < fields.size();
        ++index
    ) {
        const std::string name = trim(fields[index]);

        if (name.empty()) {
            throw std::runtime_error(
                "CSV contains an empty header field: " + path
            );
        }

        if (!header.emplace(name, index).second) {
            throw std::runtime_error(
                "CSV contains duplicate header field '"
                + name + "': " + path
            );
        }
    }

    return header;
}


std::size_t require_column(
    const HeaderMap& header,
    const std::string& column,
    const std::string& path
) {
    const auto iterator = header.find(column);

    if (iterator == header.end()) {
        throw std::runtime_error(
            "Required column '" + column
            + "' is absent from " + path
        );
    }

    return iterator->second;
}


const std::string& field_at(
    const std::vector<std::string>& fields,
    std::size_t index,
    const std::string& column,
    std::size_t line_number
) {
    if (index >= fields.size()) {
        throw std::runtime_error(
            "CSV row is missing column '" + column
            + "' at line " + std::to_string(line_number)
        );
    }

    return fields[index];
}


int parse_int(
    const std::string& raw_value,
    const std::string& column,
    std::size_t line_number
) {
    const std::string value = trim(raw_value);

    if (value.empty()) {
        throw std::runtime_error(
            "Missing integer in column '" + column
            + "' at line " + std::to_string(line_number)
        );
    }

    std::size_t consumed = 0;
    long long parsed = 0;

    try {
        parsed = std::stoll(value, &consumed);
    } catch (const std::exception&) {
        throw std::runtime_error(
            "Invalid integer in column '" + column
            + "' at line " + std::to_string(line_number)
            + ": " + value
        );
    }

    if (
        consumed != value.size()
        || parsed < std::numeric_limits<int>::min()
        || parsed > std::numeric_limits<int>::max()
    ) {
        throw std::runtime_error(
            "Invalid integer in column '" + column
            + "' at line " + std::to_string(line_number)
            + ": " + value
        );
    }

    return static_cast<int>(parsed);
}


long long parse_long_long(
    const std::string& raw_value,
    const std::string& column,
    std::size_t line_number
) {
    const std::string value = trim(raw_value);

    if (value.empty()) {
        throw std::runtime_error(
            "Missing integer in column '" + column
            + "' at line " + std::to_string(line_number)
        );
    }

    std::size_t consumed = 0;
    long long parsed = 0;

    try {
        parsed = std::stoll(value, &consumed);
    } catch (const std::exception&) {
        throw std::runtime_error(
            "Invalid integer in column '" + column
            + "' at line " + std::to_string(line_number)
            + ": " + value
        );
    }

    if (consumed != value.size()) {
        throw std::runtime_error(
            "Invalid integer in column '" + column
            + "' at line " + std::to_string(line_number)
            + ": " + value
        );
    }

    return parsed;
}


double parse_double(
    const std::string& raw_value,
    const std::string& column,
    std::size_t line_number
) {
    const std::string value = trim(raw_value);

    if (value.empty()) {
        throw std::runtime_error(
            "Missing number in column '" + column
            + "' at line " + std::to_string(line_number)
        );
    }

    std::size_t consumed = 0;
    double parsed = 0.0;

    try {
        parsed = std::stod(value, &consumed);
    } catch (const std::exception&) {
        throw std::runtime_error(
            "Invalid number in column '" + column
            + "' at line " + std::to_string(line_number)
            + ": " + value
        );
    }

    if (
        consumed != value.size()
        || !std::isfinite(parsed)
    ) {
        throw std::runtime_error(
            "Invalid finite number in column '" + column
            + "' at line " + std::to_string(line_number)
            + ": " + value
        );
    }

    return parsed;
}


std::string csv_escape(const std::string& value) {
    if (
        value.find_first_of(",\"\n\r")
        == std::string::npos
    ) {
        return value;
    }

    std::string escaped = "\"";

    for (const char character : value) {
        if (character == '"') {
            escaped += "\"\"";
        } else {
            escaped += character;
        }
    }

    escaped += '"';
    return escaped;
}


std::vector<PropertyPoint> read_properties(
    const std::string& path
) {
    std::ifstream input(path);

    if (!input) {
        throw std::runtime_error(
            "Could not open property input: " + path
        );
    }

    const HeaderMap header = read_header(input, path);

    const std::size_t sample_order_column =
        require_column(header, "sample_order", path);

    const std::size_t property_id_column =
        require_column(header, "property_id", path);

    const std::size_t x_column =
        require_column(header, "projected_x", path);

    const std::size_t y_column =
        require_column(header, "projected_y", path);

    std::vector<PropertyPoint> properties;
    std::set<std::string> property_ids;

    std::string line;
    std::size_t line_number = 1;

    while (std::getline(input, line)) {
        ++line_number;

        if (line.empty()) {
            continue;
        }

        const auto fields = parse_csv_record(
            line,
            line_number
        );

        PropertyPoint property;

        property.sample_order = parse_int(
            field_at(
                fields,
                sample_order_column,
                "sample_order",
                line_number
            ),
            "sample_order",
            line_number
        );

        property.property_id = trim(
            field_at(
                fields,
                property_id_column,
                "property_id",
                line_number
            )
        );

        property.point.x = parse_double(
            field_at(
                fields,
                x_column,
                "projected_x",
                line_number
            ),
            "projected_x",
            line_number
        );

        property.point.y = parse_double(
            field_at(
                fields,
                y_column,
                "projected_y",
                line_number
            ),
            "projected_y",
            line_number
        );

        if (property.property_id.empty()) {
            throw std::runtime_error(
                "Missing property_id at line "
                + std::to_string(line_number)
            );
        }

        if (
            property.sample_order
            != static_cast<int>(properties.size())
        ) {
            throw std::runtime_error(
                "sample_order is not contiguous at line "
                + std::to_string(line_number)
            );
        }

        if (
            !property_ids.insert(
                property.property_id
            ).second
        ) {
            throw std::runtime_error(
                "Duplicate property_id: "
                + property.property_id
            );
        }

        properties.push_back(std::move(property));
    }

    if (properties.empty()) {
        throw std::runtime_error(
            "Property input contains no rows: " + path
        );
    }

    return properties;
}


std::vector<WaterFeature> read_feature_metadata(
    const std::string& path
) {
    std::ifstream input(path);

    if (!input) {
        throw std::runtime_error(
            "Could not open feature metadata input: " + path
        );
    }

    const HeaderMap header = read_header(input, path);

    const std::size_t index_column =
        require_column(
            header,
            "water_feature_index",
            path
        );

    const std::size_t id_column =
        require_column(
            header,
            "water_feature_id",
            path
        );

    const std::size_t class_column =
        require_column(
            header,
            "water_feature_class",
            path
        );

    const std::size_t type_column =
        require_column(
            header,
            "water_feature_type",
            path
        );

    const std::size_t source_id_column =
        require_column(
            header,
            "source_feature_id",
            path
        );

    const std::size_t object_id_column =
        require_column(
            header,
            "source_object_id",
            path
        );

    const std::size_t name_column =
        require_column(
            header,
            "source_name",
            path
        );

    const std::size_t geometry_kind_column =
        require_column(
            header,
            "geometry_kind",
            path
        );

    std::vector<WaterFeature> features;
    std::set<std::string> feature_ids;

    std::string line;
    std::size_t line_number = 1;

    while (std::getline(input, line)) {
        ++line_number;

        if (line.empty()) {
            continue;
        }

        const auto fields = parse_csv_record(
            line,
            line_number
        );

        WaterFeature feature;

        feature.water_feature_index = parse_int(
            field_at(
                fields,
                index_column,
                "water_feature_index",
                line_number
            ),
            "water_feature_index",
            line_number
        );

        feature.water_feature_id = trim(
            field_at(
                fields,
                id_column,
                "water_feature_id",
                line_number
            )
        );

        feature.water_feature_class = trim(
            field_at(
                fields,
                class_column,
                "water_feature_class",
                line_number
            )
        );

        feature.water_feature_type = trim(
            field_at(
                fields,
                type_column,
                "water_feature_type",
                line_number
            )
        );

        feature.source_feature_id = trim(
            field_at(
                fields,
                source_id_column,
                "source_feature_id",
                line_number
            )
        );

        feature.source_object_id = parse_long_long(
            field_at(
                fields,
                object_id_column,
                "source_object_id",
                line_number
            ),
            "source_object_id",
            line_number
        );

        feature.source_name = field_at(
            fields,
            name_column,
            "source_name",
            line_number
        );

        feature.geometry_kind = trim(
            field_at(
                fields,
                geometry_kind_column,
                "geometry_kind",
                line_number
            )
        );

        if (
            feature.water_feature_index
            != static_cast<int>(features.size())
        ) {
            throw std::runtime_error(
                "water_feature_index is not contiguous at line "
                + std::to_string(line_number)
            );
        }

        if (
            feature.water_feature_id.empty()
            || feature.source_feature_id.empty()
        ) {
            throw std::runtime_error(
                "Missing required feature identifier at line "
                + std::to_string(line_number)
            );
        }

        if (
            !feature_ids.insert(
                feature.water_feature_id
            ).second
        ) {
            throw std::runtime_error(
                "Duplicate water_feature_id: "
                + feature.water_feature_id
            );
        }

        if (
            feature.geometry_kind != "line"
            && feature.geometry_kind != "polygon"
        ) {
            throw std::runtime_error(
                "Unsupported geometry_kind at line "
                + std::to_string(line_number)
                + ": " + feature.geometry_kind
            );
        }

        if (
            feature.geometry_kind == "line"
            && feature.water_feature_class != "flowline"
        ) {
            throw std::runtime_error(
                "Line feature is not classified as flowline: "
                + feature.water_feature_id
            );
        }

        if (
            feature.geometry_kind == "polygon"
            && feature.water_feature_class != "waterbody"
        ) {
            throw std::runtime_error(
                "Polygon feature is not classified as waterbody: "
                + feature.water_feature_id
            );
        }

        features.push_back(std::move(feature));
    }

    if (features.empty()) {
        throw std::runtime_error(
            "Feature metadata contains no rows: " + path
        );
    }

    return features;
}


std::uint64_t read_vertices(
    const std::string& path,
    std::vector<WaterFeature>& features
) {
    std::ifstream input(path);

    if (!input) {
        throw std::runtime_error(
            "Could not open vertex input: " + path
        );
    }

    const HeaderMap header = read_header(input, path);

    const std::size_t feature_column =
        require_column(
            header,
            "water_feature_index",
            path
        );

    const std::size_t part_column =
        require_column(
            header,
            "part_index",
            path
        );

    const std::size_t ring_column =
        require_column(
            header,
            "ring_index",
            path
        );

    const std::size_t vertex_column =
        require_column(
            header,
            "vertex_index",
            path
        );

    const std::size_t x_column =
        require_column(header, "x", path);

    const std::size_t y_column =
        require_column(header, "y", path);

    std::string line;
    std::size_t line_number = 1;
    std::uint64_t row_count = 0;

    while (std::getline(input, line)) {
        ++line_number;

        if (line.empty()) {
            continue;
        }

        const auto fields = parse_csv_record(
            line,
            line_number
        );

        const int feature_index = parse_int(
            field_at(
                fields,
                feature_column,
                "water_feature_index",
                line_number
            ),
            "water_feature_index",
            line_number
        );

        const int part_index = parse_int(
            field_at(
                fields,
                part_column,
                "part_index",
                line_number
            ),
            "part_index",
            line_number
        );

        const int ring_index = parse_int(
            field_at(
                fields,
                ring_column,
                "ring_index",
                line_number
            ),
            "ring_index",
            line_number
        );

        const int vertex_index = parse_int(
            field_at(
                fields,
                vertex_column,
                "vertex_index",
                line_number
            ),
            "vertex_index",
            line_number
        );

        const double x = parse_double(
            field_at(
                fields,
                x_column,
                "x",
                line_number
            ),
            "x",
            line_number
        );

        const double y = parse_double(
            field_at(
                fields,
                y_column,
                "y",
                line_number
            ),
            "y",
            line_number
        );

        if (
            feature_index < 0
            || feature_index
                >= static_cast<int>(features.size())
        ) {
            throw std::runtime_error(
                "Vertex references unknown feature index at line "
                + std::to_string(line_number)
            );
        }

        if (
            part_index < 0
            || ring_index < 0
            || vertex_index < 0
        ) {
            throw std::runtime_error(
                "Negative geometry index at line "
                + std::to_string(line_number)
            );
        }

        WaterFeature& feature = features[
            static_cast<std::size_t>(feature_index)
        ];

        if (
            feature.geometry_kind == "line"
            && ring_index != 0
        ) {
            throw std::runtime_error(
                "Line feature uses nonzero ring_index at line "
                + std::to_string(line_number)
            );
        }

        Ring& ring =
            feature.parts[part_index][ring_index];

        if (
            vertex_index
            != static_cast<int>(ring.vertices.size())
        ) {
            throw std::runtime_error(
                "vertex_index is duplicated or out of order at line "
                + std::to_string(line_number)
            );
        }

        ring.vertices.push_back(Point{x, y});
        ++row_count;
    }

    return row_count;
}


bool same_point(
    const Point& left,
    const Point& right
) {
    return (
        left.x == right.x
        && left.y == right.y
    );
}


std::uint64_t validate_geometry(
    const std::vector<WaterFeature>& features
) {
    std::uint64_t segment_count = 0;

    for (const WaterFeature& feature : features) {
        if (feature.parts.empty()) {
            throw std::runtime_error(
                "Feature has no geometry: "
                + feature.water_feature_id
            );
        }

        for (const auto& part_entry : feature.parts) {
            const auto& rings = part_entry.second;

            if (feature.geometry_kind == "line") {
                if (
                    rings.size() != 1
                    || rings.find(0) == rings.end()
                ) {
                    throw std::runtime_error(
                        "Line part must contain exactly ring 0: "
                        + feature.water_feature_id
                    );
                }

                const Ring& line = rings.at(0);

                if (line.vertices.size() < 2) {
                    throw std::runtime_error(
                        "Line part has fewer than two vertices: "
                        + feature.water_feature_id
                    );
                }

                segment_count += (
                    line.vertices.size() - 1
                );
                continue;
            }

            const auto exterior = rings.find(0);

            if (exterior == rings.end()) {
                throw std::runtime_error(
                    "Polygon part lacks exterior ring 0: "
                    + feature.water_feature_id
                );
            }

            for (const auto& ring_entry : rings) {
                const Ring& ring = ring_entry.second;

                if (ring.vertices.size() < 4) {
                    throw std::runtime_error(
                        "Polygon ring has fewer than four vertices: "
                        + feature.water_feature_id
                    );
                }

                if (
                    !same_point(
                        ring.vertices.front(),
                        ring.vertices.back()
                    )
                ) {
                    throw std::runtime_error(
                        "Polygon ring is not closed: "
                        + feature.water_feature_id
                    );
                }

                segment_count += (
                    ring.vertices.size() - 1
                );
            }
        }
    }

    return segment_count;
}


double point_segment_distance_squared(
    const Point& point,
    const Point& start,
    const Point& end
) {
    const double delta_x = end.x - start.x;
    const double delta_y = end.y - start.y;

    const double length_squared =
        delta_x * delta_x
        + delta_y * delta_y;

    if (length_squared == 0.0) {
        const double point_delta_x =
            point.x - start.x;

        const double point_delta_y =
            point.y - start.y;

        return (
            point_delta_x * point_delta_x
            + point_delta_y * point_delta_y
        );
    }

    double projection = (
        (point.x - start.x) * delta_x
        + (point.y - start.y) * delta_y
    ) / length_squared;

    projection = std::clamp(
        projection,
        0.0,
        1.0
    );

    const double closest_x =
        start.x + projection * delta_x;

    const double closest_y =
        start.y + projection * delta_y;

    const double distance_x =
        point.x - closest_x;

    const double distance_y =
        point.y - closest_y;

    return (
        distance_x * distance_x
        + distance_y * distance_y
    );
}


RingEvaluation evaluate_ring(
    const Point& point,
    const Ring& ring
) {
    RingEvaluation evaluation;

    const double boundary_epsilon_squared =
        BOUNDARY_EPSILON_METERS
        * BOUNDARY_EPSILON_METERS;

    for (
        std::size_t index = 1;
        index < ring.vertices.size();
        ++index
    ) {
        const Point& start =
            ring.vertices[index - 1];

        const Point& end =
            ring.vertices[index];

        const double distance_squared =
            point_segment_distance_squared(
                point,
                start,
                end
            );

        evaluation.minimum_distance_squared =
            std::min(
                evaluation.minimum_distance_squared,
                distance_squared
            );

        ++evaluation.segment_checks;

        if (
            distance_squared
            <= boundary_epsilon_squared
        ) {
            evaluation.on_boundary = true;
        }

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
            evaluation.inside =
                !evaluation.inside;
        }
    }

    return evaluation;
}


DistanceResult distance_to_line_feature(
    const Point& point,
    const WaterFeature& feature
) {
    double minimum_squared =
        std::numeric_limits<double>::infinity();

    std::uint64_t checks = 0;

    for (const auto& part_entry : feature.parts) {
        const Ring& line =
            part_entry.second.at(0);

        for (
            std::size_t index = 1;
            index < line.vertices.size();
            ++index
        ) {
            minimum_squared = std::min(
                minimum_squared,
                point_segment_distance_squared(
                    point,
                    line.vertices[index - 1],
                    line.vertices[index]
                )
            );

            ++checks;
        }
    }

    return DistanceResult{
        std::sqrt(minimum_squared),
        checks
    };
}


DistanceResult distance_to_polygon_feature(
    const Point& point,
    const WaterFeature& feature
) {
    double feature_minimum_squared =
        std::numeric_limits<double>::infinity();

    std::uint64_t checks = 0;

    for (const auto& part_entry : feature.parts) {
        const auto& rings = part_entry.second;

        const RingEvaluation exterior =
            evaluate_ring(
                point,
                rings.at(0)
            );

        checks += exterior.segment_checks;

        feature_minimum_squared = std::min(
            feature_minimum_squared,
            exterior.minimum_distance_squared
        );

        if (exterior.on_boundary) {
            return DistanceResult{0.0, checks};
        }

        bool inside_hole = false;

        for (const auto& ring_entry : rings) {
            if (ring_entry.first == 0) {
                continue;
            }

            const RingEvaluation hole =
                evaluate_ring(
                    point,
                    ring_entry.second
                );

            checks += hole.segment_checks;

            feature_minimum_squared = std::min(
                feature_minimum_squared,
                hole.minimum_distance_squared
            );

            if (hole.on_boundary) {
                return DistanceResult{0.0, checks};
            }

            if (hole.inside) {
                inside_hole = true;
            }
        }

        if (exterior.inside && !inside_hole) {
            return DistanceResult{0.0, checks};
        }
    }

    return DistanceResult{
        std::sqrt(feature_minimum_squared),
        checks
    };
}


DistanceResult distance_to_feature(
    const Point& point,
    const WaterFeature& feature
) {
    if (feature.geometry_kind == "line") {
        return distance_to_line_feature(
            point,
            feature
        );
    }

    return distance_to_polygon_feature(
        point,
        feature
    );
}


void write_brute_force_results(
    const std::string& output_path,
    const std::vector<PropertyPoint>& properties,
    const std::vector<WaterFeature>& features,
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
        << "distance_crs,"
        << "algorithm\n";

    output << std::setprecision(17);

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

        double best_distance =
            std::numeric_limits<double>::infinity();

        int best_feature_index = -1;
        int tie_count = 0;
        std::uint64_t property_segment_checks = 0;

        for (const WaterFeature& feature : features) {
            const DistanceResult result =
                distance_to_feature(
                    property.point,
                    feature
                );

            property_segment_checks +=
                result.segment_checks;

            if (
                result.distance
                < best_distance
                    - tie_tolerance_meters
            ) {
                best_distance = result.distance;
                best_feature_index =
                    feature.water_feature_index;
                tie_count = 1;
                continue;
            }

            if (
                std::abs(
                    result.distance - best_distance
                ) <= tie_tolerance_meters
            ) {
                ++tie_count;

                if (
                    best_feature_index < 0
                    || feature.water_feature_id
                        < features[
                            static_cast<std::size_t>(
                                best_feature_index
                            )
                        ].water_feature_id
                ) {
                    best_distance = result.distance;
                    best_feature_index =
                        feature.water_feature_index;
                }
            }
        }

        if (best_feature_index < 0) {
            throw std::runtime_error(
                "No nearest water feature found for property "
                + property.property_id
            );
        }

        const WaterFeature& selected =
            features[
                static_cast<std::size_t>(
                    best_feature_index
                )
            ];

        output
            << csv_escape(property.property_id)
            << ","
            << best_distance
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
            << tie_count
            << ","
            << property_segment_checks
            << ","
            << csv_escape(distance_crs)
            << ",brute_force\n";

        total_segment_checks +=
            property_segment_checks;

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

    std::cout
        << std::fixed
        << std::setprecision(6)
        << "Brute-force computation seconds: "
        << elapsed_seconds
        << "\n"
        << "Properties per second: "
        << (
            static_cast<double>(properties.size())
            / elapsed_seconds
        )
        << "\n"
        << "Total segment checks: "
        << total_segment_checks
        << "\n"
        << "Average segment checks per property: "
        << (
            static_cast<double>(total_segment_checks)
            / static_cast<double>(properties.size())
        )
        << "\n";
}


}  // namespace


int main(int argc, char* argv[]) {
    if (argc != 5 && argc != 6) {
        std::cerr
            << "Usage:\n"
            << "  water_distance_bruteforce.exe "
            << "<properties_csv> "
            << "<features_csv> "
            << "<vertices_csv> "
            << "<output_csv> "
            << "[distance_crs]\n";

        return 1;
    }

    const std::string properties_path = argv[1];
    const std::string features_path = argv[2];
    const std::string vertices_path = argv[3];
    const std::string output_path = argv[4];

    const std::string distance_crs =
        argc == 6
        ? argv[5]
        : "EPSG:26918";

    try {
        const auto load_start =
            std::chrono::steady_clock::now();

        const std::vector<PropertyPoint> properties =
            read_properties(properties_path);

        std::vector<WaterFeature> features =
            read_feature_metadata(features_path);

        const std::uint64_t vertex_count =
            read_vertices(
                vertices_path,
                features
            );

        const std::uint64_t segment_count =
            validate_geometry(features);

        const auto load_end =
            std::chrono::steady_clock::now();

        const double load_seconds =
            std::chrono::duration<double>(
                load_end - load_start
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
            << "Input loading seconds: "
            << std::fixed
            << std::setprecision(6)
            << load_seconds
            << "\n";

        write_brute_force_results(
            output_path,
            properties,
            features,
            distance_crs,
            DEFAULT_TIE_TOLERANCE_METERS
        );

        std::cout
            << "Wrote C++ brute-force output to "
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