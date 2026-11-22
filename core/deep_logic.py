"""Optional LLM-backed deep review for construction-cluster contradictions.

The deep reviewer is advisory. Deterministic cluster rules remain the source
of binding findings; network failures and offline mode produce marked
ClusterEvaluation records rather than false "no contradiction" judgments.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Protocol, Sequence

from core import classify
from core.logic import RULES_VERSION


DEEP_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "deep_logic_cache.json",
)


@dataclass
class ClusterEvaluation:
    """Structured deep review of one cluster."""

    contradiction_category: str = "NONE"
    severity: str = "low"
    reason_de: str = ""
    affected_positions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    offline: bool = False

    @property
    def category(self) -> str:
        return self.contradiction_category

    @property
    def rationale(self) -> str:
        return self.reason_de

    @property
    def positions(self) -> list[str]:
        return list(self.affected_positions)

    def as_dict(self) -> dict:
        return {
            "contradiction_category": self.contradiction_category,
            "severity": self.severity,
            "reason_de": self.reason_de,
            "affected_positions": list(self.affected_positions),
            "confidence": self.confidence,
            "offline": self.offline,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "ClusterEvaluation":
        data = dict(raw)
        data["affected_positions"] = list(data.get("affected_positions") or ())
        data["offline"] = bool(data.get("offline", False))
        try:
            data["confidence"] = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            data["confidence"] = 0.0
        return cls(
            contradiction_category=str(data.get("contradiction_category", "NONE")),
            severity=str(data.get("severity", "low")),
            reason_de=str(data.get("reason_de", "")),
            affected_positions=data["affected_positions"],
            confidence=data["confidence"],
            offline=data["offline"],
        )


class LogicLLM(Protocol):
    name: str

    def evaluate(self, payload: str, schema: dict) -> dict: ...


def _load_env_once() -> None:
    """Read repository .env once, analog to core.classify._load_env_once."""
    classify._load_env_once()
    if os.getenv("LOGIC_LLM_PROVIDER") and os.getenv("LOGIC_LLM_MODEL") and os.getenv("LOGIC_LLM_KEY"):
        return
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ".env",
    )
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip())
    except OSError:
        pass


class OpenAIAdapter:
    name: str

    def __init__(
        self,
        model: str | None = None,
        key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or os.getenv("LOGIC_LLM_MODEL", "gpt-4.1-mini")
        self.name = self.model
        self.key = key or os.getenv("LOGIC_LLM_KEY")
        self.base_url = (
            base_url
            or os.getenv("LOGIC_LLM_BASE_URL", "https://api.openai.com/v1")
        ).rstrip("/")

    def evaluate(self, payload: str, schema: dict) -> dict:
        if not self.key:
            raise RuntimeError("LOGIC_LLM_KEY is not set")
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Du bist ein vorsichtiger Bauingenieur. Antworte nur "
                        "nachweisbar aus dem gelieferten Cluster-Payload."
                    ),
                },
                {"role": "user", "content": payload},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "cluster_evaluation",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.key}",
            },
        )
        with urllib.request.urlopen(request, timeout=60.0) as response:
            envelope = json.loads(response.read().decode("utf-8"))
        try:
            content = envelope["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("OpenAI response contained no JSON content") from exc
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise RuntimeError("OpenAI returned a non-object result")
        return parsed


class AnthropicAdapter:
    name: str

    def __init__(
        self,
        model: str | None = None,
        key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or os.getenv(
            "LOGIC_LLM_MODEL",
            "claude-3-5-haiku-latest",
        )
        self.name = self.model
        self.key = key or os.getenv("LOGIC_LLM_KEY")
        self.base_url = (
            base_url
            or os.getenv("LOGIC_LLM_BASE_URL", "https://api.anthropic.com/v1")
        ).rstrip("/")

    def evaluate(self, payload: str, schema: dict) -> dict:
        if not self.key:
            raise RuntimeError("LOGIC_LLM_KEY is not set")
        body = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": payload}],
            "tools": [
                {
                    "name": "cluster_evaluation",
                    "description": "Strukturierte Bewertung eines LV-Clusters.",
                    "input_schema": schema,
                }
            ],
            "tool_choice": {
                "type": "tool",
                "name": "cluster_evaluation",
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/messages",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(request, timeout=60.0) as response:
            envelope = json.loads(response.read().decode("utf-8"))
        content = envelope.get("content", []) if isinstance(envelope, dict) else []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                parsed = block.get("input")
                if isinstance(parsed, dict):
                    return parsed
        raise RuntimeError("Anthropic response contained no tool input")


class OfflineAdapter:
    name = "offline"

    def evaluate(self, payload: str, schema: dict) -> dict:
        del payload, schema
        return {
            "contradiction_category": "NONE",
            "severity": "low",
            "reason_de": "Offline-Modus: Keine LLM-Bewertung durchgefuehrt.",
            "affected_positions": [],
            "confidence": 0.0,
        }


def get_adapter() -> LogicLLM:
    _load_env_once()
    provider = (os.getenv("LOGIC_LLM_PROVIDER") or "offline").strip().lower()
    key = os.getenv("LOGIC_LLM_KEY")
    model = os.getenv("LOGIC_LLM_MODEL")

    if provider == "openai" and key:
        return OpenAIAdapter(model=model, key=key)
    if provider.startswith(("http://", "https://")) and key:
        base_url = provider.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        return OpenAIAdapter(model=model, key=key, base_url=base_url)
    if provider == "anthropic" and key:
        return AnthropicAdapter(model=model, key=key)
    return OfflineAdapter()


def cache_fingerprint(payload: str, rules_version: str, model: str) -> str:
    """Cache key covering input, rule catalogue version and model."""
    raw = f"{payload}|{rules_version}|{model}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def load_deep_cache() -> dict:
    if not os.path.exists(DEEP_CACHE_PATH):
        return {}
    try:
        with open(DEEP_CACHE_PATH, encoding="utf-8") as fh:
            cache = json.load(fh)
            return cache if isinstance(cache, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_deep_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(DEEP_CACHE_PATH), exist_ok=True)
    with open(DEEP_CACHE_PATH, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=1, sort_keys=True)


CLUSTER_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "contradiction_category": {
            "type": "string",
            "enum": [
                "NONE",
                "SPEC_GAP",
                "QUANTITY_CONFLICT",
                "UNIT_CONFLICT",
                "INTERFACE_CONFLICT",
                "NORM_CONFLICT",
                "INCLUSIVE_SCOPE",
            ],
        },
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "reason_de": {"type": "string"},
        "affected_positions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
        },
    },
    "required": [
        "contradiction_category",
        "severity",
        "reason_de",
        "affected_positions",
        "confidence",
    ],
}


def evaluate_clusters(
    clusters,
    payloads: dict[str, str],
    use_llm: bool | None = None,
    max_clusters: int = 12,
    write_cache: bool = True,
) -> dict[str, ClusterEvaluation]:
    """Evaluate at most max_clusters clusters, with cache and per-cluster errors."""
    adapter = get_adapter()
    offline_adapter = isinstance(adapter, OfflineAdapter)

    if use_llm is None:
        use_llm = not offline_adapter

    cache = load_deep_cache()
    model = adapter.name
    output: dict[str, ClusterEvaluation] = {}
    misses: list[tuple[str, str, str]] = []

    for cluster in list(clusters)[:max(0, int(max_clusters))]:
        cluster_id = cluster.cluster_id
        payload = payloads.get(cluster_id)
        if payload is None:
            continue
        fingerprint = cache_fingerprint(payload, RULES_VERSION, model)
        cached = cache.get(fingerprint)
        if isinstance(cached, dict):
            cached_evaluation = ClusterEvaluation.from_dict(cached)
            if not cached_evaluation.offline:
                output[cluster_id] = cached_evaluation
            else:
                misses.append((cluster_id, payload, fingerprint))
        else:
            misses.append((cluster_id, payload, fingerprint))

    def resolve(entry: tuple[str, str, str]) -> tuple[str, ClusterEvaluation | None, str]:
        cluster_id, payload, fingerprint = entry
        if not use_llm:
            evaluation = ClusterEvaluation(
                contradiction_category="NONE",
                severity="low",
                reason_de="Offline-Modus: Keine LLM-Bewertung durchgefuehrt.",
                affected_positions=[],
                confidence=0.0,
                offline=True,
            )
            return cluster_id, evaluation, fingerprint
        try:
            raw = adapter.evaluate(payload, CLUSTER_SCHEMA)
            if not isinstance(raw, dict):
                raise RuntimeError("LLM returned a non-object result")
            raw["offline"] = False
            return cluster_id, ClusterEvaluation.from_dict(raw), fingerprint
        except Exception as exc:
            detail = f"{type(exc).__name__}: {str(exc)[:180]}"
            return (
                cluster_id,
                ClusterEvaluation(
                    contradiction_category="NONE",
                    severity="low",
                    reason_de=f"LLM-Auswertung fehlgeschlagen; offline behandelt. {detail}",
                    affected_positions=[],
                    confidence=0.0,
                    offline=True,
                ),
                fingerprint,
            )

    if misses:
        with ThreadPoolExecutor(max_workers=2) as pool:
            resolved = list(pool.map(resolve, misses))
        for cluster_id, evaluation, fingerprint in resolved:
            if evaluation is not None:
                output[cluster_id] = evaluation
                if not evaluation.offline:
                    cache[fingerprint] = evaluation.as_dict()

    if write_cache and misses:
        save_deep_cache(cache)
    return output
