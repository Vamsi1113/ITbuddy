"""General-knowledge fallback, imported vendor articles and compact vector storage."""
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
