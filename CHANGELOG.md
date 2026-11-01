# Changelog

## 1.4.0 — 2026-11-01

The second-scan method run over every entry, and a decision not to let it rename.

- `tools/second-scan.py` indexes the second scan by line, locates each entry's own sentences,
  reads the heading above them and repairs that heading by nearest known name. 61 entries
  aligned, 37 headings repaired with a confidence.
- It is a **cross-check, not a renamer**: it agrees with 18 names and flags 43, because it is
  confidently wrong on cases like `PHO.SPHOBU8` → petroleum, `PlirMBUM` → podophyllum,
  `BORAX` → bovista and `SULPHURIC ACID` → sulphur (stock symptom phrases, repeated across
  remedies). Recorded in `data/name-crosscheck.json`.
- `text_damage` now marks a quoted sentence that carries a swallowed page number, a broken
  word or a stray mark — 31 of the 55 book rows. The quote stays verbatim; the page says so.
- 541 assertions.

## 1.3.0 — 2026-11-01

The worst names are settled from the entry's own symptoms, matched in a second scan of the
same book.

- Corrected my own 1.2.0 claim: the JSON book transcribed here *is* Bell's diarrhoea volume,
  so the Internet Archive's `in.ernet.dli.2015.94901` is a second scan of the same book, not
  a different one. `tools/align-bell.py` indexes it and aligns each entry by its symptom text.
- Nine entries settled this way, each recorded with its archive.org line number:
  `JETIICSA CYlTAPIITJtt` = Aethusa cynapium, `FJ.ATERIIIM` = Ferrum metallicum,
  `N1U€£A` = Silicea terra, `BOliETUlS` = Boletus laricis, `AliOE` = Aloe socotrina,
  `GifTAPHITEN` = Graphites, `I^YCOPODICIW` = Lycopodium clavatum,
  `ItlRYTA CiRBOlVICA` = Baryta carbonica, `SABABUUt` = Sabadilla officinalis.
- `XlNOIB£R` withdrawn: it is a fragment of the book's own repertory index, not a remedy.
- Two-source remedies 6 → 11; rows 167 → 164; unresolved names 40 → 30.
- 535 assertions.

## 1.2.0 — 2026-11-01

The name matcher now reads the OCR instead of normalising it away, on the owner's
instruction to look for the nearest similar name with a minor difference.

- Matching runs over the plausible readings of the damaged letters (`8`→B or S, `1`→L or I,
  `4`→A, `€`→E, `£`→L) and uses a partial ratio as well as a whole-string one.
- A correction is accepted only with a clear winner: the right alphabetical slot and a
  margin over the runner-up. Where two readings are nearly as close, the name stays as printed.
- The archive.org index is repaired by the same rule it applies (its `Sulphuris ad` is
  `Sulphuricum acidum`), so a damaged reference can no longer cap the result.
- Four readings supplied by the owner are recorded in `data/name-overrides.json`:
  `SF.PIA` = Sepia, `KAT.l CARBONICUM` = Kali carbonicum, `KAI4I BROMICUM` = Kali bromatum,
  `Sulphuris ad` = Sulphuricum acidum.
- 302 entries: 79 confirmed, 24 corrected, 132 kept as printed, 40 unresolved, 27 withheld
  as merged. Two-source remedies 4 → 6 (Carbolicum acidum and Phosphorus now join).
- 560 assertions.

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
