/* Thermals — what each classical source actually says about a remedy's thermal
 * reaction, in its own words, with the source named.
 *
 * Zero dependencies of its own: the shared work is delegated to the estate's
 * kits, injected in `Thermals.attach` so the same code runs in the page and in
 * test-node.js —
 *
 *   Search  search-kit  ranked lookup across the bundled rows
 *   Case    case-kit    the dated override record
 *   Export  export-kit  getting bytes off the device
 *   Loom    web-kit     storage, and whether a write actually landed
 *
 * THE ONE RULE THIS FILE ENFORCES: the app quotes and compares. It never
 * assigns, derives, averages or infers a thermal state. A row's `side` is read
 * off the phrase the source itself used; the summary compares the sides of the
 * sources that spoke, and when only one source spoke it says so.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Thermals = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var T = { version: "1.0.0" };
  var deps = {};

  T.attach = function (d) { deps = d || {}; return T; };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  T.esc = esc;

  /* ------------------------------------------------------------------ sides */

  // Which way the source's own words point. Not a state label: it is read off
  // the phrase the sentence quotes.
  T.sideOf = function (row) { return row && row.side === "heat" ? "heat" : "cold"; };

  T.SIDE_WORD = {
    cold: "the cold side",
    heat: "the heat side"
  };

  /* --------------------------------------------------------------- summary */

  T.summarise = function (rows) {
    var list = (rows || []).slice();
    if (!list.length) {
      return {
        kind: "unclassified",
        label: "unclassified",
        sources: [],
        detail: "No bundled source carries a thermal statement for this remedy. " +
          "It is listed as unclassified rather than assigned a state."
      };
    }
    var sources = [];
    list.forEach(function (r) {
      if (r.source_short && sources.indexOf(r.source_short) < 0) sources.push(r.source_short);
    });
    if (sources.length === 1) {
      return {
        kind: "one-source",
        label: "one source only",
        sources: sources,
        detail: "One bundled source speaks for this remedy. That is not agreement: " +
          "no second source was found to agree with it."
      };
    }
    var sides = {};
    list.forEach(function (r) { sides[T.sideOf(r)] = true; });
    if (Object.keys(sides).length === 1) {
      return {
        kind: "agree",
        label: "sources agree (" + sources.length + ")",
        sources: sources,
        detail: "All " + sources.length + " sources that speak here point to " +
          T.SIDE_WORD[Object.keys(sides)[0]] + ". Each is quoted separately; " +
          "nothing has been merged into one value."
      };
    }
    return {
      kind: "disagree",
      label: "sources disagree",
      sources: sources,
      detail: "The sources that speak here do not point the same way. " +
        "Both are quoted; neither is preferred."
    };
  };

  /* ---------------------------------------------------------------- lookup */

  T.rowsFor = function (rows, slug) {
    return (rows || []).filter(function (r) { return r.remedy_slug === slug; });
  };

  T.remedyFor = function (index, slug) {
    for (var i = 0; i < (index || []).length; i++) if (index[i].slug === slug) return index[i];
    return null;
  };

  T.buildIndex = function (rows) {
    if (!deps.Search || !deps.Search.index) throw new Error("search-kit is not attached");
    return deps.Search.index(rows || [], { keys: ["sentence", "remedy", "source_short", "chapter"] });
  };

  // A search over the QUOTED SENTENCES. Every hit is a row, so every hit carries
  // the source that said it — a hit can never be a bare remedy name with the
  // provenance stripped off.
  T.search = function (idx, term, opts) {
    var q = String(term == null ? "" : term).trim();
    if (q.length < 2) {
      return { ok: false, error: "too-short",
        message: "That term is too short — type at least two letters." };
    }
    var hits = idx.query(q, { limit: (opts && opts.limit) || 60, fuzzy: !!(opts && opts.fuzzy) });
    return { ok: true, query: q, rows: hits.map(function (h) { return h.item; }) };
  };

  /* ---------------------------------------------------------------- notes */

  // A dated override: a temporary shift (an acute fever, a pregnancy, a proving)
  // that expires. It never rewrites the constitutional statement, and an expired
  // one stays visible as expired rather than disappearing.
  T.todayISO = function (now) {
    var d = now == null ? new Date() : new Date(now);
    return d.toISOString().slice(0, 10);
  };

  T.makeNote = function (o) {
    o = o || {};
    var from = o.from || T.todayISO();
    return {
      id: o.id || ("n" + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36)),
      slug: String(o.slug || ""),
      text: String(o.text || "").trim(),
      from: from,
      until: o.until || from
    };
  };

  T.activeNotes = function (notes, today) {
    var d = today || T.todayISO();
    var active = [], expired = [];
    (notes || []).forEach(function (n) {
      if (!n || !n.text) return;
      (String(n.until) >= d ? active : expired).push(n);
    });
    return { active: active, expired: expired };
  };

  T.notesFor = function (notes, slug, today) {
    var s = T.activeNotes(notes, today);
    return {
      active: s.active.filter(function (n) { return n.slug === slug; }),
      expired: s.expired.filter(function (n) { return n.slug === slug; })
    };
  };

  // Returns {ok:true} only when the bytes really landed. web-kit's storage.set
  // answers false when the quota is gone, and that is reported rather than
  // swallowed: the bundled rows are unaffected either way.
  T.saveNotes = function (notes) {
    if (!deps.Loom || !deps.Loom.storage) return { ok: false, message: "Storage is unavailable." };
    var ok = deps.Loom.storage.set("thermals:notes", notes || []);
    if (!ok) {
      return { ok: false,
        message: "Storage is full or unavailable — the note was not saved. " +
          "The bundled rows still read exactly as before." };
    }
    return { ok: true };
  };

  T.loadNotes = function () {
    if (!deps.Loom || !deps.Loom.storage) return [];
    var v = deps.Loom.storage.get("thermals:notes", []);
    return Array.isArray(v) ? v : [];
  };

  /* --------------------------------------------------------------- export */

  T.exportPayload = function (rows, notes, meta) {
    return {
      format: "thermals/export",
      version: 1,
      exported: new Date().toISOString(),
      rule: (meta && meta.rule) || "",
      counts: (meta && meta.counts) || {},
      rows: rows || [],
      notes: notes || []
    };
  };

  /* --------------------------------------------------------------- render */

  function sourceLine(rows) {
    var seen = [], out = [];
    rows.forEach(function (r) {
      if (seen.indexOf(r.source_short) < 0) { seen.push(r.source_short); out.push(r); }
    });
    return out;
  }

  T.renderSummary = function (rows) {
    var s = T.summarise(rows);
    return '<p class="summary summary--' + esc(s.kind) + '" data-kind="' + esc(s.kind) + '">' +
      '<strong>' + esc(s.label) + "</strong> " + esc(s.detail) + "</p>";
  };

  // The transcription is OCR. Where a name was corrected, the page says which
  // name the transcription printed and why it was corrected, so the reader can
  // check the correction rather than take it on trust.
  T.NAME_NOTE = {
    corrected: "printed as",
    "corrected-scanned": "printed as",
    "corrected-slot": "printed as",
    merged: "the transcription ran this entry together with another remedy",
    unresolved: "the transcription's spelling could not be confirmed; kept as printed",
    "ok-as-printed": ""
  };

  T.renderRows = function (rows) {
    if (!rows || !rows.length) return "";
    return rows.map(function (r) {
      var note = "";
      if (r.name_status === "unresolved") {
        note = ' <span class="name-note">spelling unconfirmed — this is the transcription\'s own text</span>';
      } else if (r.name_status && r.name_status !== "ok" && r.name_status !== "ok-as-printed" &&
          r.name_printed && r.name_printed !== r.remedy) {
        note = ' <span class="name-note">' + esc(T.NAME_NOTE[r.name_status] || "printed as") +
          " “" + esc(r.name_printed) + "”</span>";
      }
      return '<figure class="row" data-source="' + esc(r.source_short) + '">' +
        "<blockquote>" + esc(r.sentence) + "</blockquote>" +
        '<figcaption><span class="src">' + esc(r.source) + "</span>" +
        (r.chapter ? ' <span class="chapter">· ' + esc(r.chapter) + "</span>" : "") +
        note + "</figcaption></figure>";
    }).join("");
  };

  T.renderNotes = function (notes, slug, today) {
    var n = T.notesFor(notes, slug, today);
    var html = "";
    if (n.active.length) {
      html += '<ul class="notes notes--active">' + n.active.map(function (x) {
        return '<li><span class="when">' + esc(x.from) + " → " + esc(x.until) + "</span> " +
          esc(x.text) + "</li>";
      }).join("") + "</ul>";
    }
    if (n.expired.length) {
      html += '<ul class="notes notes--expired">' + n.expired.map(function (x) {
        return '<li><span class="when">expired ' + esc(x.until) + "</span> " + esc(x.text) + "</li>";
      }).join("") + "</ul>";
    }
    return html;
  };

  T.renderRemedy = function (remedy, rows, notes, today) {
    var list = rows || [];
    var s = T.summarise(list);
    var html = '<h2 class="r-name">' + esc(remedy ? remedy.name : "") + "</h2>";
    if (list.length) {
      html += T.renderSummary(list);
      html += '<div class="sources">' + sourceLine(list).map(function (r) {
        return '<span class="chip">' + esc(r.source_short) + "</span>";
      }).join("") + "</div>";
      html += T.renderRows(list);
    } else {
      html += '<p class="none">No bundled source carries a thermal statement for this remedy. ' +
        "Nothing has been assigned to it.</p>";
    }
    var n = T.renderNotes(notes, remedy ? remedy.slug : "", today);
    if (n) html += '<h3 class="notes-h">Your dated notes</h3>' + n;
    return html;
  };

  T.renderSearchHits = function (res) {
    if (!res.ok) return '<p class="msg msg--warn">' + esc(res.message) + "</p>";
    if (!res.rows.length) {
      return '<p class="msg">No quoted sentence carries “' + esc(res.query) + "” in any bundled source.</p>";
    }
    return '<p class="msg">' + res.rows.length + " quoted sentence" +
      (res.rows.length === 1 ? "" : "s") + " carry “" + esc(res.query) + "”</p>" +
      res.rows.map(function (r) {
        return '<a class="hit" href="#/remedy/' + esc(r.remedy_slug) + '">' +
          '<blockquote>' + esc(r.sentence) + "</blockquote>" +
          '<span class="hit-src">' + esc(r.source) + "</span></a>";
      }).join("");
  };

  return T;
});
