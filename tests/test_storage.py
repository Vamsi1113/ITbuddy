import json
import os
import time

import pytest

from tools import storage


@pytest.fixture
def temp_area(tmp_path, monkeypatch):
    """An allowed temp folder and a neighbouring folder that must never be touched."""
    allowed = tmp_path / "allowed_temp"
    outside = tmp_path / "documents"
    (allowed / "sub").mkdir(parents=True)
    outside.mkdir()
    old = time.time() - 3 * 3600
    for path, size in ((allowed / "old.tmp", 4000), (allowed / "sub" / "old2.log", 6000), (outside / "report.docx", 5000)):
        path.write_bytes(b"x" * size)
        os.utime(path, (old, old))
    (allowed / "fresh.tmp").write_bytes(b"y" * 1000)  # modified just now: may be in use
    monkeypatch.setattr(storage, "allowed_temp_folders", lambda: [allowed.resolve()])
    return allowed, outside


def test_disk_usage():
    out = storage.get_disk_usage()
    assert out["ok"] is True and out["drives"]
    c = out["drives"][0]
    assert c["total_gb"] > 0 and 0 <= c["used_percent"] <= 100 and c["free_gb"] >= 0
    assert len(json.dumps(out)) <= 1500


def test_find_large_temp_folders_counts_only_old_files_as_cleanable(temp_area):
    out = storage.find_large_temp_folders()
    folder = out["folders"][0]
    assert folder["files"] == 3
    assert folder["cleanable_files"] == 2


def test_clean_deletes_only_old_files_inside_allowed_folders(temp_area):
    allowed, outside = temp_area
    out = storage.clean_approved_temp_files()
    assert out["ok"] is True and out["files_deleted"] == 2
    assert not (allowed / "old.tmp").exists() and not (allowed / "sub" / "old2.log").exists()
    assert (allowed / "fresh.tmp").exists()         # too new, left alone
    assert (outside / "report.docx").exists()       # outside the allow-list, never touched


def test_clean_does_not_follow_links_out_of_the_folder(temp_area):
    allowed, outside = temp_area
    link = allowed / "link_to_documents"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks needs Developer Mode or admin rights")
    storage.clean_approved_temp_files()
    assert (outside / "report.docx").exists()


def test_real_allowed_folders_come_from_config():
    folders = [str(f).lower() for f in storage.allowed_temp_folders()]
    assert folders and all("temp" in f for f in folders)
