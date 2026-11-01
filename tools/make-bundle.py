#!/usr/bin/env python3
"""Build docs/data/bundle.js from data/rows.json + data/remedies.json.

The bundle is a JS global rather than a fetch() so the app works from file://
with no server, which is the whole point of the estate's offline-first apps.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "docs", "data", "bundle.js")

RULE = (
    "A thermal statement is a sentence in a source's own words containing one of: "
    "chilly, chilliness, always cold, feels cold, feels hot, cold feeling, cold-blooded, "
    "warm-blooded, always warm, cold/hot/warm constitution, cold/hot patient. "
    "Modality lines and modality sections are excluded, as are fragments under 12 "
    "characters. The sentence is kept verbatim."
)


def main():
    with open(os.path.join(DATA, "rows.json"), encoding="utf-8") as fh:
        rows = json.load(fh)
    with open(os.path.join(DATA, "remedies.json"), encoding="utf-8") as fh:
        remedies = json.load(fh)
    try:
        with open(os.path.join(DATA, "name-map.json"), encoding="utf-8") as fh:
            name_map = json.load(fh)
    except FileNotFoundError:
        name_map = {"entries": []}

    sources = sorted({r["source_short"] for r in rows})
    classified = [r for r in remedies if r.get("classified")]
    meta = {
        "rows": len(rows),
        "remedies": len(remedies),
        "classified": len(classified),
        "unclassified": len(remedies) - len(classified),
        "sources": len(sources),
        "source_names": sources,
        "two_source": sum(1 for r in remedies if len(r.get("sources") or []) > 1),
        "rule": RULE,
        "names": {
            "corrected": sum(1 for e in name_map["entries"] if e["status"] == "corrected"),
            "merged_not_bundled": sum(1 for e in name_map["entries"] if e["status"] == "merged"),
            "as_printed": sum(1 for e in name_map["entries"] if e["status"] == "ok-as-printed"),
            "unresolved": sum(1 for e in name_map["entries"] if e["status"] == "unresolved"),
            "confirmed": sum(1 for e in name_map["entries"] if e["status"] == "ok"),
            "authority": "Open Materia Medica names, the repertory index, and the archive.org scan of Jahr 1847",
        },
        "built": os.environ.get("THERMALS_BUILT", ""),
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    body = "window.THERMALS_BUNDLE = " + json.dumps(
        {"rows": rows, "remedies": remedies, "meta": meta},
        ensure_ascii=False, separators=(",", ":"), sort_keys=True) + ";\n"
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(body)
    print(json.dumps(meta, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
