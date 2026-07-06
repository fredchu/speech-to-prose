#!/usr/bin/env python3
import json
import os
import subprocess
import sys


# 佈局：scripts/noun_xref.py 與 scripts/tests/（本檔）同屬 scripts/ 之下
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(SCRIPTS_DIR, "noun_xref.py")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SRT = os.path.join(FIXTURES, "sample.srt")
TXT = os.path.join(FIXTURES, "sample_asr.txt")


def run(*args):
    output = subprocess.check_output(
        [sys.executable, SCRIPT, *args, SRT, TXT, "--json"],
        text=True,
    )
    return json.loads(output)


def candidates(data, term):
    return next(item for item in data["terms"] if item["term"] == term)["candidates"]


def test_kiss_keys_and_exact_and_ts():
    items = candidates(run("--term", "KISS"), "KISS")
    keys = [item for item in items if item["matched"].lower() == "keys" and item["ts"] == "05:19:18"]
    assert keys, items

    exact = [item for item in items if item["text"].startswith("KISS") and item["ts"] == "05:14:57"]
    assert exact and exact[0]["exact"] is True, items

    txt_keys = [item for item in items if item["file"].endswith("sample_asr.txt") and item["matched"].lower() == "keys"]
    assert txt_keys and txt_keys[0]["ts"] is None, items


def test_biab_fragment_and_viavi():
    items = candidates(run("--term", "BIAB"), "BIAB")
    assert any(item["matched"].lower() == "vravr" and "vr a vr" in item["text"] for item in items), items
    assert any(item["matched"] == "VIAVI" and item["file"].endswith("sample_asr.txt") for item in items), items


def test_max_per_term_caps_output():
    items = candidates(run("--term", "KISS", "--max-per-term", "1"), "KISS")
    assert len(items) == 1, items


if __name__ == "__main__":
    test_kiss_keys_and_exact_and_ts()
    test_biab_fragment_and_viavi()
    test_max_per_term_caps_output()
