"""
Dense embeddings (vector search, §3.6).

Two providers, chosen by `rag.embedding_provider` in config.yaml:

  nvidia  (default) - the NVIDIA hosted embedding model (`rag.nvidia_embedding_model`), using the same
                      NVIDIA_API_KEY as the chat model. No local ML libraries needed. Passages and queries are
                      embedded with different `input_type`s, as the model expects.
  local             - sentence-transformers on this computer (`rag.embedding_model`), if it is installed.

Everything degrades gracefully: with no key, no network or a missing library every function returns None and
retrieval runs on BM25 + exact error-code matching only. Nothing here is loaded at import time.

Vectors are L2-normalised. They are stored compactly (float16, base64: see pack/unpack) because a hosted model
returns 2048 numbers per chunk and a JSON list of those would make the index file huge.
"""
from __future__ import annotations

import base64
import importlib.util
import logging
import os
import threading
import time
from functools import lru_cache

from appconfig import cfg

log = logging.getLogger("rag.embed")

_model = None
_failed = False
_lock = threading.Lock()
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/embeddings"
BATCH = 32


def provider() -> str:
    return str(cfg("rag", "embedding_provider", default="nvidia") or "none").lower()


def model_name() -> str:
    if provider() == "nvidia":
        return cfg("rag", "nvidia_embedding_model", default="nvidia/nemotron-3-embed-1b")
    return cfg("rag", "embedding_model", default="all-MiniLM-L6-v2") or ""


def _nvidia_key() -> str:
    return os.environ.get(cfg("model", "nvidia", "api_key_env", default="NVIDIA_API_KEY"), "")


def dense_enabled() -> bool:
    """True when vectors can be made (does not call the model). Tests switch it off with IT_BUDDY_NO_DENSE=1."""
    if _failed or os.environ.get("IT_BUDDY_NO_DENSE") == "1":
        return False
    p = provider()
    if p == "nvidia":
        return bool(_nvidia_key())
    if p == "local":
        return bool(model_name()) and importlib.util.find_spec("sentence_transformers") is not None
    return False


# ---------------------------------------------------------------------------- providers
def _normalise(vec: list[float]) -> list[float]:
    norm = sum(x * x for x in vec) ** 0.5 or 1.0
    return [x / norm for x in vec]


def _nvidia(texts: list[str], kind: str) -> list[list[float] | None]:
    import requests
    out: list[list[float] | None] = []
    for start in range(0, len(texts), BATCH):
        batch = [t[:6000] for t in texts[start:start + BATCH]]
        body = {"model": model_name(), "input": batch, "input_type": kind,
                "encoding_format": "float", "truncate": "END"}
        vectors = None
        for attempt in range(5):                       # the free tier is sometimes busy: back off and retry
            try:
                r = requests.post(NVIDIA_URL, json=body, timeout=90,
                                  headers={"Authorization": f"Bearer {_nvidia_key()}"})
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 * (attempt + 1))
                    continue
                r.raise_for_status()
                data = sorted(r.json()["data"], key=lambda d: d["index"])
                vectors = [_normalise(d["embedding"]) for d in data]
                break
            except Exception as exc:
                log.warning("NVIDIA embedding failed: %s", exc)
                time.sleep(2 * (attempt + 1))
        out.extend(vectors or [None] * len(batch))
    return out


def _local_model():
    global _model, _failed
    if _model is not None or _failed:
        return _model
    with _lock:
        if _model is None and not _failed:
            try:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(model_name())
            except Exception as exc:  # missing weights, no network, bad name ...
                log.warning("Dense embeddings disabled: %s", exc)
                _failed = True
    return _model


def embed_many(texts: list[str], kind: str = "passage") -> list[list[float] | None]:
    """Normalised vectors for each text (kind: "passage" for knowledge chunks, "query" for searches).
    None entries when dense search is unavailable or the call failed."""
    if not texts or not dense_enabled():
        return [None] * len(texts)
    try:
        if provider() == "nvidia":
            return _nvidia(texts, kind)
        model = _local_model()
        if model is None:
            return [None] * len(texts)
        return [v.tolist() for v in model.encode(texts, normalize_embeddings=True)]
    except Exception as exc:
        log.warning("Embedding failed: %s", exc)
        return [None] * len(texts)


@lru_cache(maxsize=256)
def _query_vector(text: str, prov: str, model: str) -> tuple | None:
    vec = embed_many([text], kind="query")[0]
    return tuple(vec) if vec else None


def embed(text: str, kind: str = "query") -> list[float] | None:
    if kind == "query":
        vec = _query_vector(text, provider(), model_name())     # the same question twice: one call
        return list(vec) if vec else None
    return embed_many([text], kind=kind)[0]


# ---------------------------------------------------------------------------- compact storage
def pack(vec: list[float] | None) -> str | None:
    """Vector -> 'f16:<base64>' (2 bytes per number)."""
    if not vec:
        return None
    import numpy as np
    return "f16:" + base64.b64encode(np.asarray(vec, dtype=np.float16).tobytes()).decode()


def unpack(stored) -> "list[float] | None":
    """Stored text (packed or an older JSON list) -> numpy float32 array, or None."""
    if not stored:
        return None
    import json

    import numpy as np
    if isinstance(stored, str) and stored.startswith("f16:"):
        return np.frombuffer(base64.b64decode(stored[4:]), dtype=np.float16).astype(np.float32)
    try:
        return np.asarray(json.loads(stored) if isinstance(stored, str) else stored, dtype=np.float32)
    except (TypeError, ValueError):
        return None
