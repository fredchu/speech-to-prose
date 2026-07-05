# Changelog

All notable changes to `speech-to-prose` are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions track the `SKILL.md` frontmatter.

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
