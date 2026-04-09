---
layout: page
title: Biloxi Dictionary
permalink: /dictionary/
nav: true
---

<div id="password-gate" style="text-align: center; margin-top: 50px;">
  <h3>This dictionary is private.</h3>
  <p>Please enter the password to view the contents.</p>
  <input type="password" id="pass-input" placeholder="Password" style="padding: 10px; border-radius: 5px; border: 1px solid var(--global-divider-color);" />
  <button type="button" onclick="window.checkPassword()" style="padding: 10px 20px; border-radius: 5px; cursor: pointer; background-color: var(--global-theme-color); color: white; border: none;">Enter</button>
  <p id="pass-error" style="color: red; display: none; margin-top: 10px;">Incorrect password.</p>
</div>

<div id="dictionary-content" style="display: none;" markdown="1">

Welcome to the digital Biloxi dictionary, a work in progress based on data from Kaufman's (2020) *Kadakathi Tanêks-Tąyosą*. You can search for Biloxi words or their English translations below. 

> **Outstanding issues:**
> * PDF parsing failing at certain multi-line entries.
> * Certain "parts of speech" not recognised as such (DIR/LOC, prefixes, etc).

<style>
  #search { 
    width: 100%; 
    padding: 10px; 
    font-size: 16px; 
    margin-bottom: 20px;
    border: 1px solid var(--global-divider-color);
    background-color: var(--global-bg-color);
    color: var(--global-text-color);
    border-radius: 5px;
  }

  .dict-entry { 
    border-bottom: 1px solid var(--global-divider-color); 
    padding: 15px 10px; 
    margin-bottom: 15px; 
    border-radius: 5px;
    transition: background-color 1s ease-out;
  }

  .dict-entry h3 { 
    margin: 0 0 10px 0; 
  }

  .dict-source { 
    color: var(--global-text-color-light); 
    font-size: 0.85em; 
    display: block;
    margin-top: 10px;
  }

  .dict-conjugation {
    margin-top: 10px;
    font-size: 0.9em;
    background-color: var(--global-bg-color);
    border: 1px solid var(--global-divider-color);
    padding: 10px;
    border-radius: 5px;
    display: inline-block;
  }

  .dict-conjugation table {
    margin-bottom: 0;
  }

  .dict-conjugation th, .dict-conjugation td {
    padding: 2px 15px 2px 0;
    border: none;
  }

  .dict-related {
    margin-top: 15px;
  }

  .dict-related a {
    color: var(--global-theme-color);
    text-decoration: underline;
    cursor: pointer;
  }

  .dict-related a:hover {
    color: var(--global-hover-color);
  }

  .char-btn:hover {
    background-color: var(--global-divider-color);
  }
</style>

<label style="display:block; margin-bottom:10px;">
  <input type="checkbox" id="strict-toggle" />
  Strict matching (exact characters). When off, both your query and dictionary entries are stripped of diacritics before matching (e.g. “a” matches “ą”, and “ą” also matches “a”).
</label>

<input id="search" placeholder="Search for a Biloxi word or English translation..." />

<div id="char-bar" style="
  margin-bottom: 15px;
  padding: 8px;
  border: 1px solid var(--global-divider-color);
  border-radius: 5px;
  font-size: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
"></div>

<div id="entries"></div>

</div>

<script>
let data = [];
let debounceTimer;

// PASSWORD
const correctPassword = "ayeki";

if (sessionStorage.getItem("dictAuth") === "true") {
  unlockDictionary();
}

document.getElementById("pass-input").addEventListener("keypress", function(event) {
  if (event.key === "Enter") checkPassword();
});

function checkPassword() {
  const input = document.getElementById('pass-input').value;
  if (input === correctPassword) {
    sessionStorage.setItem("dictAuth", "true");
    unlockDictionary();
  } else {
    document.getElementById('pass-error').style.display = 'block';
  }
}

function unlockDictionary() {
  document.getElementById('password-gate').style.display = 'none';
  document.getElementById('dictionary-content').style.display = 'block';
  loadDictionary();
}

// LOAD
function loadDictionary() {
  fetch("{{ '/assets/json/biloxi_dictionary.json' | relative_url }}")
    .then(res => res.json())
    .then(json => {
      data = json;
      render(data);
      renderCharBar();
    });
}

// DIACRITICS
function removeDiacritics(str) {
  if (!str) return "";
  return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

// NAVIGATION
window.goToEntry = function(entryId) {
  document.getElementById('search').value = '';
  render(data);

  const target = document.getElementById(entryId);
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    target.style.backgroundColor = 'var(--global-divider-color)';
    setTimeout(() => target.style.backgroundColor = 'transparent', 1500);
  }
};

// RENDER
function render(entries) {
  const container = document.getElementById('entries');

  if (entries.length === 0) {
    container.innerHTML = '<p>No results found.</p>';
    return;
  }

  const html = entries.map(entry => {
    const definitionsHtml = entry.definitions.map(d =>
      `<li><b>${d.part_of_speech}</b>: ${d.text}</li>`
    ).join('');

    let conjugationHtml = '';
    if (entry.conjugation && Object.keys(entry.conjugation).length > 0) {
      const conjRows = Object.entries(entry.conjugation).map(([person, word]) =>
        `<tr><td><b>${person}</b></td><td>${word}</td></tr>`
      ).join('');

      conjugationHtml = `
        <div class="dict-conjugation">
          <b>Conjugations:</b>
          <table>${conjRows}</table>
        </div>`;
    }

    let relatedHtml = '';
    if (entry.related_entries && entry.related_entries.length > 0) {
      const relatedLinks = entry.related_entries.map(relId => {
        const relEntry = data.find(e => e.id === relId);
        const text = relEntry ? relEntry.headword : relId;
        return `<a onclick="goToEntry('${relId}')">${text}</a>`;
      }).join(', ');

      relatedHtml = `<div class="dict-related"><b>Related:</b> ${relatedLinks}</div>`;
    }

    return `
      <div class="dict-entry" id="${entry.id}">
        <h3>${entry.headword}</h3>
        <ul>${definitionsHtml}</ul>
        ${conjugationHtml}
        ${relatedHtml}
        <span class="dict-source">Source: ${entry.source || 'Unknown'}</span>
      </div>`;
  }).join('');

  container.innerHTML = html;
}

// SEARCH
document.getElementById('search').addEventListener('input', e => {
  clearTimeout(debounceTimer);

  debounceTimer = setTimeout(() => {
    const rawQuery = e.target.value.toLowerCase();
    const strict = document.getElementById('strict-toggle').checked;

    const q = strict ? rawQuery : removeDiacritics(rawQuery);

    const filtered = data.filter(entry => {
      const headword = entry.headword.toLowerCase();
      const defs = entry.definitions.map(d => d.text.toLowerCase());

      if (strict) {
        return headword.includes(q) || defs.some(d => d.includes(q));
      } else {
        return removeDiacritics(headword).includes(q) ||
               defs.some(d => removeDiacritics(d).includes(q));
      }
    });

    render(filtered);
  }, 200);
});

// OLD CHARACTER BAR (flattened, lowercase only)
/*   "a","ạ","â","ă","b","c","d","dȼ","dj","e","ē","ĕ","ê","f","g","h",
  "i","ī","ĭ","j","k","x","x̣","ḳ","l","m","n","ñ","ⁿ","o","ō",
  "p","p̣","r","s","t","ṭ","tc","tç","u","ū","û","ŭ","ụ","ü",
  "w","y",".",",","“","”","´","+","±","[","]","-","<","(+)",
  "ą","á","č","ę","ə","ɛ","į","ɔ","ɔ̨","φ","ú","š","ʔ","·",
  "ǫ","#","ə̨" */

const charList = [
  // PRIORITY FIRST
  "ą","ę","į","ǫ",

  // rest
  "á","ạ","â","ă","č","ç","ȼ","ē","ĕ","ê","ə","ə̨","ɛ", 
  "ī","ĭ","ḳ","ñ","ⁿ","ō",
  "p̣","š","ṭ","ú","ū","û","ŭ","ụ","ü",
  "x̣","´","+","±",
  "ɔ","ɔ̨","φ","ʔ","·"
];

function renderCharBar() {
  const bar = document.getElementById("char-bar");

  bar.innerHTML = charList.map(ch =>
    `<span class="char-btn" data-char="${ch}" style="
      cursor:pointer;
      padding:6px 8px;
      border-radius:4px;
      display:inline-block;
    ">${ch}</span>`
  ).join("");
}

// CLICK INSERT
document.addEventListener("click", e => {
  if (e.target.classList.contains("char-btn")) {
    const input = document.getElementById("search");
    input.value += e.target.dataset.char;
    input.dispatchEvent(new Event("input"));
    input.focus();
  }
});
</script>