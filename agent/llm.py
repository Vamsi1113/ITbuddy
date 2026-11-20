"""Model access from config: NVIDIA-hosted Nemotron/Kimi (OpenAI-compatible API) or local Ollama,
plus a JSON helper with the malformed-output retry (FR-19).

Provider choice is `model.provider` in config.yaml ("nvidia" or "ollama"). With the NVIDIA provider the key
is read from the environment variable named in `model.nvidia.api_key_env` (put it in .env, never in code).
Everything sent to the cloud first goes through safety.redact, so passwords, tokens and keys never leave.
If the cloud is unreachable and `model.nvidia.fallback_to_ollama` is true, the local model answers instead.
"""
from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache
from types import SimpleNamespace
from typing import Callable

import requests
from langchain_core.messages import HumanMessage, SystemMessage

from appconfig import cfg
from safety.redact import redact


class ModelError(Exception):
    """The model could not be reached, or kept returning malformed output."""


class MalformedOutput(ModelError):
    """The model answered, but not in the required format, even after the retries."""


# ---------------------------------------------------------------------------
# Local model (Ollama)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_ollama():
    from langchain_ollama import ChatOllama   # imported lazily: not needed when the cloud provider is used
    kwargs = dict(
        model=cfg("model", "name"),
        base_url=cfg("model", "base_url"),
        temperature=cfg("model", "temperature", default=0),
        num_ctx=cfg("model", "num_ctx", default=4096),
        format="json",
        client_kwargs={"timeout": cfg("model", "request_timeout_seconds", default=180)},
    )
    if cfg("model", "reasoning") is not None:
        kwargs["reasoning"] = cfg("model", "reasoning")
    return ChatOllama(**kwargs)


# ---------------------------------------------------------------------------
# Cloud model (NVIDIA API catalogue, OpenAI-compatible chat completions)
# ---------------------------------------------------------------------------
class NvidiaChat:
    """Minimal chat client: .invoke(messages) -> object with .content. Retries rate limits and 5xx errors."""

    def __init__(self) -> None:
        self.base_url = str(cfg("model", "nvidia", "base_url", default="https://integrate.api.nvidia.com/v1")).rstrip("/")
        self.models = [m for m in [cfg("model", "nvidia", "name"), cfg("model", "nvidia", "fallback_name")] if m]
        self.key_env = cfg("model", "nvidia", "api_key_env", default="NVIDIA_API_KEY")
        self.max_tokens = int(cfg("model", "nvidia", "max_tokens", default=4096))
        self.temperature = cfg("model", "nvidia", "temperature", default=0)
        self.timeout = int(cfg("model", "request_timeout_seconds", default=180))
        self.extra = cfg("model", "nvidia", "extra_body", default=None) or {}
        self.last_model = ""

    def _headers(self) -> dict:
        key = os.environ.get(self.key_env, "")
        if not key:
            raise ModelError(f"No API key: set {self.key_env} in the .env file next to config.yaml")
        return {"Authorization": f"Bearer {key}", "Accept": "application/json"}

    @staticmethod
    def _to_dicts(messages) -> list[dict]:
        role = {"system": "system", "human": "user", "ai": "assistant"}
        out = []
        for m in messages:
            text, _ = redact(str(m.content))            # secrets never leave this machine
            out.append({"role": role.get(m.type, "user"), "content": text})
        return out

    def invoke(self, messages):
        body = {"messages": self._to_dicts(messages), "max_tokens": self.max_tokens,
                "temperature": self.temperature, "stream": False, **self.extra}
        last = "no model configured"
        for model in self.models:
            for attempt in range(4):
                try:
                    r = requests.post(f"{self.base_url}/chat/completions", headers=self._headers(),
                                      json={**body, "model": model}, timeout=self.timeout)
                except requests.RequestException as e:
                    last = f"{type(e).__name__}: {str(e)[:150]}"
                    time.sleep(1 + attempt)
                    continue
                if r.status_code == 429 or r.status_code >= 500:     # busy: wait and retry
                    last = f"HTTP {r.status_code} from {model}"
                    time.sleep(min(float(r.headers.get("Retry-After", 2 * (attempt + 1))), 15))
                    continue
                if r.status_code != 200:
                    last = f"HTTP {r.status_code} from {model}: {r.text[:200]}"
                    break                                          # not retryable: try the next model
                choice = r.json()["choices"][0]
                content = (choice["message"].get("content") or "").strip()
                if not content:
                    last = f"{model} returned no answer (finish_reason={choice.get('finish_reason')})"
                    break
                self.last_model = model
                return SimpleNamespace(content=content)
        raise ModelError(last)


@lru_cache(maxsize=1)
def get_cloud() -> NvidiaChat:
    return NvidiaChat()


def provider() -> str:
    return str(cfg("model", "provider", default="ollama")).lower()


def describe_model() -> str:
    if provider() == "nvidia":
        return f"{cfg('model', 'nvidia', 'name')} (NVIDIA cloud)"
    return f"{cfg('model', 'name')} (local Ollama)"


def _invoke(messages):
    """One model call through the active provider, with the optional local fallback for cloud failures."""
    primary = get_llm()
    try:
        return primary.invoke(messages)
    except ModelError as e:                                  # the cloud client reports its failures this way
        if provider() != "nvidia" or not cfg("model", "nvidia", "fallback_to_ollama", default=True):
            raise ModelError(f"Could not reach the cloud model ({e})") from e
        cloud_error = str(e)
    except Exception as e:
        if provider() == "nvidia":
            raise ModelError(f"The model call failed ({type(e).__name__}: {str(e)[:200]})") from e
        raise ModelError(
            f"Could not reach the local model '{cfg('model', 'name')}' at "
            f"{cfg('model', 'base_url')} ({type(e).__name__}: {str(e)[:200]})"
        ) from e
    try:
        return get_ollama().invoke(messages)
    except Exception as e:
        raise ModelError(f"Cloud model failed ({cloud_error}) and the local model is not available "
                         f"({type(e).__name__}: {str(e)[:120]})") from e


def get_llm():
    """Back-compat: the active chat object (cloud client or Ollama)."""
    return get_cloud() if provider() == "nvidia" else get_ollama()


def _parse(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("reply was not JSON")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("reply was not a JSON object")
    return data


def ask_json(system: str, user: str, validate: Callable[[dict], dict]) -> dict:
    """One model call that must return a JSON object accepted by `validate`.

    `validate` returns the cleaned dict or raises ValueError. A malformed reply is
    retried up to `malformed_output_retries` times, then ModelError is raised.
    """
    retries = int(cfg("limits", "malformed_output_retries", default=2))
    messages = [SystemMessage(system), HumanMessage(user)]
    last_problem = ""
    for attempt in range(retries + 1):
        reply = _invoke(messages)
        try:
            return validate(_parse(reply.content))
        except (ValueError, KeyError, TypeError) as e:
            last_problem = str(e)
            messages = [SystemMessage(system), HumanMessage(
                f"{user}\n\nYour previous reply was rejected: {last_problem}. "
                "Reply again with one valid JSON object only."
            )]
    raise MalformedOutput(
        f"The model returned a malformed answer {retries + 1} times in a row ({last_problem})."
    )
