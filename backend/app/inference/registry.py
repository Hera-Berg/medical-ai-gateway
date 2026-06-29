"""
Model registry loader — reads models.yaml into typed descriptors used by the
inference path, the cost calculator, and the (later) model-selector UI.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

import yaml

_YAML_PATH = Path(__file__).parent / "models.yaml"


@dataclass(frozen=True)
class ModelDescriptor:
    key: str
    display_name: str
    endpoint_id: str
    gpu_tier: str
    per_second_usd: float
    capability_hint: str
    context_window: int
    hf_model_id: str = ""        # HuggingFace id (sent to the OpenAI-compatible worker)
    deployed: bool = False       # whether a real endpoint is wired (UI can flag)


@functools.lru_cache(maxsize=1)
def _load() -> tuple[dict[str, ModelDescriptor], str]:
    data = yaml.safe_load(_YAML_PATH.read_text())
    models: dict[str, ModelDescriptor] = {}
    for key, m in data["models"].items():
        models[key] = ModelDescriptor(
            key=key,
            display_name=m["display_name"],
            endpoint_id=m["endpoint_id"],
            gpu_tier=m["gpu_tier"],
            per_second_usd=float(m["per_second_usd"]),
            capability_hint=m["capability_hint"],
            context_window=int(m.get("context_window", 8192)),
            hf_model_id=m.get("hf_model_id", ""),
            deployed=not str(m["endpoint_id"]).startswith("REPLACE_"),
        )
    return models, data.get("default_model", next(iter(models)))


def all_models() -> list[ModelDescriptor]:
    return list(_load()[0].values())


def get_model(key: str) -> ModelDescriptor:
    models, _ = _load()
    try:
        return models[key]
    except KeyError as exc:
        raise ValueError(
            f"Unknown model '{key}'. Available: {sorted(models)}"
        ) from exc


def default_model_key() -> str:
    return _load()[1]
