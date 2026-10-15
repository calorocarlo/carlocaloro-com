/* concepts.js — interazioni del campo concetti.
   Solo se il body ha la classe is-home. Rispetta prefers-reduced-motion. */

(function () {
  'use strict';

  if (!document.body.classList.contains('is-home')) return;

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var nodes = Array.prototype.slice.call(document.querySelectorAll('.concept-node'));
  if (!nodes.length) return;

  // Mappa slug -> elemento
  var bySlug = {};
  nodes.forEach(function (n) { bySlug[n.dataset.slug] = n; });

  // Hover: evidenzia i vicini riducendo l'opacità degli altri
  function highlight(node) {
    if (reduced) return;
    var neighbours = (node.dataset.neighbours || '').split(/\s+/).filter(Boolean);
    var keep = {}; keep[node.dataset.slug] = true;
    neighbours.forEach(function (s) { keep[s] = true; });
    nodes.forEach(function (n) {
      if (keep[n.dataset.slug]) {
        n.style.opacity = '1';
        if (n !== node) n.style.color = 'var(--accent)';
      } else {
        n.style.opacity = '0.25';
      }
    });
  }

  function reset() {
    nodes.forEach(function (n) {
      n.style.opacity = '';
      n.style.color = '';
    });
  }

  nodes.forEach(function (n) {
    n.addEventListener('mouseenter', function () { highlight(n); });
    n.addEventListener('focus', function () { highlight(n); });
    n.addEventListener('mouseleave', reset);
    n.addEventListener('blur', reset);
  });

  // Disposizione tipografica: shuffling leggero per evitare lettura lineare.
  // Eseguito una sola volta al load. Niente animazione.
  function shuffle(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
    }
    return arr;
  }
  var field = document.querySelector('.concept-field');
  if (field) {
    // Mescola TUTTI i .field-node insieme (concetti + voci sezione)
    var allNodes = Array.prototype.slice.call(field.children);
    var meta = allNodes.filter(function (c) { return c.dataset.weight === '0'; });
    var others = shuffle(allNodes.filter(function (c) { return c.dataset.weight !== '0'; }));
    field.innerHTML = '';
    meta.concat(others).forEach(function (c) { field.appendChild(c); });
  }
})();
