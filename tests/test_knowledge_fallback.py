"""General-knowledge fallback, imported vendor articles and compact vector storage."""
import pytest
from langgraph.checkpoint.memory import MemorySaver

from agent import graph as graph_module
from agent import runner, specialists
from rag import embed


def test_kb_found_something_reads_the_knowledge_tool_outputs():
    assert not specialists.kb_found_something({"search_knowledge_base": {"ok": True, "results": [], "sufficiency": "irrelevant"}})
    assert not specialists.kb_found_something({"search_knowledge_base": {"ok": True, "results": [{"text": "x"}],
                                                                         "sufficiency": "irrelevant"}})
    assert specialists.kb_found_something({"search_knowledge_base": {"ok": True, "results": [{"text": "x"}],
                                                                     "sufficiency": "partial"}})
    assert specialists.kb_found_something({"lookup_policy": {"ok": True, "policy_text": "BYOD rules"}})


def _howto_graph(monkeypatch, kb_output, answer_text):
    monkeypatch.setattr(graph_module.router, "route", lambda request: {"agent": "howto", "question": ""})
    monkeypatch.setattr(graph_module, "_run", lambda runner_, tool, args=None, **k: kb_output)

    def fake_model(system, user, validate):
        if "has no article for this question" in system:            # the general-knowledge prompt
            return validate({"answer": "1. Press Windows + Alt + R to record with Xbox Game Bar.", "escalate": False})
        return validate({"answer": answer_text, "fix": "none", "args": {}, "reason": ""})

    monkeypatch.setattr("agent.specialists.ask_json", fake_model)
    return graph_module.build_graph(MemorySaver())


def test_empty_knowledge_base_answers_from_general_knowledge(monkeypatch):
    graph = _howto_graph(monkeypatch, {"ok": True, "results": [], "sufficiency": "irrelevant"}, "unused")
    state = runner.start(graph, "how to screen record")["state"]
    assert "Windows + Alt + R" in state["report"]
    assert "not from your company's knowledge base" in state["report"]
    assert state["outcome"] == "no_action"


def test_unrelated_articles_also_fall_back(monkeypatch):
    kb = {"ok": True, "results": [{"text": "Screen sharing is black", "source": "teams.md"}], "sufficiency": "partial"}
    graph = _howto_graph(monkeypatch, kb, "NO_KB_ANSWER")
    state = runner.start(graph, "how to screen record")["state"]
    assert "Windows + Alt + R" in state["report"]


def test_a_real_kb_answer_is_kept(monkeypatch):
    kb = {"ok": True, "results": [{"text": "Open GlobalProtect", "source": "vpn.md"}], "sufficiency": "sufficient"}
    graph = _howto_graph(monkeypatch, kb, "Open GlobalProtect and sign in. [vpn.md § Connect]")
    state = runner.start(graph, "how do I connect to the VPN")["state"]
    assert "GlobalProtect" in state["report"] and "general guidance" not in state["report"].lower()


def test_vectors_are_stored_compactly_and_round_trip():
    vec = [0.6, 0.8] + [0.0] * 2046
    packed = embed.pack(vec)
    assert packed.startswith("f16:") and len(packed) < 6000
    back = embed.unpack(packed)
    assert abs(back[0] - 0.6) < 1e-3 and len(back) == 2048
    assert embed.unpack("[0.5, 0.5]").tolist() == [0.5, 0.5]       # older JSON vectors still load


def test_vendor_articles_are_indexed_with_their_source(tmp_path):
    from rag.index import get_document_chunks
    from rag.ingest import ingest_vendor_files
    folder = tmp_path / "microsoft_learn" / "printing"
    folder.mkdir(parents=True)
    (folder / "printer-offline.md").write_text(
        "<!-- source: https://learn.microsoft.com/troubleshoot/windows-client/printing/printer-offline -->\n"
        "# Printer shows offline\n\n## Resolution\n\nRestart the Print Spooler service, then check the cable and "
        "that the printer is switched on and connected to the same network as the computer.\n", encoding="utf-8")
    stats = ingest_vendor_files(tmp_path)
    assert stats["chunks_added"] >= 1
    chunks = get_document_chunks("vendor/microsoft_learn/printing/printer-offline")
    assert chunks and chunks[0].url.startswith("https://learn.microsoft.com/")
    assert chunks[0].source_system == "vendor" and chunks[0].doc_type == "vendor"
    (folder / "printer-offline.md").unlink()
    assert ingest_vendor_files(tmp_path)["chunks_deleted"] >= 1


# --- hosted embeddings: a withdrawn model must never slow a question down -------------------------------
class _Resp:
    def __init__(self, status, vectors=None):
        self.status_code = status
        self._vectors = vectors or []

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return {"data": [{"index": i, "embedding": v} for i, v in enumerate(self._vectors)]}


@pytest.fixture
def hosted(monkeypatch):
    """The hosted provider with a key, no sleeping, and a clean session state."""
    monkeypatch.delenv("IT_BUDDY_NO_DENSE", raising=False)
    monkeypatch.setattr(embed, "_nvidia_key", lambda: "key")
    monkeypatch.setattr(embed, "_dead_models", set())
    monkeypatch.setattr(embed, "_pause_until", 0.0)
    monkeypatch.setattr(embed, "_query_cache", {})
    monkeypatch.setattr(embed, "provider", lambda: "nvidia")
    monkeypatch.setattr(embed, "candidate_models", lambda: ["model-new", "model-old"])
    sleeps = []
    monkeypatch.setattr(embed.time, "sleep", lambda s: sleeps.append(s))
    return sleeps


def test_a_withdrawn_model_moves_to_the_next_one_at_once(hosted, monkeypatch):
    used = []

    def post(url, json=None, **kw):
        used.append(json["model"])
        return _Resp(410) if json["model"] == "model-new" else _Resp(200, [[3.0, 4.0]])

    monkeypatch.setattr("requests.post", post)
    vec = embed.embed("how to screen record")
    assert used == ["model-new", "model-old"] and vec == pytest.approx([0.6, 0.8])
    assert embed.model_name() == "model-old" and hosted == []              # no waiting


def test_when_every_model_is_gone_search_falls_back_without_delay(hosted, monkeypatch):
    calls = []
    monkeypatch.setattr("requests.post", lambda url, json=None, **kw: calls.append(json["model"]) or _Resp(410))
    assert embed.embed("anything") is None
    assert len(calls) == 2 and not embed.dense_enabled() and hosted == []   # paused: no more calls for a while
    assert embed.embed("another question") is None and len(calls) == 2


def test_bad_key_pauses_vector_search_instead_of_retrying(hosted, monkeypatch):
    calls = []
    monkeypatch.setattr("requests.post", lambda url, json=None, **kw: calls.append(1) or _Resp(401))
    assert embed.embed("q") is None and len(calls) == 1 and not embed.dense_enabled()


def test_a_busy_service_is_retried_briefly_and_a_failure_is_not_cached(hosted, monkeypatch):
    answers = iter([_Resp(503), _Resp(503)])
    monkeypatch.setattr("requests.post", lambda url, json=None, **kw: next(answers))
    assert embed.embed("q") is None and len(hosted) <= 2                    # at most two short waits for a query
    monkeypatch.setattr("requests.post", lambda url, json=None, **kw: _Resp(200, [[1.0, 0.0]]))
    assert embed.embed("q") == [1.0, 0.0]                                   # the earlier failure was not remembered


def test_vectors_remember_their_model_and_other_models_are_skipped(monkeypatch):
    monkeypatch.setattr(embed, "provider", lambda: "nvidia")
    monkeypatch.setattr(embed, "candidate_models", lambda: ["model-a"])
    packed_a = embed.pack([0.6, 0.8])
    tag_a = embed.model_tag()
    assert packed_a.startswith(f"f16:{tag_a}:") and embed.unpack(packed_a, tag_a) is not None
    monkeypatch.setattr(embed, "candidate_models", lambda: ["model-b"])
    assert embed.model_tag() != tag_a
    assert embed.unpack(packed_a, embed.model_tag()) is None                # made by another model: not compared
    assert embed.unpack("f16:AAAA", embed.model_tag()) is None              # an old vector without a tag: skipped too
    assert embed.unpack(packed_a) is not None                               # no tag asked for: still readable


def test_one_rejected_text_does_not_lose_the_rest_of_the_batch(hosted, monkeypatch):
    def post(url, json=None, **kw):
        batch = json["input"]
        if "forbidden" in " ".join(batch):
            return _Resp(422)
        return _Resp(200, [[3.0, 4.0]] * len(batch))

    monkeypatch.setattr("requests.post", post)
    out = embed.embed_many(["fine one", "a forbidden text", "fine two", "fine three"], kind="passage")
    assert [v is not None for v in out] == [True, False, True, True]
    assert embed.dense_enabled()                                       # one bad text never switches search off
