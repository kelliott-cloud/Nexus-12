"""NAVC unit and integration tests."""
import numpy as np
import pytest


class TestRotation:
    def test_deterministic(self):
        from turboquant.rotation import generate_rotation_matrix
        Q1 = generate_rotation_matrix(128, seed=42)
        Q2 = generate_rotation_matrix(128, seed=42)
        np.testing.assert_array_equal(Q1, Q2)

    def test_orthogonal(self):
        from turboquant.rotation import generate_rotation_matrix
        Q = generate_rotation_matrix(64, seed=7)
        I = Q @ Q.T
        np.testing.assert_allclose(I, np.eye(64), atol=1e-5)

    def test_inner_product_preserved(self):
        from turboquant.rotation import generate_rotation_matrix, rotate_vectors
        Q = generate_rotation_matrix(32, seed=0)
        vecs = np.random.randn(10, 32).astype(np.float32)
        rotated = rotate_vectors(vecs, Q)
        ip_orig = vecs[0] @ vecs[1]
        ip_rot = rotated[0] @ rotated[1]
        np.testing.assert_allclose(ip_orig, ip_rot, atol=1e-4)


class TestQuantization:
    def test_roundtrip_shape(self):
        from turboquant.polar_quant import quantize, dequantize
        vecs = np.random.randn(100, 64).astype(np.float32)
        qr = quantize(vecs, bit_width=4)
        recon = dequantize(qr)
        assert recon.shape == vecs.shape

    def test_compression_ratio(self):
        from turboquant.polar_quant import quantize
        vecs = np.random.randn(1000, 768).astype(np.float32)
        qr = quantize(vecs, bit_width=4)
        assert qr.compression_ratio > 5.0

    def test_distortion_decreases_with_bits(self):
        from turboquant.polar_quant import quantize, dequantize, compute_distortion
        vecs = np.random.randn(200, 128).astype(np.float32)
        mse_2 = compute_distortion(vecs, dequantize(quantize(vecs, 2)))["mse"]
        mse_4 = compute_distortion(vecs, dequantize(quantize(vecs, 4)))["mse"]
        mse_8 = compute_distortion(vecs, dequantize(quantize(vecs, 8)))["mse"]
        assert mse_2 > mse_4 > mse_8


class TestQJL:
    def test_sketch_shape(self):
        from turboquant.qjl import compute_qjl_sketch
        residuals = np.random.randn(50, 64).astype(np.float32)
        sketch = compute_qjl_sketch(residuals, n_projections=64)
        assert sketch["signs"].shape == (50, 64)
        assert sketch["memory_bytes"] > 0


class TestScoring:
    def test_passing_run(self):
        from turboquant.scoring import evaluate_promotion
        metrics = {"gates": {"quality_pass": True, "memory_pass": True,
                             "recall_pass": True, "all_pass": True},
                   "memory": {"memory_reduction_pct": 75},
                   "distortion": {"mse": 0.001}, "recall_at_10": 0.98}
        result = evaluate_promotion(metrics, {})
        assert result["eligible"] is True
        assert result["score"] > 0.5

    def test_failing_run(self):
        from turboquant.scoring import evaluate_promotion
        metrics = {"gates": {"quality_pass": False, "memory_pass": True,
                             "recall_pass": True, "all_pass": False},
                   "memory": {"memory_reduction_pct": 75},
                   "distortion": {"mse": 0.5}}
        result = evaluate_promotion(metrics, {})
        assert result["eligible"] is False


class TestKVRunner:
    def test_synthetic_trace_shape(self):
        from turboquant.kv_runner import generate_synthetic_kv_trace, MODEL_CONFIGS
        cfg = MODEL_CONFIGS["custom"]
        trace = generate_synthetic_kv_trace(cfg, seed=42)
        assert trace["keys"].shape == (cfg["layers"], cfg["heads"], cfg["seq_len"], cfg["head_dim"])
        assert trace["values"].shape == trace["keys"].shape

    def test_synthetic_deterministic(self):
        from turboquant.kv_runner import generate_synthetic_kv_trace, MODEL_CONFIGS
        cfg = MODEL_CONFIGS["custom"]
        t1 = generate_synthetic_kv_trace(cfg, seed=42)
        t2 = generate_synthetic_kv_trace(cfg, seed=42)
        np.testing.assert_array_equal(t1["keys"], t2["keys"])

    def test_attention_distortion(self):
        from turboquant.kv_runner import compute_attention_distortion
        keys = np.random.randn(64, 32).astype(np.float32)
        values = np.random.randn(64, 32).astype(np.float32)
        result = compute_attention_distortion(keys, keys, values, values, n_queries=10)
        # Perfect reconstruction → cosine should be ~1.0
        assert result["output_cosine_similarity"] > 0.99

    def test_attention_distortion_degraded(self):
        from turboquant.kv_runner import compute_attention_distortion
        keys = np.random.randn(64, 32).astype(np.float32)
        values = np.random.randn(64, 32).astype(np.float32)
        noisy_keys = keys + np.random.randn(*keys.shape).astype(np.float32) * 0.5
        result = compute_attention_distortion(keys, noisy_keys, values, values, n_queries=10)
        # With noise, cosine should drop
        assert result["output_cosine_similarity"] < 0.99

    def test_model_configs_exist(self):
        from turboquant.kv_runner import MODEL_CONFIGS
        assert "llama-3-8b" in MODEL_CONFIGS
        assert "custom" in MODEL_CONFIGS
        for name, cfg in MODEL_CONFIGS.items():
            assert "layers" in cfg
            assert "heads" in cfg
            assert "head_dim" in cfg
            assert "seq_len" in cfg
