#include "search_native.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <new>
#include <queue>
#include <utility>
#include <vector>

namespace {

constexpr uint32_t kUnset = std::numeric_limits<uint32_t>::max();

struct State {
    std::vector<uint32_t> parent;
    std::vector<double> cost;
    TN_SearchStats stats{};
};

bool valid_csr(uint32_t node_count, uint64_t edge_count, const uint64_t* offsets,
               const uint32_t* targets, const double* costs, uint32_t start, uint32_t goal) {
    if (node_count == 0 || offsets == nullptr || start >= node_count || goal >= node_count) {
        return false;
    }
    if (edge_count > 0 && (targets == nullptr || costs == nullptr)) {
        return false;
    }
    if (offsets[0] != 0 || offsets[node_count] != edge_count) {
        return false;
    }
    for (uint32_t i = 0; i < node_count; ++i) {
        if (offsets[i] > offsets[i + 1] || offsets[i + 1] > edge_count) {
            return false;
        }
    }
    for (uint64_t i = 0; i < edge_count; ++i) {
        if (targets[i] >= node_count || !std::isfinite(costs[i]) || costs[i] < 0.0) {
            return false;
        }
    }
    return true;
}

bool valid_heuristics(uint32_t node_count, const double* heuristics) {
    if (heuristics == nullptr) {
        return false;
    }
    for (uint32_t i = 0; i < node_count; ++i) {
        if (!std::isfinite(heuristics[i]) || heuristics[i] < 0.0) {
            return false;
        }
    }
    return true;
}

int32_t finish(uint32_t goal, const State& state, uint32_t* path_out,
               uint32_t path_capacity, TN_SearchResult* result) {
    std::vector<uint32_t> reverse_path;
    uint32_t current = goal;
    while (current != kUnset) {
        reverse_path.push_back(current);
        if (reverse_path.size() > state.parent.size()) {
            return TN_SEARCH_INTERNAL_ERROR;
        }
        current = state.parent[current];
    }
    result->found = 1;
    result->path_length = static_cast<uint32_t>(reverse_path.size());
    result->stats = state.stats;
    result->stats.path_cost = state.cost[goal];
    if (result->path_length > path_capacity || path_out == nullptr) {
        return TN_SEARCH_PATH_BUFFER_TOO_SMALL;
    }
    std::reverse_copy(reverse_path.begin(), reverse_path.end(), path_out);
    return TN_SEARCH_OK;
}

int32_t trivial(uint32_t start, uint32_t* path_out, uint32_t path_capacity,
                TN_SearchResult* result) {
    result->found = 1;
    result->path_length = 1;
    result->stats = TN_SearchStats{0, 0, 1, 0.0};
    if (path_capacity < 1 || path_out == nullptr) {
        return TN_SEARCH_PATH_BUFFER_TOO_SMALL;
    }
    path_out[0] = start;
    return TN_SEARCH_OK;
}

int32_t uninformed(bool depth_first, uint32_t node_count, const uint64_t* offsets,
                   const uint32_t* targets, const double* costs, uint32_t start,
                   uint32_t goal, uint32_t* path_out, uint32_t path_capacity,
                   TN_SearchResult* result) {
    State state{std::vector<uint32_t>(node_count, kUnset),
                std::vector<double>(node_count, 0.0), TN_SearchStats{0, 0, 1, 0.0}};
    state.parent[start] = kUnset;
    std::vector<uint32_t> frontier{start};
    std::size_t queue_head = 0;

    while ((depth_first && !frontier.empty()) || (!depth_first && queue_head < frontier.size())) {
        uint32_t current;
        if (depth_first) {
            current = frontier.back();
            frontier.pop_back();
        } else {
            current = frontier[queue_head++];
        }
        ++state.stats.expanded;
        const uint64_t begin = offsets[current];
        const uint64_t end = offsets[current + 1];
        for (uint64_t step = 0; step < end - begin; ++step) {
            const uint64_t edge = depth_first ? end - 1 - step : begin + step;
            const uint32_t neighbor = targets[edge];
            if (neighbor == start || state.parent[neighbor] != kUnset) {
                continue;
            }
            state.parent[neighbor] = current;
            state.cost[neighbor] = state.cost[current] + costs[edge];
            ++state.stats.generated;
            if (neighbor == goal) {
                return finish(goal, state, path_out, path_capacity, result);
            }
            frontier.push_back(neighbor);
            const uint64_t frontier_size = depth_first
                ? static_cast<uint64_t>(frontier.size())
                : static_cast<uint64_t>(frontier.size() - queue_head);
            state.stats.frontier_peak = std::max(state.stats.frontier_peak, frontier_size);
        }
    }
    result->stats = state.stats;
    return TN_SEARCH_OK;
}

struct HeapEntry {
    double priority;
    uint64_t serial;
    uint32_t node;
};

struct Later {
    bool operator()(const HeapEntry& a, const HeapEntry& b) const {
        if (a.priority != b.priority) {
            return a.priority > b.priority;
        }
        return a.serial > b.serial;
    }
};

int32_t astar(uint32_t node_count, const uint64_t* offsets, const uint32_t* targets,
              const double* costs, const double* heuristics, uint32_t start, uint32_t goal,
              uint32_t* path_out, uint32_t path_capacity, TN_SearchResult* result) {
    if (heuristics == nullptr) {
        return TN_SEARCH_INVALID_ARGUMENT;
    }
    State state{std::vector<uint32_t>(node_count, kUnset),
                std::vector<double>(node_count, std::numeric_limits<double>::infinity()),
                TN_SearchStats{0, 0, 1, 0.0}};
    std::vector<uint8_t> closed(node_count, 0);
    state.cost[start] = 0.0;
    uint64_t serial = 0;
    std::priority_queue<HeapEntry, std::vector<HeapEntry>, Later> frontier;
    frontier.push(HeapEntry{heuristics[start], serial++, start});

    while (!frontier.empty()) {
        const HeapEntry entry = frontier.top();
        frontier.pop();
        const uint32_t current = entry.node;
        if (closed[current]) {
            continue;
        }
        closed[current] = 1;
        ++state.stats.expanded;
        if (current == goal) {
            return finish(goal, state, path_out, path_capacity, result);
        }
        for (uint64_t edge = offsets[current]; edge < offsets[current + 1]; ++edge) {
            const uint32_t neighbor = targets[edge];
            const double candidate = state.cost[current] + costs[edge];
            if (candidate >= state.cost[neighbor]) {
                continue;
            }
            state.parent[neighbor] = current;
            state.cost[neighbor] = candidate;
            ++state.stats.generated;
            frontier.push(HeapEntry{candidate + heuristics[neighbor], serial++, neighbor});
            state.stats.frontier_peak = std::max(
                state.stats.frontier_peak, static_cast<uint64_t>(frontier.size()));
        }
    }
    result->stats = state.stats;
    return TN_SEARCH_OK;
}

}  // namespace

extern "C" {

uint32_t tn_search_abi_version(void) {
    return TN_SEARCH_ABI_VERSION;
}

const char* tn_search_backend_info(void) {
#if defined(_MSC_VER)
    return "twinpath-search/1 csr-c++17 msvc";
#elif defined(__clang__)
    return "twinpath-search/1 csr-c++17 clang";
#elif defined(__GNUC__)
    return "twinpath-search/1 csr-c++17 gcc";
#else
    return "twinpath-search/1 csr-c++17 unknown-compiler";
#endif
}

int32_t tn_search_csr(uint32_t algorithm, uint32_t node_count, uint64_t edge_count,
                      const uint64_t* offsets, const uint32_t* targets, const double* costs,
                      const double* heuristics, uint32_t start, uint32_t goal,
                      uint32_t* path_out, uint32_t path_capacity, TN_SearchResult* result_out) {
    if (result_out == nullptr) {
        return TN_SEARCH_INVALID_ARGUMENT;
    }
    *result_out = TN_SearchResult{};
    if (!valid_csr(node_count, edge_count, offsets, targets, costs, start, goal)) {
        return TN_SEARCH_INVALID_ARGUMENT;
    }
    try {
        if (start == goal) {
            return trivial(start, path_out, path_capacity, result_out);
        }
        if (algorithm == TN_SEARCH_BFS) {
            return uninformed(false, node_count, offsets, targets, costs, start, goal,
                              path_out, path_capacity, result_out);
        }
        if (algorithm == TN_SEARCH_DFS) {
            return uninformed(true, node_count, offsets, targets, costs, start, goal,
                              path_out, path_capacity, result_out);
        }
        if (algorithm == TN_SEARCH_ASTAR) {
            if (!valid_heuristics(node_count, heuristics)) {
                return TN_SEARCH_INVALID_ARGUMENT;
            }
            return astar(node_count, offsets, targets, costs, heuristics, start, goal,
                         path_out, path_capacity, result_out);
        }
        return TN_SEARCH_INVALID_ARGUMENT;
    } catch (const std::bad_alloc&) {
        return TN_SEARCH_INTERNAL_ERROR;
    } catch (...) {
        return TN_SEARCH_INTERNAL_ERROR;
    }
}

int32_t tn_search_self_test(void) {
    const uint64_t offsets[] = {0, 2, 3, 4, 4};
    const uint32_t targets[] = {1, 2, 3, 3};
    const double costs[] = {5.0, 1.0, 5.0, 1.0};
    const double heuristics[] = {0.0, 0.0, 0.0, 0.0};
    uint32_t path[4] = {};
    TN_SearchResult result{};
    const int32_t status = tn_search_csr(TN_SEARCH_BFS, 4, 4, offsets, targets, costs,
                                         heuristics, 0, 3, path, 4, &result);
    return status == TN_SEARCH_OK && result.found == 1 && result.path_length == 3 &&
           path[0] == 0 && path[1] == 1 && path[2] == 3 && result.stats.expanded == 2 &&
           result.stats.generated == 3 && result.stats.frontier_peak == 2 &&
           result.stats.path_cost == 10.0;
}

}  // extern "C"
