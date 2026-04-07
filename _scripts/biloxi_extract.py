#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
biloxi_extract.py
=================
Extracts Biloxi-English dictionary entries from the Kaufman 2020 Biloxi
Dictionary PDF (pages 55-257) and writes them as a structured JSON array.

PDF character encoding:
  The PDF stores every glyph as an individual character object.  Spaces
  are encoded as explicit ' ' glyphs.  This script therefore works at the
  raw `page.chars` level, grouping consecutive non-space chars on the same
  baseline into "tokens", then applying font metadata from the dominant
  glyph in each group.

Layout geometry (empirically calibrated on pages 55-257):
  Two-column layout.
  LEFT column headword x0 in {54 ± 6, 90 ± 6}
  LEFT column sub-sense x0 in {72 ± 6, 108 ± 6}
  RIGHT column headword x0 in {252 ± 6, 288 ± 6}
  RIGHT column sub-sense x0 in {270 ± 6, 306 ± 6}

Font conventions:
  Bold headwords     : fontname contains "Bold"
  Italic POS / refs  : fontname contains "Italic"
  Arrow cross-ref    : Wingdings-Regular, char U+F0DC
  Conj table marker  : Wingdings 3,       char U+F075
  Example bullet     : Wingdings-Regular,  char U+F0A1

Two-pass algorithm:
  Pass 1 – collect all headword tokens, build headword_text -> entry_id map.
  Pass 2 – slice token stream into per-entry chunks; parse each into JSON.

JSON schema per entry:
  id, headword, definitions[], conjugation{}, related_entries[], source,
  metadata{gender_speech, inalienable}
"""

import json
import re
import sys
from pathlib import Path

import pdfplumber

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PDF_PATH    = Path("/mnt/user-data/uploads/Kaufman_2020_Biloxi_Dictionary.pdf")
OUTPUT_PATH = Path("/mnt/user-data/outputs/biloxi_dictionary.json")

START_PAGE = 55   # first page of Biloxi-English dictionary section
END_PAGE   = 257  # last page (exclusive of index/appendices)

# Wingdings glyphs
ARROW_CHAR  = "\uf0dc"   # ➔  cross-reference
BULLET_CHAR = "\uf0a1"   # ■  example-sentence bullet
CONJ_CHAR   = "\uf075"   # ▶  conjugation-table start

# Column geometry  (x0 anchor sets + tolerance)
HW_X_ANCHORS = {54, 90, 252, 288}   # headword-start positions
SN_X_ANCHORS = {72, 108, 270, 306}  # sub-sense number positions
ANCHOR_TOL   = 6                     # ± pt

MIN_HW_SIZE  = 11.5   # minimum bold font size for headword detection

# Recognised POS tokens (without trailing dot)
POS_TOKENS = {
    "n", "v", "adj", "adv", "interj", "pref", "suf",
    "conj", "prep", "pron", "num", "part", "var",
}

# Conjugation pronoun labels -> JSON key
CONJ_MAP = {
    "i":       "1s",
    "you":     "2s",
    "s/he/it": "3s",
    "we":      "1p",
    "you pl.": "2p",
    "they":    "3p",
}

# Citation introducer tokens (skip in definition text)
SOURCE_KEYS = {"DS.", "D.", "G.", "H.", "O.", "S.", "Sw.", "lit."}


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def is_bold(tok):
    return "Bold" in tok.get("fontname", "")

def is_italic(tok):
    fn = tok.get("fontname", "")
    return "Italic" in fn and "Bold" not in fn

def is_wingdings(tok):
    return "Wingdings" in tok.get("fontname", "")

def is_body(tok):
    fn = tok.get("fontname", "")
    return "Bold" not in fn and "Italic" not in fn and "Wingdings" not in fn


# ---------------------------------------------------------------------------
# ID / slug
# ---------------------------------------------------------------------------

def slug(text):
    """Map a Biloxi headword to a safe ASCII-ish id component."""
    # Replace common diacritics with base letters
    _pairs = [
        ("ąą", "aa"), ("čč", "cc"), ("ęę", "ee"), ("įį", "ii"),
        ("ǫǫ", "oo"), ("šš", "ss"), ("ôô", "oo"), ("êê", "ee"),
        ("ą", "a"),  ("č", "c"),  ("ę", "e"),  ("į", "i"),
        ("ǫ", "o"),  ("š", "s"),  ("ô", "o"),  ("ê", "e"),
        ("ā", "a"),  ("ē", "e"),  ("ī", "i"),  ("ū", "u"),
        ("à", "a"),  ("á", "a"),  ("â", "a"),  ("ä", "a"),
        ("è", "e"),  ("é", "e"),  ("ë", "e"),
        ("ì", "i"),  ("í", "i"),  ("î", "i"),  ("ï", "i"),
        ("ò", "o"),  ("ó", "o"),  ("ö", "o"),
        ("ù", "u"),  ("ú", "u"),  ("û", "u"),  ("ü", "u"),
        ("ý", "y"),  ("ñ", "n"),
    ]
    s = text.lower()
    for src, dst in _pairs:
        s = s.replace(src, dst)
    s = re.sub(r"[^\w]", "_", s).strip("_")
    s = re.sub(r"_+", "_", s)
    return s or "entry"


# ---------------------------------------------------------------------------
# Char-level tokeniser  (core of the fix)
# ---------------------------------------------------------------------------

def chars_to_tokens(page):
    """
    Convert raw page.chars into a list of word-level token dicts.

    Groups consecutive non-space characters on the same baseline (top ± 1.5 pt)
    into a single token.  Uses the font of the FIRST non-space char in each
    group for font classification (reliable for headwords and POS tags; the
    conjugation forms may mix fonts, but we only need the text).

    Each returned dict has:
        text     – concatenated glyph texts
        fontname – font of first glyph
        size     – point size of first glyph
        x0       – x-coordinate of first glyph
        top      – baseline y of first glyph
    """
    tokens = []
    current_chars = []

    def flush():
        if not current_chars:
            return
        text = "".join(c["text"] for c in current_chars)
        if text.strip():
            tokens.append({
                "text":     text,
                "fontname": current_chars[0]["fontname"],
                "size":     current_chars[0]["size"],
                "x0":       current_chars[0]["x0"],
                "top":      current_chars[0]["top"],
            })
        current_chars.clear()

    prev_top = None

    for ch in page.chars:
        # Skip page-header / footer chars (running header at very top of page)
        if ch["top"] < 50:
            flush()
            continue

        txt = ch["text"]

        # Space character = word boundary
        if txt == " ":
            flush()
            prev_top = ch["top"]
            continue

        # Significant baseline change = new line (also flush)
        if prev_top is not None and abs(ch["top"] - prev_top) > 1.5:
            flush()

        current_chars.append(ch)
        prev_top = ch["top"]

    flush()
    return tokens


# ---------------------------------------------------------------------------
# Token stream over full page range
# ---------------------------------------------------------------------------

def build_token_stream(pdf, start_page, end_page):
    tokens = []
    for page_num in range(start_page, end_page + 1):
        idx = page_num - 1
        try:
            page = pdf.pages[idx]
        except IndexError:
            break
        for tok in chars_to_tokens(page):
            tok["page_num"] = page_num
            tokens.append(tok)
    return tokens


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def near(x, anchors, tol=ANCHOR_TOL):
    return any(abs(x - a) <= tol for a in anchors)

def is_headword_start(tok):
    if not is_bold(tok):
        return False
    if tok.get("size", 0) < MIN_HW_SIZE:
        return False
    txt = tok["text"].strip()
    if re.match(r"^\d+\.?$", txt.strip()):   # sub-sense numbers
        return False
    if txt in (".", ","):
        return False
    return near(tok["x0"], HW_X_ANCHORS)

def is_sense_number(tok):
    return (
        is_bold(tok)
        and tok.get("size", 0) >= MIN_HW_SIZE
        and re.match(r"^\d+\.?$", tok["text"].strip())
        and near(tok["x0"], SN_X_ANCHORS)
    )


# ---------------------------------------------------------------------------
# Pass 1 helpers
# ---------------------------------------------------------------------------

def find_entry_positions(tokens):
    """
    Return sorted list of indices of the FIRST token of each headword.
    Skips continuation tokens of the same multi-token headword by tracking
    the last baseline seen per column.
    """
    positions = []
    last_top = {"L": -999.0, "R": -999.0}

    for i, tok in enumerate(tokens):
        if not is_headword_start(tok):
            continue
        col = "L" if tok["x0"] < 200 else "R"
        if abs(tok["top"] - last_top[col]) <= 2.0:
            continue  # continuation of same headword
        positions.append(i)
        last_top[col] = tok["top"]

    return positions


def reconstruct_headword(tokens, start_idx):
    """
    Starting from start_idx, concatenate consecutive bold tokens on the same
    baseline to produce the full headword string.
    """
    baseline = tokens[start_idx]["top"]
    parts = []
    i = start_idx
    while i < len(tokens):
        tok = tokens[i]
        if (is_bold(tok)
                and abs(tok["top"] - baseline) <= 2.0
                and not re.match(r"^\d+\.?$", tok["text"])):
            parts.append(tok["text"])
            i += 1
        else:
            break
    return "".join(parts).strip(" ,.")


def build_headword_map(tokens):
    """
    Returns (headword_to_id dict, positions list).
    Duplicate headwords get a numeric suffix: ade_1, ade_2, ...
    """
    positions = find_entry_positions(tokens)
    headword_to_id = {}
    slug_counter = {}

    for pos in positions:
        hw = reconstruct_headword(tokens, pos)
        if not hw:
            continue
        base = slug(hw)
        slug_counter[base] = slug_counter.get(base, 0) + 1
        eid = f"{base}_{slug_counter[base]}"
        headword_to_id.setdefault(hw, eid)

    return headword_to_id, positions


# ---------------------------------------------------------------------------
# Cross-reference resolver
# ---------------------------------------------------------------------------

def build_ref_resolver(headword_to_id):
    def resolve(ref_text):
        clean = ref_text.strip(" ,.")
        if clean in headword_to_id:
            return headword_to_id[clean]
        # Prefix / contained match as fallback
        for hw, eid in headword_to_id.items():
            if hw == clean or hw.startswith(clean) or clean.startswith(hw):
                return eid
        return None
    return resolve


# ---------------------------------------------------------------------------
# Source-reference extractor
# ---------------------------------------------------------------------------

def extract_source(tokens):
    """
    Scan token list for 'DS.' followed by page numbers.
    Returns e.g. 'DS. 169' or 'DS. 242, 275', or None.
    """
    for i, tok in enumerate(tokens):
        if tok["text"] == "DS.":
            nums = []
            j = i + 1
            while j < len(tokens):
                t = tokens[j]["text"]
                if re.match(r"^\d+[,.]?$", t):
                    nums.append(t.rstrip(",."))
                    j += 1
                elif t == ",":
                    j += 1
                else:
                    break
            if nums:
                return "DS. " + ", ".join(nums)
    return None


# ---------------------------------------------------------------------------
# Inalienable checker
# ---------------------------------------------------------------------------

def check_inalienable(tokens):
    """
    Return True if the sequence (His/her) appears in the token stream.
    Works at token level: looks for '(' token followed immediately by
    a token starting with 'His' or 'his', and later a ')' token.
    """
    for i, tok in enumerate(tokens):
        if tok["text"] in ("(His/her)", "(his/her)"):
            return True
        # Also handle multi-token: '(' + 'His/her' + ')'
        if tok["text"] == "(" and i + 1 < len(tokens):
            nxt = tokens[i + 1]["text"]
            if nxt.lower().startswith("his/her"):
                return True
    return None


# ---------------------------------------------------------------------------
# Sense-block parser
# ---------------------------------------------------------------------------

def parse_sense_block(sense_tokens, conjugation, related_entries, resolve_ref):
    """
    Parse tokens for one numbered sense (or whole un-numbered entry).

    Conjugation tables:
      Detected by CONJ_CHAR (▶).  After the marker, rows consist of an
      italic pronoun label (matched against CONJ_MAP) followed by the
      conjugated form on the same baseline.  The "you pl." label spans
      two tokens ("you" + "pl.").

    Cross-references:
      Detected by ARROW_CHAR (➔).  All immediately following non-punctuation
      tokens are collected as the surface form of the referent and resolved
      to an entry id via resolve_ref().

    Returns {part_of_speech: str, text: str} or None.
    Mutates conjugation and related_entries in place.
    """
    pos_text    = ""
    def_parts   = []
    in_conj     = False
    in_arrow    = False
    conj_label  = None
    arrow_parts = []

    def flush_arrow():
        if arrow_parts:
            ref_text = "".join(arrow_parts)
            ref_id = resolve_ref(ref_text)
            if ref_id and ref_id not in related_entries:
                related_entries.append(ref_id)
            arrow_parts.clear()

    i = 0
    while i < len(sense_tokens):
        tok = sense_tokens[i]
        txt = tok["text"]

        # ── Wingdings symbols ────────────────────────────────────────────
        if is_wingdings(tok):
            if txt == CONJ_CHAR:
                flush_arrow()
                in_conj    = True
                in_arrow   = False
                conj_label = None
            elif txt == ARROW_CHAR:
                flush_arrow()
                in_arrow = True
                in_conj  = False
            elif txt == BULLET_CHAR:
                flush_arrow()
                in_arrow = False
                in_conj  = False
            i += 1
            continue

        # ── Collecting arrow reference ───────────────────────────────────
        if in_arrow:
            if txt in (",", ".", ";") or txt in SOURCE_KEYS:
                flush_arrow()
                in_arrow = False
                # fall through to handle this token normally
            else:
                arrow_parts.append(txt)
                i += 1
                continue

        # ── Conjugation table ────────────────────────────────────────────
        if in_conj:
            txt_lower = txt.lower().rstrip(".")

            # "you" followed by "pl." (both italic) -> 2p label
            if is_italic(tok) and txt_lower == "you":
                nxt = sense_tokens[i + 1] if i + 1 < len(sense_tokens) else None
                if nxt and nxt["text"].lower().rstrip(".") == "pl":
                    conj_label = "2p"
                    i += 2   # consume both "you" and "pl."
                    continue
                else:
                    conj_label = "2s"
                    i += 1
                    continue

            # Other pronoun labels (s/he/it, we, they)
            if is_italic(tok) and txt_lower in CONJ_MAP:
                conj_label = CONJ_MAP[txt_lower]
                i += 1
                continue

            # Conjugated form: first non-pronoun-label token after conj_label set
            if conj_label and not is_wingdings(tok):
                conjugation[conj_label] = conjugation.get(conj_label, "") + txt
                conj_label = None
                i += 1
                continue

            # End of conjugation block
            if txt in SOURCE_KEYS or (is_bold(tok) and not re.match(r"^\d+\.?$", txt.strip())):
                in_conj = False
                # fall through to process token below
            else:
                i += 1
                continue

        # ── Part-of-speech (italic token before definition) ──────────────
        if is_italic(tok) and not pos_text:
            tag = txt.rstrip(".")
            if tag.lower() in POS_TOKENS:
                pos_text = tag
                i += 1
                continue

        # ── Skip metadata-only tokens ────────────────────────────────────
        if txt in ("f.", "m.", "(f.)", "(m.)"):
            i += 1
            continue
        # Skip inalienable marker text in definition
        if txt in ("(His/her)", "(his/her)"):
            i += 1
            continue
        # Skip all citation clusters: DS., D., G., H., O., S., Sw., lit. + their following tokens
        # These always appear at x0 >= 108 (indented) and are followed by alphanumeric/digit tokens
        ALL_CITE_KEYS = {"DS.", "D.", "G.", "H.", "O.", "S.", "Sw.", "lit.",
                         "G,", "H,", "D,", "S,"}
        if txt in ALL_CITE_KEYS:
            # Skip this token and all immediately following citation content on same/next lines
            # Citation content = digits, letters up to next entry boundary
            i += 1
            while i < len(sense_tokens):
                nt = sense_tokens[i]
                # Stop when we hit: a Wingdings symbol, or a new bold headword-start token
                if is_wingdings(nt):
                    break
                if is_bold(nt) and not re.match(r"^\d+\.?$", nt["text"].strip()):
                    break
                # Stop when we hit what looks like a real definition word (italic POS or
                # a body token at a headword-level x0)
                if near(nt["x0"], HW_X_ANCHORS) and not is_body(nt):
                    break
                # Otherwise consume it as citation noise
                i += 1
            continue

        # Skip bare digit strings (citation page numbers not caught above)
        if re.match(r"^\d+[,.]?$", txt) and is_body(tok):
            i += 1
            continue

        # ── Definition text accumulation ─────────────────────────────────
        if not is_bold(tok) and not is_wingdings(tok):
            if txt not in SOURCE_KEYS:
                def_parts.append(txt)

        i += 1

    # Flush any remaining arrow reference
    flush_arrow()

    def_text = " ".join(def_parts).strip()
    # Clean up definition: remove leading/trailing punctuation clutter
    def_text = re.sub(r"^[\s,\.;]+", "", def_text)
    def_text = re.sub(r"[\s,\.;]+$", "", def_text)

    if not pos_text and not def_text:
        return None

    return {"part_of_speech": pos_text, "text": def_text}


# ---------------------------------------------------------------------------
# Top-level entry parser
# ---------------------------------------------------------------------------

def parse_entry(hw_text, entry_tokens, headword_to_id, resolve_ref):
    entry_id = headword_to_id.get(hw_text, f"{slug(hw_text)}_0")

    result = {
        "id":              entry_id,
        "headword":        hw_text,
        "definitions":     [],
        "conjugation":     {},
        "related_entries": [],
        "source":          None,
        "metadata": {
            "gender_speech": None,
            "inalienable":   False,
        },
    }

    # Quick full-entry scans
    result["metadata"]["inalienable"] = bool(check_inalienable(entry_tokens))

    for tok in entry_tokens:
        if tok["text"] in ("f.", "m.") and is_body(tok):
            result["metadata"]["gender_speech"] = tok["text"].rstrip(".")
            break

    result["source"] = extract_source(entry_tokens)

    # Split into sense blocks at sub-sense-number positions
    sense_starts = [
        i for i, tok in enumerate(entry_tokens) if is_sense_number(tok)
    ]

    if not sense_starts:
        blocks = [entry_tokens]
    else:
        blocks = []
        for k, sn_idx in enumerate(sense_starts):
            end = sense_starts[k + 1] if k + 1 < len(sense_starts) else len(entry_tokens)
            blocks.append(entry_tokens[sn_idx:end])

    for block in blocks:
        defn = parse_sense_block(
            block,
            result["conjugation"],
            result["related_entries"],
            resolve_ref,
        )
        if defn:
            result["definitions"].append(defn)

    return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def extract(pdf_path, start_page, end_page):
    print(f"Opening {pdf_path} ...", flush=True)
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        print(f"  PDF has {total} pages; processing pages {start_page}-{end_page}.", flush=True)

        # Pass 1: build token stream and headword map
        print("Pass 1: loading char-level tokens ...", flush=True)
        tokens = build_token_stream(pdf, start_page, end_page)
        print(f"  {len(tokens):,} tokens built.", flush=True)

        print("Pass 1: identifying headwords ...", flush=True)
        headword_to_id, positions = build_headword_map(tokens)
        print(f"  {len(headword_to_id):,} unique headwords / "
              f"{len(positions)} entry positions.", flush=True)

        resolve_ref = build_ref_resolver(headword_to_id)

        # Pass 2: parse each entry
        print("Pass 2: parsing entries ...", flush=True)
        entries = []
        for n, pos in enumerate(positions):
            next_pos = positions[n + 1] if n + 1 < len(positions) else len(tokens)
            hw_text  = reconstruct_headword(tokens, pos)
            if not hw_text:
                continue
            entry_tokens = tokens[pos:next_pos]
            entry = parse_entry(hw_text, entry_tokens, headword_to_id, resolve_ref)
            entries.append(entry)

        print(f"  {len(entries):,} entries parsed.", flush=True)

    return entries


def main():
    if not PDF_PATH.exists():
        sys.exit(f"ERROR: PDF not found: {PDF_PATH}")

    entries = extract(PDF_PATH, START_PAGE, END_PAGE)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=2)

    print(f"\nWritten {len(entries):,} entries -> {OUTPUT_PATH}", flush=True)

    # Quality report
    with_defs   = sum(1 for e in entries if e["definitions"])
    with_conj   = sum(1 for e in entries if e["conjugation"])
    with_refs   = sum(1 for e in entries if e["related_entries"])
    with_source = sum(1 for e in entries if e["source"])
    inalienable = sum(1 for e in entries if e["metadata"]["inalienable"])
    gendered    = sum(1 for e in entries if e["metadata"]["gender_speech"])

    print(f"\nQuality report:")
    print(f"  Entries with definitions  : {with_defs:,}")
    print(f"  Entries with conjugation  : {with_conj:,}")
    print(f"  Entries with cross-refs   : {with_refs:,}")
    print(f"  Entries with DS. source   : {with_source:,}")
    print(f"  Inalienable (his/her)     : {inalienable:,}")
    print(f"  Gender-speech markers     : {gendered:,}")

    # Representative samples
    samples = {
        "conjugation": next((e for e in entries if len(e["conjugation"]) >= 3), None),
        "cross-ref":   next((e for e in entries if e["related_entries"]), None),
        "inalienable": next((e for e in entries if e["metadata"]["inalienable"]), None),
        "source":      next((e for e in entries if e["source"]), None),
        "multi-sense": next((e for e in entries if len(e["definitions"]) >= 2), None),
    }

    for label, entry in samples.items():
        if entry:
            print(f"\n--- Sample [{label}] ---")
            print(json.dumps(entry, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
