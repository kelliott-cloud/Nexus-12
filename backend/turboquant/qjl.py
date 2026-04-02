"""QJL Residual Correction — 1-bit sketch to remove inner-product bias.
After primary quantization, the residual may have systematic inner-product bias.
QJL projects the residual into a random subspace and stores 1-bit signs.
"""
import numpy as np


def compute_qjl_sketch(residuals: np.ndarray, n_projections: int = 128, seed: int = 7) -> dict:
    N, dim = residuals.shape
    rng = np.random.RandomState(seed)
    P = rng.randn(dim, n_projections).astype(np.float32) / np.sqrt(n_projections)
    projected = residuals @ P
    signs = projected >= 0
    scale = float(np.sqrt(np.mean(residuals ** 2)))
    memory_bytes = (N * n_projections + 7) // 8
    return {
        "signs": signs,
        "projection_seed": seed,
        "n_projections": n_projections,
        "scale": scale,
        "memory_bytes": memory_bytes,
    }


def correct_inner_product(ip_estimate: float, sketch_a: dict, sketch_b: dict, idx_a: int, idx_b: int) -> float:
    signs_a = sketch_a["signs"][idx_a]
    signs_b = sketch_b["signs"][idx_b]
    agreement = np.mean(signs_a == signs_b)
    correction = sketch_a["scale"] * sketch_b["scale"] * (2 * agreement - 1)
    return ip_estimate + correction
