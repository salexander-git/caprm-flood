#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <cmath>

struct Point {
    double x = 0.0;
    double y = 0.0;
};

struct PropertyPoint {
    std::string property_id;
    double x = 0.0;
    double y = 0.0;
};

struct Ring {
    std::vector<Point> vertices;
};

struct Feature {
    int fema_feature_index = -1;
    std::string fema_zone;
    std::string sfha_flag;

    double min_x = 0.0;
    double min_y = 0.0;
    double max_x = 0.0;
    double max_y = 0.0;
    bool has_bbox = false;

    // part_index -> ring_index -> Ring
    std::map<int, std::map<int, Ring>> parts;
};

std::vector<std::string> split_csv_line(const std::string& line) {
    std::vector<std::string> fields;
    std::stringstream ss(line);
    std::string field;

    while (std::getline(ss, field, ',')) {
        fields.push_back(field);
    }

    return fields;
}

std::string trim(const std::string& value) {
    size_t start = 0;
    while (start < value.size() && std::isspace(static_cast<unsigned char>(value[start]))) {
        ++start;
    }

    size_t end = value.size();
    while (end > start && std::isspace(static_cast<unsigned char>(value[end - 1]))) {
        --end;
    }

    return value.substr(start, end - start);
}

std::string csv_escape(const std::string& value) {
    if (value.find_first_of(",\"\n\r") == std::string::npos) {
        return value;
    }

    std::string escaped = "\"";
    for (char c : value) {
        if (c == '"') {
            escaped += "\"\"";
        } else {
            escaped += c;
        }
    }
    escaped += "\"";
    return escaped;
}

bool normalize_sfha_flag(const std::string& value) {
    std::string text = trim(value);
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char c) {
        return static_cast<char>(std::toupper(c));
    });

    return text == "T" || text == "TRUE" || text == "Y" || text == "YES" || text == "1";
}

void update_bbox(Feature& feature, double x, double y) {
    if (!feature.has_bbox) {
        feature.min_x = x;
        feature.max_x = x;
        feature.min_y = y;
        feature.max_y = y;
        feature.has_bbox = true;
        return;
    }

    feature.min_x = std::min(feature.min_x, x);
    feature.max_x = std::max(feature.max_x, x);
    feature.min_y = std::min(feature.min_y, y);
    feature.max_y = std::max(feature.max_y, y);
}

bool bbox_contains_point(const Feature& feature, const Point& point) {
    if (!feature.has_bbox) {
        return false;
    }

    return point.x >= feature.min_x &&
           point.x <= feature.max_x &&
           point.y >= feature.min_y &&
           point.y <= feature.max_y;
}

std::vector<PropertyPoint> read_properties(const std::string& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("Could not open properties input file: " + path);
    }

    std::vector<PropertyPoint> properties;
    std::string line;

    // Header:
    // property_id,projected_x,projected_y,longitude,latitude
    std::getline(input, line);

    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }

        const auto fields = split_csv_line(line);
        if (fields.size() < 3) {
            continue;
        }

        PropertyPoint point;
        point.property_id = fields[0];
        point.x = std::stod(fields[1]);
        point.y = std::stod(fields[2]);

        properties.push_back(point);
    }

    return properties;
}

std::vector<Feature> read_fema_rings(const std::string& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("Could not open FEMA rings input file: " + path);
    }

    std::map<int, Feature> features;
    std::string line;

    // Header:
    // fema_feature_index,part_index,ring_index,vertex_index,x,y,fema_zone,sfha_flag,source_geometry_id
    std::getline(input, line);

    size_t row_count = 0;

    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }

        const auto fields = split_csv_line(line);
        if (fields.size() < 8) {
            continue;
        }

        const int fema_feature_index = std::stoi(fields[0]);
        const int part_index = std::stoi(fields[1]);
        const int ring_index = std::stoi(fields[2]);
        const double x = std::stod(fields[4]);
        const double y = std::stod(fields[5]);

        Feature& feature = features[fema_feature_index];
        feature.fema_feature_index = fema_feature_index;
        feature.fema_zone = fields[6];
        feature.sfha_flag = fields[7];

        feature.parts[part_index][ring_index].vertices.push_back(Point{x, y});
        update_bbox(feature, x, y);

        ++row_count;
    }

    std::vector<Feature> output;
    output.reserve(features.size());

    for (auto& item : features) {
        output.push_back(std::move(item.second));
    }

    std::cout << "Read " << output.size() << " FEMA features from " << row_count
              << " ring vertices\n";

    return output;
}

bool point_on_segment(const Point& p, const Point& a, const Point& b, double eps = 1e-9) {
    const double cross = (p.y - a.y) * (b.x - a.x) - (p.x - a.x) * (b.y - a.y);
    if (std::abs(cross) > eps) {
        return false;
    }

    const double dot = (p.x - a.x) * (b.x - a.x) + (p.y - a.y) * (b.y - a.y);
    if (dot < 0.0) {
        return false;
    }

    const double length_sq = (b.x - a.x) * (b.x - a.x) + (b.y - a.y) * (b.y - a.y);
    if (dot > length_sq) {
        return false;
    }

    return true;
}

bool point_in_ring_within_semantics(const Point& p, const Ring& ring) {
    const auto& vertices = ring.vertices;

    if (vertices.size() < 4) {
        return false;
    }

    bool inside = false;
    size_t j = vertices.size() - 1;

    for (size_t i = 0; i < vertices.size(); ++i) {
        const Point& vi = vertices[i];
        const Point& vj = vertices[j];

        const bool crosses = ((vi.y > p.y) != (vj.y > p.y)) &&
            (p.x < (vj.x - vi.x) * (p.y - vi.y) / (vj.y - vi.y) + vi.x);

        if (crosses) {
            inside = !inside;
        }

        j = i;
    }

    return inside;
}

bool feature_contains_point(const Feature& feature, const Point& point) {
    for (const auto& part_item : feature.parts) {
        const auto& rings = part_item.second;

        const auto exterior_it = rings.find(0);
        if (exterior_it == rings.end()) {
            continue;
        }

        if (!point_in_ring_within_semantics(point, exterior_it->second)) {
            continue;
        }

        bool inside_hole = false;

        for (const auto& ring_item : rings) {
            const int ring_index = ring_item.first;
            if (ring_index == 0) {
                continue;
            }

            if (point_in_ring_within_semantics(point, ring_item.second)) {
                inside_hole = true;
                break;
            }
        }

        if (!inside_hole) {
            return true;
        }
    }

    return false;
}

void write_results(
    const std::string& output_path,
    const std::vector<PropertyPoint>& properties,
    const std::vector<Feature>& features
) {
    std::filesystem::create_directories(std::filesystem::path(output_path).parent_path());

    std::ofstream output(output_path);
    if (!output) {
        throw std::runtime_error("Could not open output file: " + output_path);
    }

    output << "property_id,cpp_matched_fema_polygon,cpp_sfha_result,cpp_fema_zone,cpp_fema_feature_index\n";

    for (const auto& property : properties) {
        const Point point{property.x, property.y};

        bool matched = false;
        bool sfha = false;
        std::string matched_zone;
        int matched_feature_index = -1;

        for (const auto& feature : features) {
            if (!bbox_contains_point(feature, point)) {
                continue;
            }

            if (feature_contains_point(feature, point)) {
                matched = true;
                sfha = normalize_sfha_flag(feature.sfha_flag);
                matched_zone = feature.fema_zone;
                matched_feature_index = feature.fema_feature_index;
                break;
            }
        }

        output
            << csv_escape(property.property_id) << ","
            << (matched ? "true" : "false") << ","
            << (sfha ? "true" : "false") << ","
            << csv_escape(matched_zone) << ","
            << matched_feature_index << "\n";
    }
}

int main(int argc, char* argv[]) {
    std::string properties_path = "outputs/cpp_input/properties_projected_dev.csv";
    std::string rings_path = "outputs/cpp_input/fema_polygon_rings_dev.csv";
    std::string output_path = "outputs/cpp/cpp_fema_membership_dev.csv";

    if (argc == 4) {
        properties_path = argv[1];
        rings_path = argv[2];
        output_path = argv[3];
    } else if (argc != 1) {
        std::cerr
            << "Usage:\n"
            << "  fema_pip_dev.exe\n"
            << "or:\n"
            << "  fema_pip_dev.exe <properties_csv> <rings_csv> <output_csv>\n";
        return 1;
    }

    try {
        const auto properties = read_properties(properties_path);
        const auto features = read_fema_rings(rings_path);

        std::cout << "Read " << properties.size() << " property points\n";

        write_results(output_path, properties, features);

        std::cout << "Wrote C++ FEMA membership output to " << output_path << "\n";
    } catch (const std::exception& ex) {
        std::cerr << "Error: " << ex.what() << "\n";
        return 1;
    }

    return 0;
}