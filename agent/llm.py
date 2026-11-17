"""ChatOllama setup from config, plus a JSON helper with the malformed-output retry (FR-19)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from appconfig import cfg


class ModelError(Exception):
    """The model could not be reached, or kept returning malformed output."""


@lru_cache(maxsize=1)
def get_llm() -> ChatOllama:
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


def _parse(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
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
        try:
            reply = get_llm().invoke(messages)
        except Exception as e:
            raise ModelError(
                f"Could not reach the local model '{cfg('model', 'name')}' at "
                f"{cfg('model', 'base_url')} ({type(e).__name__}: {str(e)[:200]})"
            ) from e
        try:
            return validate(_parse(reply.content))
        except (ValueError, KeyError, TypeError) as e:
            last_problem = str(e)
            messages = [SystemMessage(system), HumanMessage(
                f"{user}\n\nYour previous reply was rejected: {last_problem}. "
                "Reply again with one valid JSON object only."
            )]
    raise ModelError(
        f"The model returned a malformed answer {retries + 1} times in a row ({last_problem}). "
        "Stopping here; nothing was changed."
    )
