"""KV-Cache compression runner — benchmarks NAVC on key-value cache tensors.

Simulates KV-cache compression by generating synthetic replay traces that mimic
the structure of transformer key/value tensors (num_layers × num_heads × seq_len × head_dim).
Applies rotation + quantization + optional QJL per-layer and per-head, measuring
reconstruction quality, memory savings, and attention score distortion.
"""
import numpy as np
import time
import logging
from .rotation import generate_rotation_matrix, rotate_vectors, unrotate_vectors
from .polar_quant import quantize, dequantize, compute_distortion
from .qjl import compute_qjl_sketch

logger = logging.getLogger(__name__)

# Common model configurations for synthetic trace generation
MODEL_CONFIGS = {
    "llama-3-8b": {"layers": 32, "heads": 32, "head_dim": 128, "seq_len": 512},
    "llama-3-70b": {"layers": 80, "heads": 64, "head_dim": 128, "seq_len": 512},
    "mistral-7b": {"layers": 32, "heads": 32, "head_dim": 128, "seq_len": 1024},
    "gpt2-small": {"layers": 12, "heads": 12, "head_dim": 64, "seq_len": 256},
    "custom": {"layers": 8, "heads": 8, "head_dim": 64, "seq_len": 128},
}


def generate_synthetic_kv_trace(config: dict, seed: int = 42) -> dict:
    """Generate synthetic KV-cache tensors mimicking transformer attention patterns.

    Returns dict with:
        keys: (layers, heads, seq_len, head_dim) float32
        values: (layers, heads, seq_len, head_dim) float32
    """
    rng = np.random.RandomState(seed)
    layers = config["layers"]
    heads = config["heads"]
    head_dim = config["head_dim"]
    seq_len = config["seq_len"]

    # Simulate layer-wise variance decay (deeper layers have smaller magnitudes)
    layer_scales = np.linspace(1.0, 0.5, layers).astype(np.float32)

    keys = np.zeros((layers, heads, seq_len, head_dim), dtype=np.float32)
    values = np.zeros((layers, heads, seq_len, head_dim), dtype=np.float32)

    for l in range(layers):
        scale = layer_scales[l]
        for h in range(heads):
            # Keys: structured with positional patterns
            keys[l, h] = rng.randn(seq_len, head_dim).astype(np.float32) * scale
            # Values: slightly different distribution
            values[l, h] = rng.randn(seq_len, head_dim).astype(np.float32) * scale * 0.8

    return {"keys": keys, "values": values, "config": config}


def compute_attention_distortion(orig_keys: np.ndarray, recon_keys: np.ndarray,
                                  orig_values: np.ndarray, recon_values: np.ndarray,
                                  n_queries: int = 50, seed: int = 0) -> dict:
    """Measure how quantization affects attention output quality.

    Simulates random queries against original and reconstructed KV-cache,
    compares attention weights and output vectors.
    """
    rng = np.random.RandomState(seed)
    seq_len, head_dim = orig_keys.shape

    # Random query vectors
    queries = rng.randn(n_queries, head_dim).astype(np.float32) * 0.5

    # Attention scores: softmax(Q @ K.T / sqrt(d))
    scale = 1.0 / np.sqrt(head_dim)

    orig_scores = queries @ orig_keys.T * scale
    recon_scores = queries @ recon_keys.T * scale

    # Softmax
    def softmax(x):
        e = np.exp(x - x.max(axis=-1, keepdims=True))
        return e / e.sum(axis=-1, keepdims=True)

    orig_attn = softmax(orig_scores)
    recon_attn = softmax(recon_scores)

    # Attention weight distortion
    attn_mse = float(np.mean((orig_attn - recon_attn) ** 2))
    attn_kl = float(np.mean(np.sum(orig_attn * np.log(np.clip(orig_attn, 1e-10, 1) / np.clip(recon_attn, 1e-10, 1)), axis=-1)))

    # Output distortion: attn @ V
    orig_output = orig_attn @ orig_values
    recon_output = recon_attn @ recon_values
    output_mse = float(np.mean((orig_output - recon_output) ** 2))
    output_cosine = float(np.mean([
        np.dot(orig_output[i], recon_output[i]) / (np.linalg.norm(orig_output[i]) * np.linalg.norm(recon_output[i]) + 1e-10)
        for i in range(n_queries)
    ]))

    return {
        "attention_mse": attn_mse,
        "attention_kl_div": attn_kl,
        "output_mse": output_mse,
        "output_cosine_similarity": round(output_cosine, 6),
    }


async def run_kv_benchmark(db, profile: dict, dataset: dict = None,
                            model_name: str = "custom") -> dict:
    """Execute NAVC pipeline on KV-cache tensors and measure quality.

    Args:
        db: MongoDB handle
        profile: Profile dict with bit_width, rotation_seed, enable_residual, thresholds,
                 and optional kv_config (layer_range, head_range, per_layer_bits)
        dataset: Pre-loaded dataset dict with keys/values tensors, or None for synthetic
        model_name: Model config key for synthetic generation
    """
    t0 = time.time()
    bit_width = profile.get("bit_width", 4)
    seed = profile.get("rotation_seed", 42)
    enable_residual = profile.get("enable_residual", True)
    thresholds = profile.get("thresholds", {})
    kv_config = profile.get("kv_config") or {}

    # Load or generate KV tensors
    if dataset and "keys" in dataset:
        kv_data = dataset
    else:
        model_cfg = dict(MODEL_CONFIGS.get(model_name, MODEL_CONFIGS["custom"]))
        # Apply overrides from kv_config
        if kv_config.get("layers"):
            model_cfg["layers"] = min(kv_config["layers"], model_cfg["layers"])
        if kv_config.get("seq_len"):
            model_cfg["seq_len"] = kv_config["seq_len"]
        kv_data = generate_synthetic_kv_trace(model_cfg, seed)

    keys = kv_data["keys"]
    values = kv_data["values"]
    config = kv_data.get("config", MODEL_CONFIGS["custom"])
    n_layers, n_heads, seq_len, head_dim = keys.shape

    logger.info(f"NAVC KV benchmark: layers={n_layers}, heads={n_heads}, seq={seq_len}, dim={head_dim}, bits={bit_width}")

    # Determine which layers/heads to compress (handle None values from Pydantic)
    layer_range = kv_config.get("layer_range") or list(range(n_layers))
    head_range = kv_config.get("head_range") or list(range(n_heads))
    per_layer_bits = kv_config.get("per_layer_bits") or {}

    # Run compression per-layer, per-head
    total_original_bytes = 0
    total_compressed_bytes = 0
    layer_metrics = []
    all_key_distortions = []
    all_value_distortions = []
    all_attention_distortions = []

    t_compress = time.time()

    for l in (layer_range if isinstance(layer_range, list) else list(range(n_layers))):
        if l >= n_layers:
            continue
        layer_bit = per_layer_bits.get(str(l), bit_width)
        layer_key_mse = []
        layer_val_mse = []

        for h in (head_range if isinstance(head_range, list) else list(range(n_heads))):
            if h >= n_heads:
                continue

            orig_k = keys[l, h]  # (seq_len, head_dim)
            orig_v = values[l, h]

            # Stage 1: Rotation
            Q = generate_rotation_matrix(head_dim, seed + l * 1000 + h)
            rot_k = rotate_vectors(orig_k, Q)
            rot_v = rotate_vectors(orig_v, Q)

            # Stage 2: Quantization
            qr_k = quantize(rot_k, layer_bit)
            qr_v = quantize(rot_v, layer_bit)
            recon_rot_k = dequantize(qr_k)
            recon_rot_v = dequantize(qr_v)

            # Unrotate
            recon_k = unrotate_vectors(recon_rot_k, Q)
            recon_v = unrotate_vectors(recon_rot_v, Q)

            # Distortion
            k_dist = compute_distortion(orig_k, recon_k)
            v_dist = compute_distortion(orig_v, recon_v)
            layer_key_mse.append(k_dist["mse"])
            layer_val_mse.append(v_dist["mse"])
            all_key_distortions.append(k_dist)
            all_value_distortions.append(v_dist)

            # Attention distortion (sample)
            if h < 4:  # Only check first 4 heads for speed
                attn_dist = compute_attention_distortion(orig_k, recon_k, orig_v, recon_v, n_queries=20)
                all_attention_distortions.append(attn_dist)

            # Memory accounting
            orig_bytes = seq_len * head_dim * 4 * 2  # keys + values, float32
            comp_bytes = (qr_k.memory_bytes + qr_v.memory_bytes)
            if enable_residual:
                res_k = rot_k - recon_rot_k
                res_v = rot_v - recon_rot_v
                sketch_k = compute_qjl_sketch(res_k, n_projections=64, seed=seed + l * 100 + h + 5000)
                sketch_v = compute_qjl_sketch(res_v, n_projections=64, seed=seed + l * 100 + h + 6000)
                comp_bytes += sketch_k["memory_bytes"] + sketch_v["memory_bytes"]

            total_original_bytes += orig_bytes
            total_compressed_bytes += comp_bytes

        layer_metrics.append({
            "layer": l,
            "bit_width": layer_bit,
            "avg_key_mse": float(np.mean(layer_key_mse)) if layer_key_mse else 0,
            "avg_value_mse": float(np.mean(layer_val_mse)) if layer_val_mse else 0,
        })

    compress_ms = (time.time() - t_compress) * 1000

    # Aggregate metrics
    avg_key_mse = float(np.mean([d["mse"] for d in all_key_distortions])) if all_key_distortions else 0
    avg_value_mse = float(np.mean([d["mse"] for d in all_value_distortions])) if all_value_distortions else 0
    avg_key_snr = float(np.mean([d["snr_db"] for d in all_key_distortions])) if all_key_distortions else 0
    avg_value_snr = float(np.mean([d["snr_db"] for d in all_value_distortions])) if all_value_distortions else 0

    memory_reduction = 1.0 - (total_compressed_bytes / max(total_original_bytes, 1))
    compression_ratio = total_original_bytes / max(total_compressed_bytes, 1)

    # Attention quality
    avg_attn_cosine = float(np.mean([d["output_cosine_similarity"] for d in all_attention_distortions])) if all_attention_distortions else None
    avg_attn_kl = float(np.mean([d["attention_kl_div"] for d in all_attention_distortions])) if all_attention_distortions else None

    total_ms = (time.time() - t0) * 1000

    # Gate evaluation
    combined_mse = (avg_key_mse + avg_value_mse) / 2
    gates = {
        "quality_pass": combined_mse <= thresholds.get("max_quality_delta", 0.02),
        "memory_pass": memory_reduction >= thresholds.get("min_memory_reduction", 0.30),
        "attention_pass": avg_attn_cosine is None or avg_attn_cosine >= 0.95,
        "all_pass": False,
    }
    gates["all_pass"] = all([gates["quality_pass"], gates["memory_pass"], gates["attention_pass"]])

    return {
        "target_type": "kv_cache",
        "model_config": {
            "model_name": model_name,
            "layers": n_layers, "heads": n_heads,
            "seq_len": seq_len, "head_dim": head_dim,
            "layers_compressed": len(layer_range) if isinstance(layer_range, list) else n_layers,
            "heads_compressed": len(head_range) if isinstance(head_range, list) else n_heads,
        },
        "distortion": {
            "key_mse": avg_key_mse, "value_mse": avg_value_mse,
            "key_snr_db": round(avg_key_snr, 2), "value_snr_db": round(avg_value_snr, 2),
            "combined_mse": combined_mse,
            "mse": combined_mse,  # Compat with vector runner
            "snr_db": round((avg_key_snr + avg_value_snr) / 2, 2),
        },
        "attention_quality": {
            "output_cosine_similarity": round(avg_attn_cosine, 6) if avg_attn_cosine is not None else None,
            "attention_kl_div": round(avg_attn_kl, 6) if avg_attn_kl is not None else None,
        },
        "memory": {
            "original_bytes": total_original_bytes,
            "compressed_bytes": total_compressed_bytes,
            "compression_ratio": round(compression_ratio, 2),
            "memory_reduction_pct": round(memory_reduction * 100, 1),
        },
        "timing": {
            "compress_ms": round(compress_ms, 1),
            "total_ms": round(total_ms, 1),
        },
        "per_layer": layer_metrics,
        "qjl_residual": {"enabled": enable_residual},
        "gates": gates,
        "config": {"bit_width": bit_width, "seed": seed},
    }
