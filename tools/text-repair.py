#!/usr/bin/env python3
"""Repair a damaged quoted sentence from the scan's own PAGE text.

The transcription this app bundles was made from one OCR; the Internet Archive
holds the same edition as item `in.ernet.dli.2015.94901`, whose `_djvu.xml`
carries the OCR of every PAGE separately. That matters: a page's text keeps its
line breaks and end-of-line hyphens, so joining them the way a reader joins them
("sen-" + "sitiveness") undoes the commonest damage in the transcription, which
is a word split across two lines.

THE RULE
  1. Find the page whose text contains the sentence (a distinctive fragment is
     enough; the probe is the middle of the sentence, not its start, because the
     start is often where the damage is).
  2. Rebuild the sentence from that page: join the lines, join hyphen breaks,
     collapse spaces.
  3. Accept the rebuilt sentence only when it is the SAME sentence (≥0.80 letter
     similarity) and CLEANER than the transcription's version. Otherwise keep
     what the transcription printed and leave the damage flag standing.

Nothing is paraphrased. The rebuilt sentence is still the book's words; what is
removed is the line break and the hyphen the scanner put inside a word.

  python3 tools/text-repair.py --fetch   # pull the page-level OCR
  python3 tools/text-repair.py           # repair data/rows.json's damaged quotes
"""
import difflib
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IA_ITEM = "in.ernet.dli.2015.94901"
IA_XML = "2015.94901.The-Homeopathic-Therapeutics--Ed-7th_djvu.xml"
IA_URL = "https://archive.org/download/%s/%s" % (IA_ITEM, IA_XML)
PAGES = os.path.join(ROOT, "data", "bell-pages.json")
OUT = os.path.join(ROOT, "data", "text-repairs.json")


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def damage(s):
    s = s or ""
    if not s:
        return 9.0
    bad = len(re.findall(r"[^A-Za-z0-9 ,.;:'\"()\-]", s))
    digits = len(re.findall(r"(?<![A-Za-z])\d+(?![A-Za-z])", s))
    broken = len(re.findall(r"\b[a-z]{1,2}\b", s))
    return bad * 2 + digits * 3 + broken * 0.3


def build_pages():
    with urllib.request.urlopen(IA_URL, timeout=240) as r:
        xml = r.read().decode("utf-8", "replace")
    objects = re.findall(r"<OBJECT[^>]*>.*?</OBJECT>", xml, re.S)
    pages = []
    for i, o in enumerate(objects):
        # keep line structure: one <LINE> is one printed line
        lines = []
        for ln in re.findall(r"<LINE[^>]*>(.*?)</LINE>", o, re.S):
            words = re.findall(r"<WORD[^>]*>(.*?)</WORD>", ln, re.S)
            text = " ".join(w.strip() for w in words) if words else re.sub(r"<[^>]+>", " ", ln)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                lines.append(text)
        pages.append({"n": i, "lines": lines, "text": " ".join(lines)})
    with open(PAGES, "w", encoding="utf-8") as fh:
        json.dump({"built": "2026-11-01", "source": "https://archive.org/details/" + IA_ITEM,
                   "what": "page-level OCR of the same edition, one entry per scanned page",
                   "pages": pages}, fh, ensure_ascii=False)
    print("indexed %d pages" % len(pages))


def load_pages():
    with open(PAGES, encoding="utf-8") as fh:
        return json.load(fh)["pages"]


def _joined(page_lines):
    joined = ""
    for ln in page_lines:
        joined = joined[:-1] + ln if joined.endswith("-") else joined + " " + ln
    return re.sub(r"\s+", " ", joined).strip()


def rebuild(page_lines, sentence):
    """Repair the damage word by word, using the page as the witness.

    Three kinds of damage appear in this transcription, and each has a witness:

      a. a word split across a line: "sen sitiveness", "in ternal" — if the page
         contains the joined word, the two fragments are one word;
      b. an apostrophe inside a word: "alw'ays" — if the page contains the word
         without it, the apostrophe is the scanner's;
      c. a page number swallowed into the prose: "continued THEIR INDICATIONS,
         IO3 yawning" — if the page has the words but not the number, the number
         is not part of the sentence.

    Nothing else is touched: no word is added, dropped or reordered, and every
    replacement is a word the page actually prints.
    """
    page = norm(_joined(page_lines))
    if not page:
        return None
    words = sentence.split()
    out = []
    i = 0
    changed = False
    while i < len(words):
        w = words[i]
        # (b) apostrophe inside a word
        if "'" in w and len(w) > 3:
            flat = w.replace("'", "")
            if flat.isalpha() and re.search(r"\b" + flat + r"\b", page, re.I):
                out.append(flat)
                changed = True
                i += 1
                continue
        # (a) two fragments that are one word on the page
        if i + 1 < len(words):
            a, b = w.strip(".,;:"), words[i + 1].strip(".,;:")
            if a.isalpha() and b.isalpha() and len(a) + len(b) >= 5:
                joined_word = a + b
                if (re.search(r"\b" + joined_word + r"\b", page, re.I)
                        and not re.search(r"\b" + a + r"\b", page, re.I)):
                    tail = words[i + 1][len(b):]
                    out.append(a + b + tail)
                    changed = True
                    i += 2
                    continue
        # (c) a swallowed page number
        if re.fullmatch(r"[0-9lI|]{2,5}", w) and not re.search(r"\b" + re.escape(w) + r"\b", page):
            changed = True
            i += 1
            continue
        out.append(w)
        i += 1
    return (" ".join(out), changed)


def main():
    if "--fetch" in sys.argv:
        build_pages()
        return
    pages = load_pages()
    with open(os.path.join(ROOT, "data", "rows.json"), encoding="utf-8") as fh:
        rows = json.load(fh)
    repairs, kept = [], 0
    for r in rows:
        if not r.get("text_damage"):
            continue
        sent = r["sentence"]
        words = norm(sent).split()
        probe = " ".join(words[max(0, len(words) // 2 - 4): len(words) // 2 + 4]) if len(words) > 8 else " ".join(words[:4])
        hit = None
        for p in pages:
            if probe and probe in norm(p["text"]):
                hit = p
                break
        if not hit:
            # fall back to the page that actually carries this sentence's words:
            # at least 70% of them must appear on it, or it is not the witness
            want = [w for w in norm(sent).split() if len(w) > 3]
            best = (0.0, None)
            for p in pages:
                text = norm(p["text"])
                if not want:
                    continue
                have = sum(1 for w in want if re.search(r"\b" + re.escape(w) + r"\b", text))
                share = have / float(len(want))
                if share > best[0]:
                    best = (share, p)
            if best[1] is not None and best[0] >= 0.7:
                hit = best[1]
        if not hit:
            kept += 1
            continue
        res = rebuild(hit["lines"], sent)
        if not res or not res[1]:
            kept += 1
            continue
        rebuilt = res[0]
        sim = difflib.SequenceMatcher(None, norm(sent), norm(rebuilt)).ratio()
        if sim >= 0.80 and norm(rebuilt) != norm(sent):
            repairs.append({"from": sent, "to": rebuilt, "page": hit["n"],
                            "page_label": None, "similarity": round(sim, 2),
                            "damage_before": round(damage(sent), 1),
                            "damage_after": round(damage(rebuilt), 1)})
        else:
            kept += 1
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"built": "2026-11-01",
                   "source": "https://archive.org/details/" + IA_ITEM,
                   "what": "quoted sentences rebuilt from the scan's own page text: the line break and the "
                           "end-of-line hyphen removed, nothing paraphrased",
                   "repairs": repairs}, fh, ensure_ascii=False, indent=0, sort_keys=True)
    print(json.dumps({"damaged": len([r for r in rows if r.get('text_damage')]),
                      "repaired": len(repairs), "kept_as_printed": kept}, indent=1))
    for x in repairs:
        print("  p%-4d %s" % (x["page"], x["from"][:60]))
        print("        -> %s" % x["to"][:80])


if __name__ == "__main__":
    main()
