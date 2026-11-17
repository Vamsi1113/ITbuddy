"""Phase 2 check: ten sample requests must reach the correct agent at least nine times.

Needs Ollama running with the configured model, so it is skipped otherwise.
Run it alone with:  pytest tests/test_routing.py -s
"""
import urllib.request

import pytest

from agent import router
from appconfig import cfg

SAMPLES = [
    ("My computer is very slow.", "performance"),
    ("Everything freezes when I open Excel, the laptop is lagging badly.", "performance"),
    ("Something is eating all my memory.", "performance"),
    ("My C drive is almost full.", "storage"),
    ("I get a low disk space warning every few minutes.", "storage"),
    ("Can you clean up temporary files? I have no space left.", "storage"),
    ("Wi-Fi is connected but websites do not open.", "network"),
    ("The internet is not working on my laptop.", "network"),
    ("Open Notepad, write a summary of my system health and save it in Documents.", "computer_use"),
    ("Open the test portal and download the latest report.", "computer_use"),
]


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen(cfg("model", "base_url") + "/api/version", timeout=2)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="Ollama is not running")
def test_ten_samples_route_correctly_at_least_nine_times():
    wrong = []
    for text, expected in SAMPLES:
        got = router.route(text)["agent"]
        print(f"{expected:13} <- {got:13} {text}")
        if got != expected:
            wrong.append((text, expected, got))
    assert len(wrong) <= 1, wrong


@pytest.mark.skipif(not _ollama_up(), reason="Ollama is not running")
def test_unrelated_request_goes_to_none():
    assert router.route("What is the capital of France?")["agent"] == "none"
