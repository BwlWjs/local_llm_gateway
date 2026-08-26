from dataclasses import dataclass
import json
import os
from typing import Any


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_json(name: str, default: dict[str, Any]) -> dict[str, Any]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return default
    if not isinstance(value, dict):
        return default
    merged = dict(default)
    merged.update(value)
    return merged


@dataclass(frozen=True)
class Settings:
    provider_default: str = os.getenv("GATEWAY_PROVIDER_DEFAULT", "ollama")
    ollama_base_url: str = os.getenv("GATEWAY_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    vllm_base_url: str = os.getenv("GATEWAY_VLLM_BASE_URL", "http://127.0.0.1:8000")
    request_timeout_s: float = _env_float("GATEWAY_REQUEST_TIMEOUT_S", 120.0)
    model_map_raw: str = os.getenv("GATEWAY_MODEL_MAP", "{}")
    model_defaults: dict[str, Any] = None  # type: ignore[assignment]
    provider_caps: dict[str, Any] = None  # type: ignore[assignment]
    gateway_name: str = os.getenv("GATEWAY_NAME", "ModelRelay")
    gateway_version: str = os.getenv("GATEWAY_VERSION", "0.1.0")
    db_path: str = os.getenv("GATEWAY_DB_PATH", "./modelrelay.db")
    admin_token: str = os.getenv("GATEWAY_ADMIN_TOKEN", "")

    def __post_init__(self) -> None:
        default_models = {
            "local-coder": {
                "provider": "ollama",
                "model": "qwen2.5-coder:7b",
                "display_name": "Local Coder",
            }
        }
        default_caps = {
            "ollama": {
                "supports_messages": True,
                "supports_stream": True,
                "supports_count_tokens": False,
                "supports_tools": True,
                "supports_system": True,
                "max_context_tokens": 8192,
            },
            "vllm": {
                "supports_messages": False,
                "supports_stream": False,
                "supports_count_tokens": False,
                "supports_tools": False,
                "supports_system": True,
                "max_context_tokens": 8192,
            },
        }
        object.__setattr__(self, "model_defaults", _env_json("GATEWAY_MODEL_DEFAULTS", default_models))
        object.__setattr__(self, "provider_caps", _env_json("GATEWAY_PROVIDER_CAPS", default_caps))


settings = Settings()
