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
import hashlib
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
_dead_models: set[str] = set()        # hosted models the service has withdrawn (404 / 410), this session
_pause_until = 0.0                    # after a permanent failure vector search stays off for a while (keyword search runs)
_query_cache: dict = {}
_used_models: set[str] = set()        # the models that produced the vectors of the last hosted call


def provider() -> str:
    return str(cfg("rag", "embedding_provider", default="nvidia") or "none").lower()


def candidate_models() -> list[str]:
    """Hosted models to try, in order: the first one the service still offers is used."""
    listed = cfg("rag", "nvidia_embedding_models", default=None)
    if listed:
        return [str(m) for m in listed]
    return [cfg("rag", "nvidia_embedding_model", default="nvidia/nemotron-3.5-embed-1b")]


def model_name() -> str:
    if provider() == "nvidia":
        alive = [m for m in candidate_models() if m not in _dead_models]
        return (alive or candidate_models())[0]
    return cfg("rag", "embedding_model", default="all-MiniLM-L6-v2") or ""


def model_tag() -> str:
    """Short id of the active embedding model. Stored with every vector, so vectors from another model are never
    compared (two models can both give 2048 numbers and still mean different things)."""
    return hashlib.md5(f"{provider()}:{model_name()}".encode()).hexdigest()[:6]


def _nvidia_key() -> str:
    return os.environ.get(cfg("model", "nvidia", "api_key_env", default="NVIDIA_API_KEY"), "")


def _pause(seconds: float, why: str) -> None:
    global _pause_until
    _pause_until = time.time() + seconds
    log.warning("Vector search paused for %d s (%s): keyword search is used meanwhile", seconds, why)


def dense_enabled() -> bool:
    """True when vectors can be made (does not call the model). Tests switch it off with IT_BUDDY_NO_DENSE=1."""
    if _failed or os.environ.get("IT_BUDDY_NO_DENSE") == "1" or time.time() < _pause_until:
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


def _nvidia(texts: list[str], kind: str, _top: bool = True) -> list[list[float] | None]:
    """Hosted embeddings. A withdrawn model (404 / 410) moves on to the next candidate at once; other permanent errors
    (bad key, bad request) switch vector search off for 10 minutes instead of retrying; only busy-service errors are
    retried, briefly, so a question never waits long for the keyword fallback."""
    import requests
    global _used_models
    if _top:
        _used_models = set()
    out: list[list[float] | None] = []
    attempts = 4 if kind == "passage" else 2
    timeout = 60 if kind == "passage" else 8
    for start in range(0, len(texts), BATCH):
        batch = [t[:6000] for t in texts[start:start + BATCH]]
        vectors = None
        for attempt in range(attempts + len(candidate_models())):
            body = {"model": model_name(), "input": batch, "input_type": kind, "encoding_format": "float", "truncate": "END"}
            try:
                r = requests.post(NVIDIA_URL, json=body, timeout=timeout, headers={"Authorization": f"Bearer {_nvidia_key()}"})
            except requests.RequestException as exc:
                log.warning("NVIDIA embedding request failed: %s", exc)
                time.sleep(1.0 * (attempt + 1))
                if attempt + 1 >= attempts:
                    break
                continue
            if r.status_code in (404, 410):
                _dead_models.add(body["model"])
                log.warning("Embedding model %s is no longer offered (HTTP %s)", body["model"], r.status_code)
                if not [m for m in candidate_models() if m not in _dead_models]:
                    _pause(600, "no embedding model is available")
                    break
                continue                                           # try the next candidate straight away
            if r.status_code == 422:
                # the service refused this input (content screening): find which text, the others are still embedded
                if len(batch) == 1:
                    log.info("One text was rejected by the embedding service; it stays keyword-searchable only")
                    vectors = [None]
                else:
                    half = len(batch) // 2
                    vectors = _nvidia(batch[:half], kind, _top=False) + _nvidia(batch[half:], kind, _top=False)
                break
            if r.status_code in (400, 401, 403):
                _pause(600, f"HTTP {r.status_code} from the embedding service")
                break
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                if attempt + 1 >= attempts:
                    break
                continue
            try:
                r.raise_for_status()
                data = sorted(r.json()["data"], key=lambda d: d["index"])
                vectors = [_normalise(d["embedding"]) for d in data]
                _used_models.add(body["model"])
            except Exception as exc:
                log.warning("NVIDIA embedding failed: %s", exc)
            break
        out.extend(vectors or [None] * len(batch))
        if vectors is None and time.time() < _pause_until:
            out.extend([None] * (len(texts) - len(out)))          # paused: do not try the remaining batches
            break
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
            vectors = _nvidia(texts, kind)
            if len(_used_models) > 1 and dense_enabled():           # the model changed between batches: redo with one model
                vectors = _nvidia(texts, kind)
            return vectors
        model = _local_model()
        if model is None:
            return [None] * len(texts)
        return [v.tolist() for v in model.encode(texts, normalize_embeddings=True)]
    except Exception as exc:
        log.warning("Embedding failed: %s", exc)
        return [None] * len(texts)


def embed(text: str, kind: str = "query") -> list[float] | None:
    if kind == "query":
        key = (text, provider(), model_name())
        if key in _query_cache:
            return list(_query_cache[key])                           # the same question twice: one call
        vec = embed_many([text], kind="query")[0]
        if vec:                                                     # a failure is never cached
            if len(_query_cache) > 256:
                _query_cache.clear()
            _query_cache[key] = tuple(vec)
        return vec
    return embed_many([text], kind=kind)[0]


# ---------------------------------------------------------------------------- compact storage
def pack(vec: list[float] | None) -> str | None:
    """Vector -> 'f16:<model tag>:<base64>' (2 bytes per number)."""
    if not vec:
        return None
    import numpy as np
    return f"f16:{model_tag()}:" + base64.b64encode(np.asarray(vec, dtype=np.float16).tobytes()).decode()


def unpack(stored, tag: str | None = None):
    """Stored text -> numpy float32 array, or None. With `tag`, only vectors made by that model are returned
    (older vectors without a tag, or from another model, are skipped until they are re-embedded)."""
    if not stored:
        return None
    import json

    import numpy as np
    if isinstance(stored, str) and stored.startswith("f16:"):
        parts = stored.split(":", 2)
        if len(parts) == 3:
            if tag is not None and parts[1] != tag:
                return None
            return np.frombuffer(base64.b64decode(parts[2]), dtype=np.float16).astype(np.float32)
        return None if tag is not None else np.frombuffer(base64.b64decode(parts[1]), dtype=np.float16).astype(np.float32)
    if tag is not None:
        return None
    try:
        return np.asarray(json.loads(stored) if isinstance(stored, str) else stored, dtype=np.float32)
    except (TypeError, ValueError):
        return None
