#!/usr/bin/env python3
"""prose_timestamp.py — 把 ASR srt 的時間軸對齊到 speech-to-prose 的散文 md，
在每個內文段落開頭就地加上 `[HH:MM:SS]　` 時間戳。

用法:
    prose_timestamp.py <srt> <md> [--fmt hms|ms] [--dry-run]

演算法: srt 字元流 + 每字時間 → 段落 8-gram 叢集錨定（非中毒游標）
→ 單調骨架（丟倒退離群）→ 相鄰錨點間按段落序內插 → 單調 clamp。
冪等: 段落若已有時間戳前綴會先剝除再重加，可安全 re-run。
"""
import re
import sys
import argparse

TS_PREFIX_RE = re.compile(r"^\[\d+:\d{2}(?::\d{2})?\][　 ]*")


def parse_srt(path):
    txt = open(path, encoding="utf-8").read()
    cues = []
    for b in re.split(r"\n\s*\n", txt.strip()):
        ls = b.splitlines()
        ti = next((i for i, l in enumerate(ls) if "-->" in l), None)
        if ti is None:
            continue
        m = re.match(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", ls[ti])
        if not m:
            continue
        h, mn, s, ms = map(int, m.groups())
        cues.append((h * 3600 + mn * 60 + s + ms / 1000, "".join(ls[ti + 1:])))
    return cues


def norm(s):
    return re.sub(r"[^一-鿿A-Za-z0-9]", "", s)


def is_cjk_dominant(s):
    """中文字數 > 拉丁字母數 → 視為譯文行(非來源語)。用於 bilingual 結構防呆。"""
    cjk = len(re.findall(r"[一-鿿]", s))
    latin = len(re.findall(r"[A-Za-z]", s))
    return cjk > latin


def build_stream(cues):
    chars, pos = [], []
    for start, text in cues:
        for ch in norm(text):
            chars.append(ch)
            pos.append(start)
    return "".join(chars), pos


def fmt_time(sec, mode):
    sec = int(round(sec))
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    if mode == "ms":
        return f"{h * 60 + m:02d}:{s:02d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


G = 8


def cluster_anchor(stream, q, floor):
    grams = {q[i:i + G] for i in range(0, len(q) - G + 1, 2)}
    hits = []
    for g in grams:
        idx = stream.find(g, floor)
        if idx != -1:
            hits.append(idx)
    if len(hits) < 3:
        return None
    hits.sort()
    span = max(200, int(len(q) * 1.5))
    best = None
    for a in range(len(hits)):
        lo = hits[a]
        k = a
        while k < len(hits) and hits[k] <= lo + span:
            k += 1
        if best is None or (k - a) > best[1]:
            best = (lo, k - a)
    return best if best and best[1] >= 3 else None


def align(stream, pos, norm_paras):
    n = len(norm_paras)
    anchor = [None] * n
    floor = 0
    for k, q in enumerate(norm_paras):
        if len(q) < G + 4:
            continue
        r = cluster_anchor(stream, q, floor)
        if r:
            anchor[k] = pos[r[0]]
            floor = r[0]  # 只在錨定成功時前進，避免中毒
    # 單調骨架: 丟棄倒退離群
    backbone, last = [], -1.0
    for k, t in enumerate(anchor):
        if t is None:
            continue
        if t < last - 5:
            anchor[k] = None
            continue
        backbone.append((k, max(t, last)))
        last = max(t, last)
    # 內插
    final = [None] * n
    if backbone:
        for k in range(0, backbone[0][0]):
            final[k] = backbone[0][1]
        for (k0, t0), (k1, t1) in zip(backbone, backbone[1:]):
            final[k0] = t0
            for k in range(k0 + 1, k1):
                final[k] = t0 + (t1 - t0) * ((k - k0) / (k1 - k0))
        for k in range(backbone[-1][0], n):
            final[k] = backbone[-1][1]
    run = 0.0
    for k in range(n):
        if final[k] is None:
            final[k] = run
        final[k] = max(final[k], run)
        run = final[k]
    return final, sum(1 for a in anchor if a is not None)


def collect_blocks(lines):
    """把內文分成「空行分隔的區塊」(每個區塊 = 連續非空內文行的行號 list)。
    跳過空行、# 標題、> blockquote/前言、``` code fence 區塊、開頭 YAML front matter。"""
    blocks = []
    cur = []
    in_fence = False
    in_front = False
    for i, line in enumerate(lines):
        s = line.strip()
        if i == 0 and s == "---":
            in_front = True
            continue
        if in_front:
            if s == "---":
                in_front = False
            continue
        if s.startswith("```") or s.startswith("~~~"):
            in_fence = not in_fence
            if cur:
                blocks.append(cur)
                cur = []
            continue
        if in_fence:
            continue
        if not s or s.startswith("#") or s.startswith(">"):
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append(i)
    if cur:
        blocks.append(cur)
    return blocks


def collect_body_indices(lines):
    """回傳所有內文行號 (flat)。"""
    return [i for blk in collect_blocks(lines) for i in blk]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("srt")
    ap.add_argument("md")
    ap.add_argument("--fmt", choices=["hms", "ms"], default="hms")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-coverage", type=float, default=0.5,
                    help="錨定段落佔比低於此值 → fail-closed 不寫（預設 0.5）")
    ap.add_argument("--force", action="store_true",
                    help="覆蓋率過低仍強制寫入")
    ap.add_argument("--bilingual", action="store_true",
                    help="對照模式: 每空行分隔區塊只對首行(來源語)對齊加戳+硬換行，"
                         "其餘行(譯文)原樣保留")
    args = ap.parse_args()

    cues = parse_srt(args.srt)
    if not cues:
        print(f"ERROR: srt 無有效字幕: {args.srt}", file=sys.stderr)
        return 2
    stream, pos = build_stream(cues)
    if not stream:
        print(f"ERROR: srt 抽不出文字: {args.srt}", file=sys.stderr)
        return 2

    lines = open(args.md, encoding="utf-8").read().splitlines()
    blocks = collect_blocks(lines)
    if not blocks:
        print(f"ERROR: md 無內文段落: {args.md}", file=sys.stderr)
        return 2
    # bilingual: 每區塊只取首行(來源語)對齊；否則每行都是一段
    if args.bilingual:
        target_idx = []
        has_secondary = {}
        skipped = 0
        for blk in blocks:
            head = TS_PREFIX_RE.sub("", lines[blk[0]])
            # 防呆: 首行若中文為主 → 結構畸形(譯文誤當來源語)，跳過不加戳，不汙染
            if is_cjk_dominant(head):
                skipped += 1
                continue
            target_idx.append(blk[0])
            has_secondary[blk[0]] = (len(blk) > 1)
        if skipped:
            print(f"WARN: bilingual 有 {skipped} 個區塊首行為中文為主，"
                  f"判定結構畸形已跳過（來源語應在上、譯文在下）", file=sys.stderr)
        if not target_idx:
            print("ERROR: bilingual 找不到任何來源語段落", file=sys.stderr)
            return 2
    else:
        target_idx = [i for blk in blocks for i in blk]
        has_secondary = {}

    # 冪等: 先剝除既有前綴後再對齊
    stripped = [TS_PREFIX_RE.sub("", lines[i]) for i in target_idx]
    norms = [norm(s) for s in stripped]

    final, n_anchor = align(stream, pos, norms)
    coverage = n_anchor / len(target_idx)

    nonmono = sum(1 for a, b in zip(final, final[1:]) if b < a)
    print(f"段數={len(target_idx)} 錨點={n_anchor} 覆蓋率={coverage:.2f} "
          f"首={fmt_time(final[0], 'hms')} 尾={fmt_time(final[-1], 'hms')} "
          f"非單調={nonmono}{' [bilingual]' if args.bilingual else ''}")

    # fail-closed: 錨點太少 → 對齊不可信，不做靜默 [00:00:00] 汙染
    if not args.force and (n_anchor == 0 or coverage < args.min_coverage):
        print(f"ERROR: 錨定覆蓋率 {coverage:.2f} < {args.min_coverage} "
              f"（或零錨點）→ 對齊不可信，未寫入。"
              f"請確認 srt 與 md 對應；確定要寫用 --force。", file=sys.stderr)
        return 2

    for j, i in enumerate(target_idx):
        prefix = f"[{fmt_time(final[j], args.fmt)}]　"
        # bilingual 且該區塊有譯文行 → 尾端補 markdown 硬換行讓譯文渲染在下方
        suffix = "  " if (args.bilingual and has_secondary.get(i)) else ""
        lines[i] = prefix + stripped[j].rstrip() + suffix

    if args.dry_run:
        return 0
    open(args.md, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
