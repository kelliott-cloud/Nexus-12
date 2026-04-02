"""Promotion scoring and gating logic."""


def evaluate_promotion(run_metrics: dict, thresholds: dict) -> dict:
    gates = run_metrics.get("gates", {})
    if not gates.get("all_pass"):
        failed = [k for k, v in gates.items() if k != "all_pass" and not v]
        return {
            "eligible": False,
            "gates": gates,
            "score": 0.0,
            "reason": f"Failed gates: {', '.join(failed)}",
        }

    mem = run_metrics.get("memory", {})
    dist = run_metrics.get("distortion", {})
    recall = run_metrics.get("recall_at_10")

    score = (
        0.4 * min(mem.get("memory_reduction_pct", 0) / 100, 1.0) +
        0.3 * max(1.0 - dist.get("mse", 1.0) * 10, 0) +
        0.3 * (recall if recall is not None else 0.95)
    )

    return {
        "eligible": True,
        "gates": gates,
        "score": round(score, 4),
        "reason": "All gates passed",
    }
