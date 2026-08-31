/* reactive.js — logica della homepage reattiva
   Carica /data/feed.json, ruota una notizia ogni 60s, posiziona
   le opere correlate in punti fluidi senza sovrapposizioni.
   Solo se body.is-home. Rispetta prefers-reduced-motion. */

(function () {
  "use strict";

  if (!document.body.classList.contains("is-home")) return;

  var ROTATION_INTERVAL = 60000; // 60 secondi
  var FADE_OUT_MS = 1000;        // attesa tra fade-out vecchie e arrivo nuove
  var MAX_WORKS_VISIBLE = 5;
  var FONT_SIZE_MIN = 18;
  var FONT_SIZE_MAX = 30;

  var stage = document.getElementById("reactive-stage");
  var newsHeadline = document.getElementById("news-headline");
  var newsLang = document.getElementById("news-lang");
  var newsSource = document.getElementById("news-source");
  var silenceEl = document.getElementById("silence-phrase");

  var feed = null;
  var rotationIdx = 0;
  var works = {}; // mappa id → { title, year, medium, link }

  // === Carica feed.json e catalogo opere ===
  Promise.all([
    fetch("/data/feed.json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("feed.json " + r.status);
      return r.json();
    }),
    fetch("/data/works.json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) return null;
      return r.json();
    }).catch(function () { return null; })
  ]).then(function (results) {
    feed = results[0];
    var worksData = results[1];
    if (worksData && worksData.works) {
      worksData.works.forEach(function (w) { works[w.id] = w; });
    }
    if (!feed.rotation || feed.rotation.length === 0) {
      newsHeadline.textContent = "il dispositivo è in attesa di notizie";
      newsLang.textContent = "[··]";
      return;
    }
    setTimeout(function () { rotate(); }, 600);
    if (ROTATION_INTERVAL > 0) {
      setInterval(rotate, ROTATION_INTERVAL);
    }
  }).catch(function (err) {
    console.warn("Feed non disponibile:", err);
    newsHeadline.textContent = "il dispositivo è in attesa di notizie";
    newsLang.textContent = "[··]";
  });

  // === Rotation step ===
  function rotate() {
    if (!feed || !feed.rotation || feed.rotation.length === 0) return;
    var entry = feed.rotation[rotationIdx % feed.rotation.length];
    rotationIdx++;

    // 1) Fade-out della headline e delle opere visibili
    newsHeadline.classList.add("fade-out");
    Array.prototype.forEach.call(stage.querySelectorAll(".work-node"), function (n) {
      n.classList.remove("is-visible");
    });
    silenceEl.classList.remove("is-visible");

    setTimeout(function () {
      // 2) Aggiorna headline
      updateNewsBar(entry);
      // 3) Ricostruisce le opere o mostra silenzio
      stage.querySelectorAll(".work-node").forEach(function (n) { n.remove(); });

      if (!entry.works || entry.works.length === 0) {
        showSilence();
      } else {
        placeWorks(entry.works);
      }
      // 4) Fade-in headline
      newsHeadline.classList.remove("fade-out");
    }, FADE_OUT_MS);
  }

  function updateNewsBar(entry) {
    newsHeadline.textContent = entry.headline || "—";
    newsLang.textContent = "[" + (entry.lang || "··").toUpperCase() + "]";
    var src = entry.source || "";
    var ts = "";
    if (entry.timestamp) {
      var d = new Date(entry.timestamp);
      if (!isNaN(d.getTime())) {
        var dd = String(d.getDate()).padStart(2, "0");
        var mm = String(d.getMonth() + 1).padStart(2, "0");
        var yy = String(d.getFullYear()).slice(2);
        var hh = String(d.getHours()).padStart(2, "0");
        var mn = String(d.getMinutes()).padStart(2, "0");
        ts = " · " + dd + "." + mm + "." + yy + " " + hh + ":" + mn;
      }
    }
    newsSource.textContent = src + ts;
  }

  function showSilence() {
    if (!feed.silence_phrases || feed.silence_phrases.length === 0) return;
    var phrase = feed.silence_phrases[Math.floor(Math.random() * feed.silence_phrases.length)];
    silenceEl.textContent = phrase;
    silenceEl.classList.add("is-visible");
  }

  // === Posizionamento fluido senza sovrapposizioni ===
  function placeWorks(workIds) {
    var stageBox = stage.getBoundingClientRect();
    var W = stageBox.width;
    var H = stageBox.height;
    var occupied = [];
    var reserved = collectReservedZones();

    var ids = workIds.slice(0, MAX_WORKS_VISIBLE);

    ids.forEach(function (id) {
      var w = works[id];
      if (!w) return;
      var fontSize = FONT_SIZE_MIN + Math.random() * (FONT_SIZE_MAX - FONT_SIZE_MIN);
      var titleW = estimateTextWidth(w.title || id, fontSize);
      var boxW = Math.min(titleW + 20, 360);
      var boxH = fontSize * 2.4;

      var pos = findFreeSpot(W, H, boxW, boxH, occupied, reserved);
      if (!pos) return;

      occupied.push({ x: pos.x, y: pos.y, w: boxW, h: boxH });
      var node = renderWork(w, pos, fontSize);
      stage.appendChild(node);
      // animate-in
      requestAnimationFrame(function () {
        node.classList.add("is-visible");
      });
    });
  }

  function collectReservedZones() {
    var zones = [];
    var stageBox = stage.getBoundingClientRect();
    Array.prototype.forEach.call(document.querySelectorAll(".float-link"), function (el) {
      var b = el.getBoundingClientRect();
      zones.push({
        x: b.left - stageBox.left - 30,
        y: b.top - stageBox.top - 10,
        w: b.width + 60,
        h: b.height + 30
      });
    });
    return zones;
  }

  function findFreeSpot(W, H, boxW, boxH, occupied, reserved) {
    for (var i = 0; i < 80; i++) {
      var x = Math.random() * (W - boxW - 20) + 10;
      var y = Math.random() * (H - boxH - 20) + 10;
      var rect = { x: x, y: y, w: boxW, h: boxH };
      var collide = false;
      for (var j = 0; j < occupied.length; j++) {
        if (overlaps(rect, occupied[j], 16)) { collide = true; break; }
      }
      if (!collide) {
        for (var k = 0; k < reserved.length; k++) {
          if (overlaps(rect, reserved[k], 8)) { collide = true; break; }
        }
      }
      if (!collide) return { x: x, y: y };
    }
    return null;
  }

  function overlaps(a, b, padding) {
    padding = padding || 0;
    return !(a.x + a.w + padding < b.x ||
             b.x + b.w + padding < a.x ||
             a.y + a.h + padding < b.y ||
             b.y + b.h + padding < a.y);
  }

  function estimateTextWidth(text, fontSize) {
    return text.length * fontSize * 0.42;
  }

  function renderWork(w, pos, fontSize) {
    var a = document.createElement("a");
    a.className = "work-node";
    a.href = w.link || ("/lavori/" + w.id + "/");
    a.style.left = pos.x + "px";
    a.style.top = pos.y + "px";
    a.style.fontSize = fontSize + "px";
    var title = document.createElement("span");
    title.className = "w-title";
    title.textContent = w.title || w.id;
    a.appendChild(title);
    if (w.year || w.medium) {
      var meta = document.createElement("span");
      meta.className = "w-meta";
      var bits = [];
      if (w.year) bits.push(String(w.year));
      if (w.medium) bits.push(w.medium);
      meta.textContent = bits.join(" · ");
      a.appendChild(meta);
    }
    return a;
  }
})();
