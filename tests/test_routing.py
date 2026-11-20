"""Routing check: sample requests must reach the correct specialist at least 90% of the time.

Needs Ollama running with the configured model, so it is skipped otherwise.
Run it alone with:  pytest tests/test_routing.py -s
"""
import urllib.request

import pytest

from agent import router
from appconfig import cfg

# Some requests fit two specialists equally well; either is accepted.
SAMPLES = [
    ("My computer is very slow.", {"performance"}),
    ("Everything freezes when I open Excel, the laptop is lagging badly.", {"performance", "logs"}),
    ("Something is eating all my memory.", {"performance"}),
    ("My C drive is almost full.", {"storage"}),
    ("I get a low disk space warning every few minutes.", {"storage"}),
    ("Can you clean up temporary files? I have no space left.", {"storage"}),
    ("Wi-Fi is connected but websites do not open.", {"network"}),
    ("The internet is not working on my laptop.", {"network"}),
    ("My VPN keeps disconnecting.", {"network", "howto"}),
    ("Is developer mode on or off in my settings?", {"settings"}),
    ("What is my default browser?", {"settings"}),
    ("Is Zoom installed on this computer?", {"software"}),
    ("Which Windows updates were installed recently?", {"software"}),
    ("My printer is not printing.", {"devices"}),
    ("My headset microphone is not working in calls.", {"devices"}),
    ("Outlook keeps crashing, can you see why?", {"logs"}),
    ("Is my antivirus running?", {"security", "settings"}),
    ("Is this link safe? http://paypa1-secure.xyz/login", {"security"}),
    ("Do I have admin rights on this laptop?", {"account"}),
    ("How do I set an out-of-office reply?", {"howto"}),
    ("I need a new keyboard.", {"it_request"}),
    ("Open Notepad, write a summary of my system health and save it in Documents.", {"computer_use"}),
    ("Open the test portal and download the latest report.", {"computer_use"}),
]


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen(cfg("model", "base_url") + "/api/version", timeout=2)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="Ollama is not running")
def test_samples_route_correctly_at_least_90_percent():
    wrong = []
    for text, expected in SAMPLES:
        got = router.route(text)["agent"]
        mark = "ok " if got in expected else "BAD"
        print(f"{mark} {got:13} {text}")
        if got not in expected:
            wrong.append((text, sorted(expected), got))
    assert len(wrong) <= len(SAMPLES) // 10, wrong


@pytest.mark.skipif(not _ollama_up(), reason="Ollama is not running")
def test_unrelated_request_goes_to_none():
    assert router.route("What is the capital of France?")["agent"] == "none"
