# Changelog

## 1.1.0 — 2026-11-01

Remedy names in the two transcribed books are corrected where a named authority confirms
the reading, and left exactly as printed where none does.

- New `tools/names.py`, with three free authorities recorded in `data/reference-names.json`:
  Open Materia Medica's 344 names, the repertory index, and the Internet Archive's numbered
  index of Jahr's *Manual of Homoeopathic Medicine* (1847).
- Of 302 transcribed entries: 79 confirmed, 17 corrected, 132 readable and kept as printed,
  64 unreadable and marked `spelling unconfirmed`, 10 withheld because the transcription
  ran two remedies together.
- Every correction carries its evidence in `data/name-map.json`; the app shows the name the
  transcription printed next to the correction.
- Sentences from merged entries are no longer bundled: one row must be one remedy, one
  source, one sentence. Rows 172 → 168; two-source remedies remain 4.
- 5 new test groups; the suite now runs 559 assertions.

## 1.0.0 — 2026-11-01

First release, built from `QUEUE/app-thermals.md` v3 (master-list #129).

- 172 quoted sentences from 3 sources; 382 remedies indexed, 127 classified, 255 unclassified.
- Summary computed from the quotes: `sources agree (n)`, `sources disagree`, `one source only`, `unclassified`.
- Dated notes with an expiry, kept separate from the constitutional quotes.
- Search over the quoted sentences, so every hit carries the source that said it.
- Export of the whole bundle and the notes.
- 78 assertions in `test-node.js`, checked to bite.
