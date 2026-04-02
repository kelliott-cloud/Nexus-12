"""Deterministic random rotation for high-dimensional vectors.
Uses a seeded orthogonal matrix (QR decomposition of random Gaussian)
to distribute vector energy uniformly across dimensions before quantization.
"""
import numpy as np


def generate_rotation_matrix(dim: int, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    G = rng.randn(dim, dim).astype(np.float32)
    Q, R = np.linalg.qr(G)
    signs = np.sign(np.diag(R))
    signs[signs == 0] = 1
    Q = Q * signs[np.newaxis, :]
    return Q


def rotate_vectors(vectors: np.ndarray, Q: np.ndarray) -> np.ndarray:
    return vectors @ Q.T


def unrotate_vectors(rotated: np.ndarray, Q: np.ndarray) -> np.ndarray:
    return rotated @ Q
