# Changelog

All notable changes to `speech-to-prose` are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions track the `SKILL.md` frontmatter.

## 0.5.0 - 2026-07-06

### Features
- **Noun verification pass (Step 3.5).** Proper nouns that contradict their context
  (companies, tickers, people, jargon) are collected into a sidecar during prose
  integration, then verified through four evidence layers before any fix is applied:
  L0 whole-transcript phonetic cross-reference first (the same entity is usually
  mentioned more than once and mis-recognized differently each time), L1 local sources
  (speaker glossary / slide OCR terms), L2 neutral web search — **the model's guess is
  barred from queries** (hypothesis-driven search only confirms itself), L3 keep the
  `〔註：…〕` mark rather than guess. Confirmed fixes are applied per-occurrence
  (context-substring locating, never whole-file substitution) and written back to the
  speaker glossary with provenance comment lines.
- `scripts/noun_xref.py`: L0 phonetic-variant scanner. Latin-token fuzzy matching with
  Mandarin-accent confusion folding (v/w→b, catches VIAVI→"BIAB"), merged windows of
  fragmented tokens (catches "vr a vr"), weak Chinese char-overlap fallback. Recall over
  precision — output feeds an LLM judgment step. Stdlib only; tests in `scripts/tests/`.
- Sidecar contract: single JSON envelope per segment; long-audio segment subagents bind
  the sidecar to their returned prose text with SHA-256 (stale sidecars from retries are
  detected and dropped); sidecar content never enters `prose.md`, and Step 3.5 completes
  before the coverage gate and timestamping.

### Docs
- README (EN/zh): pipeline line + noun-verification section + test instructions.
- Field-validated on a 7-hour finance livestream: 138 unique flagged nouns, ~100
  applied fixes incl. KISS→KEYS, "one room"→萬潤, asyna→Synaptics; design converged
  through 5 adversarial review rounds + 2 implementation verify rounds (codex).

## 0.4.1 - 2026-07-05

### Fixes
- EPUB chapters: `prose_to_epub.py` now passes `--toc --split-level=2`, so `## ` section
  headings in the prose become navigable chapters with a table of contents. Prose with only
  a single `#` title and no `##` headings produced a chapterless single-file EPUB.
- SKILL.md: Step 3 now instructs inserting `## [HH:MM:SS] topic` section headings at topic
  boundaries for chapter navigation. Removed a duplicated Chinese dual-ASR block that had been
  left under the English branch.

## 0.4.0 - 2026-07-05

### Features
- **Bilingual output for non-Chinese audio (default).** English (or other non-Chinese)
  audio is transcribed with Whisper large-v3 and rendered as a source-on-top /
  Traditional-Chinese-below bilingual document, timestamped per paragraph.
- `prose_timestamp.py --bilingual`: aligns and timestamps only the source-language line
  of each block, leaves the translation line untouched, and adds a Markdown hard break so
  the pairing renders source-over-translation (incl. EPUB). CJK-dominant first line is
  treated as malformed structure and skipped (fail-safe).
- English ASR path documented with **mandatory anti-hallucination flags**
  (`--condition-on-previous-text False --hallucination-silence-threshold 2`) — the default
  Whisper decode can loop-hallucinate on trailing/silent audio and silently drop content.

### Docs
- SKILL.md: language-detection step, English branch, bilingual assembly, boundaries.
  README updated (English + 繁體中文).

## 0.3.0 - 2026-07-04

### Features
- **Per-paragraph timestamps (default on).** `scripts/prose_timestamp.py` aligns each
  paragraph to the ASR timeline via non-poisoning n-gram cluster anchoring + monotonic
  backbone + interpolation, prepending an approximate `[HH:MM:SS]`. Idempotent; fail-closed
  when anchor coverage is too low (`--min-coverage`, `--force`); `--fmt ms` for short clips.
- **Optional EPUB** (`scripts/prose_to_epub.py`, `--epub`): timestamped-paragraph e-book
  via pandoc, fail-closed when pandoc is missing or output is malformed.
- Skip code fences and YAML front matter when timestamping.

## 0.2.0

### Features
- `--local` prose mode: offline LLM integration (default gemma4:26b) with a deterministic,
  fail-closed runner that never silently falls back to the cloud.

## 0.1.0

### Features
- Initial release: recording/video/YouTube → faithful Traditional-Chinese prose, dual-ASR
  (Breeze + VibeVoice) cross-referencing, fidelity modes, and a prose coverage gate.
