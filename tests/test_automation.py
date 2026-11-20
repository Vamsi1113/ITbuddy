"""Hands-on tools: screen recording, screenshots, keyboard shortcuts, and the one-approval-per-window rule."""
import subprocess

import pytest

from agent import autopilot
from agent.router import fast_route
from tools import automation


# --- file names ---------------------------------------------------------------------------
def test_safe_filename_keeps_words_and_blocks_paths():
    assert automation.safe_filename("first video by tobi", "x", "mp4") == "first video by tobi.mp4"
    assert automation.safe_filename("..\\..\\evil/name.mp4", "x", "mp4") == "evilname.mp4"
    assert automation.safe_filename("", "fallback", "png") == "fallback.png"
    assert automation.safe_filename("clip.MP4", "x", "mp4") == "clip.mp4"


def test_free_path_never_overwrites(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    assert automation.free_path(tmp_path, "a.mp4").name == "a (2).mp4"
    (tmp_path / "a (2).mp4").write_bytes(b"x")
    assert automation.free_path(tmp_path, "a.mp4").name == "a (3).mp4"


# --- recording and screenshots (ffmpeg and the screen are faked) ----------------------------
def test_record_screen_saves_the_named_file(tmp_path, monkeypatch):
    monkeypatch.setattr(automation, "videos_folder", lambda: tmp_path)
    monkeypatch.setattr(automation, "_ffmpeg", lambda: "ffmpeg.exe")
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        open(cmd[-1], "wb").write(b"0" * 2048)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(automation.subprocess, "run", fake_run)
    out = automation.record_screen(3, "first video by tobi")
    assert out["ok"] and out["file_name"] == "first video by tobi.mp4" and (tmp_path / out["file_name"]).exists()
    assert "-t" in seen["cmd"] and seen["cmd"][seen["cmd"].index("-t") + 1] == "3"


@pytest.mark.parametrize("seconds", [0, -1, 9999])
def test_record_screen_refuses_bad_lengths(seconds):
    assert automation.record_screen(seconds, "x")["ok"] is False


def test_record_screen_reports_a_failed_recording(tmp_path, monkeypatch):
    monkeypatch.setattr(automation, "videos_folder", lambda: tmp_path)
    monkeypatch.setattr(automation, "_ffmpeg", lambda: "ffmpeg.exe")
    monkeypatch.setattr(automation.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "no device"))
    out = automation.record_screen(2, "x")
    assert out["ok"] is False and "failed" in out["error"]


def test_screenshot_is_saved_as_png(tmp_path, monkeypatch):
    from PIL import Image, ImageGrab
    monkeypatch.setattr(ImageGrab, "grab", lambda **k: Image.new("RGB", (40, 30), "white"))
    monkeypatch.setattr(automation, "pictures_folder", lambda: tmp_path)
    out = automation.take_screenshot("my shot")
    assert out["ok"] and (tmp_path / "my shot.png").exists()


# --- keyboard shortcuts ---------------------------------------------------------------------
@pytest.mark.parametrize("keys", ["win+shift+r", "ctrl+s", "enter", "esc", "f5", "ctrl+shift+s", "alt+left"])
def test_normal_shortcuts_are_accepted(keys):
    codes, normal = automation.parse_keys(keys)
    assert codes and normal == keys


@pytest.mark.parametrize("keys", ["alt+f4", "win+l", "win+r", "ctrl+alt+delete", "ctrl+shift+esc", "win+x", "alt+tab",
                                  "banana", "ctrl", "", "a+b", "ctrl+alt+shift+win+x"])
def test_dangerous_or_invalid_shortcuts_are_refused(keys):
    with pytest.raises(ValueError):
        automation.parse_keys(keys)


def test_press_keys_only_works_in_allowed_windows():
    out = automation.press_keys("Google Chrome", "ctrl+t")
    assert out["ok"] is False and "allowed window" in out["error"]
    assert automation.list_controls("Google Chrome")["ok"] is False


def test_ui_tools_are_checked_by_the_policy_gate():
    from safety.policy import PolicyError, check_step
    with pytest.raises(PolicyError):
        check_step("computer_use", "press_keys", {"window": "Google Chrome", "keys": "ctrl+t"})
    assert check_step("computer_use", "press_keys", {"window": "Snipping Tool", "keys": "ctrl+n"})


# --- one approval per window for the rest of the task ---------------------------------------
def test_an_approved_window_can_be_operated_without_asking_again():
    granted = ["snipping tool"]
    assert autopilot._ui_granted(granted, "click_control", {"window": "Snipping Tool", "control_name": "Save"})
    assert autopilot._ui_granted(granted, "press_keys", {"window": "snipping tool", "keys": "ctrl+s"})
    assert not autopilot._ui_granted(granted, "press_keys", {"window": "Notepad", "keys": "ctrl+s"})
    assert not autopilot._ui_granted(granted, "record_screen", {"seconds": 3})          # a recording always asks
    assert not autopilot._ui_granted([], "click_control", {"window": "Snipping Tool", "control_name": "Save"})


# --- routing --------------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "can u open snipping tool and start a recording of the desktop screen for 3 seconds and save it as first video",
    "record my screen for 5 seconds", "take a screenshot of my screen"])
def test_screen_tasks_go_to_the_general_agent(text):
    assert fast_route(text) == {"agent": "autopilot", "question": ""}


def test_how_to_screen_record_is_still_a_question():
    assert fast_route("how to screen record")["agent"] == "howto"
    assert (fast_route("how do I take a screenshot") or {}).get("agent") != "autopilot"
