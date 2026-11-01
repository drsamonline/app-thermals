/* Thermals — a cache-first service worker, so the app opens with the network off.
   Every file it needs is bundled; nothing is fetched from a server at any point. */
var CACHE = "thermals-v1";
var FILES = [
  "./", "index.html", "thermals.js", "icon.svg", "manifest.webmanifest",
  "vendor/web-kit.js", "vendor/search-kit.js", "vendor/case-kit.js", "vendor/export-kit.js",
  "data/bundle.js"
];
self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(FILES); })
    .then(function () { return self.skipWaiting(); }));
});
self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  e.respondWith(caches.match(e.request).then(function (hit) {
    return hit || fetch(e.request).then(function (res) {
      var copy = res.clone();
      caches.open(CACHE).then(function (c) { c.put(e.request, copy); });
      return res;
    }).catch(function () { return caches.match("index.html"); });
  }));
});
