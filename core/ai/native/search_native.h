#ifndef TWINPATH_SEARCH_NATIVE_H
#define TWINPATH_SEARCH_NATIVE_H

#include <stdint.h>

#if defined(_WIN32)
#define TN_EXPORT __declspec(dllexport)
#else
#define TN_EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define TN_SEARCH_ABI_VERSION 1u

enum TN_SearchAlgorithm {
    TN_SEARCH_BFS = 1,
    TN_SEARCH_DFS = 2,
    TN_SEARCH_ASTAR = 3
};

enum TN_SearchStatus {
    TN_SEARCH_OK = 0,
    TN_SEARCH_INVALID_ARGUMENT = 1,
    TN_SEARCH_PATH_BUFFER_TOO_SMALL = 2,
    TN_SEARCH_INTERNAL_ERROR = 3
};

typedef struct TN_SearchStats {
    uint64_t expanded;
    uint64_t generated;
    uint64_t frontier_peak;
    double path_cost;
} TN_SearchStats;

typedef struct TN_SearchResult {
    uint32_t found;
    uint32_t path_length;
    TN_SearchStats stats;
} TN_SearchResult;

TN_EXPORT uint32_t tn_search_abi_version(void);
TN_EXPORT const char *tn_search_backend_info(void);
TN_EXPORT int32_t tn_search_self_test(void);

TN_EXPORT int32_t tn_search_csr(
    uint32_t algorithm,
    uint32_t node_count,
    uint64_t edge_count,
    const uint64_t *offsets,
    const uint32_t *targets,
    const double *costs,
    const double *heuristics,
    uint32_t start,
    uint32_t goal,
    uint32_t *path_out,
    uint32_t path_capacity,
    TN_SearchResult *result_out
);

#ifdef __cplusplus
}
#endif

#endif
