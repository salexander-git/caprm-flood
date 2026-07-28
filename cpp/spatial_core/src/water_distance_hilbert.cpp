// Hilbert-ordered nearest-water program (Milestone 4, chunks B3a + B3b).
//
// Replaces the segment BVH's 2D box hierarchy (phase 1) with a 1D Hilbert
// ordering of split-segment midpoints and an exact inflated-disk range query.
// Phase 2 verification is UNCHANGED from B2: it reuses distance_to_feature
// (OriginalGeometry, default, byte-identical) or the split minimum plus
// polygon_contains_point (SplitGeometry), selected by the same VerificationMode
// flag. Only phase-1 candidate selection is new here.
//
//   #define CAPRM_SEGMENT_BVH_NO_MAIN
//   #include "water_distance_segment_bvh.cpp"   // transitively includes the
//                                               // brute-force kernel/IO/tie rule
//
// Reuses from the included translation units: SegmentLeaf, build_split_segments,
// SplitStatistics, Bounds, bounds_distance_squared, point_segment_distance_squared,
// distance_to_feature, VerificationMode, polygon_contains_point,
// build_part_exterior_bounds, PartExteriorBounds, BOUNDARY_EPSILON_METERS,
// DEFAULT_TIE_TOLERANCE_METERS, csv_escape, read_* / validate_geometry.
//
// ---------------------------------------------------------------------------
// Completeness of the inflated-disk query (proved once, at the region interface)
// ---------------------------------------------------------------------------
//
// L = the longest split segment in the index (<= cap). For a query point p and
// radius r, to find every segment whose nearest point to p lies in disk(r) it
// suffices to admit every segment whose MIDPOINT lies in disk(r + L/2):
//   a segment s of length <= L has all its points within L of each other, so its
//   midpoint m and its nearest point q satisfy |q - m| <= L/2; if |p - q| <= r
//   then |p - m| <= r + L/2. Contrapositive: a midpoint outside disk(r + L/2)
//   belongs to a segment whose nearest point is outside disk(r).
//
// The tie rule counts features within tie_tol of the best distance, so the
// admission radius folds in tie_tol as well:  R = d_best + L/2 + tie_tol.
// A feature at distance d <= true + tie_tol has a split segment at ~d whose
// midpoint is within d + L/2 <= true + tie_tol + L/2 = R of p, so it is admitted
// and its tie is counted, matching the brute-force reference exactly.
//
// The recursion prunes a grid node only when the region reports the node's
// coordinate bounds disjoint from it. Soundness requirement, discharged ONCE
// here for any region: every midpoint contained in a node lies inside that
// node's coordinate bounds (by construction of the cell->coord mapping), so if
// the bounds are disjoint from disk(R) no contained midpoint is within R. Two
// concrete regions satisfy this:
//   - DiskBBox (box-primary, this chunk): bounds vs the axis-aligned bounding
//     box of disk(R). disk(R) is a subset of its box, so a false "disjoint" is
//     still sound; it merely over-covers the disk corners.
//   - Disk (deferred to B3b): bounds vs disk(R) itself (bounds_distance_squared).
//     Tighter: prunes a superset of what DiskBBox prunes.
// Both are correct against the same completeness proof; the swap is one region
// object at one call site, with identical traversal. B3b decides whether to
// switch on the Disk region from the measured box-vs-disk over-covering ratio.
//
// ---------------------------------------------------------------------------
// Interior-zero, re-proved for 1D midpoint selection (NOT assumed)
// ---------------------------------------------------------------------------
//
// Under B1 interior-zero rode on 2D box overlap admitting the containing polygon.
// The 1D admission rule is different (a feature is admitted iff one of its
// split-segment midpoints lies in disk(R)), so the guarantee is re-established:
// for p interior to polygon P with delta = dist(p, boundary(P)), the USGS 3DHP
// non-overlap invariant makes P's boundary the globally nearest boundary, so
// phase-1 d_best = delta via P's own boundary and R = delta + L/2 + tie_tol.
// The split segment carrying P's nearest boundary point has its nearest point at
// distance <= delta, hence (lemma) a midpoint within delta + L/2 <= R, so P is a
// candidate. Phase 2 then returns exact 0.0 (OriginalGeometry via the ring
// interior test in distance_to_feature; SplitGeometry via polygon_contains_point).
// If the invariant ever failed, polygon_contains_point over candidate polygons is
// the exact fallback. The fixture asserts the interior/boundary/hole cases, so a
// silently-wrong zero fails acceptance rather than passing.
//
// ---------------------------------------------------------------------------
// B3b: the seed seam is correctness-neutral (this is why B5 cannot break exactness)
// ---------------------------------------------------------------------------
//
// The start position is the ONLY thing the B5 RMI replaces, and it is isolated
// behind `--seed`. The seam is a pure performance hint, provably:
//   d_seed is the minimum over a WINDOW OF REAL SEGMENTS of an achieved
//   point-to-segment distance, so d_seed >= d_true for any window, whatever
//   position the seeder returned. Hence R_seed = d_seed + L/2 + tie_tol covers
//   disk(d_true + L/2 + tie_tol), the resolve descent admits the true nearest
//   segment by the lemma above, and d_best is exact. The final candidate set is
//   then rebuilt by an independent descent at R = d_best + L/2 + tie_tol, which
//   does not reference the seed at all.
// Therefore a mispredicting model widens the FIRST descent and slows the query;
// it cannot change any emitted field (Nucleus 18.16, made concrete). This is
// tested, not merely argued: `--seed zero` returns position 0 for every query —
// the worst legal hint — and the fixture asserts its output is byte-identical to
// `--seed binary`. That is B5's acceptance criterion, pre-validated before the
// model exists. `--seed zero` is a test mode only; countywide it degenerates to
// near-brute-force.
//
// ---------------------------------------------------------------------------
// B3b: why the inflation denominator is N_true, not N_disk_r
// ---------------------------------------------------------------------------
//
// B3a instrumented `n_disk_r` = midpoints in disk(d_best + tie_tol), intending it
// as the "uninflated disk" denominator. It is structurally degenerate: d_best is
// a distance to the nearest POINT ON A SEGMENT, while n_disk_r tests MIDPOINTS,
// and |p - m_i| >= d(p, s_i) >= d_best for every entry. An entry is therefore
// counted only when its perpendicular foot lands within tie_tol of its own
// midpoint — a coincidence, not a population. Measured on the fixture: 0 of 1093
// properties have n_disk_r > 0. Dividing by it is undefined or arbitrary.
//
// `n_true_r` = |{entries : d(p, s_i) <= d_best + tie_tol}| replaces it. It counts
// the entries that genuinely satisfy the range predicate at the answer radius —
// what an exact index would have to admit if entries had zero extent — so it is
// >= 1 always (the nearest split segment attains d_best). It is exact from the
// tight descent alone: any entry with d(p, s_i) <= r has its midpoint in
// disk(r + L/2) by the lemma, hence lies in the scanned set.
//
// Provable per-property ordering, asserted by the fixture:
//     n_disk_r <= n_true_r <= n_disk_infl <= n_disk_unc
//     n_disk_infl <= n_decomp
// (first: d(p,s_i) <= |p-m_i|; second: the lemma; third: nested disks, same
// predicate; fourth: disk(R) is a subset of every region used for the descent.)
//
// n_disk_r, n_true_r and n_disk_infl are exact counts over disk(R) and so are
// INVARIANT across region predicates; only n_decomp differs between disk_bbox
// and disk. The fixture asserts that invariance, which tests both predicates
// against each other rather than trusting either.

#define CAPRM_SEGMENT_BVH_NO_MAIN
#include "water_distance_segment_bvh.cpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <map>
#include <numeric>
#include <set>
#include <string>
#include <utility>
#include <vector>


namespace {

constexpr std::uint32_t DEFAULT_HILBERT_ORDER = 32;

// Entries examined either side of the seed position to obtain d_seed. A pure
// performance parameter (see the header note): any window size, or a wrong
// position, yields the same emitted fields. Recorded in the manifest because it
// affects measured query cost, and because B5's model error bound plays the
// same role.
constexpr std::size_t SEED_WINDOW = 64;


// ---------------------------------------------------------------------------
// The seed seam. Implementations #4 (binary search) and #5 (RMI) are ONE binary
// differing only here; everything downstream — inflated-disk decomposition,
// verification, tie rule — is shared code on the same path.
// ---------------------------------------------------------------------------
enum class SeedMode {
    BinarySearch,   // #4, the control: std::lower_bound over the sorted keys
    Rmi,            // #5, B5: predicted position from the recursive model index
    Zero,           // test only: always position 0, the worst legal hint
};


const char* seed_mode_name(SeedMode mode) {
    switch (mode) {
        case SeedMode::Rmi:  return "rmi";
        case SeedMode::Zero: return "zero";
        case SeedMode::BinarySearch: break;
    }
    return "binary";
}


struct SeedResult {
    std::size_t position = 0;
    std::uint64_t probes = 0;   // key comparisons: the cost B6 attributes to #5 vs #4
};


// ---------------------------------------------------------------------------
// Hilbert transform (Skilling iteration). p bits per axis -> 2p-bit index.
// ---------------------------------------------------------------------------
std::uint64_t hilbert_xy2d(std::uint32_t bits, std::uint32_t x, std::uint32_t y) {
    std::uint64_t d = 0;
    for (std::uint32_t s = 1u << (bits - 1); s > 0; s >>= 1) {
        std::uint32_t rx = (x & s) ? 1u : 0u;
        std::uint32_t ry = (y & s) ? 1u : 0u;
        d += static_cast<std::uint64_t>(s) * static_cast<std::uint64_t>(s)
             * ((3u * rx) ^ ry);
        if (ry == 0) {
            if (rx == 1) { x = s - 1 - x; y = s - 1 - y; }
            std::uint32_t t = x; x = y; y = t;
        }
    }
    return d;
}


// The Hilbert index range of an aligned 2^k x 2^k cell block is exactly
// [base, base + 4^k), with base = min over the block's four corner cells.
// (Verified exhaustively for p=1..8 and against brute cell enumeration in
// hilbert_probe.cpp; it is the self-similar locality property of the curve, so
// no orientation state is needed to emit ranges.)
std::pair<std::uint64_t, std::uint64_t> square_key_range(
    std::uint32_t order, std::uint32_t ox, std::uint32_t oy, std::uint32_t k
) {
    const std::uint64_t sz = 1ull << k;                 // 2^k, up to 2^32
    const std::uint32_t hx = static_cast<std::uint32_t>(ox + (sz - 1));
    const std::uint32_t hy = static_cast<std::uint32_t>(oy + (sz - 1));
    const std::uint64_t c0 = hilbert_xy2d(order, ox, oy);
    const std::uint64_t c1 = hilbert_xy2d(order, hx, oy);
    const std::uint64_t c2 = hilbert_xy2d(order, ox, hy);
    const std::uint64_t c3 = hilbert_xy2d(order, hx, hy);
    const std::uint64_t base = std::min(std::min(c0, c1), std::min(c2, c3));
    const std::uint64_t size = sz * sz;   // 4^k; only emitted for k < 32
    return {base, size};
}


// ---------------------------------------------------------------------------
// Coordinate <-> integer-cell normalization (a manifest parameter set).
// Per-axis so the grid is used fully; only monotonicity and consistency between
// build and query matter for correctness, not isotropy.
// ---------------------------------------------------------------------------
struct HilbertNormalization {
    std::uint32_t order = DEFAULT_HILBERT_ORDER;
    double min_x = 0.0;
    double min_y = 0.0;
    double scale_x = 1.0;   // cells per metre on x
    double scale_y = 1.0;   // cells per metre on y

    std::uint32_t max_cell() const {
        return static_cast<std::uint32_t>((1ull << order) - 1ull);
    }

    std::uint32_t cell_x(double x) const {
        double c = std::floor((x - min_x) * scale_x);
        if (c < 0.0) return 0u;
        if (c > static_cast<double>(max_cell())) return max_cell();
        return static_cast<std::uint32_t>(c);
    }
    std::uint32_t cell_y(double y) const {
        double c = std::floor((y - min_y) * scale_y);
        if (c < 0.0) return 0u;
        if (c > static_cast<double>(max_cell())) return max_cell();
        return static_cast<std::uint32_t>(c);
    }

    // Coordinate bounds of an aligned cell block [ox,ox+sz) x [oy,oy+sz).
    // Contains every midpoint whose cell lies in the block (soundness of prune).
    Bounds block_bounds(std::uint32_t ox, std::uint32_t oy, std::uint64_t sz) const {
        Bounds b;
        b.min_x = min_x + static_cast<double>(ox) / scale_x;
        b.max_x = min_x + static_cast<double>(ox + sz) / scale_x;
        b.min_y = min_y + static_cast<double>(oy) / scale_y;
        b.max_y = min_y + static_cast<double>(oy + sz) / scale_y;
        return b;
    }
};


HilbertNormalization build_normalization(
    const std::vector<Point>& midpoints, std::uint32_t order
) {
    HilbertNormalization norm;
    norm.order = order;

    Bounds bb;
    for (const Point& m : midpoints) { expand_bounds(bb, m); }

    norm.min_x = bb.min_x;
    norm.min_y = bb.min_y;

    const double extent_x = std::max(bb.max_x - bb.min_x, 1e-9);
    const double extent_y = std::max(bb.max_y - bb.min_y, 1e-9);
    const double cells = static_cast<double>((1ull << order) - 1ull);

    norm.scale_x = cells / extent_x;
    norm.scale_y = cells / extent_y;
    return norm;
}


// ---------------------------------------------------------------------------
// Region interface. Both concrete regions are built from (center, radius); the
// box version carries the center in its signature even though its disjoint/
// contains tests use only the center-plus-radius bounding box, so the B3b swap
// is region-object-for-region-object with no call-site change.
// ---------------------------------------------------------------------------
struct Region {
    enum class Kind { DiskBBox, Disk } kind = Kind::DiskBBox;
    Point center;
    double radius = 0.0;
    double radius_squared = 0.0;

    // true => no midpoint reachable in this node can be within radius of center.
    bool disjoint(const Bounds& b) const {
        if (kind == Kind::Disk) {
            return bounds_distance_squared(center, b) > radius_squared;
        }
        return b.max_x < center.x - radius
            || b.min_x > center.x + radius
            || b.max_y < center.y - radius
            || b.min_y > center.y + radius;
    }

    // true => every point of the node lies within the admitted region.
    bool contains(const Bounds& b) const {
        if (kind == Kind::Disk) {
            const double dx = std::max(
                std::abs(b.min_x - center.x), std::abs(b.max_x - center.x));
            const double dy = std::max(
                std::abs(b.min_y - center.y), std::abs(b.max_y - center.y));
            return dx * dx + dy * dy <= radius_squared;
        }
        return b.min_x >= center.x - radius && b.max_x <= center.x + radius
            && b.min_y >= center.y - radius && b.max_y <= center.y + radius;
    }
};


Region make_region(Region::Kind kind, const Point& center, double radius) {
    Region r;
    r.kind = kind;
    r.center = center;
    r.radius = radius;
    r.radius_squared = radius * radius;
    return r;
}


// ---------------------------------------------------------------------------
// The Hilbert-ordered index: split segments and their midpoints sorted by key.
// ---------------------------------------------------------------------------
struct HilbertIndex {
    HilbertNormalization norm;
    std::vector<std::uint64_t> keys;      // sorted ascending
    std::vector<SegmentLeaf> segments;    // parallel to keys
    std::vector<Point> midpoints;         // parallel to keys
    std::uint64_t distinct_cells = 0;     // == distinct keys
    std::uint32_t min_order_distinct = 0; // smallest p with zero collisions
};


// ---------------------------------------------------------------------------
// B5: the recursive model index (implementation #5), INFERENCE ONLY.
//
// Python trains (python/caprm/rmi.py); C++ infers. The model replaces the
// binary search and nothing else: it returns a start position, the same
// +/- SEED_WINDOW entries are read around it, and every downstream stage is
// untouched. By 18.22 a wrong position costs time and cannot cost an answer,
// so NO error bound is consulted here. The stored-key bound is the academic
// deliverable and the domain bound is a diagnostic; sizing a search window
// from either would be machinery imitating a correctness mechanism.
//
// The arithmetic mirrors RmiModel.route/predict in rmi.py exactly, INCLUDING
// the two different rounding orders: the root FLOORS then clamps, the leaf
// CLAMPS then floors. Property-point keys routinely fall outside
// [key_min, key_max], so x < 0 and x > 1 are the normal case rather than an
// error and the clamps are the whole of the out-of-range handling. Swapping
// either order changes the predicted position for exactly that population.
// ---------------------------------------------------------------------------
constexpr std::size_t RMI_HEADER_BYTES = 96;
constexpr std::uint32_t RMI_FORMAT_VERSION = 1;
constexpr std::uint32_t RMI_LEAF_STRIDE_BYTES = 32;


struct RmiModel {
    std::uint64_t n_keys = 0;
    std::uint64_t n_leaves = 0;
    std::uint64_t key_min = 0;
    std::uint64_t key_max = 0;
    double root_a = 0.0;
    double root_b = 0.0;
    double key_min_d = 0.0;       // derived from the raw uint64, never from text
    double inv_span = 0.0;
    std::vector<double> leaf_a;
    std::vector<double> leaf_b;
    std::string keys_sha256_hex;  // carried from the header; see bind_rmi_model
};


struct RmiPrediction {
    double x = 0.0;
    std::size_t leaf = 0;
    std::size_t position = 0;
};


RmiPrediction rmi_predict(const RmiModel& model, std::uint64_t key) {
    RmiPrediction out;
    out.x = (static_cast<double>(key) - model.key_min_d) * model.inv_span;

    // Root: floor, THEN clamp (rmi.py RmiModel.route).
    double j = std::floor(model.root_a + model.root_b * out.x);
    const double j_max = static_cast<double>(model.n_leaves - 1);
    if (!(j >= 0.0)) j = 0.0;      // negated form so a NaN would also land at 0
    if (j > j_max) j = j_max;
    out.leaf = static_cast<std::size_t>(j);

    // Leaf: clamp, THEN floor (rmi.py RmiModel.predict).
    double p = model.leaf_a[out.leaf] + model.leaf_b[out.leaf] * out.x;
    const double p_max = static_cast<double>(model.n_keys - 1);
    if (!(p >= 0.0)) p = 0.0;
    if (p > p_max) p = p_max;
    out.position = static_cast<std::size_t>(std::floor(p));
    return out;
}


// lower_bound over index.keys, written out so the probe count (the quantity the
// RMI is supposed to reduce) is measurable. Semantics are identical to
// std::lower_bound; --verify-counts asserts that equality per query.
//
// B5: in `rmi` mode the model returns the position directly and performs ZERO
// key comparisons, so `probes` stays 0. That is the honest count for the
// shipped path, which reads one 32-byte leaf record and does four
// multiply-adds, two clamps and two floors. B4's "6.323 mean last-mile probes"
// is a MODELLED quantity -- ceil(log2(err_max - err_min + 2)) over index keys,
// describing a last-mile binary search this path does not perform -- and B6
// must not report it as a measured probe count against the control's measured
// 20.2376.
SeedResult seed_position(
    const HilbertIndex& index, std::uint64_t key, SeedMode mode,
    const RmiModel* model
) {
    SeedResult out;
    if (mode == SeedMode::Zero) return out;          // position 0, 0 probes
    if (mode == SeedMode::Rmi) {
        if (model == nullptr) {
            throw std::runtime_error("--seed rmi reached inference with no model.");
        }
        out.position = rmi_predict(*model, key).position;
        return out;                                  // zero key comparisons
    }

    std::size_t low = 0;
    std::size_t length = index.keys.size();
    while (length > 0) {
        const std::size_t half = length / 2;
        const std::size_t mid = low + half;
        ++out.probes;
        if (index.keys[mid] < key) {
            low = mid + 1;
            length -= half + 1;
        } else {
            length = half;
        }
    }
    out.position = low;
    return out;
}


std::uint64_t count_distinct_cells(
    const std::vector<Point>& midpoints, const HilbertNormalization& base_norm,
    std::uint32_t order
) {
    HilbertNormalization norm = base_norm;
    // Re-derive scale for this order over the same extent (min_x/min_y fixed).
    const double extent_x = static_cast<double>(base_norm.max_cell())
                          / base_norm.scale_x;
    const double extent_y = static_cast<double>(base_norm.max_cell())
                          / base_norm.scale_y;
    norm.order = order;
    const double cells = static_cast<double>((1ull << order) - 1ull);
    norm.scale_x = cells / extent_x;
    norm.scale_y = cells / extent_y;

    std::vector<std::uint64_t> packed;
    packed.reserve(midpoints.size());
    for (const Point& m : midpoints) {
        const std::uint64_t cx = norm.cell_x(m.x);
        const std::uint64_t cy = norm.cell_y(m.y);
        packed.push_back((cx << 32) | cy);
    }
    std::sort(packed.begin(), packed.end());
    packed.erase(std::unique(packed.begin(), packed.end()), packed.end());
    return packed.size();
}


HilbertIndex build_hilbert_index(
    std::vector<SegmentLeaf> segments, std::uint32_t order
) {
    HilbertIndex index;

    std::vector<Point> midpoints;
    midpoints.reserve(segments.size());
    for (const SegmentLeaf& s : segments) {
        midpoints.push_back(Point{
            (s.start.x + s.end.x) / 2.0,
            (s.start.y + s.end.y) / 2.0
        });
    }

    index.norm = build_normalization(midpoints, order);

    std::vector<std::uint64_t> keys(segments.size());
    for (std::size_t i = 0; i < segments.size(); ++i) {
        keys[i] = hilbert_xy2d(
            order,
            index.norm.cell_x(midpoints[i].x),
            index.norm.cell_y(midpoints[i].y)
        );
    }

    // Sort by (key, original index) for a reproducible total order.
    std::vector<std::uint32_t> perm(segments.size());
    std::iota(perm.begin(), perm.end(), 0u);
    std::sort(perm.begin(), perm.end(),
        [&](std::uint32_t a, std::uint32_t b) {
            if (keys[a] != keys[b]) return keys[a] < keys[b];
            return a < b;
        });

    index.keys.reserve(segments.size());
    index.segments.reserve(segments.size());
    index.midpoints.reserve(segments.size());
    for (std::uint32_t p : perm) {
        index.keys.push_back(keys[p]);
        index.segments.push_back(segments[p]);
        index.midpoints.push_back(midpoints[p]);
    }

    index.distinct_cells = count_distinct_cells(midpoints, index.norm, order);

    // Smallest order at which all midpoints occupy distinct cells (the honest
    // "how much resolution does this data need" number). Bounded by `order`.
    index.min_order_distinct = order;
    for (std::uint32_t p = 1; p <= order; ++p) {
        if (count_distinct_cells(midpoints, index.norm, p) == midpoints.size()) {
            index.min_order_distinct = p;
            break;
        }
    }
    return index;
}


// ---------------------------------------------------------------------------
// Data-adaptive range descent.
//
// A blind geometric decomposition of the query box would emit O(box side in
// cells) ranges; at order 32 the side is ~10^7 cells, so it must be pruned by
// DATA, not resolution. An aligned block's cells occupy the contiguous key
// interval [base, base + 4^k), so a single binary-search pair on the sorted key
// array counts the indexed midpoints inside the block. Empty blocks (count 0)
// are pruned immediately, so the descent follows the ~N indexed points rather
// than the 2^(2p) grid. This is the standard quadtree-over-sorted-array query;
// it does not change the admitted candidate set versus an exact box
// decomposition (blocks are only skipped when they contain no midpoint or are
// geometrically disjoint from the region), so completeness is unaffected.
// ---------------------------------------------------------------------------
constexpr std::size_t HILBERT_LEAF_THRESHOLD = 16;


struct ScanContext {
    const HilbertIndex* index = nullptr;
    Point point;

    double d_best = std::numeric_limits<double>::infinity();
    std::vector<int>* candidate_features = nullptr;
    std::vector<char>* feature_is_candidate = nullptr;
    std::vector<double>* feature_best_split_distance = nullptr;

    // Instrumentation.
    std::uint64_t nodes_visited = 0;
    std::uint64_t leaves_scanned = 0;
    std::uint64_t entries_scanned = 0;

    // Optional inflation measurement at the tight radius.
    bool measure = false;
    double r_disk_sq = 0.0;     // (d_best + tie_tol)^2, tested against MIDPOINTS
    double r_true_sq = 0.0;     // (d_best + tie_tol)^2, tested against SEGMENTS
    double r_infl_sq = 0.0;     // (d_best + L/2 + tie_tol)^2, against MIDPOINTS
    std::uint64_t n_disk_r = 0;
    std::uint64_t n_true_r = 0;
    std::uint64_t n_disk_infl = 0;
};


// Scan the [lo, hi) entries of a leaf block: distance, candidate set, counters.
void scan_entry_range(ScanContext& ctx, std::size_t lo, std::size_t hi) {
    const HilbertIndex& index = *ctx.index;
    ++ctx.leaves_scanned;
    for (std::size_t i = lo; i < hi; ++i) {
        ++ctx.entries_scanned;
        const SegmentLeaf& seg = index.segments[i];
        const double dsq =
            point_segment_distance_squared(ctx.point, seg.start, seg.end);
        const double dist = std::sqrt(dsq);
        if (dist < ctx.d_best) ctx.d_best = dist;

        const std::size_t f = static_cast<std::size_t>(seg.feature_index);
        if (!(*ctx.feature_is_candidate)[f]) {
            (*ctx.feature_is_candidate)[f] = 1;
            (*ctx.feature_best_split_distance)[f] = dist;
            ctx.candidate_features->push_back(seg.feature_index);
        } else if (dist < (*ctx.feature_best_split_distance)[f]) {
            (*ctx.feature_best_split_distance)[f] = dist;
        }

        if (ctx.measure) {
            const double mdx = ctx.point.x - index.midpoints[i].x;
            const double mdy = ctx.point.y - index.midpoints[i].y;
            const double md_sq = mdx * mdx + mdy * mdy;
            if (md_sq <= ctx.r_infl_sq) ++ctx.n_disk_infl;
            if (md_sq <= ctx.r_disk_sq) ++ctx.n_disk_r;
            // The honest denominator: entries whose NEAREST POINT (not midpoint)
            // satisfies the range predicate at the answer radius. Exact from this
            // scan because any such entry has its midpoint in disk(R).
            if (dsq <= ctx.r_true_sq) ++ctx.n_true_r;
        }
    }
}


void descend_and_scan(ScanContext& ctx, const Region& region) {
    const HilbertIndex& index = *ctx.index;
    const HilbertNormalization& norm = index.norm;
    const auto k_begin = index.keys.begin();

    // (ox, oy, k, lo, hi): block origin/level and its entry span in the array.
    struct Node {
        std::uint32_t ox, oy, k;
        std::size_t lo, hi;
    };
    std::vector<Node> stack;
    stack.push_back({0u, 0u, norm.order, 0,
                     static_cast<std::size_t>(index.keys.size())});

    while (!stack.empty()) {
        const Node node = stack.back();
        stack.pop_back();

        if (node.lo >= node.hi) continue;          // empty block: prune by data
        ++ctx.nodes_visited;

        const std::uint64_t sz = 1ull << node.k;
        const Bounds bounds = norm.block_bounds(node.ox, node.oy, sz);
        if (region.disjoint(bounds)) continue;      // geometric prune

        const std::size_t count = node.hi - node.lo;
        if (region.contains(bounds) || node.k == 0
            || count <= HILBERT_LEAF_THRESHOLD) {
            scan_entry_range(ctx, node.lo, node.hi);
            continue;
        }

        // Subdivide; locate each child's entry span by its key interval.
        const std::uint32_t h = static_cast<std::uint32_t>(sz >> 1);
        const std::uint32_t children[4][2] = {
            {node.ox,     node.oy},
            {node.ox + h, node.oy},
            {node.ox,     node.oy + h},
            {node.ox + h, node.oy + h},
        };
        for (const auto& c : children) {
            const auto rs = square_key_range(norm.order, c[0], c[1], node.k - 1);
            const std::uint64_t cbase = rs.first;
            const std::uint64_t cend = cbase + rs.second;   // may reach 2^64
            const bool wrap = cend < cbase;                 // top block: [cbase, 2^64)
            const std::size_t clo = static_cast<std::size_t>(
                std::lower_bound(k_begin + node.lo, k_begin + node.hi, cbase)
                - k_begin);
            const std::size_t chi = wrap ? node.hi : static_cast<std::size_t>(
                std::lower_bound(k_begin + node.lo, k_begin + node.hi, cend)
                - k_begin);
            if (clo < chi) {
                stack.push_back({c[0], c[1], node.k - 1, clo, chi});
            }
        }
    }
}


// ---------------------------------------------------------------------------
// Counting-only descent (B3b).
//
// Returns |{index entries whose midpoint lies in disk(centre, radius)}| exactly,
// without touching the candidate set, d_best, or phase 2. Two uses:
//   1. the UNCAPPED counterfactual, radius d_best + L_uncapped/2 + tie_tol. That
//      radius (2,874.12 m) is far outside the tight query region, so the counter
//      inside scan_entry_range cannot see it; a re-count over the same countywide
//      midpoint set is required.
//   2. --verify-counts: an independent second implementation of n_disk_r and
//      n_disk_infl, which must agree exactly with the scan-derived counters.
//
// A block whose coordinate bounds lie entirely inside the disk contributes its
// entry count in O(1) — no per-entry test — so the cost is proportional to the
// blocks straddling the circle rather than to the (very large) enclosed
// population. Exactness is unaffected: block bounds contain every midpoint in
// the block, so "bounds inside the disk" implies "all its midpoints inside".
// ---------------------------------------------------------------------------
struct CountStats {
    std::uint64_t nodes_visited = 0;
    std::uint64_t whole_blocks = 0;    // O(1) contained-block shortcuts
    std::uint64_t entries_tested = 0;  // midpoints tested individually
};


std::uint64_t count_midpoints_in_disk(
    const HilbertIndex& index, const Point& centre, double radius,
    CountStats& stats
) {
    const HilbertNormalization& norm = index.norm;
    const auto k_begin = index.keys.begin();
    const Region region = make_region(Region::Kind::Disk, centre, radius);
    const double radius_squared = radius * radius;

    struct Node { std::uint32_t ox, oy, k; std::size_t lo, hi; };
    std::vector<Node> stack;
    stack.push_back({0u, 0u, norm.order, 0,
                     static_cast<std::size_t>(index.keys.size())});

    std::uint64_t count = 0;
    while (!stack.empty()) {
        const Node node = stack.back();
        stack.pop_back();
        if (node.lo >= node.hi) continue;
        ++stats.nodes_visited;

        const std::uint64_t sz = 1ull << node.k;
        const Bounds bounds = norm.block_bounds(node.ox, node.oy, sz);
        if (region.disjoint(bounds)) continue;

        if (region.contains(bounds)) {          // whole block inside: O(1)
            count += static_cast<std::uint64_t>(node.hi - node.lo);
            ++stats.whole_blocks;
            continue;
        }

        const std::size_t entries = node.hi - node.lo;
        if (node.k == 0 || entries <= HILBERT_LEAF_THRESHOLD) {
            for (std::size_t i = node.lo; i < node.hi; ++i) {
                ++stats.entries_tested;
                const double dx = centre.x - index.midpoints[i].x;
                const double dy = centre.y - index.midpoints[i].y;
                if (dx * dx + dy * dy <= radius_squared) ++count;
            }
            continue;
        }

        const std::uint32_t h = static_cast<std::uint32_t>(sz >> 1);
        const std::uint32_t children[4][2] = {
            {node.ox,     node.oy},
            {node.ox + h, node.oy},
            {node.ox,     node.oy + h},
            {node.ox + h, node.oy + h},
        };
        for (const auto& c : children) {
            const auto rs = square_key_range(norm.order, c[0], c[1], node.k - 1);
            const std::uint64_t cbase = rs.first;
            const std::uint64_t cend = cbase + rs.second;
            const bool wrap = cend < cbase;
            const std::size_t clo = static_cast<std::size_t>(
                std::lower_bound(k_begin + node.lo, k_begin + node.hi, cbase)
                - k_begin);
            const std::size_t chi = wrap ? node.hi : static_cast<std::size_t>(
                std::lower_bound(k_begin + node.lo, k_begin + node.hi, cend)
                - k_begin);
            if (clo < chi) stack.push_back({c[0], c[1], node.k - 1, clo, chi});
        }
    }
    return count;
}


// ---------------------------------------------------------------------------
// Query result: phase-2 answer plus B3a phase-1 / inflation instrumentation.
// ---------------------------------------------------------------------------
struct HilbertNearestResult {
    SegmentNearestResult verify;   // distance, feature, tie, phase-2 counters

    // Phase-1 descent work (kept separate from verification): quadtree-over-
    // sorted-array nodes visited, leaf blocks scanned, and entries read.
    std::uint64_t range_nodes_visited = 0;
    std::uint64_t range_ranges_emitted = 0;   // leaf blocks scanned
    std::uint64_t entries_scanned = 0;    // N_decomp: midpoints the descent reads

    // The two stacked inflations, per property, at the tight query radius.
    std::uint64_t n_disk_r = 0;           // midpoints in disk(d_best + tie_tol)
    std::uint64_t n_disk_infl = 0;        // midpoints in disk(d_best + L/2 + tie_tol)

    // B3b additions.
    std::uint64_t n_true_r = 0;           // entries with d(p, segment) <= d_best + tie_tol
    std::uint64_t n_disk_unc = 0;         // midpoints in disk(d_best + L_unc/2 + tie_tol)
    std::uint64_t seed_probes = 0;        // key comparisons spent finding the start position

    // B5 instrumentation. Never emitted to the CSV -- adding a per-property
    // seed column would break the byte-identical seam test that is the whole
    // acceptance criterion. The seed-error report needs the query key and the
    // position the seeder returned, and recomputing the Hilbert key outside the
    // query would duplicate the transform.
    std::uint64_t seed_key = 0;
    std::size_t seed_position_used = 0;
};


void reset_candidates(
    std::vector<int>& candidate_features,
    std::vector<char>& feature_is_candidate,
    std::vector<double>& feature_best_split_distance
) {
    for (int f : candidate_features) {
        const std::size_t fp = static_cast<std::size_t>(f);
        feature_is_candidate[fp] = 0;
        feature_best_split_distance[fp] =
            std::numeric_limits<double>::infinity();
    }
    candidate_features.clear();
}


// Phase 2 mirrors B2's find_nearest_segment_bvh selection/tie loop exactly,
// restricted to the Hilbert candidate set. The verification PRIMITIVES
// (distance_to_feature, polygon_contains_point) are reused unchanged; only the
// loop is re-expressed because its candidate source is the Hilbert query rather
// than the BVH traversal. A future refactor could hoist this into a shared
// verify() used by both programs; that is out of scope for B3a (it would edit
// the frozen B2 file).
void verify_candidates(
    const Point& point, const std::vector<WaterFeature>& features,
    const std::vector<int>& candidate_features,
    std::vector<char>& feature_is_candidate,
    std::vector<double>& feature_best_split_distance,
    const PartExteriorBounds& part_exterior_bounds,
    VerificationMode verification_mode, double tie_tolerance_meters,
    SegmentNearestResult& result
) {
    double best_distance = std::numeric_limits<double>::infinity();
    int best_feature_index = -1;
    int tie_count = 0;

    for (const int feature_index : candidate_features) {
        const std::size_t fp = static_cast<std::size_t>(feature_index);
        feature_is_candidate[fp] = 0;                       // clear scratch
        const double split_distance = feature_best_split_distance[fp];
        feature_best_split_distance[fp] =
            std::numeric_limits<double>::infinity();

        const WaterFeature& feature = features[fp];
        ++result.candidate_feature_checks;

        double candidate_distance = std::numeric_limits<double>::infinity();

        if (verification_mode == VerificationMode::OriginalGeometry) {
            const DistanceResult candidate = distance_to_feature(point, feature);
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
                if (candidate_distance <= BOUNDARY_EPSILON_METERS) {
                    candidate_distance = 0.0;
                } else {
                    const ContainmentResult containment = polygon_contains_point(
                        point, feature, part_exterior_bounds[fp]);
                    result.containment_ring_checks += containment.ring_checks;
                    result.containment_parts_tested += containment.parts_tested;
                    result.containment_parts_skipped += containment.parts_skipped;
                    result.segment_checks += containment.ring_checks;
                    if (containment.inside) candidate_distance = 0.0;
                }
            }
        }

        if (candidate_distance < best_distance - tie_tolerance_meters) {
            best_distance = candidate_distance;
            best_feature_index = feature_index;
            tie_count = 1;
            continue;
        }
        if (std::abs(candidate_distance - best_distance) <= tie_tolerance_meters) {
            ++tie_count;
            if (best_feature_index < 0
                || feature.water_feature_id
                    < features[static_cast<std::size_t>(best_feature_index)]
                        .water_feature_id) {
                best_distance = candidate_distance;
                best_feature_index = feature_index;
            }
        }
    }

    if (best_feature_index < 0) {
        throw std::runtime_error(
            "The Hilbert query did not return a nearest feature.");
    }
    result.feature_index = best_feature_index;
    result.distance = best_distance;
    result.tie_count = tie_count;
}


// ---------------------------------------------------------------------------
// One property: seed -> resolve d_best -> tight decomposition -> verify.
// ---------------------------------------------------------------------------
HilbertNearestResult find_nearest_hilbert(
    const Point& point, const std::vector<WaterFeature>& features,
    const HilbertIndex& index, const PartExteriorBounds& part_exterior_bounds,
    double inflation_half, Region::Kind region_kind,
    VerificationMode verification_mode, double tie_tolerance_meters,
    SeedMode seed_mode, const RmiModel* rmi_model,
    double uncapped_inflation_half, bool verify_counts,
    std::vector<int>& candidate_features,
    std::vector<char>& feature_is_candidate,
    std::vector<double>& feature_best_split_distance
) {
    HilbertNearestResult out;

    // --- Seed: a finite achieved split distance from the curve neighbourhood.
    // The ONLY seam between implementation #4 and #5; correctness-neutral.
    const std::uint64_t key = hilbert_xy2d(
        index.norm.order, index.norm.cell_x(point.x), index.norm.cell_y(point.y));
    const SeedResult seed = seed_position(index, key, seed_mode, rmi_model);
    out.seed_probes = seed.probes;
    const std::size_t pos = seed.position;
    const std::size_t n = index.keys.size();
    out.seed_key = key;
    out.seed_position_used = pos;

    if (verify_counts && seed_mode == SeedMode::BinarySearch) {
        const std::size_t reference = static_cast<std::size_t>(
            std::lower_bound(index.keys.begin(), index.keys.end(), key)
            - index.keys.begin());
        if (reference != pos) {
            throw std::runtime_error(
                "Counted binary search disagrees with std::lower_bound.");
        }
    }
    const std::size_t lo = (pos > SEED_WINDOW) ? pos - SEED_WINDOW : 0;
    const std::size_t hi = std::min(n, pos + SEED_WINDOW);
    double d_seed = std::numeric_limits<double>::infinity();
    for (std::size_t i = lo; i < hi; ++i) {
        const SegmentLeaf& s = index.segments[i];
        const double dsq =
            point_segment_distance_squared(point, s.start, s.end);
        if (dsq < d_seed * d_seed) d_seed = std::sqrt(dsq);
    }
    if (!std::isfinite(d_seed)) {
        // Empty window can only happen for an empty index; be safe.
        d_seed = std::numeric_limits<double>::max() / 4.0;
    }

    // --- Resolve: descend at the seed radius to obtain the exact nearest split
    // distance d_best. box(R_seed) covers box(true + L/2 + tie_tol), so the
    // scanned set contains the true nearest segment.
    const double R_seed = d_seed + inflation_half + tie_tolerance_meters;

    ScanContext resolve;
    resolve.index = &index;
    resolve.point = point;
    resolve.candidate_features = &candidate_features;
    resolve.feature_is_candidate = &feature_is_candidate;
    resolve.feature_best_split_distance = &feature_best_split_distance;
    descend_and_scan(resolve, make_region(region_kind, point, R_seed));
    const double d_best = resolve.d_best;

    // --- Tight: R = d_best + L/2 + tie_tol (<= R_seed). The final candidate set
    // and the honest box-vs-disk counters must reflect the tight radius, so the
    // resolve candidates are discarded and a single measured descent at R is run
    // (one extra descent; a B3b micro-optimization could fuse the two when the
    // seed is already tight).
    const double R = d_best + inflation_half + tie_tolerance_meters;
    const double r_disk = d_best + tie_tolerance_meters;

    reset_candidates(candidate_features, feature_is_candidate,
                     feature_best_split_distance);

    ScanContext tight;
    tight.index = &index;
    tight.point = point;
    tight.candidate_features = &candidate_features;
    tight.feature_is_candidate = &feature_is_candidate;
    tight.feature_best_split_distance = &feature_best_split_distance;
    tight.measure = true;
    tight.r_disk_sq = r_disk * r_disk;
    tight.r_true_sq = r_disk * r_disk;
    tight.r_infl_sq = R * R;
    descend_and_scan(tight, make_region(region_kind, point, R));

    out.range_nodes_visited = tight.nodes_visited;
    out.range_ranges_emitted = tight.leaves_scanned;
    out.entries_scanned = tight.entries_scanned;
    out.n_disk_r = tight.n_disk_r;
    out.n_true_r = tight.n_true_r;
    out.n_disk_infl = tight.n_disk_infl;

    // --- B3b: the uncapped counterfactual, re-counted over the same midpoints.
    CountStats count_stats;
    if (uncapped_inflation_half > 0.0) {
        out.n_disk_unc = count_midpoints_in_disk(
            index, point,
            d_best + uncapped_inflation_half + tie_tolerance_meters,
            count_stats);
        if (out.n_disk_unc < out.n_disk_infl) {
            throw std::runtime_error(
                "Uncapped disk admitted fewer midpoints than the capped disk.");
        }
    }

    // --- B3b: independent re-count of the two scan-derived disk counters.
    if (verify_counts) {
        const std::uint64_t recount_r =
            count_midpoints_in_disk(index, point, r_disk, count_stats);
        const std::uint64_t recount_infl =
            count_midpoints_in_disk(index, point, R, count_stats);
        if (recount_r != out.n_disk_r || recount_infl != out.n_disk_infl) {
            throw std::runtime_error(
                "Counting descent disagrees with the scan-derived disk counters.");
        }
        if (out.n_true_r < 1 || out.n_disk_r > out.n_true_r
            || out.n_true_r > out.n_disk_infl
            || out.n_disk_infl > out.entries_scanned) {
            throw std::runtime_error(
                "Per-property inflation ordering violated.");
        }
    }

    verify_candidates(point, features, candidate_features, feature_is_candidate,
                      feature_best_split_distance, part_exterior_bounds,
                      verification_mode, tie_tolerance_meters, out.verify);
    candidate_features.clear();
    return out;
}


// ---------------------------------------------------------------------------
// B5: seed-error report.
//
// The measurement Current Status section 21 asks for: predicted-vs-actual
// position error on the REAL property-point keys. B4's 94.240 percent within
// +/-64 is an INDEX-key figure and does not carry over, because index keys are
// the training set and property keys are not.
//
// Deliberately NOT in the index manifest: that file describes the index, this
// describes one run against it, and the two have different provenance. Also
// deliberately not a CSV column: a per-property seed column would break the
// byte-identical seam test.
//
// A run carrying --seed-error-stats is NOT benchmark-eligible. Computing the
// reference costs a full lower_bound per property -- in rmi mode that is
// precisely the ~20 probes the model exists to remove.
// ---------------------------------------------------------------------------

// numpy's default percentile (method="linear"), so these figures are directly
// comparable with the p50/p90/p99/p99.9 rmi.py recorded over index keys. A
// different convention here would silently make the two incomparable, which is
// the mistake 18.21 warns about.
double linear_percentile(const std::vector<std::int64_t>& sorted_values,
                         double quantile) {
    if (sorted_values.empty()) return 0.0;
    const double position = (quantile / 100.0)
        * static_cast<double>(sorted_values.size() - 1);
    const double lower_index = std::floor(position);
    const std::size_t lo = static_cast<std::size_t>(lower_index);
    const std::size_t hi = std::min(lo + 1, sorted_values.size() - 1);
    const double fraction = position - lower_index;
    return static_cast<double>(sorted_values[lo])
        + fraction * (static_cast<double>(sorted_values[hi])
                      - static_cast<double>(sorted_values[lo]));
}


void write_seed_error_report(
    const std::string& path, SeedMode seed_mode, std::size_t index_entries,
    std::vector<std::int64_t> errors
) {
    const std::filesystem::path fspath(path);
    if (!fspath.parent_path().empty()) {
        std::filesystem::create_directories(fspath.parent_path());
    }
    std::ofstream out(path);
    if (!out) {
        throw std::runtime_error("Could not open seed-error report: " + path);
    }

    const std::size_t n = errors.size();
    std::vector<std::int64_t> absolute(n);
    std::uint64_t within_window = 0;
    std::uint64_t exact_zero = 0;
    long double sum_signed = 0.0L;
    long double sum_absolute = 0.0L;
    for (std::size_t i = 0; i < n; ++i) {
        const std::int64_t value = errors[i];
        absolute[i] = value < 0 ? -value : value;
        if (value == 0) ++exact_zero;
        if (static_cast<std::uint64_t>(absolute[i]) <= SEED_WINDOW) {
            ++within_window;
        }
        sum_signed += static_cast<long double>(value);
        sum_absolute += static_cast<long double>(absolute[i]);
    }
    std::sort(errors.begin(), errors.end());
    std::sort(absolute.begin(), absolute.end());
    const double denominator = n ? static_cast<double>(n) : 1.0;

    out << std::setprecision(17)
        << "{\n"
        << "  \"chunk\": \"B5\",\n"
        << "  \"report\": \"seed_position_error_on_property_keys\",\n"
        << "  \"reference\": \"std::lower_bound over the index key array\",\n"
        << "  \"benchmark_eligible\": false,\n"
        << "  \"seed_mode\": \"" << seed_mode_name(seed_mode) << "\",\n"
        << "  \"properties\": " << n << ",\n"
        << "  \"index_entries\": " << index_entries << ",\n"
        << "  \"seed_window_entries\": " << SEED_WINDOW << ",\n"
        << "  \"exact_zero\": " << exact_zero << ",\n"
        << "  \"within_seed_window\": " << within_window << ",\n"
        << "  \"fraction_within_seed_window\": "
        << static_cast<double>(within_window) / denominator << ",\n"
        << "  \"signed_error\": {\n"
        << "    \"min\": " << (n ? errors.front() : 0) << ",\n"
        << "    \"max\": " << (n ? errors.back() : 0) << ",\n"
        << "    \"mean\": " << static_cast<double>(sum_signed / denominator) << ",\n"
        << "    \"p50\": " << linear_percentile(errors, 50.0) << ",\n"
        << "    \"p90\": " << linear_percentile(errors, 90.0) << ",\n"
        << "    \"p99\": " << linear_percentile(errors, 99.0) << ",\n"
        << "    \"p99.9\": " << linear_percentile(errors, 99.9) << "\n"
        << "  },\n"
        << "  \"absolute_error\": {\n"
        << "    \"max\": " << (n ? absolute.back() : 0) << ",\n"
        << "    \"mean\": " << static_cast<double>(sum_absolute / denominator) << ",\n"
        << "    \"p50\": " << linear_percentile(absolute, 50.0) << ",\n"
        << "    \"p90\": " << linear_percentile(absolute, 90.0) << ",\n"
        << "    \"p99\": " << linear_percentile(absolute, 99.0) << ",\n"
        << "    \"p99.9\": " << linear_percentile(absolute, 99.9) << "\n"
        << "  }\n"
        << "}\n";
}


// ---------------------------------------------------------------------------
// Output writer.
// ---------------------------------------------------------------------------
void write_hilbert_results(
    const std::string& output_path, const std::vector<PropertyPoint>& properties,
    const std::vector<WaterFeature>& features, const HilbertIndex& index,
    const PartExteriorBounds& part_exterior_bounds, double inflation_half,
    Region::Kind region_kind, const std::string& distance_crs,
    VerificationMode verification_mode, double tie_tolerance_meters,
    SeedMode seed_mode, const RmiModel* rmi_model,
    double uncapped_inflation_half, bool verify_counts,
    const std::string& seed_error_stats_path
) {
    const std::filesystem::path fspath(output_path);
    if (!fspath.parent_path().empty()) {
        std::filesystem::create_directories(fspath.parent_path());
    }
    std::ofstream output(output_path);
    if (!output) {
        throw std::runtime_error("Could not open output file: " + output_path);
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
        << "cpp_line_segment_checks,"
        << "cpp_polygon_segment_checks,"
        << "cpp_containment_ring_checks,"
        << "cpp_containment_parts_tested,"
        << "cpp_containment_parts_skipped,"
        << "cpp_range_nodes_visited,"
        << "cpp_range_ranges_emitted,"
        << "cpp_entries_scanned,"
        << "cpp_n_disk_r,"
        << "cpp_n_true_r,"
        << "cpp_n_disk_infl,"
        << "cpp_n_disk_unc,"
        << "cpp_seed_probes,"
        << "distance_crs,"
        << "verification_mode,"
        << "region_mode,"
        << "seed_mode,"
        << "algorithm\n";

    output << std::setprecision(17);

    const char* region_name =
        region_kind == Region::Kind::Disk ? "disk" : "disk_bbox";

    std::vector<int> candidate_features;
    candidate_features.reserve(64);
    std::vector<char> feature_is_candidate(features.size(), 0);
    std::vector<double> feature_best_split_distance(
        features.size(), std::numeric_limits<double>::infinity());

    std::uint64_t tot_scanned = 0, tot_ndr = 0, tot_ndi = 0;
    std::uint64_t tot_nodes = 0, tot_ranges = 0, tot_seg_checks = 0;
    std::uint64_t tot_ntrue = 0, tot_nunc = 0, tot_probes = 0;
    std::uint64_t properties_with_ndr = 0;

    const bool collect_seed_errors = !seed_error_stats_path.empty();
    std::vector<std::int64_t> seed_errors;
    if (collect_seed_errors) seed_errors.reserve(properties.size());

    const auto start = std::chrono::steady_clock::now();

    for (std::size_t pi = 0; pi < properties.size(); ++pi) {
        const PropertyPoint& property = properties[pi];
        const HilbertNearestResult r = find_nearest_hilbert(
            property.point, features, index, part_exterior_bounds,
            inflation_half, region_kind, verification_mode, tie_tolerance_meters,
            seed_mode, rmi_model, uncapped_inflation_half, verify_counts,
            candidate_features, feature_is_candidate, feature_best_split_distance);

        if (collect_seed_errors) {
            const std::int64_t reference = static_cast<std::int64_t>(
                std::lower_bound(index.keys.begin(), index.keys.end(),
                                 r.seed_key) - index.keys.begin());
            seed_errors.push_back(
                static_cast<std::int64_t>(r.seed_position_used) - reference);
        }

        const WaterFeature& sel =
            features[static_cast<std::size_t>(r.verify.feature_index)];

        output
            << csv_escape(property.property_id) << ","
            << r.verify.distance << ","
            << csv_escape(sel.water_feature_id) << ","
            << csv_escape(sel.water_feature_class) << ","
            << csv_escape(sel.water_feature_type) << ","
            << csv_escape(sel.source_feature_id) << ","
            << sel.source_object_id << ","
            << csv_escape(sel.source_name) << ","
            << r.verify.tie_count << ","
            << r.verify.segment_checks << ","
            << r.verify.candidate_feature_checks << ","
            << r.verify.line_segment_checks << ","
            << r.verify.polygon_segment_checks << ","
            << r.verify.containment_ring_checks << ","
            << r.verify.containment_parts_tested << ","
            << r.verify.containment_parts_skipped << ","
            << r.range_nodes_visited << ","
            << r.range_ranges_emitted << ","
            << r.entries_scanned << ","
            << r.n_disk_r << ","
            << r.n_true_r << ","
            << r.n_disk_infl << ","
            << r.n_disk_unc << ","
            << r.seed_probes << ","
            << csv_escape(distance_crs) << ","
            << verification_mode_name(verification_mode) << ","
            << region_name << ","
            << seed_mode_name(seed_mode) << ",hilbert\n";

        tot_scanned += r.entries_scanned;
        tot_ndr += r.n_disk_r;
        tot_ndi += r.n_disk_infl;
        tot_ntrue += r.n_true_r;
        tot_nunc += r.n_disk_unc;
        tot_probes += r.seed_probes;
        if (r.n_disk_r > 0) ++properties_with_ndr;
        tot_nodes += r.range_nodes_visited;
        tot_ranges += r.range_ranges_emitted;
        tot_seg_checks += r.verify.segment_checks;

        if ((pi + 1) % 100 == 0 || pi + 1 == properties.size()) {
            std::cout << "Processed " << (pi + 1) << "/"
                      << properties.size() << " properties\n";
        }
    }

    const auto end = std::chrono::steady_clock::now();
    const double seconds = std::chrono::duration<double>(end - start).count();
    const double pc = static_cast<double>(properties.size());

    const double geom_infl = tot_ntrue ? static_cast<double>(tot_ndi)
                                       / static_cast<double>(tot_ntrue) : 0.0;
    const double unc_infl = tot_ntrue ? static_cast<double>(tot_nunc)
                                      / static_cast<double>(tot_ntrue) : 0.0;
    const double split_gain = tot_ndi ? static_cast<double>(tot_nunc)
                                      / static_cast<double>(tot_ndi) : 0.0;
    const double box_infl = tot_ndi ? static_cast<double>(tot_scanned)
                                    / static_cast<double>(tot_ndi) : 0.0;

    std::cout
        << std::fixed << std::setprecision(6)
        << "Hilbert computation seconds: " << seconds << "\n"
        << "Properties per second: " << pc / seconds << "\n"
        << "Average seed probes per property: " << tot_probes / pc << "\n"
        << "Average range nodes visited per property: " << tot_nodes / pc << "\n"
        << "Average ranges emitted per property: " << tot_ranges / pc << "\n"
        << "Average entries scanned per property (N_decomp): "
        << tot_scanned / pc << "\n"
        << "Average entries satisfying the predicate (N_true_r): "
        << tot_ntrue / pc << "\n"
        << "Average midpoints in disk(r+L/2) per property (N_disk_infl): "
        << tot_ndi / pc << "\n"
        << "Average midpoints in disk(r+L_unc/2) per property (N_disk_unc): "
        << tot_nunc / pc << "\n"
        << "Geometric L/2 inflation, capped (N_disk_infl / N_true_r): "
        << geom_infl << "\n"
        << "Geometric inflation, UNCAPPED (N_disk_unc / N_true_r): "
        << unc_infl << "\n"
        << "What the B1 split bought (N_disk_unc / N_disk_infl): "
        << split_gain << "\n"
        << "Box-vs-disk indexing inflation (N_decomp / N_disk_infl): "
        << box_infl << "\n"
        << "Average phase-2 segment checks per property: "
        << tot_seg_checks / pc << "\n"
        // B3a's intended denominator, retained and reported as degenerate:
        // d_best is a segment distance while this counter tests midpoints, so it
        // is a coincidence counter, not a population. See the header note.
        << "Degenerate B3a denominator (N_disk_r): total " << tot_ndr
        << ", nonzero on " << properties_with_ndr << " of "
        << properties.size() << " properties\n";

    if (collect_seed_errors) {
        write_seed_error_report(seed_error_stats_path, seed_mode,
                                index.keys.size(), seed_errors);
        std::cout
            << "Seed-error report: " << seed_error_stats_path << "\n"
            << "  NOT benchmark-eligible: a reference lower_bound was computed "
            << "per property.\n";
    }
}


[[maybe_unused]] Region::Kind parse_region_mode(const std::string& raw) {
    if (raw == "disk_bbox") return Region::Kind::DiskBBox;
    if (raw == "disk") return Region::Kind::Disk;
    throw std::runtime_error(
        "Invalid region_mode (expected 'disk_bbox' or 'disk'): " + raw);
}


[[maybe_unused]] SeedMode parse_seed_mode(const std::string& raw) {
    if (raw == "binary") return SeedMode::BinarySearch;
    if (raw == "rmi") return SeedMode::Rmi;
    if (raw == "zero") return SeedMode::Zero;
    throw std::runtime_error(
        "Invalid --seed (expected 'binary', 'rmi', or 'zero'): " + raw);
}


// Options may appear anywhere; the positional interface used by
// fixture_crosscheck.py, the cap sweep, and the benchmark harness is unchanged.
// Unknown options are an error rather than a silent no-op.
struct CommandLine {
    std::vector<std::string> positional;
    std::map<std::string, std::string> options;
};


CommandLine parse_command_line(int argc, char* argv[]) {
    static const std::set<std::string> VALUE_OPTIONS = {
        "seed", "uncapped-half", "dump-keys", "rmi-model", "rmi-probes",
        "seed-error-stats"};
    static const std::set<std::string> FLAG_OPTIONS = {"verify-counts"};

    CommandLine parsed;
    for (int i = 1; i < argc; ++i) {
        const std::string token = argv[i];
        if (token.rfind("--", 0) != 0) {
            parsed.positional.push_back(token);
            continue;
        }
        std::string name = token.substr(2);
        std::string value;
        bool have_value = false;
        const std::size_t equals = name.find('=');
        if (equals != std::string::npos) {
            value = name.substr(equals + 1);
            name = name.substr(0, equals);
            have_value = true;
        }
        const bool is_flag = FLAG_OPTIONS.count(name) > 0;
        if (!is_flag && VALUE_OPTIONS.count(name) == 0) {
            throw std::runtime_error("Unknown option: --" + name);
        }
        if (!have_value) {
            if (is_flag) {
                value = "1";
            } else if (i + 1 < argc) {
                value = argv[++i];
            } else {
                throw std::runtime_error(
                    "Option --" + name + " requires a value.");
            }
        }
        parsed.options[name] = value;
    }
    return parsed;
}


[[maybe_unused]] double parse_double_argument(
    const std::string& raw, const char* what
) {
    std::size_t consumed = 0;
    double parsed = 0.0;
    try { parsed = std::stod(raw, &consumed); }
    catch (const std::exception&) {
        throw std::runtime_error(std::string("Invalid ") + what + ": " + raw);
    }
    if (consumed != raw.size() || !std::isfinite(parsed)) {
        throw std::runtime_error(std::string("Invalid ") + what + ": " + raw);
    }
    return parsed;
}


[[maybe_unused]] std::uint64_t parse_uint64_argument(
    const std::string& raw, const char* what
) {
    // std::stoull accepts a leading sign and wraps it, so the digits are
    // screened first rather than trusted.
    if (raw.empty()
        || raw.find_first_not_of("0123456789") != std::string::npos) {
        throw std::runtime_error(std::string("Invalid ") + what + ": " + raw);
    }
    std::size_t consumed = 0;
    std::uint64_t parsed = 0;
    try { parsed = std::stoull(raw, &consumed); }
    catch (const std::exception&) {
        throw std::runtime_error(std::string("Invalid ") + what + ": " + raw);
    }
    if (consumed != raw.size()) {
        throw std::runtime_error(std::string("Invalid ") + what + ": " + raw);
    }
    return parsed;
}


std::vector<std::string> split_on(const std::string& raw, char delimiter) {
    std::vector<std::string> parts;
    std::size_t start = 0;
    while (true) {
        const std::size_t hit = raw.find(delimiter, start);
        if (hit == std::string::npos) {
            parts.push_back(raw.substr(start));
            break;
        }
        parts.push_back(raw.substr(start, hit - start));
        start = hit + 1;
    }
    return parts;
}


// One probe record from the B4 model manifest: index, key, the normalized x as
// a C99 hex float, the routed leaf, and the predicted position.
struct RmiProbe {
    std::uint64_t index = 0;
    std::uint64_t key = 0;
    double x = 0.0;
    std::uint64_t leaf = 0;
    std::uint64_t position = 0;
};


// --rmi-probes "i,k,x,l,p;i,k,x,l,p;..."  -- one option, so the CLI parser is
// untouched. Python owns JSON (Nucleus section 6); the manifest's probe_records
// are transcribed into scalars and C++ never learns to parse JSON.
[[maybe_unused]] std::vector<RmiProbe> parse_rmi_probes(const std::string& raw) {
    std::vector<RmiProbe> probes;
    for (const std::string& record : split_on(raw, ';')) {
        if (record.empty()) continue;              // tolerate a trailing ';'
        const std::vector<std::string> fields = split_on(record, ',');
        if (fields.size() != 5) {
            throw std::runtime_error(
                "Each --rmi-probes record needs 5 fields "
                "'index,key,x_hex,leaf,position': " + record);
        }
        RmiProbe probe;
        probe.index = parse_uint64_argument(fields[0], "probe index");
        probe.key = parse_uint64_argument(fields[1], "probe key");
        // std::stod -> strtod parses C99 hex-float natively. The endptr check
        // inside parse_double_argument makes that an assertion rather than an
        // assumption: this program never calls setlocale, so it stays in the
        // "C" locale where '.' is the radix point, but a locale-shifted build
        // would fail loudly here instead of silently truncating at the '.'.
        probe.x = parse_double_argument(fields[2], "probe x");
        probe.leaf = parse_uint64_argument(fields[3], "probe leaf");
        probe.position = parse_uint64_argument(fields[4], "probe position");
        probes.push_back(probe);
    }
    if (probes.empty()) {
        throw std::runtime_error("--rmi-probes supplied no records.");
    }
    return probes;
}


[[maybe_unused]] RmiModel load_rmi_model(const std::string& path) {
    // Unconditional and independent of whether probes were supplied, so there
    // is no silent hole on any invocation: the coarsest way the float contract
    // can fail is a build whose uint64 -> double conversion is not
    // round-to-nearest-even, which [conv.fpint] permits. (double)(2^53 + 3) is
    // exactly halfway between 2^53 + 2 and 2^53 + 4; round-half-to-even gives
    // 2^53 + 4, truncation gives 2^53 + 2. The probe records remain strictly
    // stronger -- they pin normalization, root, leaf and floor as well -- but
    // this fires even if someone adds an invocation that omits them.
    const std::uint64_t rounding_probe = (1ull << 53) + 3ull;
    if (static_cast<double>(rounding_probe) != 9007199254740996.0) {
        throw std::runtime_error(
            "uint64 -> double on this build is not round-to-nearest-even; the "
            "RMI float contract (Nucleus 18.20) does not hold here.");
    }

    std::ifstream file(path, std::ios::binary);
    if (!file) {
        throw std::runtime_error("Could not open RMI model: " + path);
    }
    file.seekg(0, std::ios::end);
    const std::streamoff file_size = file.tellg();
    if (file_size < static_cast<std::streamoff>(RMI_HEADER_BYTES)) {
        throw std::runtime_error("RMI model is shorter than its header: " + path);
    }
    std::vector<char> bytes(static_cast<std::size_t>(file_size));
    file.seekg(0, std::ios::beg);
    file.read(bytes.data(), file_size);
    if (!file) {
        throw std::runtime_error("RMI model read failed: " + path);
    }

    // Fixed little-endian layout, matching struct.Struct("<8sIIQQQQdd32s") plus
    // a packed leaf array in rmi.py. Same little-endian assumption --dump-keys
    // already documents; a big-endian build would need byte swaps here.
    if (std::memcmp(bytes.data(), "CAPRMRMI", 8) != 0) {
        throw std::runtime_error("RMI model has bad magic: " + path);
    }
    std::uint32_t version = 0;
    std::uint32_t stride = 0;
    std::memcpy(&version, bytes.data() + 8, 4);
    std::memcpy(&stride, bytes.data() + 12, 4);
    if (version != RMI_FORMAT_VERSION) {
        throw std::runtime_error(
            "Unsupported RMI model format version: " + std::to_string(version));
    }
    if (stride != RMI_LEAF_STRIDE_BYTES) {
        throw std::runtime_error(
            "Unsupported RMI leaf stride: " + std::to_string(stride));
    }

    RmiModel model;
    std::memcpy(&model.n_keys, bytes.data() + 16, 8);
    std::memcpy(&model.n_leaves, bytes.data() + 24, 8);
    std::memcpy(&model.key_min, bytes.data() + 32, 8);
    std::memcpy(&model.key_max, bytes.data() + 40, 8);
    std::memcpy(&model.root_a, bytes.data() + 48, 8);
    std::memcpy(&model.root_b, bytes.data() + 56, 8);

    static const char HEX_DIGITS[] = "0123456789abcdef";
    model.keys_sha256_hex.resize(64);
    for (std::size_t i = 0; i < 32; ++i) {
        const unsigned char byte =
            static_cast<unsigned char>(bytes[64 + i]);
        model.keys_sha256_hex[2 * i] = HEX_DIGITS[byte >> 4];
        model.keys_sha256_hex[2 * i + 1] = HEX_DIGITS[byte & 0x0f];
    }

    if (model.n_keys == 0 || model.n_leaves == 0) {
        throw std::runtime_error("RMI model declares zero keys or zero leaves.");
    }
    const std::size_t expected_bytes = RMI_HEADER_BYTES
        + static_cast<std::size_t>(stride)
        * static_cast<std::size_t>(model.n_leaves);
    if (bytes.size() != expected_bytes) {
        throw std::runtime_error(
            "RMI model is " + std::to_string(bytes.size())
            + " bytes; its header implies " + std::to_string(expected_bytes));
    }
    if (model.key_max <= model.key_min) {
        throw std::runtime_error("RMI model key span is not positive.");
    }
    model.key_min_d = static_cast<double>(model.key_min);
    const double span = static_cast<double>(model.key_max) - model.key_min_d;
    if (!std::isfinite(span) || span <= 0.0) {
        throw std::runtime_error("RMI model key span is degenerate as a double.");
    }
    model.inv_span = 1.0 / span;

    const std::size_t leaves = static_cast<std::size_t>(model.n_leaves);
    model.leaf_a.resize(leaves);
    model.leaf_b.resize(leaves);
    for (std::size_t i = 0; i < leaves; ++i) {
        const char* leaf = bytes.data() + RMI_HEADER_BYTES + i * stride;
        std::memcpy(&model.leaf_a[i], leaf, 8);
        std::memcpy(&model.leaf_b[i], leaf + 8, 8);
        // The remaining 16 bytes are err_min/err_max/gap_err_min/gap_err_max.
        // Neither bound gates correctness (Nucleus 18.22) and this query path
        // reads a fixed +/- SEED_WINDOW window, so they are deliberately not
        // loaded rather than loaded and ignored.
    }
    return model;
}


// The model must be bound to the index it was trained on. C++ does NOT verify
// the header's training-array SHA-256: nothing in this project implements
// SHA-256 and adding it inside a chunk scoped as "swap one function" is not a
// trade worth making. What is checked instead is a fingerprint that costs
// nothing: the array length, and its content at five fixed positions carried by
// the probe records -- plus the full inference chain reproducing x, the routed
// leaf and the predicted position from those keys. The digest is verified by
// the trainer, which refuses to fit unless the key dump matches the index
// manifest. This is a documented weakening of Nucleus 18.20 on the C++ side.
[[maybe_unused]] void bind_rmi_model(
    const RmiModel& model, const HilbertIndex& index,
    const std::vector<RmiProbe>& probes
) {
    if (index.keys.empty()) {
        throw std::runtime_error("Cannot bind an RMI model to an empty index.");
    }
    if (model.n_keys != index.keys.size()) {
        throw std::runtime_error(
            "RMI model was trained on " + std::to_string(model.n_keys)
            + " keys; this index holds " + std::to_string(index.keys.size()));
    }
    if (model.key_min != index.keys.front() || model.key_max != index.keys.back()) {
        throw std::runtime_error(
            "RMI model key_min/key_max do not match this index's first/last key.");
    }

    for (const RmiProbe& probe : probes) {
        if (probe.index >= index.keys.size()) {
            throw std::runtime_error(
                "Probe index " + std::to_string(probe.index)
                + " is outside this index.");
        }
        if (index.keys[static_cast<std::size_t>(probe.index)] != probe.key) {
            throw std::runtime_error(
                "Probe key mismatch at index " + std::to_string(probe.index)
                + ": the model was trained on a different key array.");
        }
        const RmiPrediction predicted = rmi_predict(model, probe.key);
        std::uint64_t observed_bits = 0;
        std::uint64_t expected_bits = 0;
        std::memcpy(&observed_bits, &predicted.x, 8);
        std::memcpy(&expected_bits, &probe.x, 8);
        if (observed_bits != expected_bits) {
            throw std::runtime_error(
                "Normalized x differs from the training platform at probe index "
                + std::to_string(probe.index) + ": bits "
                + std::to_string(observed_bits) + " vs "
                + std::to_string(expected_bits)
                + ". The uint64 -> double float contract does not hold on this "
                  "build (Nucleus 18.20).");
        }
        if (predicted.leaf != probe.leaf) {
            throw std::runtime_error(
                "Routed leaf differs at probe index "
                + std::to_string(probe.index) + ": "
                + std::to_string(predicted.leaf) + " vs "
                + std::to_string(probe.leaf));
        }
        if (predicted.position != probe.position) {
            throw std::runtime_error(
                "Predicted position differs at probe index "
                + std::to_string(probe.index) + ": "
                + std::to_string(predicted.position) + " vs "
                + std::to_string(probe.position));
        }
    }
}

}  // namespace


int main(int argc, char* argv[]) {
    CommandLine command_line;
    try {
        command_line = parse_command_line(argc, argv);
    } catch (const std::exception& exception) {
        std::cerr << "Error: " << exception.what() << "\n";
        return 1;
    }
    const std::vector<std::string>& positional = command_line.positional;

    if (positional.size() < 4) {
        std::cerr
            << "Usage:\n"
            << "  water_distance_hilbert.exe <properties_csv> <features_csv> "
            << "<vertices_csv> <output_csv> [distance_crs] "
            << "[max_segment_length_m] [verification_mode] [region_mode] "
            << "[hilbert_order] [manifest_json] [options]\n"
            << "    verification_mode  'original' (default) or 'split'\n"
            << "    region_mode        'disk_bbox' (default) or 'disk'\n"
            << "    hilbert_order      bits per axis, default 32\n"
            << "  Options (order-independent):\n"
            << "    --seed binary|rmi|zero   start-position source; default "
            << "binary (the B3 control).\n"
            << "                             'rmi' requires --rmi-model and "
            << "--rmi-probes; 'zero'\n"
            << "                             is a test mode that always "
            << "returns position 0.\n"
            << "    --rmi-model <path>       B4 model artifact "
            << "(models/water_hilbert_rmi.bin).\n"
            << "    --rmi-probes <records>   REQUIRED with --seed rmi. "
            << "Semicolon-separated\n"
            << "                             'index,key,x_hex,leaf,position' "
            << "records copied from\n"
            << "                             the model manifest's "
            << "probe_records. Asserted at\n"
            << "                             load, which is how the "
            << "uint64->double contract is\n"
            << "                             checked rather than inherited.\n"
            << "    --seed-error-stats <p>   write predicted-vs-actual seed "
            << "position error over\n"
            << "                             the property keys to <p> as JSON. "
            << "Works under any\n"
            << "                             seed mode; under 'binary' the "
            << "error must be\n"
            << "                             identically zero, which self-tests "
            << "the harness.\n"
            << "                             A run carrying this is NOT "
            << "benchmark-eligible.\n"
            << "    --uncapped-half <m>      also count midpoints in "
            << "disk(d_best + <m> + tie_tol)\n"
            << "                             per property, the uncapped-L "
            << "counterfactual. 0 = off.\n"
            << "    --verify-counts          re-derive the disk counters with "
            << "an independent\n"
            << "                             counting descent and assert the "
            << "orderings.\n"
            << "    --dump-keys <path>       write the sorted uint64 key "
            << "array as little-endian\n"
            << "                             binary. This is B4's training "
            << "array; its SHA-256\n"
            << "                             attests to the index itself, "
            << "not to a reconstruction.\n";
        return 1;
    }

    const std::string properties_path = positional[0];
    const std::string features_path = positional[1];
    const std::string vertices_path = positional[2];
    const std::string output_path = positional[3];

    const std::string distance_crs =
        positional.size() >= 5 ? positional[4] : "EPSG:26918";

    SeedMode seed_mode = SeedMode::BinarySearch;
    std::string rmi_model_path;
    std::string seed_error_stats_path;
    std::vector<RmiProbe> rmi_probes;
    double uncapped_inflation_half = 0.0;
    bool verify_counts = false;
    double max_segment_length_m = DEFAULT_MAX_SEGMENT_LENGTH_METERS;
    VerificationMode verification_mode = VerificationMode::OriginalGeometry;
    // B3b gate decision (2026-07-28): the tighter disk predicate is
    // answer-identical bit-for-bit and cheaper on both phases, so it is
    // the default from B4 onward. B6 must run the whole ladder under one
    // predicate; mixing them would confound the 4-vs-3 comparison.
    Region::Kind region_kind = Region::Kind::Disk;
    std::uint32_t hilbert_order = DEFAULT_HILBERT_ORDER;

    try {
        if (positional.size() >= 6) {
            max_segment_length_m = parse_double_argument(
                positional[5], "max_segment_length_m");
        }
        if (positional.size() >= 7) {
            verification_mode = parse_verification_mode(positional[6]);
        }
        if (positional.size() >= 8) {
            region_kind = parse_region_mode(positional[7]);
        }
        if (positional.size() >= 9) {
            hilbert_order = static_cast<std::uint32_t>(
                parse_double_argument(positional[8], "hilbert_order"));
        }
        if (command_line.options.count("seed")) {
            seed_mode = parse_seed_mode(command_line.options.at("seed"));
        }
        if (command_line.options.count("uncapped-half")) {
            uncapped_inflation_half = parse_double_argument(
                command_line.options.at("uncapped-half"), "uncapped-half");
            if (uncapped_inflation_half < 0.0) {
                throw std::runtime_error("--uncapped-half must be >= 0.");
            }
        }
        if (command_line.options.count("rmi-model")) {
            rmi_model_path = command_line.options.at("rmi-model");
        }
        if (command_line.options.count("rmi-probes")) {
            rmi_probes = parse_rmi_probes(
                command_line.options.at("rmi-probes"));
        }
        if (command_line.options.count("seed-error-stats")) {
            seed_error_stats_path =
                command_line.options.at("seed-error-stats");
        }
        // Fail closed. There is no invocation of --seed rmi in this project
        // that does not have the model manifest to hand, so making the probe
        // assertion optional would only create a silent hole.
        if (seed_mode == SeedMode::Rmi) {
            if (rmi_model_path.empty()) {
                throw std::runtime_error("--seed rmi requires --rmi-model <path>.");
            }
            if (rmi_probes.empty()) {
                throw std::runtime_error(
                    "--seed rmi requires --rmi-probes: the model manifest's "
                    "probe records are how the float contract is checked "
                    "rather than inherited (Nucleus 18.20).");
            }
        } else if (!rmi_model_path.empty() || !rmi_probes.empty()) {
            throw std::runtime_error(
                "--rmi-model and --rmi-probes are only meaningful with "
                "--seed rmi.");
        }
        verify_counts = command_line.options.count("verify-counts") > 0;
    } catch (const std::exception& exception) {
        std::cerr << "Error: " << exception.what() << "\n";
        return 1;
    }

    const std::string manifest_path =
        positional.size() >= 10 ? positional[9] : "";

    if (hilbert_order < 1 || hilbert_order > 32) {
        std::cerr << "Error: hilbert_order must be in [1, 32] (2*order <= 64).\n";
        return 1;
    }

    try {
        const std::vector<PropertyPoint> properties =
            read_properties(properties_path);
        std::vector<WaterFeature> features =
            read_feature_metadata(features_path);
        const std::uint64_t vertex_count =
            read_vertices(vertices_path, features);
        const std::uint64_t segment_count = validate_geometry(features);

        SplitStatistics split_statistics;
        std::vector<SegmentLeaf> segments = build_split_segments(
            features, max_segment_length_m, split_statistics);

        const PartExteriorBounds part_exterior_bounds =
            build_part_exterior_bounds(features);

        const auto index_start = std::chrono::steady_clock::now();
        const HilbertIndex index =
            build_hilbert_index(std::move(segments), hilbert_order);
        const auto index_end = std::chrono::steady_clock::now();
        const double index_seconds =
            std::chrono::duration<double>(index_end - index_start).count();

        // L/2 uses the measured longest split segment (the tightest exact value).
        const double inflation_half = split_statistics.max_split_length_m / 2.0;
        const std::size_t key_bytes = index.keys.size() * sizeof(std::uint64_t);

        std::cout
            << "Properties: " << properties.size() << "\n"
            << "Water features: " << features.size() << "\n"
            << "Vertices: " << vertex_count << "\n"
            << "Segments (kernel count): " << segment_count << "\n"
            << "Split segments (index entries): "
            << split_statistics.split_segments << "\n"
            << "Verification mode: "
            << verification_mode_name(verification_mode) << "\n"
            << "Region mode: "
            << (region_kind == Region::Kind::Disk ? "disk" : "disk_bbox") << "\n"
            << "Seed mode: " << seed_mode_name(seed_mode)
            << " (window " << SEED_WINDOW << " entries either side)\n"
            << "Uncapped counterfactual half-length (m): "
            << uncapped_inflation_half << "\n"
            << "Count cross-check: " << (verify_counts ? "on" : "off") << "\n"
            << "Hilbert order (bits/axis): " << index.norm.order << "\n"
            << "Normalization min_x: " << std::setprecision(17)
            << index.norm.min_x << "\n"
            << "Normalization min_y: " << index.norm.min_y << "\n"
            << "Normalization scale_x (cells/m): " << index.norm.scale_x << "\n"
            << "Normalization scale_y (cells/m): " << index.norm.scale_y << "\n"
            << std::setprecision(6)
            << "Max split segment length L (m): "
            << split_statistics.max_split_length_m << "\n"
            << "Inflation half L/2 (m): " << inflation_half << "\n"
            << "Index entries: " << index.keys.size() << "\n"
            << "Key array bytes: " << key_bytes << "\n"
            << "Distinct cells at order: " << index.distinct_cells
            << " of " << index.keys.size() << "\n"
            << "Min order for distinct cells: " << index.min_order_distinct
            << "\n"
            << "Index construction seconds: " << index_seconds << "\n";

        RmiModel rmi_model;
        const RmiModel* rmi_model_pointer = nullptr;
        if (seed_mode == SeedMode::Rmi) {
            rmi_model = load_rmi_model(rmi_model_path);
            bind_rmi_model(rmi_model, index, rmi_probes);
            rmi_model_pointer = &rmi_model;
            std::cout
                << "RMI model: " << rmi_model_path << "\n"
                << "RMI second-stage models: " << rmi_model.n_leaves << "\n"
                << "RMI model bytes: "
                << (RMI_HEADER_BYTES
                    + static_cast<std::size_t>(RMI_LEAF_STRIDE_BYTES)
                    * static_cast<std::size_t>(rmi_model.n_leaves)) << "\n"
                << "RMI training-array sha256 (from the header; verified by the "
                << "trainer, not here): " << rmi_model.keys_sha256_hex << "\n"
                << "RMI probe records asserted: " << rmi_probes.size() << "\n";
        }

        if (!manifest_path.empty()) {
            const std::filesystem::path mp(manifest_path);
            if (!mp.parent_path().empty()) {
                std::filesystem::create_directories(mp.parent_path());
            }
            std::ofstream mf(manifest_path);
            mf << std::setprecision(17)
               << "{\n"
               << "  \"algorithm\": \"hilbert\",\n"
               << "  \"distance_crs\": \"" << distance_crs << "\",\n"
               << "  \"verification_mode\": \""
               << verification_mode_name(verification_mode) << "\",\n"
               << "  \"region_mode\": \""
               << (region_kind == Region::Kind::Disk ? "disk" : "disk_bbox")
               << "\",\n"
               << "  \"seed_mode\": \"" << seed_mode_name(seed_mode) << "\",\n"
               << "  \"seed_window_entries\": " << SEED_WINDOW << ",\n"
               << "  \"uncapped_inflation_half_m\": "
               << uncapped_inflation_half << ",\n"
               << "  \"count_cross_check\": "
               << (verify_counts ? "true" : "false") << ",\n"
               << "  \"max_segment_length_cap_m\": " << max_segment_length_m << ",\n"
               << "  \"max_split_segment_length_m\": "
               << split_statistics.max_split_length_m << ",\n"
               << "  \"inflation_half_m\": " << inflation_half << ",\n"
               << "  \"hilbert_order_bits_per_axis\": " << index.norm.order << ",\n"
               << "  \"normalization_min_x\": " << index.norm.min_x << ",\n"
               << "  \"normalization_min_y\": " << index.norm.min_y << ",\n"
               << "  \"normalization_scale_x_cells_per_m\": "
               << index.norm.scale_x << ",\n"
               << "  \"normalization_scale_y_cells_per_m\": "
               << index.norm.scale_y << ",\n"
               << "  \"rmi_model_leaves\": " << rmi_model.n_leaves << ",\n"
               << "  \"rmi_probes_asserted\": " << rmi_probes.size() << ",\n"
               << "  \"rmi_training_array_sha256\": \""
               << rmi_model.keys_sha256_hex << "\",\n"
               << "  \"index_entries\": " << index.keys.size() << ",\n"
               << "  \"key_array_bytes\": " << key_bytes << ",\n"
               << "  \"distinct_cells_at_order\": " << index.distinct_cells << ",\n"
               << "  \"min_order_for_distinct_cells\": "
               << index.min_order_distinct << "\n"
               << "}\n";
        }

        // B4: export the sorted key array the RMI trains on.
        //
        // This is an export of an artifact already in memory, not a move
        // of functionality into C++: it is off the query path and costs
        // nothing unless requested. It exists because the alternative --
        // rebuilding the split, the normalization and the Hilbert
        // transform in Python -- would duplicate this file's logic, could
        // differ from it by a floating-point ULP in the segment split with
        // no way to detect which case you were in, and would yield a
        // training-array checksum attesting to what Python built rather
        // than to what the index holds (Nucleus 18.10, 18.20).
        //
        // Raw little-endian uint64, no header: std::uint64_t is fixed
        // width and every platform this project measures on is
        // little-endian x86-64. A big-endian build would need a byte swap.
        if (command_line.options.count("dump-keys")) {
            const std::string keys_path =
                command_line.options.at("dump-keys");
            const std::filesystem::path keys_fspath(keys_path);
            if (!keys_fspath.parent_path().empty()) {
                std::filesystem::create_directories(
                    keys_fspath.parent_path());
            }
            std::ofstream key_file(keys_path, std::ios::binary);
            if (!key_file) {
                throw std::runtime_error(
                    "Could not open key dump: " + keys_path);
            }
            const std::streamsize key_dump_bytes =
                static_cast<std::streamsize>(
                    index.keys.size() * sizeof(std::uint64_t));
            key_file.write(
                reinterpret_cast<const char*>(index.keys.data()),
                key_dump_bytes);
            key_file.flush();
            if (!key_file) {
                throw std::runtime_error(
                    "Key dump write failed: " + keys_path);
            }
            std::cout << "Key dump: " << keys_path << " ("
                      << key_dump_bytes << " bytes, "
                      << index.keys.size() << " entries)\n";
        }

        write_hilbert_results(
            output_path, properties, features, index, part_exterior_bounds,
            inflation_half, region_kind, distance_crs, verification_mode,
            DEFAULT_TIE_TOLERANCE_METERS, seed_mode, rmi_model_pointer,
            uncapped_inflation_half, verify_counts, seed_error_stats_path);

        std::cout << "Wrote Hilbert C++ output to " << output_path << "\n";
    } catch (const std::exception& exception) {
        std::cerr << "Error: " << exception.what() << "\n";
        return 1;
    }
    return 0;
}