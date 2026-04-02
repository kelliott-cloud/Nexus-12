"""Pydantic schemas for NAVC profiles, runs, and promotions."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from enum import Enum

class TargetType(str, Enum):
    KV_CACHE = "kv_cache"
    VECTOR_INDEX = "vector_index"

class OptimizationTarget(str, Enum):
    MSE = "mse"
    INNER_PRODUCT = "ip"

class KVCacheConfig(BaseModel):
    """Per-layer/per-head configuration for KV-cache compression."""
    model_name: str = Field(default="custom", description="Model config: llama-3-8b, llama-3-70b, mistral-7b, gpt2-small, custom")
    layers: Optional[int] = Field(default=None, description="Override number of layers to compress")
    seq_len: Optional[int] = Field(default=None, description="Override sequence length")
    layer_range: Optional[List[int]] = Field(default=None, description="Specific layer indices to compress")
    head_range: Optional[List[int]] = Field(default=None, description="Specific head indices to compress")
    per_layer_bits: Optional[Dict[str, int]] = Field(default=None, description="Per-layer bit-width overrides, e.g. {'0': 8, '1': 4}")

class ProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    target_type: TargetType = TargetType.VECTOR_INDEX
    optimization_target: OptimizationTarget = OptimizationTarget.MSE
    bit_width: int = Field(default=4, ge=1, le=8)
    rotation_seed: int = Field(default=42)
    enable_residual: bool = Field(default=True, description="Enable QJL 1-bit residual correction")
    kv_config: Optional[KVCacheConfig] = Field(default=None, description="KV-cache specific options")
    thresholds: Dict = Field(default_factory=lambda: {
        "max_quality_delta": 0.02,
        "max_latency_regression": 0.10,
        "min_memory_reduction": 0.30,
        "min_recall_at_10": 0.90,
    })
    description: str = ""

class RunCreate(BaseModel):
    profile_id: str
    dataset_id: Optional[str] = None
    workload_ref: Optional[str] = None
    run_baseline: bool = Field(default=True, description="Also run uncompressed baseline")

class DatasetUpload(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    dataset_type: str = Field(default="vectors", description="vectors or kv_trace")
    source: str = Field(default="upload", description="upload, workspace_memory, or synthetic")
    model_name: Optional[str] = Field(default=None, description="For synthetic KV traces")

class PromotionCreate(BaseModel):
    run_id: str
    target_binding: str = Field(..., description="e.g. knowledge_retrieval, model:llama-3")
    notes: str = ""
