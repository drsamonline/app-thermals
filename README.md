# Thermals

<!-- shot:start -->

![Screenshot](docs/shot.png)

<!-- shot:end -->

**What each classical source actually says about a remedy's thermal reaction — in its own words, with the source named — and where those sources do not say the same thing.**

Live: https://drsamonline.github.io/app-thermals/

Offline, no accounts, no server, no network at any point. One page, no build step, no dependencies beyond the estate's own kits.

## What it does

Look up a remedy and read what every bundled source says about its thermal reaction, each statement quoted verbatim against the source that wrote it. Above the quotes sits a summary **computed from those quotes**:

| Summary | When |
|---|---|
| `sources agree (n)` | two or more bundled sources speak, and all of them point the same way |
| `sources disagree` | two or more speak and they point opposite ways |
| `one source only` | exactly one bundled source speaks. **This is the common case and is never agreement** |
| `unclassified` | no bundled source carries a thermal statement for that remedy. It carries no quote and no summary |

A **dated note** is a temporary shift — an acute fever, a pregnancy, a proving — with an end date. When the date passes the note stays visible, marked expired, and the constitutional quotes are untouched.

## What it must not do, and does not

- It never assigns, derives, averages or infers a thermal state. One row is one remedy, one source, one verbatim sentence.
- It never derives a classification from rubric counts or grades.
- It never selects or prescribes a remedy, and it does not decide anyone's thermal state.
- `ambithermal` is not a state this app looks for: no bundled source uses the word (0 occurrences in the JSON books, 0 across the 344 Open Materia Medica pages).

## The extraction rule (it ships, because the row count is a property of it)

A **thermal statement** is a sentence in a source's own words containing one of these phrases, as whole words, case-insensitively:

`chilly` · `chilliness` · `always cold` · `feels cold` · `feels hot` · `cold feeling` · `cold-blooded` · `warm-blooded` · `always warm` · `cold constitution` · `hot constitution` · `warm constitution` · `cold patient` · `hot patient`

Then:

1. **Modality lines and modality sections are excluded.** A sentence under a heading containing "Modalit", or one that opens with "Worse" or "Better", is what changes a state, not what the state is.
2. **Fragments under 12 characters and paragraphs over 400 are excluded.** 12 and not 20 because *"Chilly disposition."* — Jahr 1847, Cistus canadensis — is 19 characters and is exactly the statement this app exists to show.
3. **The sentence is kept verbatim.** Whitespace is normalised; nothing else is paraphrased, reordered, merged or trimmed.
4. The set is deliberately narrow. A bare *cold* or *heat* is **not** in it: in this corpus those words are overwhelmingly about water, air, a room, a modality or a fever episode, and quoting them as the patient's thermal reaction would be the app putting a meaning into the source's mouth.

`tools/extract.py` applies the rule; `tools/make-bundle.py` turns the result into the bundle the page loads; `test-node.js` checks the rule's output.

## The data, measured (2026-11-01)

| | |
|---|---|
| quoted sentences (rows) | **168** |
| remedies in the index | **380** |
| remedies with at least one statement | **125** |
| remedies with no statement in any source (`unclassified`) | **255** |
| sources | **3** |
| remedies carried by two sources | **4** — Cistus canadensis, Kali carbonicum, Nux vomica, Sulphur |

Sources bundled:

- **Open Materia Medica** — 344 remedy pages, © Dr. Sohil Momin, BHMS, 2026. Quoted with permission of the copyright holder, who is the owner of this repository.
- **Manual of Homoeopathic Medicine, Part I: Materia Medica** — G. H. G. Jahr, trans. P. F. Curie, 1847 (public domain).
- **Homoeopathic Therapeutics** — James B. Bell, 1906 (public domain).

Both books come from `drsamonline/homoeopathic-materia-medica-repertory-json`, whose `repertory/repertorium-publicum-2008/` is GPL v3 and is **not** bundled.

### Honest limits, stated rather than papered over

- **There is no genuine disagreement in the bundle today.** Every two-source remedy points the same way (both say the patient is cold), so `sources disagree` is real machinery with nothing to fire on yet. It fires the day a third source lands that reads the other way. Nothing was invented to make the demo look better.
- **The books are OCR transcriptions and some of their remedy names are damaged** ("a8arum eiiropeijii", "ntjx vomica"). Those names are kept exactly as printed and do not join across sources — a name we cannot read is not a name we may correct. Book remedies enter the index only when they carry a statement.
- **No page numbers.** The JSON books carry no `page` field on any record and the Open Materia Medica pages are not paginated, so a row names its source and its chapter and never a page. A guessed page number is a fabricated citation.
- 255 of the 380 indexed remedies are `unclassified`. That is the honest answer for a corpus this size, not a gap to fill by inference.

## Correcting the names (added 2026-11-01)

The two transcribed books are OCR. Some of their remedy names arrive damaged
("NTJX VOMICA", "A8ARUM EIIROPEIJII"), some arrive merged with the next remedy
("Hepar Sulphuris. Haracleum Spondilium"), and some are really the book's own
chapter headings. Quoting a source under a name it never printed is a small lie, and
it stops the app joining two sources for the same remedy, so `tools/names.py` corrects
what can be proven and says so where it cannot.

**The authorities, all free and all named in `data/reference-names.json`:**

1. **Open Materia Medica** — the 344 remedy names curated in this estate (no OCR in them).
2. The **repertory remedy index** in the same JSON repository.
3. The **remedy index of Jahr's Manual of Homoeopathic Medicine (1847) as scanned by the
   Internet Archive** — [manualhomopathi01jahrgoog](https://archive.org/details/manualhomopathi01jahrgoog) —
   the same book, a second scan, with a numbered alphabetical index of every remedy.

**The rule, in order:** exact → merged (two known names run together) → the entry's own
abbreviation names one curated remedy → a curated name at ≥85% letter similarity *that
also sits in the right alphabetical slot* → otherwise **unresolved, kept exactly as
printed**. A readable name the reference simply does not carry is **not** an error and
is kept as printed; only visible OCR damage is ever corrected.

| outcome | entries |
|---|---|
| confirmed — the printed name is already a known name | **79** |
| corrected from a named authority | **17** |
| readable, kept as printed (a remedy the reference does not carry) | **132** |
| unreadable, kept as printed and marked `spelling unconfirmed` in the app | **64** |
| **not bundled** — the transcription ran two remedies together, so no sentence can be attributed | **10** |

Every correction carries its evidence in `data/name-map.json`, and the app shows the name
the transcription printed next to the correction, so a reader can check it rather than
take it on trust. Two rules the tests enforce: a correction may never be justified by a
guess, and an entry the transcription merged with another remedy is **withheld** rather
than attributed to either.

Two honest notes. The 64 unresolved names include 16 that carry a statement the app
shows — they are visibly marked, and I did not guess them: for Bell's *Homoeopathic
Therapeutics* the Internet Archive holds the diarrhoea volume under that author, not the
general one, so no second scan of that book was available to confirm them. And the
corrections changed the *index*, not the quotes: none of the corrected entries happened
to carry a thermal statement, so the row count moved only because 4 sentences from
merged entries were withheld (172 → 168).

## Run it

```bash
node test-node.js          # 78 assertions
python3 -m http.server -d docs 8000   # or just open docs/index.html
```

Regenerating the data needs the two source repositories next to each other:

```bash
python3 tools/names.py --fetch      # rebuild the name reference (needs archive.org)
python3 tools/names.py              # apply it -> data/name-map.json
python3 tools/extract.py src/open-materia-medica src/materia-medica-json data
python3 tools/make-bundle.py
node test-node.js
```

## Layout

```
docs/index.html            the app (one page, no build step)
docs/thermals.js           the logic the page and the tests both use
docs/data/bundle.js        the bundle: rows, remedies, the rule, the counts
docs/vendor/               web-kit, search-kit, case-kit, export-kit (vendored)
thermals.js, vendor/       the same two, at the root, for `node test-node.js`
data/rows.json             the extracted rows
data/remedies.json         the remedy index
tools/extract.py           the extraction rule
tools/names.py             the name-correction rule and its authorities
data/name-map.json         every correction, with the evidence for it
data/reference-names.json  the three authorities, with their URLs
tools/make-bundle.py       bundle builder
test-node.js               the suite
```

## Kits

- **web-kit** — storage, and whether a write actually landed
- **search-kit** — ranked lookup across the quoted sentences
- **case-kit** — the dated-override record shape
- **export-kit** — getting the bundle and the notes off the device

## Licence

PolyForm Noncommercial 1.0.0 — see `LICENSE`. The public-domain materia medica text inside stays public domain.
