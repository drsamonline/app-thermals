#!/usr/bin/env python3
"""Name every Bell entry and repair its text from a second scan of the same book.

THE BOOK. `bell-therapeutics-1906.json` is Bell's *Homoeopathic Therapeutics of
Diarrhoea, Dysentery, Cholera…*, 7th ed. 1906. The Internet Archive holds the
same edition as item `in.ernet.dli.2015.94901` — a second scan, with the remedies
numbered 1..141 in alphabetical order.

TWO THINGS THIS FIXES, both with evidence rather than inference:

1. THE NAME. The transcribed headings are wrecked ("N1U€£A", "XlNOIB£R"). But an
   entry's own symptom sentences are long, distinctive, and present in both
   scans. Find them in the second scan and the numbered heading above them is the
   remedy. The heading itself is OCR'd too, so it is repaired by nearest name
   against the estate's curated remedy names, and by the remedies' alphabetical
   order (the k-th heading in document order is remedy k).

2. THE TEXT. The transcription carries OCR damage inside the sentences — page
   numbers swallowed into the prose ("continued THEIR INDICATIONS, IO3 yawning"),
   broken words ("sen sitiveness", "alw'ays"), stray marks ("Sulph*", "- ,"). Where
   the second scan renders the same sentence more cleanly, the cleaner rendering
   is kept, and the row says it came from the second scan.

A repair is only accepted when the two renderings are the same sentence: the
match must be ≥0.86 similar, and the cleaner version must actually be cleaner.

  python3 tools/second-scan.py --fetch   # index the second scan
  python3 tools/second-scan.py           # name + repair every entry
"""
import difflib
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IA_ITEM = "in.ernet.dli.2015.94901"
IA_FILE = "2015.94901.The-Homeopathic-Therapeutics--Ed-7th_djvu.txt"
IA_URL = "https://archive.org/download/%s/%s" % (IA_ITEM, IA_FILE)
INDEX = os.path.join(ROOT, "data", "bell-1906-index.json")
REF = os.path.join(ROOT, "data", "reference-names.json")
OVERRIDES = os.path.join(ROOT, "data", "name-overrides.json")
OUT = os.path.join(ROOT, "data", "bell-second-scan.json")

MATERIA_END = 8900  # the repertory index starts after the materia medica

CONFUSABLE = {"\u20ac": "e", "\u00a3": "l", "1": "l", "|": "l", "!": "l", "0": "o",
              "5": "s", "8": "b", "4": "a", "3": "e", "7": "t", "6": "b", "9": "g"}


def norm(s):
    s = (s or "").lower().replace("\u00ad", "")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def letters(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def ocr_letters(s):
    return re.sub(r"[^a-z]", "", "".join(CONFUSABLE.get(c, c) for c in (s or "").lower()))


def damage_score(s):
    """How much of a string looks like OCR damage. Lower is cleaner."""
    s = s or ""
    if not s:
        return 9.0
    bad = len(re.findall(r"[^A-Za-z0-9 ,.;:'\"()\-]", s))       # stray marks
    digits = len(re.findall(r"(?<![A-Za-z])\d+(?![A-Za-z])", s))  # swallowed page numbers
    broken = len(re.findall(r"\b[a-z]{1,2}\b", s))               # 'sen sitiveness'
    return bad * 2 + digits * 3 + broken * 0.3


# --------------------------------------------------------------------- index
KNOWN = []


def build_index():
    with urllib.request.urlopen(IA_URL, timeout=180) as r:
        text = r.read().decode("utf-8", "replace")
    lines = text.split("\n")
    heads = []
    for i, line in enumerate(lines):
        if i >= MATERIA_END:
            break
        if re.match(r"^\s*\d{1,3}\.\s*[A-Z][A-Za-z\-\'\. ]{2,40}\.?\s*\d*\s*$", line):
            heads.append(i)
        elif i > 700 and re.match(r"^\s*[A-Z][A-Za-z\-]{3,20}\.\s*$", line):
            # a heading that lost its number in this scan ("Silicea."). Accepted
            # only when it names a remedy we know - otherwise a chapter subheading
            # ("Chlorosis.") would be mistaken for one and split a section in two.
            word = letters(line)
            if any(letters(n).startswith(word[:6]) and word[:4] == letters(n)[:4] for n in KNOWN):
                heads.append(i)
    sections = []
    for k, start in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else MATERIA_END
        block = lines[start:end]
        heading = re.sub(r"^\s*\d{1,3}\.\s*", "", block[0]).strip().rstrip(".")
        body = " ".join(block[1:])
        sections.append({
            "position": k + 1,
            "line": start + 1,
            "end_line": end,
            "heading": heading,
            "text": norm(body),
            "sentences": [x.strip() for x in re.split(r"(?<=[.!?])\s+", body) if len(x.strip()) > 25],
        })
    # one searchable stream plus a map from offset back to the line it came from
    starts, chunks, cursor = [], [], 0
    for i, line in enumerate(lines):
        t = norm(line)
        starts.append((cursor, i))
        chunks.append(t)
        cursor += len(t) + 1
    flat = " ".join(chunks)
    data = {"built": "2026-11-01", "source": "https://archive.org/details/" + IA_ITEM,
            "flat": flat,
            "starts": starts,
            "what": "Bell, Homoeopathic Therapeutics of Diarrhoea, 7th ed. 1906 — the numbered remedy "
                    "sections of a second scan of the same edition",
            "sections": sections}
    with open(INDEX, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    print("indexed %d sections" % len(sections))


def load_index():
    with open(INDEX, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- vocabulary
def load_names():
    with open(REF, encoding="utf-8") as fh:
        ref = json.load(fh)
    curated = [n["name"] for n in ref["names"]
               if any(o.startswith(("open-materia-medica", "repertory:")) for o in n["origins"])]
    extra = []
    try:
        with open(OVERRIDES, encoding="utf-8") as fh:
            ov = json.load(fh)
        for o in ov.get("owner_confirmations", []):
            extra.append(o["corrected"])
        for o in ov.get("second_scan_confirmations", {}).get("readings", []):
            extra.append(o["corrected"])
    except FileNotFoundError:
        pass
    return sorted(set(curated) | set(extra))


def clean_heading(h):
    """'BOLETUS L A RI CIS' -> 'Boletus laricis'; 'FEBROf METAIXICUM' -> as printed."""
    h = re.sub(r"\s+", " ", h).strip()
    if h.isupper():
        # letters separated by single spaces are one word split by the scan
        h = re.sub(r"\b([A-Za-z])\s+(?=[A-Za-z]\b)", r"\1", h)
    words = h.split()
    out = []
    for w in words:
        if w.isupper() and len(w) > 3:
            out.append(w[0] + w[1:].lower())
        else:
            out.append(w)
    return " ".join(out).strip(" .")


AMBIG = {"1": ["l", "i"], "8": ["b", "s"], "4": ["a", "h"], "0": ["o", "u"],
         "5": ["s", "e"], "\u20ac": ["e", "c"], "\u00a3": ["l", "e"], "|": ["l", "i"]}


def variants(s, limit=12):
    words = re.sub(r"[^a-z0-9\u20ac\u00a3|]+", "", (s or "").lower())
    outs = [""]
    for ch in words:
        opts = AMBIG.get(ch)
        if not opts:
            if ch.isalpha():
                outs = [o + ch for o in outs]
            continue
        outs = [(o + opt) for o in outs for opt in opts][:limit]
    return outs or [""]


def score(printed, candidate):
    cands = {ocr_letters(candidate)}
    cands.discard("")
    best = 0.0
    for a in variants(printed):
        for b in cands:
            if not a or not b:
                continue
            best = max(best, difflib.SequenceMatcher(None, a, b).ratio())
            short, long_ = (a, b) if len(a) <= len(b) else (b, a)
            if len(short) >= 4:
                for i in range(0, len(long_) - len(short) + 1):
                    best = max(best, difflib.SequenceMatcher(None, short, long_[i:i + len(short)]).ratio())
    return best


def repair_heading(heading, names):
    """Nearest curated remedy name for a damaged heading, or the heading itself."""
    cleaned = clean_heading(heading)
    scored = []
    for n in names:
        r = score(cleaned, n)
        if r >= 0.72:
            scored.append((r, n))
    scored.sort(reverse=True)
    if not scored:
        return cleaned, None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.05:
        return cleaned, None  # two readings are nearly as close: no decision
    return scored[0][1], round(scored[0][0], 2)


# ------------------------------------------------------------------- align
def line_of(starts, at):
    lo, hi = 0, len(starts) - 1
    best = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if starts[mid][0] <= at:
            best = starts[mid][1]
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def align(sections, names, book_json, flat=None, starts=None):
    """Each entry's symptoms are located by LINE; the heading above owns them.

    Section slicing was the wrong tool: a single missing heading shifts every
    boundary after it, and the whole book lands one remedy out. A line number
    cannot shift. For each symptom sentence we find where it sits in the second
    scan, and the last remedy heading above that line is the owner.
    """
    with open(book_json, encoding="utf-8") as fh:
        book = json.load(fh)
    flat = flat or ""
    # a searchable copy with offsets
    offsets = []
    pos = 0
    for ch in flat:
        offsets.append(pos)
        pos += 1
    out = []
    for rem in book.get("remedies") or []:
        votes, considered, repairs = {}, 0, []
        for sym in rem.get("symptoms") or []:
            raw = sym.get("text") or ""
            s_norm = norm(raw)
            if len(s_norm) < 30:
                continue
            considered += 1
            # A sentence that occurs exactly once in the whole book names its own
            # owner. A stock phrase that recurs in ten remedies names nothing, so
            # only unique probes are allowed to vote.
            probe = s_norm[:90]
            if len(probe) < 60 or flat.count(probe) != 1:
                continue
            at = flat.find(probe)
            if at < 0:
                continue
            line = line_of(starts or [], at)
            owner = None
            for sec in sections:
                if sec["line"] - 1 <= line:
                    owner = sec
                else:
                    break
            if owner is None:
                continue
            votes.setdefault(owner["position"], {"sec": owner, "n": 0})
            votes[owner["position"]]["n"] += 1
            best = None
            for cand in owner["sentences"]:
                r = difflib.SequenceMatcher(None, s_norm[:160], norm(cand)[:160]).ratio()
                if r >= 0.86 and (best is None or r > best[0]):
                    best = (r, cand)
            if best and damage_score(best[1]) < damage_score(raw) - 0.5:
                repairs.append({"from": raw, "to": best[1]})
        if not votes:
            continue
        ranked = sorted(votes.values(), key=lambda v: -v["n"])
        if len(ranked) > 1 and ranked[0]["n"] - ranked[1]["n"] < 2:
            continue
        sec = ranked[0]["sec"]
        name, conf = repair_heading(sec["heading"], names)
        out.append({
            "id": rem.get("id"),
            "printed": rem.get("name"),
            "section": sec["position"],
            "line": sec["line"],
            "heading": sec["heading"],
            "name": name,
            "name_confidence": conf,
            "symptoms_matched": ranked[0]["n"],
            "symptoms_considered": considered,
            "text_repairs": repairs,
        })
    return out


def main():
    if "--fetch" in sys.argv:
        KNOWN[:] = load_names()
        build_index()
        return
    index = load_index()
    names = load_names()
    KNOWN[:] = names
    rows = align(index["sections"], names,
                 "src/materia-medica-json/materia_medica/bell-therapeutics-1906.json",
                 index.get("flat"), index.get("starts"))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"built": "2026-11-01", "source": index["source"],
                   "method": "each entry's own symptom sentences located in a second scan of the same edition; "
                             "the numbered heading above them is the remedy, repaired by nearest curated name; "
                             "and where the second scan renders a damaged sentence more cleanly, the cleaner text is kept",
                   "entries": rows}, fh, ensure_ascii=False, indent=0, sort_keys=True)
    named = [r for r in rows if r["name_confidence"]]
    print(json.dumps({"entries": len(rows), "named_with_confidence": len(named),
                      "text_repairs": sum(len(r["text_repairs"]) for r in rows)}, indent=1))
    for r in rows[:20]:
        print("  %-28s -> %s" % (repr(r["printed"])[:28], r["name"]))


if __name__ == "__main__":
    main()
