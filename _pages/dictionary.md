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
    transition: background-color 1s ease-out; /* For the highlight effect */
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
  /* Style the conjugation box to stand out slightly */
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
  /* Style the clickable links */
  .dict-related a {
    color: var(--global-theme-color);
    text-decoration: underline;
    cursor: pointer;
  }
  .dict-related a:hover {
    color: var(--global-hover-color);
  }
</style>

<input id="search" placeholder="Search for a Biloxi word or English translation..." />

<div id="entries"></div>

</div>

<script>
  let data = [];
  let debounceTimer;

  // --- PASSWORD LOGIC ---
  const correctPassword = "ayeki";
  
  // Check if they already logged in during this session
  if (sessionStorage.getItem("dictAuth") === "true") {
    unlockDictionary();
  }

  // Handle "Enter" key press in the password box
  document.getElementById("pass-input").addEventListener("keypress", function(event) {
    if (event.key === "Enter") checkPassword();
  });

  function checkPassword() {
    const input = document.getElementById('pass-input').value;
    if (input === correctPassword) {
      sessionStorage.setItem("dictAuth", "true"); // Save login for this session
      unlockDictionary();
    } else {
      document.getElementById('pass-error').style.display = 'block';
    }
  }

  function unlockDictionary() {
    document.getElementById('password-gate').style.display = 'none';
    document.getElementById('dictionary-content').style.display = 'block';
    loadDictionary(); // Only fetch the heavy JSON if they are allowed in
  }

  // --- DICTIONARY LOGIC ---
  function loadDictionary() {
    // Fetch the JSON file
    fetch("{{ '/assets/json/biloxi_dictionary.json' | relative_url }}")
      .then(res => res.json())
      .then(json => {
        data = json;
        render(data);
      })
      .catch(err => console.error("Error loading dictionary:", err));
  }

  // Helper function to strip diacritics
  function removeDiacritics(str) {
    if (!str) return "";
    return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  // Function to navigate directly to an entry
  window.goToEntry = function(entryId) {
    // 1. Clear the search box so we are looking at the full list
    document.getElementById('search').value = '';
    
    // 2. Re-render the full dictionary to ensure the target entry is on the page
    render(data);
    
    // 3. Find the entry and scroll to it
    const target = document.getElementById(entryId);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      
      // Optional: Briefly highlight the background so the user sees where they landed
      target.style.backgroundColor = 'var(--global-divider-color)';
      setTimeout(() => {
        target.style.backgroundColor = 'transparent';
      }, 1500);
    }
  };

  // Render function
  function render(entries) {
    const container = document.getElementById('entries');
    
    if (entries.length === 0) {
      container.innerHTML = '<p>No results found.</p>';
      return;
    }

    const html = entries.map(entry => {
      // 1. Format Definitions
      const definitionsHtml = entry.definitions.map(d => 
        `<li><b>${d.part_of_speech}</b>: ${d.text}</li>`
      ).join('');

      // 2. Format Conjugations
      let conjugationHtml = '';
      if (entry.conjugation && Object.keys(entry.conjugation).length > 0) {
        const conjRows = Object.entries(entry.conjugation).map(([person, word]) => 
          `<tr><td><b>${person}</b></td><td>${word}</td></tr>`
        ).join('');
        
        conjugationHtml = `
          <div class="dict-conjugation">
            <b>Conjugations:</b>
            <table>
              ${conjRows}
            </table>
          </div>
        `;
      }

      // 3. Format Related Entries (UPDATED)
      let relatedHtml = '';
      if (entry.related_entries && entry.related_entries.length > 0) {
        const relatedLinks = entry.related_entries.map(relId => {
          const relEntry = data.find(e => e.id === relId);
          const text = relEntry ? relEntry.headword : relId;
          
          // Now we pass the ID to goToEntry instead of the text
          return `<a onclick="goToEntry('${relId}')">${text}</a>`;
        }).join(', ');
        
        relatedHtml = `
          <div class="dict-related">
            <b>Related:</b> ${relatedLinks}
          </div>
        `;
      }

      // 4. Combine everything into the final HTML (Added id="${entry.id}")
      return `
        <div class="dict-entry" id="${entry.id}">
          <h3>${entry.headword}</h3>
          <ul>${definitionsHtml}</ul>
          ${conjugationHtml}
          ${relatedHtml}
          <span class="dict-source">Source: ${entry.source || 'Unknown'}</span>
        </div>
      `;
    }).join('');

    container.innerHTML = html;
  }

  // Search logic (unchanged)
  document.getElementById('search').addEventListener('input', e => {
    clearTimeout(debounceTimer);
    
    debounceTimer = setTimeout(() => {
      const q = removeDiacritics(e.target.value.toLowerCase());
      
      const filtered = data.filter(entry => {
        const headwordMatch = removeDiacritics(entry.headword.toLowerCase()).includes(q);
        const definitionsMatch = entry.definitions.some(d => 
          removeDiacritics(d.text.toLowerCase()).includes(q)
        );
        return headwordMatch || definitionsMatch;
      });
      
      render(filtered);
    }, 200);
  });
</script>