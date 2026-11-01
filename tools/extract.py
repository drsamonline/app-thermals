#!/usr/bin/env python3
"""Extract thermal statements from the two bundled sources.

THE RULE (v3) — the row count is a property of this rule, so the rule ships,
is documented in README.md and is tested in test-node.js.

1. A sentence is a *thermal statement* when it contains one of these phrases,
   case-insensitively, as whole words:

       chilly · chilliness · always cold · feels cold · feels hot · cold feeling
       cold-blooded · warm-blooded · always warm · cold constitution
       hot constitution · warm constitution · cold patient · hot patient

   The set is deliberately narrow. It holds the phrases sources use to describe
   a PERSON's thermal reaction. A bare "cold" or "heat" is NOT in it, because in
   this corpus those words are overwhelmingly about water, air, a room, a
   modality or a fever episode — quoting them as the patient's thermal reaction
   would be the app putting a meaning into the source's mouth.

2. Sentences under a modality heading (a heading containing "Modalit"), or
   sentences that are modality lines themselves (they open with "Worse" or
   "Better"), are dropped: a modality is what changes a state, not what the
   state is.

3. Sentences shorter than 12 or longer than 400 characters are dropped: the
   first is a fragment, the second is a paragraph the source did not write as
   one sentence. (12 and not 20 because "Chilly disposition." — Jahr 1847,
   Cistus canadensis — is 19 characters and is exactly the statement the app
   exists to show.)

4. The sentence is kept VERBATIM. Whitespace is normalised; nothing else is
   paraphrased, reordered, merged or trimmed.

Two sources are read:

* open-materia-medica — one HTML page per remedy, 344 pages. Source name is
  "Open Materia Medica — <remedy> (Dr. Sohil Momin, BHMS, 2026)".
* homoeopathic-materia-medica-repertory-json — three materia medica books, each
  remedy carrying symptom records with a chapter and a text. Source name is the
  book title, author and year.

The books are OCR transcriptions, so some of their remedy names arrive damaged
("a8arum eiiropeijii", "ntjx vomica"). They are kept exactly as printed and they
do not join across sources: a name we cannot read is not a name we may correct.

Outputs, into data/:
  rows.json      — one object per row: remedy, source, chapter, sentence, side
  remedies.json  — every remedy any source names, with its classified flag
"""
import json
import os
import re
import sys

PHRASES = [
    r"\bchilly\b", r"\bchilliness\b", r"\balways cold\b", r"\bfeels? cold\b",
    r"\bfeels? hot\b", r"\bcold feeling\b", r"\bcold-blooded\b", r"\bwarm-blooded\b",
    r"\balways warm\b", r"\bcold constitution\b", r"\bhot constitution\b",
    r"\bwarm constitution\b", r"\bcold patient\b", r"\bhot patient\b",
]
PHRASE_RE = re.compile("|".join(PHRASES), re.I)
COLD_RE = re.compile(
    r"\b(chilly|chilliness|cold|coldness|always cold|cold feeling|cold-blooded|"
    r"cold constitution|cold patient)\b", re.I)
HEAT_RE = re.compile(
    r"\b(hot|heat|warm|warmth|always warm|feels hot|warm-blooded|warm constitution|"
    r"hot constitution|hot patient|feels cold)\b", re.I)

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


COMMON_SHORT = {
    "a", "an", "as", "at", "be", "by", "do", "go", "he", "if", "in", "is", "it",
    "me", "my", "no", "of", "on", "or", "so", "to", "up", "us", "we", "ye", "am",
    "ad", "ah", "oh", "lo", "ha", "ed", "id", "ox", "ex", "re", "st",
}


def text_damage(s):
    """Visible OCR damage inside a quoted sentence.

    Deliberately strict, because a false flag is its own small lie: an ordinary
    "by" or "of" must not read as a broken word. Only three things count -
    a stray mark, a page number swallowed into the prose, and a split word where
    the fragment is not a word at all ("sen sitiveness", "in ternal").
    """
    s = s or ""
    if re.search(r"[*|~^\\<>{}]", s):
        return True
    if re.search(r"\b[A-Z]{4,}\s*,?\s*[A-Z]{1,2}\d\b", s):      # 'INDICATIONS, IO3'
        return True
    if re.search(r"(?<=[a-z])\d+|\d{2,}(?=[a-z])", s):            # 'TIIX05A', '154 thr'
        return True
    for m in re.finditer(r"\b([a-z]{1,2})\s+([a-z]{4,})\b", s):
        frag = m.group(1)
        if frag not in COMMON_SHORT:
            return True                                             # 'sen sitiveness'
    return False


def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("\u00a0", " ")).strip()


def sentences(text):
    for part in SENT_SPLIT.split(text or ""):
        p = clean(part)
        if p:
            yield p


def is_modality(sentence, chapter):
    if chapter and "modalit" in chapter.lower():
        return True
    return bool(re.match(r"^(worse|better)\b", sentence.lower()))


def qualifies(sentence, chapter):
    if not PHRASE_RE.search(sentence):
        return False
    if len(sentence) < 12 or len(sentence) > 400:
        return False
    if is_modality(sentence, chapter):
        return False
    return True


def side(sentence):
    """Which way the source's own words point. 'cold' or 'heat'.

    This is not a state label: it is read off the phrase the sentence quotes, so
    "Chilly disposition." is cold-side and "warm-blooded" is heat-side. When a
    sentence carries both, the first phrase in reading order decides, and the row
    keeps the whole sentence so a reader can see the other one.
    """
    m = PHRASE_RE.search(sentence)
    if not m:
        return ""
    phrase = m.group(0).lower()
    if re.search(r"\b(chilly|chilliness|cold|coldness)\b", phrase):
        return "cold"
    return "heat"


# ---------------------------------------------------------------- open-materia-medica
def html_blocks(path):
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    body = html[html.find("<body"):] if "<body" in html else html
    body = re.sub(r"<script.*?</script>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<(nav|header|footer)\b.*?</\1>", " ", body, flags=re.S | re.I)
    for block in re.split(r"(?i)</?(?:h1|h2|h3|h4|p|li|div|section|br|td|tr)\b[^>]*>", body):
        text = clean(re.sub(r"<[^>]+>", " ", block))
        if text:
            yield text


def extract_omm(root):
    rows, pages = [], []
    rem_dir = os.path.join(root, "remedies")
    for fn in sorted(os.listdir(rem_dir)):
        if not fn.endswith(".html"):
            continue
        slug = fn[:-5]
        pages.append(slug)
        name = slug.replace("-", " ")
        source = "Open Materia Medica — %s (Dr. Sohil Momin, BHMS, 2026)" % name
        chapter = ""
        for text in html_blocks(os.path.join(rem_dir, fn)):
            if len(text) < 60 and not text.endswith((".", "!", "?")) and text[:1].isupper():
                chapter = text
                continue
            for s in sentences(text):
                if qualifies(s, chapter):
                    rows.append({
                        "remedy": name,
                        "remedy_slug": slug,
                        "source": source,
                        "source_short": "Open Materia Medica",
                        "source_kind": "collection",
                        "chapter": chapter,
                        "sentence": s,
                        "side": side(s),
                    })
    return rows, pages


# ---------------------------------------------------------------- JSON books
def load_text_repairs(path="data/text-repairs.json"):
    """Quotes repaired from the scan's own page text, keyed by what was printed."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    return {r["from"]: r for r in data.get("repairs", [])}


def load_name_map(path="data/name-map.json"):
    """The corrections proven by tools/names.py, keyed by (book file, remedy id)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    return {(e["book"], e["id"]): e for e in data.get("entries", [])}


def extract_books(root, name_map=None, repairs=None):
    name_map = name_map or {}
    repairs = repairs or {}
    rows, books, names = [], [], {}
    stats = {}
    md = os.path.join(root, "materia_medica")
    for fn in sorted(os.listdir(md)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(md, fn), encoding="utf-8") as fh:
            book = json.load(fh)
        b = book.get("book", {})
        title = b.get("title") or b.get("id") or fn
        author = b.get("author", "")
        year = b.get("year", "")
        source = "%s — %s, %s" % (title, author, year) if author else "%s (%s)" % (title, year)
        books.append({"file": fn, "title": title, "author": author, "year": year,
                      "remedies": len(book.get("remedies", []))})
        for rem in book.get("remedies", []):
            printed = rem.get("name") or rem.get("id") or ""
            fix = name_map.get((fn, rem.get("id")))
            if fix and fix.get("corrected"):
                rname = fix["corrected"]
                name_status = fix["status"]
            else:
                rname = printed
                name_status = (fix or {}).get("status", "unverified")
            slug = re.sub(r"[^a-z0-9]+", "-", rname.lower()).strip("-")
            if name_status in ("merged", "not-a-remedy", "duplicate"):
                # An entry the transcription ran together with the next remedy
                # cannot be attributed to either, so its sentences are not
                # bundled: one row must be one remedy, one source, one sentence.
                key = {"merged": "merged_not_bundled"}.get(name_status, name_status)
                stats[key] = stats.get(key, 0) + 1
                continue
            if slug:
                names[slug] = rname
            stats[name_status] = stats.get(name_status, 0) + 1
            for sym in rem.get("symptoms") or []:
                chapter = sym.get("chapter") or ""
                for s in sentences(clean(sym.get("text") or "")):
                    if qualifies(s, chapter):
                        fix = repairs.get(s)
                        shown = fix["to"] if fix else s
                        rows.append({
                            "remedy": rname,
                            "remedy_slug": slug,
                            "source": source,
                            "source_short": title,
                            "source_kind": "book",
                            "chapter": chapter,
                            "sentence": shown,
                            "sentence_printed": s if fix else None,
                            "text_page": fix["page"] if fix else None,
                            "side": side(shown),
                            "name_status": name_status,
                            "name_printed": printed,
                            "text_damage": text_damage(shown),
                        })
    return rows, books, names, stats


def main():
    omm_root = sys.argv[1] if len(sys.argv) > 1 else "src/open-materia-medica"
    book_root = sys.argv[2] if len(sys.argv) > 2 else "src/materia-medica-json"
    out_dir = sys.argv[3] if len(sys.argv) > 3 else "data"

    omm_rows, omm_pages = extract_omm(omm_root)
    book_rows, books, book_names, name_stats = extract_books(book_root, load_name_map(), load_text_repairs())
    rows = omm_rows + book_rows
    seen, deduped = set(), []
    for r in rows:
        k = (r["remedy_slug"], r["source_short"], r["sentence"])
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)
    rows = deduped

    index = {}
    for slug in omm_pages:
        index[slug] = {"slug": slug, "name": slug.replace("-", " "), "sources": [], "rows": 0}
    # Book remedies enter the index only when they have something to say: the
    # books are OCR transcriptions and many of their names are unreadable, so an
    # "unclassified" entry built from one would be a garbage name and a claim
    # ("this remedy has no thermal statement") we cannot stand behind.
    for r in rows:
        e = index.setdefault(r["remedy_slug"], {"slug": r["remedy_slug"], "name": r["remedy"],
                                                "sources": [], "rows": 0})
        e["rows"] += 1
        if r["source_short"] not in e["sources"]:
            e["sources"].append(r["source_short"])
    for e in index.values():
        e["classified"] = e["rows"] > 0

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "rows.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=0, sort_keys=True)
    with open(os.path.join(out_dir, "remedies.json"), "w", encoding="utf-8") as fh:
        json.dump(sorted(index.values(), key=lambda x: x["name"].lower()), fh,
                  ensure_ascii=False, indent=0, sort_keys=True)

    multi = [e for e in index.values() if len(e["sources"]) > 1]
    print(json.dumps({
        "omm_pages": len(omm_pages),
        "omm_rows": len(omm_rows),
        "books": books,
        "book_rows": len(book_rows),
        "rows_total": len(rows),
        "remedies_total": len(index),
        "remedies_classified": sum(1 for e in index.values() if e["classified"]),
        "remedies_unclassified": sum(1 for e in index.values() if not e["classified"]),
        "remedies_with_two_sources": len(multi),
        "two_source_names": sorted(e["name"] for e in multi),
        "book_name_status": name_stats,
    }, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
