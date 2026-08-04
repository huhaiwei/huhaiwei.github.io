---
layout: default
title: K'iche' fst
permalink: /k'iche'-fst/
---
<style>
  .parser-wrap {
    max-width: 700px;
    margin: 2em 0;
  }
  .parser-wrap input {
    font-family: inherit;
    font-size: 1.1em;
    padding: 0.4em 0.6em;
    border: 1px solid #ccc;
    border-radius: 4px;
    width: 100%;
    max-width: 320px;
    box-sizing: border-box;
  }
  .status {
    font-size: 0.9em;
    color: #666;
    margin: 0.4em 0;
    min-height: 1.3em;
  }
  .featured {
    margin: 0.75em 0;
  }
  .featured-label {
    font-size: 0.85em;
    color: #666;
    margin-bottom: 0.4em;
  }
  .featured-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  .featured-chip {
    font-family: monospace;
    font-size: 0.9em;
    padding: 0.25em 0.6em;
    background: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.15s;
  }
  .featured-chip:hover {
    background: #e8e8e8;
  }
  .wordlist {
    border: 1px solid #ddd;
    border-radius: 4px;
    max-height: 320px;
    overflow-y: auto;
    padding: 0;
    margin: 0.5em 0 1.5em 0;
    list-style: none;
    background: #fff;
  }
  .wordlist li {
    padding: 0.35em 0.7em;
    cursor: pointer;
    font-family: monospace;
    font-size: 0.95em;
    border-bottom: 1px solid #f0f0f0;
  }
  .wordlist li:last-child {
    border-bottom: none;
  }
  .wordlist li:hover,
  .wordlist li.active {
    background: #f5f5f5;
  }
  .wordlist li.active {
    outline: 1px solid #ccc;
  }
  .result {
    margin-top: 1em;
  }
  .result table {
    border-collapse: collapse;
    margin-top: 0.5em;
    font-size: 0.95em;
  }
  .result th, .result td {
    border: 1px solid #ddd;
    padding: 0.5em 0.8em;
    text-align: left;
    vertical-align: top;
  }
  .result th {
    background: #f5f5f5;
  }
  .result .no-match {
    color: #888;
    font-style: italic;
  }
  .seg-label {
    font-size: 0.9em;
    color: #666;
    margin: 1em 0 0.3em 0;
  }
  .seg-list {
    margin-bottom: 1em;
  }
  .seg-chain {
    margin: 0.3em 0;
  }
  .seg-sep {
    color: #999;
    margin: 0 0.3em;
    font-size: 0.9em;
  }
  .morpheme {
    display: inline-block;
    background: #f0f0f0;
    padding: 0.15em 0.5em;
    border-radius: 4px;
    margin: 0.1em;
    font-family: monospace;
    font-size: 0.9em;
  }
</style>
<div class="parser-wrap">
  <input type="text" id="word-input" placeholder="Search K'iche' words…" autocomplete="off">
  <div class="featured">
    <div class="featured-label">Try these:</div>
    <div class="featured-chips" id="featured-chips"></div>
  </div>
  <div id="status" class="status"></div>
  <ul id="wordlist" class="wordlist"></ul>
  <div id="output" class="result"></div>
</div>
<script>
let dictionary = {};
let wordlist = [];
let filtered = [];
let selectedIndex = -1;

const featuredWords = [
  "nutinamit",
  "katinchʼabʼej",
  "jun",
  "xekitzoqopij",
  "ubʼajixik",
  "retzʼabʼaʼl",
  "kixkitzuqu"

];

const input = document.getElementById('word-input');
const listEl = document.getElementById('wordlist');
const statusEl = document.getElementById('status');
const output = document.getElementById('output');
const chipsEl = document.getElementById('featured-chips');

// Load both data files
Promise.all([
  fetch('{{ "/assets/json/quc_dict.json" | relative_url }}').then(r => r.json()),
  fetch('{{ "/assets/json/quc_wordlist.json" | relative_url }}').then(r => r.json())
]).then(([dict, words]) => {
  dictionary = dict;
  wordlist = words;
  renderFeatured();
  renderList(wordlist.slice(0, 100));
  statusEl.textContent = 'Type to filter ' + wordlist.length.toLocaleString() + ' words';
}).catch(err => {
  statusEl.textContent = 'Error loading dictionary.';
});

function normalize(str) {
  return str.toLowerCase()
    .replace(/['’'‘'´]/g, 'ʼ')
    .normalize('NFD').replace(/̈/g, '').normalize('NFC');
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
}

function renderFeatured() {
  chipsEl.innerHTML = featuredWords.map(w =>
    '<span class="featured-chip" data-word="' + escapeHtml(w) + '">' + escapeHtml(w) + '</span>'
  ).join('');
}

function filterWords(query) {
  const q = normalize(query);
  if (!q) return wordlist.slice(0, 100);

  const matches = wordlist.filter(w => normalize(w).includes(q));

  matches.sort((a, b) => {
    const aNorm = normalize(a);
    const bNorm = normalize(b);
    const aStarts = aNorm.startsWith(q);
    const bStarts = bNorm.startsWith(q);
    if (aStarts && !bStarts) return -1;
    if (!aStarts && bStarts) return 1;
    return aNorm.localeCompare(bNorm);
  });

  return matches.slice(0, 100);
}

function renderList(words) {
  filtered = words;
  selectedIndex = -1;
  if (words.length === 0) {
    listEl.innerHTML = '<li class="no-match">No matches</li>';
    return;
  }
  listEl.innerHTML = words.map((w, i) =>
    '<li data-index="' + i + '" data-word="' + escapeHtml(w) + '">' + escapeHtml(w) + '</li>'
  ).join('');
}

function updateStatus(query) {
  const q = query.trim();
  if (!q) {
    statusEl.textContent = 'Showing first 100 of ' + wordlist.length.toLocaleString() + ' words';
  } else {
    const total = wordlist.filter(w => normalize(w).includes(normalize(q))).length;
    statusEl.textContent = 'Showing ' + filtered.length + ' of ' + total + ' matches for "' + escapeHtml(q) + '"';
  }
}

function selectWord(word) {
  input.value = word;
  analyse(word);
}

function setActive(idx) {
  const items = listEl.querySelectorAll('li[data-index]');
  items.forEach(el => el.classList.remove('active'));
  if (idx >= 0 && idx < items.length) {
    items[idx].classList.add('active');
    items[idx].scrollIntoView({ block: 'nearest' });
  }
}

// Input events
input.addEventListener('input', function() {
  const q = input.value;
  renderList(filterWords(q));
  updateStatus(q);
});

input.addEventListener('keydown', function(e) {
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    selectedIndex = Math.min(selectedIndex + 1, filtered.length - 1);
    setActive(selectedIndex);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    selectedIndex = Math.max(selectedIndex - 1, 0);
    setActive(selectedIndex);
  } else if (e.key === 'Enter') {
    e.preventDefault();
    if (selectedIndex >= 0 && filtered[selectedIndex]) {
      selectWord(filtered[selectedIndex]);
    } else if (filtered.length === 1) {
      selectWord(filtered[0]);
    } else {
      analyse(input.value.trim());
    }
  }
});

// List click
listEl.addEventListener('click', function(e) {
  const li = e.target.closest('li[data-word]');
  if (!li) return;
  selectWord(li.dataset.word);
});

// Featured chips click
chipsEl.addEventListener('click', function(e) {
  const chip = e.target.closest('.featured-chip');
  if (!chip) return;
  selectWord(chip.dataset.word);
});

// Analysis
function analyse(raw) {
  const key = normalize(raw);
  if (!key) { output.innerHTML = ''; return; }

  const entry = dictionary[key];
  if (!entry) {
    output.innerHTML = '<p class="no-match">No analysis found for <strong>' + escapeHtml(raw) + '</strong>.</p>';
    return;
  }

  const morphemes = entry.morphemes || [];
  const analyses = entry.analyses || [];

  if (morphemes.length === 0 && analyses.length === 0) {
    output.innerHTML = '<p class="no-match">No analysis found for <strong>' + escapeHtml(raw) + '</strong>.</p>';
    return;
  }

  let html = '<p><strong>' + escapeHtml(raw) + '</strong>';
  if (analyses.length > 0) {
    html += ' &mdash; ' + analyses.length + ' analys' + (analyses.length === 1 ? 'is' : 'es');
  }
  if (morphemes.length > 0) {
    html += ', ' + morphemes.length + ' segmentation' + (morphemes.length === 1 ? '' : 's');
  }
  html += '</p>';

  if (morphemes.length > 0) {
    html += '<p class="seg-label">Segmentations</p>';
    html += '<div class="seg-list">';
    morphemes.forEach(seg => {
      html += '<div class="seg-chain">';
      seg.forEach((m, i) => {
        html += '<span class="morpheme">' + escapeHtml(m) + '</span>';
        if (i < seg.length - 1) html += '<span class="seg-sep">&gt;</span>';
      });
      html += '</div>';
    });
    html += '</div>';
  }

  if (analyses.length > 0) {
    html += '<table><tr><th>#</th><th>Analysis</th></tr>';
    analyses.forEach((a, i) => {
      html += '<tr><td>' + (i + 1) + '</td><td><code>' + escapeHtml(a) + '</code></td></tr>';
    });
    html += '</table>';
  }

  output.innerHTML = html;
}
</script>