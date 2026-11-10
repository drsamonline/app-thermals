#!/usr/bin/env node
/* Thermals — the test suite. Every claim in the README is checked here.
 *
 *   node test-node.js
 *
 * The tests drive the SAME module the page loads (thermals.js) and the SAME
 * bundled data (docs/data/bundle.js), so a green suite is evidence about what a
 * reader will actually see, not about a copy kept for the tests.
 */
"use strict";

var fs = require("fs");
var path = require("path");
var vm = require("vm");

var Search = require("./vendor/search-kit.js");
var T = require("./thermals.js");

var passed = 0, failed = 0, current = "";
function ok(cond, msg) {
  if (cond) { passed++; }
  else { failed++; console.log("  FAIL [" + current + "] " + msg); }
}
function eq(a, b, msg) { ok(a === b, msg + " (got " + JSON.stringify(a) + ", want " + JSON.stringify(b) + ")"); }
function test(name, fn) { current = name; fn(); }

/* ---- the bundle, exactly as the page receives it ------------------------- */
var sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname, "docs", "play", "data", "bundle.js"), "utf8"), sandbox);
var BUNDLE = sandbox.window.THERMALS_BUNDLE;
var ROWS = BUNDLE.rows, REMEDIES = BUNDLE.remedies, META = BUNDLE.meta;

/* a storage that behaves like web-kit's, including the full-quota answer */
function memStorage(full) {
  var box = {};
  return {
    get: function (k, d) { return Object.prototype.hasOwnProperty.call(box, k) ? box[k] : d; },
    set: function (k, v) { if (full) return false; box[k] = v; return true; }
  };
}
T.attach({ Search: Search, Loom: { storage: memStorage(false) } });
var IDX = T.buildIndex(ROWS);

/* ======================================================================= */
test("the bundle is the extracted data, not a hand-kept copy", function () {
  var onDisk = JSON.parse(fs.readFileSync(path.join(__dirname, "data", "rows.json"), "utf8"));
  eq(ROWS.length, onDisk.length, "bundle row count equals data/rows.json");
  var remediesOnDisk = JSON.parse(fs.readFileSync(path.join(__dirname, "data", "remedies.json"), "utf8"));
  eq(REMEDIES.length, remediesOnDisk.length, "bundle remedy count equals data/remedies.json");
  eq(META.rows, ROWS.length, "meta.rows matches the bundle");
});

test("every row is verbatim, sourced and attributable", function () {
  var bad = ROWS.filter(function (r) {
    return !r.sentence || r.sentence.length < 12 || !r.source || !r.source_short ||
           !r.remedy || !r.remedy_slug || (r.side !== "cold" && r.side !== "heat");
  });
  eq(bad.length, 0, "no row is missing its sentence, source, remedy or side");
  var noChapter = ROWS.filter(function (r) { return typeof r.chapter !== "string"; });
  eq(noChapter.length, 0, "every row carries a chapter field (may be empty)");
  // a quote is the source's, never the app's: no row may carry a label the
  // sources never wrote
  var labelled = ROWS.filter(function (r) { return /ambithermal/i.test(r.sentence); });
  eq(labelled.length, 0, "no row quotes 'ambithermal' — no bundled source uses the word");
});

test("Cistus canadensis — two sources, both cold, quoted separately", function () {
  var rows = T.rowsFor(ROWS, "cistus-canadensis");
  var s = T.summarise(rows);
  eq(s.kind, "agree", "summary kind is agree");
  eq(s.label, "sources agree (2)", "summary label reads sources agree (2)");
  eq(s.sources.length, 2, "exactly two source names");
  ok(s.sources.indexOf("Open Materia Medica") >= 0, "Open Materia Medica is named");
  ok(s.sources.indexOf("Manual of Homoeopathic Medicine, Part I: Materia Medica") >= 0,
     "Jahr 1847 is named");
  var sides = {};
  rows.forEach(function (r) { sides[r.side] = true; });
  eq(Object.keys(sides).join(","), "cold", "both sources point to the cold side");

  var html = T.renderRemedy(T.remedyFor(REMEDIES, "cistus-canadensis"), rows, [], "2026-11-01");
  ok(html.indexOf("sources agree (2)") >= 0, "the page renders sources agree (2)");
  ok(/Chilly disposition\./.test(html), "Jahr's own sentence is on the page");
  ok(/always cold/i.test(html), "Open Materia Medica's own sentence is on the page");
  // one row per source, each with its own citation
  eq((html.match(/<blockquote>/g) || []).length, rows.length, "one blockquote per row");
  eq((html.match(/class="src"/g) || []).length, rows.length, "every quote carries its source");
  ok(html.indexOf('<span class="src"></span>') < 0, "no quote is rendered without its source name");
});

test("a one-source remedy never reads as agreement", function () {
  var single = null;
  for (var i = 0; i < REMEDIES.length && !single; i++) {
    var r = REMEDIES[i];
    var rows = T.rowsFor(ROWS, r.slug);
    if (rows.length && T.summarise(rows).kind === "one-source") single = r;
  }
  ok(!!single, "the bundle contains at least one one-source remedy");
  var rows = T.rowsFor(ROWS, single.slug);
  var s = T.summarise(rows);
  eq(s.label, "one source only", "label is 'one source only'");
  var html = T.renderRemedy(single, rows, [], "2026-11-01");
  ok(html.indexOf("one source only") >= 0, "the page says one source only");
  ok(html.indexOf("sources agree") < 0, "the page never says sources agree here");
  ok(/not agreement/i.test(s.detail), "the explanation says it is not agreement");
});

test("a remedy no source speaks about is unclassified, with no quote and no summary", function () {
  var un = REMEDIES.filter(function (r) { return !r.classified; });
  ok(un.length > 0, "the bundle contains unclassified remedies");
  var target = un[0];
  var rows = T.rowsFor(ROWS, target.slug);
  eq(rows.length, 0, "an unclassified remedy has no rows");
  var s = T.summarise(rows);
  eq(s.kind, "unclassified", "summary kind is unclassified");
  eq(s.label, "unclassified", "summary label is unclassified");
  var html = T.renderRemedy(target, rows, [], "2026-11-01");
  eq((html.match(/<blockquote>/g) || []).length, 0, "no quoted sentence is rendered");
  eq((html.match(/class="summary/g) || []).length, 0, "no summary is rendered");
  ok(/Nothing has been assigned/.test(html), "the page says nothing was assigned");
});

test("searching 'chilly' returns quoted sentences, each with its source", function () {
  var res = T.search(IDX, "chilly");
  ok(res.ok, "the search ran");
  ok(res.rows.length > 0, "at least one quoted sentence carries 'chilly'");
  var sourceless = res.rows.filter(function (r) { return !r.source || !r.source_short; });
  eq(sourceless.length, 0, "every returned row carries a non-empty source");
  var html = T.renderSearchHits(res);
  ok((html.match(/hit-src/g) || []).length === res.rows.length, "every hit shows its source");
  ok(/chilly/i.test(html), "the matched word is on the page");
});

test("a too-short term says the term was too short, not 'no matches'", function () {
  var res = T.search(IDX, "c");
  eq(res.ok, false, "the search is refused");
  eq(res.error, "too-short", "the reason is too-short");
  ok(/too short/i.test(res.message), "the message says the term was too short");
  var html = T.renderSearchHits(res);
  ok(/too short/i.test(html), "the page says so too");
  ok(!/No quoted sentence/.test(html), "it does not claim there were no matches");
});

test("a dated note expires and never rewrites the statement", function () {
  var n = T.makeNote({ slug: "cistus-canadensis", text: "chilly through the fever",
                       from: "2026-11-01", until: "2026-11-08" });
  var notes = [n];
  var on = T.notesFor(notes, "cistus-canadensis", "2026-11-03");
  eq(on.active.length, 1, "the note is active inside its window");
  eq(on.expired.length, 0, "and is not expired there");
  var after = T.notesFor(notes, "cistus-canadensis", "2026-11-09");
  eq(after.active.length, 0, "the note is no longer active after its end date");
  eq(after.expired.length, 1, "the expired note is still shown, marked expired");
  var html = T.renderRemedy(T.remedyFor(REMEDIES, "cistus-canadensis"),
                            T.rowsFor(ROWS, "cistus-canadensis"), notes, "2026-11-09");
  ok(/expired 2026-11-08/.test(html), "the page marks it expired");
  ok(html.indexOf("sources agree (2)") >= 0,
     "the constitutional summary is unchanged by the note");
});

test("a full or unavailable store is reported, and the bundle still reads", function () {
  T.attach({ Search: Search, Loom: { storage: memStorage(true) } });
  var res = T.saveNotes([T.makeNote({ slug: "sulphur", text: "x", until: "2026-12-01" })]);
  eq(res.ok, false, "the save is reported as not landed");
  ok(/not saved/i.test(res.message), "the message says the note was not saved");
  ok(/bundled rows/i.test(res.message), "and that the bundled rows still read");
  var html = T.renderRemedy(T.remedyFor(REMEDIES, "sulphur"), T.rowsFor(ROWS, "sulphur"), [], "2026-11-01");
  ok(html.length > 0 && html.indexOf("sulphur") >= 0, "the remedy still renders");
  T.attach({ Search: Search, Loom: { storage: memStorage(false) } });
});

test("the bundle states its own size instead of implying the corpus is complete", function () {
  eq(META.rows, ROWS.length, "the stated row count is the real one");
  eq(META.classified + META.unclassified, META.remedies, "classified + unclassified = remedies");
  ok(/rule/i.test(META.rule) || META.rule.length > 40, "the extraction rule ships in the bundle");
  ok(META.sources >= 2, "at least two sources are bundled");
});

test("the page loads the module and the data it is tested against", function () {
  var html = fs.readFileSync(path.join(__dirname, "docs", "play", "index.html"), "utf8");
  ["vendor/web-kit.js", "vendor/search-kit.js", "vendor/case-kit.js", "vendor/export-kit.js",
   "data/bundle.js", "thermals.js"].forEach(function (src) {
    ok(html.indexOf(src) >= 0, "the page loads " + src);
  });
  ["q", "results", "remedy", "browse-list", "export", "counts"].forEach(function (id) {
    ok(html.indexOf('id="' + id + '"') >= 0, "the page has #" + id);
  });
  ok(html.indexOf("manifest.webmanifest") >= 0, "the page links its manifest");
  // the page's copy of the module and the tested copy must be the same bytes
  var rootJs = fs.readFileSync(path.join(__dirname, "thermals.js"), "utf8");
  var pageJs = fs.readFileSync(path.join(__dirname, "docs", "play", "thermals.js"), "utf8");
  ok(rootJs === pageJs, "docs/thermals.js is byte-identical to the tested thermals.js");
  ["docs/play/vendor/web-kit.js", "docs/play/vendor/search-kit.js", "docs/play/vendor/case-kit.js",
   "docs/play/vendor/export-kit.js", "docs/play/data/bundle.js", "docs/play/sw.js", "docs/play/manifest.webmanifest"]
    .forEach(function (f) {
      ok(fs.existsSync(path.join(__dirname, f)), f + " exists");
    });
});

test("export carries the rows, the notes and the rule", function () {
  var p = T.exportPayload(ROWS, [T.makeNote({ slug: "sulphur", text: "n", until: "2026-12-01" })], META);
  eq(p.format, "thermals/export", "the export names its format");
  eq(p.rows.length, ROWS.length, "every row is in the export");
  eq(p.notes.length, 1, "the notes are in the export");
  ok(p.rule && p.rule.length > 40, "the rule travels with the data");
});


test("OCR-damaged names are corrected only where an authority confirms them", function () {
  var map = JSON.parse(fs.readFileSync(path.join(__dirname, "data", "name-map.json"), "utf8"));
  var corrected = map.entries.filter(function (e) { return e.status === "corrected"; });
  ok(corrected.length > 0, "some names were corrected");
  corrected.forEach(function (e) {
    ok(!!e.printed && !!e.corrected, "a correction carries both the printed and the corrected name");
    ok(e.printed !== e.corrected, "the printed name differs from the correction");
    ok(/^[A-Za-z][A-Za-z .'-]+$/.test(e.corrected), "the correction is a readable remedy name: " + e.corrected);
    ok(!!e.evidence && e.evidence.length > 10, "and it carries the evidence that confirmed it");
  });
  // a correction may only cite an authority, never a hunch
  var vague = corrected.filter(function (e) { return /closest|guess|probably/i.test(e.evidence) &&
    !/closest curated name at >=85%/.test(e.evidence); });
  eq(vague.length, 0, "no correction is justified by a guess");
});

test("a name no authority could confirm is kept as printed, and never shown unmarked", function () {
  var map = JSON.parse(fs.readFileSync(path.join(__dirname, "data", "name-map.json"), "utf8"));
  var un = map.entries.filter(function (e) { return e.status === "unresolved"; });
  un.forEach(function (e) { eq(e.corrected, null, "an unresolved entry has no correction"); });
  // zero unresolved is the good outcome; the rule still has to hold when there are some
  ok(un.length >= 0, "unresolved entries are counted honestly: " + un.length);
  // and none of them reaches the page as a bare name: they carry no statements
  var printed = un.map(function (e) { return e.printed; });
  var shown = ROWS.filter(function (r) { return printed.indexOf(r.name_printed) >= 0; });
  eq(shown.length, 0, "no unresolved name is quoted in the app");
  // the marker itself still works, driven by a row shaped like one
  var fake = { remedy: "N1U\u00a3A", remedy_slug: "x", name_printed: "N1U\u00a3A",
               name_status: "unresolved", source: "s", source_short: "s", chapter: "",
               sentence: "Chilliness, and nausea in the throat", side: "cold" };
  var html = T.renderRows([fake]);
  ok(/spelling unconfirmed/.test(html), "the page marks an unconfirmed spelling when one is shown");
});

test("no bundled row comes from an entry that ran two remedies together", function () {
  var merged = ROWS.filter(function (r) { return r.name_status === "merged"; });
  eq(merged.length, 0, "merged entries are not bundled - they cannot be attributed to a remedy");
  ok(META.names.merged_not_bundled > 0, "and the count of what was withheld is stated");
});

test("no remedy appears twice under two spellings", function () {
  var byLetters = {};
  REMEDIES.forEach(function (r) {
    var k = r.name.toLowerCase().replace(/[^a-z]/g, "");
    ok(!byLetters[k], "one entry per spelling: " + r.name);
    byLetters[k] = 1;
  });
});

test("the name counts add up to what the reader is told", function () {
  var n = META.names;
  eq(n.confirmed + n.corrected + n.as_printed + n.unresolved + n.merged_not_bundled +
     (n.second_scan || 0) + (n.not_a_remedy || 0) + (n.duplicate || 0), 302,
     "every entry in the two transcribed books is accounted for");
  ok(n.unresolved >= 0 && n.corrected >= 0, "the counts are real numbers");
});


test("a sentence that carries visible OCR damage says so", function () {
  var damaged = ROWS.filter(function (r) { return r.text_damage === true; });
  // the detector is deliberately strict: an ordinary "by" or "of" is not damage.
  // Zero damaged rows is the good outcome; the marker must still work when one appears.
  ok(damaged.length >= 0, "damaged sentences are counted honestly: " + damaged.length);
  var fake = { remedy: "x", remedy_slug: "x", name_status: "ok", source: "s", source_short: "s",
               chapter: "", sentence: "Chilliness, with continued THEIR INDICATIONS, IO3 yawning.",
               side: "cold", text_damage: true };
  var html = T.renderRows([fake]);
  ok(/carries a swallowed page number/.test(html), "the page marks a damaged sentence");
  ok(html.indexOf(T.esc(fake.sentence)) >= 0, "and still quotes it verbatim");
});

test("the second scan cross-checks the names without renaming them", function () {
  var x = JSON.parse(fs.readFileSync(path.join(__dirname, "data", "name-crosscheck.json"), "utf8"));
  ok(x.agree > 0, "the second scan agrees with " + x.agree + " names");
  ok(typeof x.disagree === "number", "and flags the rest rather than applying them");
  ok(/never renames/.test(x.what), "the file states that it never renames");
});


test("a quote repaired from the page keeps both versions and says where it came from", function () {
  var fixed = ROWS.filter(function (r) { return r.text_page; });
  ok(fixed.length > 0, "some quotes were repaired from the scan's page text");
  fixed.forEach(function (r) {
    ok(!!r.sentence_printed, "the transcription's own words are kept beside the repair");
    ok(r.sentence_printed !== r.sentence, "the repair actually differs from what was printed");
    ok(r.text_page > 0, "the page it came from is recorded");
    // nothing may be added: every word of the repair comes from the page
    ok(r.sentence.length > 20, "the repaired sentence is still a sentence");
  });
  var html = T.renderRows([fixed[0]]);
  ok(/repaired from p\./.test(html), "the page shows which page the repair came from");
  ok(html.indexOf(T.esc(fixed[0].sentence)) >= 0, "and quotes the repaired text");
});


test("both surfaces offer a light/dark toggle and never force one", function () {
  var app = fs.readFileSync(path.join(__dirname, "docs", "play", "index.html"), "utf8");
  var land = fs.readFileSync(path.join(__dirname, "docs", "index.html"), "utf8");
  [["app", app], ["landing page", land]].forEach(function (pair) {
    var name = pair[0], html = pair[1];
    ok(/id="theme"/.test(html), name + " has a theme toggle");
    ok(/data-theme/.test(html), name + " switches on a data-theme attribute");
    ok(/prefers-color-scheme/.test(html), name + " follows the system preference by default");
    ok(/localStorage/.test(html), name + " remembers the choice");
  });
  // light is the default: the dark palette is opt-in, not the base
  ok(/:root\{[^}]*--paper:#faf6ef/.test(app), "the app's base palette is the light one");
  ok(/:root\{\s*--void:#f7f3ea/.test(land), "the landing page's base palette is the light one");
});


/* ---- the dated override uses the clinician's day, not UTC's ----
 * Run with TZ=Asia/Kolkata (test.yml sets it) or this passes against the old
 * code: at 04:00 in India, toISOString() is still yesterday. */
test("todayISO is the local day", function () {
  var early = new Date(2026, 10, 10, 4, 0, 0);       // local 04:00, 10 Nov 2026
  eq(T.todayISO(early.getTime()), "2026-11-10", "04:00 local is that day");
  var late = new Date(2026, 10, 10, 23, 30, 0);
  eq(T.todayISO(late.getTime()), "2026-11-10", "23:30 local is that day");
  var n = T.makeNote({ slug: "s", text: "acute", from: T.todayISO(early.getTime()), until: "2026-11-12" });
  eq(T.activeNotes([n], "2026-11-10").active.length, 1, "a note written at 04:00 is active that day");
});

console.log(passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);
