#!/usr/bin/env python3
"""Name the Bell entries from their SYMPTOMS, not from their damaged headings.

`Homoeopathic Therapeutics` (Bell, 7th ed., 1906) is transcribed in the JSON
repository with headings the OCR has wrecked ("N1U€£A", "XlNOIB£R",
"JETIICSA CYlTAPIITJtt"). The Internet Archive holds the same book as item
`in.ernet.dli.2015.94901` — a second scan, with the remedies numbered.

So the name does not have to be guessed from the heading at all. The symptom
text is long, distinctive and present in both scans: find where an entry's own
sentences sit in the second scan, and the numbered heading above them is the
remedy. That is evidence, not inference.

  python3 tools/align-bell.py --fetch    # pull the second scan and index it
  python3 tools/align-bell.py            # align the JSON entries to it
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
OUT = os.path.join(ROOT, "data", "bell-alignment.json")

REMEDY_PART_END = 8900  # the repertory index begins after the materia medica


def norm(s):
    s = (s or "").lower().replace("\u00ad", "")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def build_index():
    with urllib.request.urlopen(IA_URL, timeout=180) as r:
        text = r.read().decode("utf-8", "replace")
    lines = text.split("\n")
    heads = []
    for i, line in enumerate(lines):
        m = re.match(r"^\s*(\d{1,3})\.\s*([A-Z][A-Za-z\-\'\. ]{2,40})\.?\s*$", line)
        if m and i < REMEDY_PART_END:
            heads.append((i, m.group(2).strip()))
            continue
        # a few headings lost their number in this scan ("Silicea." on its own line)
        m2 = re.match(r"^\s*([A-Z][a-z]{3,18})\.\s*$", line)
        if m2 and i < REMEDY_PART_END:
            heads.append((i, m2.group(1).strip()))
    sections = []
    for k, (start, heading) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else REMEDY_PART_END
        body = norm(" ".join(lines[start:end]))
        sections.append({"number": k + 1, "heading": heading, "text": body})
    data = {
        "built": "2026-11-01",
        "source": "https://archive.org/details/" + IA_ITEM,
        "what": "Bell, Homoeopathic Therapeutics, 7th ed. 1906 - the numbered remedy "
                "headings of a second scan of the same book, with each section's text",
        "sections": sections,
    }
    with open(INDEX, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    print("indexed %d sections from %s" % (len(sections), IA_URL))


def load_index():
    with open(INDEX, encoding="utf-8") as fh:
        return json.load(fh)


def align(book_json, index):
    """For each entry, the section its own sentences are found in.

    Strict on purpose: a probe must appear in a section nearly verbatim, and the
    vote must be clear. A wrong name is worse than no name, so an entry that only
    half-matches stays unresolved.
    """
    sections = index["sections"]
    out = []
    with open(book_json, encoding="utf-8") as fh:
        book = json.load(fh)
    for rem in book.get("remedies") or []:
        votes, considered = {}, 0
        for sym in rem.get("symptoms") or []:
            s = norm(sym.get("text") or "")
            if len(s) < 30:
                continue
            considered += 1
            probe = s[:120]
            found = None
            exact = False
            for sec in sections:
                if probe[:60] in sec["text"]:
                    found = sec
                    exact = True
                    break
            if found is None:
                head = probe[:40]
                for sec in sections:
                    pos = sec["text"].find(head)
                    if pos < 0:
                        continue
                    window = sec["text"][pos:pos + len(probe) + 40]
                    if difflib.SequenceMatcher(None, probe, window).ratio() >= 0.92:
                        found = sec
                        break
            if found is not None:
                votes.setdefault(found["number"], {"section": found, "n": 0, "exact": 0})
                votes[found["number"]]["n"] += 1
                if exact:
                    votes[found["number"]]["exact"] += 1
        if not votes:
            continue
        key = max(votes, key=lambda k: votes[k]["n"])
        best = votes[key]
        if best["n"] < 2 and considered > 2 and not best.get("exact"):
            continue
        share = best["n"] / float(max(considered, 1))
        if share < 0.5:
            continue
        sec = best["section"]
        out.append({
            "id": rem.get("id"),
            "printed": rem.get("name"),
            "section": sec["number"],
            "heading": sec["heading"],
            "symptoms_matched": best["n"],
            "symptoms_total": len(rem.get("symptoms") or []),
            "agreement": round(share, 2),
        })
    return out


def main():
    if "--fetch" in sys.argv:
        build_index()
        return
    index = load_index()
    rows = align("src/materia-medica-json/materia_medica/bell-therapeutics-1906.json", index)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"built": "2026-11-01",
                   "source": index["source"],
                   "method": "each entry's own symptom sentences are located in a second scan of the same book; "
                             "the numbered remedy heading above them is the entry's remedy",
                   "entries": rows}, fh, ensure_ascii=False, indent=0, sort_keys=True)
    print("aligned %d of the book's entries" % len(rows))
    for r in rows:
        print("  %-30s -> #%s %s (agree %.2f, %d symptoms)"
              % (repr(r["printed"])[:30], r["section"], r["heading"], r["agreement"], r["symptoms_matched"]))


if __name__ == "__main__":
    main()
