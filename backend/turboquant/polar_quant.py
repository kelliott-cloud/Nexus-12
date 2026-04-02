"""Primary quantization — PolarQuant-style uniform scalar quantization.
Operates on rotated vectors. Supports configurable bit-widths (1-8 bits).
Online/data-oblivious: no codebook training required.
"""
import numpy as np
from dataclasses import dataclass


@dataclass
class QuantizedResult:
    codes: np.ndarray
    scale: np.ndarray
    offset: np.ndarray
    bit_width: int
    original_shape: tuple

    @property
    def memory_bytes(self) -> int:
        N, dim = self.original_shape
        code_bits = N * dim * self.bit_width
        meta_bytes = N * 8
        return (code_bits + 7) // 8 + meta_bytes

    @property
    def compression_ratio(self) -> float:
        original = self.original_shape[0] * self.original_shape[1] * 4
        return original / max(self.memory_bytes, 1)


def quantize(vectors: np.ndarray, bit_width: int = 4) -> QuantizedResult:
    n_levels = (1 << bit_width) - 1
    v_min = vectors.min(axis=1, keepdims=True)
    v_max = vectors.max(axis=1, keepdims=True)
    v_range = v_max - v_min
    v_range = np.where(v_range < 1e-8, 1e-8, v_range)
    normalized = (vectors - v_min) / v_range * n_levels
    codes = np.clip(np.round(normalized), 0, n_levels).astype(np.uint8)
    scale = (v_range / n_levels).squeeze(axis=1).astype(np.float32)
    offset = v_min.squeeze(axis=1).astype(np.float32)
    return QuantizedResult(codes=codes, scale=scale, offset=offset, bit_width=bit_width, original_shape=vectors.shape)


def dequantize(qr: QuantizedResult) -> np.ndarray:
    return qr.codes.astype(np.float32) * qr.scale[:, np.newaxis] + qr.offset[:, np.newaxis]


def compute_distortion(original: np.ndarray, reconstructed: np.ndarray) -> dict:
    diff = original - reconstructed
    mse = float(np.mean(diff ** 2))
    signal_power = float(np.mean(original ** 2))
    snr_db = float(10 * np.log10(signal_power / max(mse, 1e-12)))
    max_error = float(np.max(np.abs(diff)))
    N = original.shape[0]
    if N >= 2:
        rng = np.random.RandomState(0)
        n_pairs = min(100, N * (N - 1) // 2)
        idx_a = rng.randint(0, N, n_pairs)
        idx_b = rng.randint(0, N, n_pairs)
        ip_orig = np.sum(original[idx_a] * original[idx_b], axis=1)
        ip_recon = np.sum(reconstructed[idx_a] * reconstructed[idx_b], axis=1)
        ip_error = float(np.mean(np.abs(ip_orig - ip_recon)))
    else:
        ip_error = 0.0
    return {"mse": mse, "snr_db": snr_db, "max_error": max_error, "ip_error": ip_error}
