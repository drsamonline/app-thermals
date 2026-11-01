#!/usr/bin/env python3
"""Correct the OCR-damaged remedy names in the two transcribed books.

WHY THIS EXISTS
The books come from `homoeopathic-materia-medica-repertory-json`, whose remedy
names are OCR transcriptions. Some arrive damaged ("NTJX VOMICA", "A8ARUM
EIIROPEIJII", "C01X7H1CUII1"), some arrive merged with the next remedy
("Agaricus Muscarius Agnus Castus"), and some appear several times. Quoting a
source under a name the source never printed is a small lie, and it also stops
the app joining two sources for the same remedy.

WHAT IT MAY AND MAY NOT DO
It corrects a name only when an independent authority confirms the reading. It
never guesses a name to make the list look tidy: an unconfirmed name stays
exactly as printed and is marked `unresolved`, and the app shows it as printed.

THE AUTHORITIES, all free and all named in data/reference-names.json
  1. Open Materia Medica — the 344 remedy names curated in this estate.
  2. The repertory remedy index in the same JSON repository (resolved names).
  3. The remedy index of Jahr's *Manual of Homoeopathic Medicine* (1847) as
     OCR'd by the Internet Archive, item `manualhomopathi01jahrgoog`
     (https://archive.org/details/manualhomopathi01jahrgoog) — the same book, a
     different scan, and a numbered alphabetical index of every remedy in it.

THE RULE, in order
  a. exact        the printed name is already a known name            -> ok
  b. merged       the printed name is two known names run together    -> merged
  c. abbrev       the entry's own abbreviation pins one known name    -> corrected
  d. fuzzy        one known name is close, AND it sits in the right
                  alphabetical slot between its named neighbours      -> corrected
  e. otherwise                                                        -> unresolved

Usage
  python3 tools/names.py --fetch          # rebuild the reference (needs archive.org)
  python3 tools/names.py                  # apply it, write data/name-map.json
"""
import difflib
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "data", "reference-names.json")
OUT = os.path.join(ROOT, "data", "name-map.json")

IA_ITEM = "manualhomopathi01jahrgoog"
IA_URL = "https://archive.org/download/%s/%s_djvu.txt" % (IA_ITEM, IA_ITEM)


def letters(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def tidy(s):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    s = s.strip(" .,;:-—")
    return s


# --------------------------------------------------------------- the reference
def build_reference(src_omm, src_json):
    names = {}

    def add(name, origin):
        n = tidy(name)
        if len(letters(n)) < 3:
            return
        names.setdefault(letters(n), {"name": n, "origins": []})
        if origin not in names[letters(n)]["origins"]:
            names[letters(n)]["origins"].append(origin)

    rem_dir = os.path.join(src_omm, "remedies")
    for fn in sorted(os.listdir(rem_dir)):
        if fn.endswith(".html"):
            add(fn[:-5].replace("-", " "), "open-materia-medica")

    rep = os.path.join(src_json, "repertory")
    if os.path.isdir(rep):
        for fn in sorted(os.listdir(rep)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(rep, fn), encoding="utf-8") as fh:
                book = json.load(fh)
            for v in (book.get("remedy_index") or {}).values():
                if isinstance(v, dict) and v.get("name"):
                    add(v["name"], "repertory:" + fn[:-5])

    # the Internet Archive scan of the same Jahr volume, its numbered index
    try:
        with urllib.request.urlopen(IA_URL, timeout=120) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception as e:  # pragma: no cover - network
        raise SystemExit("could not fetch the archive.org scan: %s" % e)
    pat = re.compile(r"^\s*(\d{1,3})\.\s*([^\s—–-]{1,14})\.?\s*[—–-]+\s*(.+?)\s*$", re.M)
    jahr = {}
    for m in pat.finditer(text):
        n = int(m.group(1))
        nm = tidy(re.sub(r"\s*-\s*$", "", m.group(3)))
        nm = re.sub(r"\s{2,}", " ", nm)
        if (1 <= n <= 250 and 4 <= len(letters(nm)) <= 40 and re.match(r"^[A-Za-z]", nm)
                and not re.search(r"[0-9]", nm) and not re.search(r"[^A-Za-z .\-']", nm)
                and len(nm.split()[-1]) >= 3):
            jahr.setdefault(n, nm)
            add(nm, "jahr-1847-index")
    ref = {
        "built": "2026-11-01",
        "sources": [
            {"what": "Open Materia Medica remedy names", "where": "drsamonline/open-materia-medica", "count": 344},
            {"what": "repertory remedy index", "where": "drsamonline/homoeopathic-materia-medica-repertory-json", "count": None},
            {"what": "Jahr, Manual of Homoeopathic Medicine (1847), numbered remedy index",
             "where": "https://archive.org/details/" + IA_ITEM, "count": len(jahr)},
        ],
        "jahr_index": {str(k): jahr[k] for k in sorted(jahr)},
        "names": sorted(names.values(), key=lambda x: x["name"].lower()),
    }
    os.makedirs(os.path.dirname(REF), exist_ok=True)
    with open(REF, "w", encoding="utf-8") as fh:
        json.dump(ref, fh, ensure_ascii=False, indent=1)
    print("reference: %d distinct names, %d from the Jahr index -> %s"
          % (len(ref["names"]), len(jahr), REF))


def load_reference():
    with open(REF, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ the matcher
class Corrector(object):
    """Corrects a name only when a CLEAN authority confirms it.

    Two classes of authority, because they are not equally good:
      curated — Open Materia Medica's 344 names and the repertory index. Human
                names, no OCR in them.
      scanned — the Internet Archive's index of the same Jahr volume. A second
                OCR, useful but itself imperfect ("Sulphuris ad" is a damaged
                "Sulphuricum acidum"), so it may only confirm a reading the
                entry's own abbreviation already points at.
    """

    def __init__(self, ref):
        self.by_key = {letters(n["name"]): n["name"] for n in ref["names"]}
        self.curated = []
        self.scanned = []
        for n in ref["names"]:
            origins = n.get("origins") or []
            if any(o.startswith("open-materia-medica") or o.startswith("repertory:") for o in origins):
                self.curated.append(n["name"])
            if "jahr-1847-index" in origins:
                self.scanned.append(n["name"])
        self._abbrev = {}
        for n in self.curated:
            k = letters(n)
            self._abbrev.setdefault(k[:4], set()).add(n)

    def exact(self, printed):
        return self.by_key.get(letters(printed))

    def curated_exact(self, printed):
        k = letters(printed)
        for n in self.curated:
            if letters(n) == k:
                return n
        return None

    @staticmethod
    def _parts(printed):
        return [p.strip(" .,;:") for p in re.split(r"\.\s+|,\s+", printed) if p.strip(" .,;:")]

    def merged(self, printed):
        """'Lycopodium. Magnesia Carbonica' -> ('Lycopodium', 'Magnesia Carbonica')."""
        parts = self._parts(printed)
        if len(parts) < 2:
            return None
        head = self.curated_exact(parts[0]) or self.by_key.get(letters(parts[0]))
        if not head:
            return None
        return head, parts[1]

    def by_abbrev(self, abbrev, pool):
        k = letters(abbrev)
        if len(k) < 4:
            return None
        cands = [n for n in pool if letters(n)[:4] == k[:4]]
        return cands[0] if len(cands) == 1 else None

    def fuzzy_curated(self, printed, low, high):
        k = letters(printed)
        if len(k) < 5:
            return None
        best = None
        for n in self.curated:
            nk = letters(n)
            if nk[:1] != k[:1]:
                continue
            if abs(len(nk) - len(k)) > max(3, int(0.3 * len(k))):
                continue
            r = difflib.SequenceMatcher(None, k, nk).ratio()
            if r < 0.85:
                continue
            if low and high and not (low.lower() <= n.lower() <= high.lower()):
                continue
            if best is None or r > best[0]:
                best = (r, n)
        return best[1] if best else None


def looks_clean(printed):
    """A name that a reader can read: letters, spaces, apostrophes, hyphens.

    A clean name the reference does not carry is a remedy we simply do not have,
    NOT an error - so it is kept as printed. Only a name with visible OCR damage
    is ever corrected.
    """
    if not printed:
        return False
    if re.search(r"[0-9]", printed):
        return False
    if re.search(r"[^A-Za-z .'\-]", printed):
        return False
    words = [w for w in re.split(r"[ .\-]+", printed) if w]
    if not words or len(words) > 3:
        return False
    for w in words:
        if len(w) < 2:
            return False
        # a word is readable if it is all-caps of length>=3 or capitalised
        if not (w.isupper() and len(w) >= 3) and not (w[0].isupper() and w[1:].islower()):
            return False
    return True


def correct_books(corrector, src_json):
    out = []
    md = os.path.join(src_json, "materia_medica")
    for fn in sorted(os.listdir(md)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(md, fn), encoding="utf-8") as fh:
            book = json.load(fh)
        rems = book.get("remedies") or []

        # a "remedy" whose name is one of this book's own chapter headings is a
        # heading that the transcription promoted into a remedy
        headings = set()
        for r in rems:
            for sym in (r.get("symptoms") or []):
                ch = (sym.get("chapter") or "").strip().lower()
                if ch:
                    headings.add(ch)

        # a first pass of confident names gives every position a slot
        fixed = {}
        for i, r in enumerate(rems):
            e = corrector.curated_exact(r.get("name") or "")
            if e:
                fixed[i] = e

        for i, r in enumerate(rems):
            printed = tidy(r.get("name") or "")
            entry = {"book": fn, "id": r.get("id"), "printed": printed,
                     "abbrev": r.get("abbrev") or ""}

            if printed.strip().lower() in headings:
                entry.update(corrected=None, status="not-a-remedy",
                             evidence="this name is one of the book's own chapter headings, not a remedy")
                out.append(entry)
                continue

            e = corrector.curated_exact(printed)
            if e:
                entry.update(corrected=e, status="ok", evidence="the printed name is already a known name")
                out.append(entry)
                continue

            if looks_clean(printed):
                entry.update(corrected=printed, status="ok-as-printed",
                             evidence="a readable name the reference does not carry; kept exactly as printed")
                out.append(entry)
                continue

            m = corrector.merged(printed)
            if m:
                entry.update(corrected=m[0], status="merged", also=m[1],
                             evidence="two names run together in the transcription: %s + %s" % m)
                out.append(entry)
                continue

            a = corrector.by_abbrev(entry["abbrev"], corrector.curated)
            if a:
                entry.update(corrected=a, status="corrected",
                             evidence="the entry's own abbreviation '%s' names one curated remedy" % entry["abbrev"])
                out.append(entry)
                continue

            low = high = None
            for j in range(i - 1, -1, -1):
                if j in fixed:
                    low = fixed[j]
                    break
            for j in range(i + 1, len(rems)):
                if j in fixed:
                    high = fixed[j]
                    break

            f = corrector.fuzzy_curated(printed, low, high)
            if f:
                entry.update(corrected=f, status="corrected",
                             evidence="closest curated name at >=85% letter similarity, in the right alphabetical slot"
                                      + (" between %s and %s" % (low, high) if low and high else ""))
                out.append(entry)
                continue

            # the scanned index may only CONFIRM an abbreviation, never lead
            sc = corrector.by_abbrev(entry["abbrev"], corrector.scanned)
            if (sc and looks_clean(sc)
                    and difflib.SequenceMatcher(None, letters(printed), letters(sc)).ratio() >= 0.6):
                entry.update(corrected=sc, status="corrected-scanned",
                             evidence="confirmed by the archive.org index of the same volume via the entry's abbreviation")
                out.append(entry)
                continue

            entry.update(corrected=None, status="unresolved",
                         evidence="no clean authority confirms a reading; kept exactly as printed")
            out.append(entry)
    return out


def main():
    args = sys.argv[1:]
    if "--fetch" in args:
        build_reference("src/open-materia-medica", "src/materia-medica-json")
        return
    ref = load_reference()
    corr = Corrector(ref)
    entries = correct_books(corr, "src/materia-medica-json")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"built": "2026-11-01", "rule": __doc__.split("THE RULE")[0].strip().splitlines()[0],
                   "entries": entries}, fh, ensure_ascii=False, indent=0, sort_keys=True)
    tally = {}
    for e in entries:
        tally[e["status"]] = tally.get(e["status"], 0) + 1
    print(json.dumps({"entries": len(entries), "by_status": tally}, indent=1))
    for e in entries:
        if e["status"] in ("corrected", "merged"):
            print("  %-9s %-32s -> %s" % (e["status"], e["printed"], e["corrected"]))


if __name__ == "__main__":
    main()
