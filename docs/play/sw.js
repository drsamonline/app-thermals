/* Thermals — the service worker.

   THE RULE HERE, learned the hard way: **the HTML is network-first, everything else is
   cache-first.** A cache-first worker on the page itself hides every future release from
   everyone who has visited once — the reader keeps the old app forever, with no way to know
   and no way to ask for the new one. Offline still works: when the network is gone, the copy
   in the cache is served.

   Bump CACHE on every release that changes a file in FILES. The name is the only thing that
   makes the old cache get deleted.
*/
var CACHE = "thermals-v3";
var FILES = [
  "./", "index.html", "thermals.js", "icon.svg", "manifest.webmanifest",
  "vendor/web-kit.js", "vendor/search-kit.js", "vendor/case-kit.js", "vendor/export-kit.js",
  "data/bundle.js"
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return c.addAll(FILES.map(function (f) { return new Request(f, { cache: "reload" }); }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; })
        .map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;

  var isPage = req.mode === "navigate" ||
    (req.headers.get("accept") || "").indexOf("text/html") !== -1;

  if (isPage) {
    // network first, cache as the offline fallback
    e.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put("index.html", copy); });
        return res;
      }).catch(function () {
        return caches.match("index.html").then(function (hit) {
          return hit || caches.match("./");
        });
      })
    );
    return;
  }

  // assets: cache first, refreshed in the background
  e.respondWith(
    caches.match(req).then(function (hit) {
      if (hit) {
        fetch(req).then(function (res) {
          caches.open(CACHE).then(function (c) { c.put(req, res.clone()); });
        }).catch(function () {});
        return hit;
      }
      return fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); });
        return res;
      });
    })
  );
});
