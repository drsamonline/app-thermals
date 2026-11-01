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


CONFUSABLE = {
    "\u20ac": "e", "\u00a3": "l", "\u00a5": "y", "1": "l", "|": "l", "!": "l",
    "0": "o", "5": "s", "8": "b", "4": "a", "3": "e", "7": "t", "6": "b",
    "2": "z", "9": "g", "@": "a", "$": "s", "<": "c", ">": "c", "\u00a7": "s",
    "\u00ab": "", "\u00bb": "", "*": "", "^": "", "~": "", "\\": "", "/": "",
    "}": "", "{": "", "]": "", "[": "", "(": "", ")": "", "\"": "", "'": "",
}


def letters(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


AMBIGUOUS = {
    "1": ["l", "i"], "8": ["b", "s"], "4": ["a", "h"], "0": ["o", "u"],
    "5": ["s", "e"], "\u20ac": ["e", "c"], "\u00a3": ["l", "e"], "|": ["l", "i"],
    "6": ["b", "g"], "9": ["g", "q"], "2": ["z", "r"], "7": ["t", "l"],
}


def ocr_variants(s, limit=12):
    """The plausible readings of an OCR'd name, not just one.

    A scan writes 8 for B in 'A8ARUM' and for S elsewhere, 1 for L or I, 4 for A.
    Trying the readings and keeping the best match is what turns
    'A8ARUM EIIROPEIJII' into 'asarum europaeum' instead of leaving it unread.
    """
    words = re.sub(r"[^a-z0-9\u20ac\u00a3|]+", "", (s or "").lower())
    outs = [""]
    for ch in words:
        opts = AMBIGUOUS.get(ch)
        if not opts:
            if ch.isalpha():
                outs = [o + ch for o in outs]
            continue
        nxt = []
        for o in outs:
            for opt in opts:
                nxt.append(o + opt)
        outs = nxt[:limit]
    return outs or [""]


def ocr_letters(s):
    """Letters with the OCR's usual character substitutions undone.

    A scan writes E as euro, L as 1, | or pound, A as 4, O as 0, S as 5, B as 8.
    Comparing the repaired letters is what lets 'PETR01.\u00a31Jli' meet
    'petroleum' instead of sliding past it.
    """
    out = []
    for ch in (s or "").lower():
        out.append(CONFUSABLE.get(ch, ch))
    return re.sub(r"[^a-z]", "", "".join(out))


def ocr_letters_i(s):
    return ocr_letters(s).replace("l", "i")


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


def load_overrides(path=os.path.join(ROOT, "data", "name-overrides.json")):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    out = {}
    for o in data.get("second_scan_confirmations", {}).get("readings", []):
        out[letters(o["printed"])] = {"corrected": o["corrected"], "note": o["evidence"], "status": "second-scan"}
    for o in data.get("second_scan_confirmations", {}).get("duplicates", []):
        out[letters(o["printed"])] = {"corrected": None, "note": o["evidence"], "status": "duplicate"}
    for o in data.get("second_scan_confirmations", {}).get("not_a_remedy", []):
        out[letters(o["printed"])] = {"corrected": None, "note": o["evidence"], "status": "not-a-remedy"}
    for o in data.get("owner_confirmations", []):
        out[letters(o["printed"])] = {"corrected": o["corrected"], "note": o["note"], "status": "owner-confirmed"}
    return out


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
        # The scanned index is OCR too ("Sulphuris ad", "Menyanthes trifo",
        # "Silicia"), so each scanned name is repaired against the curated ones
        # by the same nearest-name rule before it may join the pool.
        repaired = []
        for n in self.scanned:
            best = None
            for c in self.curated:
                r = difflib.SequenceMatcher(None, letters(n), letters(c)).ratio()
                if r >= 0.85 and (best is None or r > best[0]):
                    best = (r, c)
            repaired.append(best[1] if best else n)
        self.scanned = sorted(set(repaired))

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
        if not head and looks_clean(parts[0]) and len(parts[0].split()) >= 1:
            head = parts[0]
        if not head:
            best = None
            for n in self.pool():
                if ocr_letters(n)[:1] != ocr_letters(parts[0])[:1]:
                    continue
                r = self.similarity(parts[0], n)
                if r >= 0.88 and (best is None or r > best[0]):
                    best = (r, n)
            head = best[1] if best else None
        if not head:
            return None
        return head, parts[1]

    def by_abbrev(self, abbrev, pool):
        k = letters(abbrev)
        if len(k) < 4:
            return None
        cands = [n for n in pool if letters(n)[:4] == k[:4]]
        return cands[0] if len(cands) == 1 else None

    @staticmethod
    def similarity(printed, candidate):
        """How alike two spellings are, with the OCR's letter damage undone."""
        cands = {ocr_letters(candidate), ocr_letters_i(candidate)}
        cands.discard("")
        if not cands:
            return 0.0
        best = 0.0
        for a in ocr_variants(printed):
            for b in cands:
                r = difflib.SequenceMatcher(None, a, b).ratio()
                if r > best:
                    best = r
        return best

    def pool(self):
        names = list(self.curated)
        seen = set(letters(n) for n in names)
        for n in self.scanned:
            if looks_clean(n) and letters(n) not in seen:
                names.append(n)
                seen.add(letters(n))
        return names

    @staticmethod
    def partial_similarity(printed, candidate):
        """The best match of the shorter spelling inside the longer one.

        An OCR adds and drops letters ("I^YCOPODICIW" for Lycopodium), so the
        whole-string ratio under-rates a match that is obvious to a reader.
        """
        best = 0.0
        cands = {ocr_letters(candidate), ocr_letters_i(candidate)}
        cands.discard("")
        for a in ocr_variants(printed):
            if not a:
                continue
            for b in cands:
                short, long = (a, b) if len(a) <= len(b) else (b, a)
                if len(short) < 4:
                    continue
                for i in range(0, len(long) - len(short) + 1):
                    r = difflib.SequenceMatcher(None, short, long[i:i + len(short)]).ratio()
                    if r > best:
                        best = r
        return best

    def score(self, printed, candidate):
        return max(self.similarity(printed, candidate), self.partial_similarity(printed, candidate))

    def fuzzy_curated(self, printed, low, high):
        """The nearest curated name, when the difference is small AND it fits.

        Small means: same opening letter, a length within a quarter, and either
        85% letter similarity or 75% with the alphabetical slot agreeing. The slot
        is what stops a near miss landing on the wrong remedy.
        """
        k = ocr_letters(printed)
        if len(k) < 4:
            return None
        scored = []
        for n in self.pool():
            nk = ocr_letters(n)
            if not nk:
                continue
            if abs(len(nk) - len(k)) > max(3, int(0.35 * len(k))):
                continue
            have_slot = bool(low and high)
            in_slot = have_slot and low.lower() <= n.lower() <= high.lower()
            if have_slot and not in_slot:
                continue
            r = self.score(printed, n)
            if r < (0.72 if have_slot else 0.86):
                continue
            bonus = 0.02 if n in self.curated else 0.0
            scored.append((r + bonus, n, r))
        scored.sort(reverse=True)
        if not scored:
            return None
        best_r, best_n, raw = scored[0]
        # a clear winner only: if a second name is nearly as close, the reading is
        # not decided by the evidence and the name stays as printed
        margin = 0.05 if (low and high) else 0.08
        if len(scored) > 1 and (best_r - scored[1][0]) < margin:
            return None
        return best_n


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


def correct_books(corrector, src_json, overrides=None):
    overrides = overrides or {}
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

            ov = overrides.get(letters(printed))
            if ov:
                entry.update(corrected=ov["corrected"], status=ov.get("status", "owner-confirmed"),
                             evidence=ov["note"])
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
                entry.update(corrected=f, status="corrected" if f in corrector.curated else "corrected-scanned",
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
    entries = correct_books(corr, "src/materia-medica-json", load_overrides())
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
