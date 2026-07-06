#!/usr/bin/env python3
import argparse
import difflib
import json
import os
import re
import sys


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9&+.-]*")
SRT_TS_RE = re.compile(r"(\d{2}:\d{2}:\d{2}),\d{3}\s+-->\s+")


def norm_latin(value):
    folded = re.sub(r"[^a-z0-9]", "", value.lower())
    return folded.translate(str.maketrans({"v": "b", "w": "b"}))


def raw_norm(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def has_ascii_letter(value):
    return bool(re.search(r"[A-Za-z]", value))


def parse_srt(path):
    text = open(path, encoding="utf-8").read()
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        ts_line_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if ts_line_index is None:
            continue
        match = SRT_TS_RE.search(lines[ts_line_index])
        if not match:
            continue
        body = " ".join(lines[ts_line_index + 1 :]).strip()
        if body:
            yield {"file": path, "ts": match.group(1), "text": body}


def parse_text(path):
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if text:
                yield {"file": path, "ts": None, "text": text}


def iter_segments(paths):
    for path in paths:
        parser = parse_srt if os.path.splitext(path)[1].lower() == ".srt" else parse_text
        yield from parser(path)


def token_candidates(text):
    tokens = TOKEN_RE.findall(text)
    seen = set()
    for token in tokens:
        if token not in seen:
            seen.add(token)
            yield token

    for size in range(2, 5):
        for index in range(0, len(tokens) - size + 1):
            window = tokens[index : index + size]
            if not all(0 < len(raw_norm(token)) <= 3 for token in window):
                continue
            merged = "".join(window)
            if merged not in seen:
                seen.add(merged)
                yield merged


def chinese_score(term, text):
    # 弱召回優先的中文 fallback（無拼音引擎）；升級路徑是真正的音近比對器
    term_chars = [char for char in term if not char.isspace()]
    text_chars = [char for char in text if not char.isspace()]
    bigrams = {term_chars[i] + term_chars[i + 1] for i in range(len(term_chars) - 1)}
    text_bigrams = {text_chars[i] + text_chars[i + 1] for i in range(len(text_chars) - 1)}
    overlap = len(bigrams & text_bigrams)
    shared = len(set(term_chars) & set(text_chars))
    if overlap >= 1 or shared >= 2:
        return max(overlap / max(len(bigrams), 1), shared / max(len(set(term_chars)), 1))
    return 0.0


def best_latin_match(term, text):
    target = norm_latin(term)
    if not target:
        return None
    best = None
    for token in token_candidates(text):
        normalized = norm_latin(token)
        if not normalized:
            continue
        score = difflib.SequenceMatcher(None, target, normalized).ratio()
        exact = raw_norm(token) == raw_norm(term)
        if score >= 0.45 and (best is None or score > best["score"]):
            best = {"matched": token, "score": score, "exact": exact}
    return best


def candidates_for_term(term, segments, max_per_term):
    results = []
    latin = has_ascii_letter(term)
    for segment in segments:
        if latin:
            match = best_latin_match(term, segment["text"])
            if not match:
                continue
        else:
            score = chinese_score(term, segment["text"])
            if score <= 0:
                continue
            match = {"matched": term, "score": score, "exact": term in segment["text"]}
        results.append(
            {
                "file": segment["file"],
                "ts": segment["ts"],
                "text": segment["text"],
                "matched": match["matched"],
                "score": round(match["score"], 4),
                "exact": match["exact"],
            }
        )
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:max_per_term]


def scan(terms, paths, max_per_term):
    segments = list(iter_segments(paths))
    return {
        "terms": [
            {"term": term, "candidates": candidates_for_term(term, segments, max_per_term)}
            for term in terms
        ]
    }


def print_human(envelope):
    for term_block in envelope["terms"]:
        print(term_block["term"])
        for item in term_block["candidates"]:
            ts = item["ts"] if item["ts"] is not None else "-"
            exact = " exact" if item["exact"] else ""
            print(f"  {item['score']:.4f}{exact} {item['file']}:{ts} {item['matched']} :: {item['text']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Find likely ASR noun cross-references.")
    parser.add_argument("--term", action="append", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-per-term", type=int, default=20)
    parser.add_argument("scanfiles", nargs="+")
    args = parser.parse_args(argv)

    if args.max_per_term < 1:
        parser.error("--max-per-term must be >= 1")

    envelope = scan(args.term, args.scanfiles, args.max_per_term)
    if args.json:
        print(json.dumps(envelope, ensure_ascii=False, indent=2))
    else:
        print_human(envelope)
    return 0


if __name__ == "__main__":
    sys.exit(main())
