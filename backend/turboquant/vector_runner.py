"""Vector-index compression runner — benchmarks NAVC on embeddings."""
import numpy as np
import time
import logging
from .rotation import generate_rotation_matrix, rotate_vectors, unrotate_vectors
from .polar_quant import quantize, dequantize, compute_distortion
from .qjl import compute_qjl_sketch

logger = logging.getLogger(__name__)


async def run_vector_benchmark(db, profile: dict, dataset_vectors: np.ndarray,
                                query_vectors: np.ndarray = None,
                                ground_truth_neighbors: np.ndarray = None) -> dict:
    t0 = time.time()
    N, dim = dataset_vectors.shape
    bit_width = profile.get("bit_width", 4)
    seed = profile.get("rotation_seed", 42)
    enable_residual = profile.get("enable_residual", True)
    thresholds = profile.get("thresholds", {})

    logger.info(f"NAVC vector benchmark: N={N}, dim={dim}, bits={bit_width}")

    t_rot = time.time()
    Q = generate_rotation_matrix(dim, seed)
    rotated = rotate_vectors(dataset_vectors, Q)
    rotation_ms = (time.time() - t_rot) * 1000

    t_quant = time.time()
    qr = quantize(rotated, bit_width)
    reconstructed_rotated = dequantize(qr)
    quantize_ms = (time.time() - t_quant) * 1000

    reconstructed = unrotate_vectors(reconstructed_rotated, Q)
    distortion = compute_distortion(dataset_vectors, reconstructed)

    qjl_meta = None
    if enable_residual:
        residuals = rotated - reconstructed_rotated
        qjl_meta = compute_qjl_sketch(residuals, n_projections=128, seed=seed + 1000)
        qjl_meta.pop("signs", None)

    original_bytes = N * dim * 4
    compressed_bytes = qr.memory_bytes + (qjl_meta["memory_bytes"] if qjl_meta else 0)
    memory_reduction = 1.0 - (compressed_bytes / original_bytes)

    recall_at_10 = None
    query_latency_ms = None
    if query_vectors is not None and ground_truth_neighbors is not None:
        t_q = time.time()
        Q_q = rotate_vectors(query_vectors, Q)
        sims = reconstructed_rotated @ Q_q.T
        top_k = np.argsort(-sims, axis=0)[:10, :].T
        query_latency_ms = (time.time() - t_q) * 1000 / query_vectors.shape[0]
        hits = 0
        total = 0
        for i in range(min(query_vectors.shape[0], ground_truth_neighbors.shape[0])):
            gt_set = set(ground_truth_neighbors[i].tolist())
            pred_set = set(top_k[i].tolist())
            hits += len(gt_set & pred_set)
            total += len(gt_set)
        recall_at_10 = hits / max(total, 1)

    total_ms = (time.time() - t0) * 1000

    gates = {
        "quality_pass": distortion["mse"] <= thresholds.get("max_quality_delta", 0.02),
        "memory_pass": memory_reduction >= thresholds.get("min_memory_reduction", 0.30),
        "recall_pass": recall_at_10 is None or recall_at_10 >= thresholds.get("min_recall_at_10", 0.90),
        "all_pass": False,
    }
    gates["all_pass"] = all([gates["quality_pass"], gates["memory_pass"], gates["recall_pass"]])

    return {
        "distortion": distortion,
        "memory": {
            "original_bytes": original_bytes,
            "compressed_bytes": compressed_bytes,
            "compression_ratio": round(qr.compression_ratio, 2),
            "memory_reduction_pct": round(memory_reduction * 100, 1),
        },
        "timing": {
            "rotation_ms": round(rotation_ms, 1),
            "quantize_ms": round(quantize_ms, 1),
            "total_ms": round(total_ms, 1),
            "query_latency_ms": round(query_latency_ms, 2) if query_latency_ms else None,
        },
        "recall_at_10": round(recall_at_10, 4) if recall_at_10 is not None else None,
        "qjl_residual": {"enabled": enable_residual, "memory_bytes": qjl_meta["memory_bytes"] if qjl_meta else 0},
        "gates": gates,
        "config": {"bit_width": bit_width, "seed": seed, "dim": dim, "n_vectors": N},
    }
