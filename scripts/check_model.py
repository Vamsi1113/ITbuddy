"""Phase 0 check: send one prompt through ChatOllama and print the reply and speed."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_ollama import ChatOllama  # noqa: E402

from appconfig import cfg  # noqa: E402

llm = ChatOllama(model=cfg("model", "name"), base_url=cfg("model", "base_url"),
                 temperature=0, num_ctx=cfg("model", "num_ctx"))
start = time.monotonic()
reply = llm.invoke("Say hello in one short sentence.")
elapsed = time.monotonic() - start
meta = reply.response_metadata or {}
print(f"Model: {cfg('model', 'name')}\nReply: {reply.content.strip()}\nTime: {elapsed:.1f}s")
if meta.get("eval_count") and meta.get("eval_duration"):
    rate = meta["eval_count"] / (meta["eval_duration"] / 1e9)
    print(f"Eval rate: {rate:.1f} tokens/s" + ("  (under 5: switch to a smaller model)" if rate < 5 else ""))
