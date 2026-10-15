#!/usr/bin/env python3
"""
match-themes.py — Per ogni articolo in raw_news.json, trova i temi che
matchano (per lingua) e collega le opere correlate.
Output: static/data/feed.json (servito dal sito a /data/feed.json)
"""

import json
import random
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW_NEWS = ROOT / "data" / "raw_news.json"
THEMES_FILE = ROOT / "data" / "themes.yaml"
WORKS_FILE = ROOT / "data" / "works.yaml"
SOURCES_FILE = ROOT / "data" / "sources.yaml"
OUTPUT_FILE = ROOT / "static" / "data" / "feed.json"

# Lingue scrittura non-latina (no word boundary funziona male)
NON_LATIN_LANGS = {"ar", "zh", "ja", "ko", "ru", "uk", "sw"}

SILENCE_PHRASES = [
    "the world is silent on this archive for now",
    "this passage does not concern the archive",
    "operational silence",
    "the archive does not answer",
    "no echo today",
    "the news passes through, it does not stop here",
]


def normalize(s, lang):
    """Lowercase + rimozione diacritici per lingue latine."""
    s = s.lower()
    if lang not in NON_LATIN_LANGS:
        s = "".join(c for c in unicodedata.normalize("NFD", s)
                    if unicodedata.category(c) != "Mn")
    return s


def match_themes(headline, lang, themes_data):
    """
    Ritorna lista temi che matchano nel titolo per la lingua data.
    Per lingue latine usa boundary regex (\\b…\\b), per altre 'in' semplice.
    """
    matched = set()
    norm = normalize(headline, lang)

    for theme_id, theme in themes_data.items():
        keywords_for_lang = theme.get("keywords", {}).get(lang, [])
        # Fallback su EN se la lingua non ha keyword
        if not keywords_for_lang and lang != "en":
            keywords_for_lang = theme.get("keywords", {}).get("en", [])

        for kw in keywords_for_lang:
            kw_norm = normalize(kw, lang)
            if not kw_norm:
                continue
            if lang in NON_LATIN_LANGS:
                if kw_norm in norm:
                    matched.add(theme_id)
                    break
            else:
                # word boundary
                pattern = r"\b" + re.escape(kw_norm) + r"\b"
                if re.search(pattern, norm):
                    matched.add(theme_id)
                    break
    return list(matched)


def works_for_themes(theme_ids, works_data):
    """Lista di slug-opera per cui almeno un tag intersechi i theme_ids."""
    if not theme_ids:
        return []
    theme_set = set(theme_ids)
    matching = []
    for w in works_data:
        tags = set(w.get("tags", []))
        if tags & theme_set:
            matching.append(w["id"])
    return matching


def parse_timestamp(ts):
    """Tenta di normalizzare a ISO UTC, ritorna stringa originale in caso di fallimento."""
    if not ts:
        return ""
    # Formati comuni
    formats = [
        "%Y%m%dT%H%M%SZ",        # GDELT
        "%a, %d %b %Y %H:%M:%S %z",  # RFC822 con TZ
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for f in formats:
        try:
            dt = datetime.strptime(ts, f)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
    return ts


def main():
    if not RAW_NEWS.exists():
        print(f"ERROR: {RAW_NEWS} non trovato. Esegui prima fetch-news.py", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(RAW_NEWS.read_text())
    themes_data = yaml.safe_load(THEMES_FILE.read_text())["themes"]
    works_data = yaml.safe_load(WORKS_FILE.read_text())["works"]
    sources_cfg = yaml.safe_load(SOURCES_FILE.read_text())
    behavior = sources_cfg.get("behavior", {})

    silence_ratio = behavior.get("silence_ratio", 6)
    max_entries = behavior.get("max_rotation_entries", 80)

    rotation = []
    silence_count = 0

    items = raw.get("items", [])
    random.shuffle(items)  # mescola per varietà

    for item in items:
        headline = item.get("headline", "").strip()
        if not headline or len(headline) < 10:
            continue
        lang = item.get("lang", "en")
        themes = match_themes(headline, lang, themes_data)
        works = works_for_themes(themes, works_data)

        entry = {
            "headline": headline,
            "lang": lang,
            "source": item.get("source", ""),
            "url": item.get("url", ""),
            "timestamp": parse_timestamp(item.get("timestamp", "")),
            "themes": themes,
            "works": works,
        }
        if works:
            rotation.append(entry)
        else:
            # ogni N voci con match, inseriamo una voce "silenzio"
            if (len(rotation) > 0
                and len(rotation) % silence_ratio == 0
                and silence_count < len(rotation) // silence_ratio):
                silence_count += 1
                rotation.append(entry)

        if len(rotation) >= max_entries:
            break

    # Anti-clustering: evita che voci con gli stessi temi siano consecutive
    rotation = anti_cluster(rotation)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rotation_size": len(rotation),
        "silence_phrases": SILENCE_PHRASES,
        "rotation": rotation,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"feed.json scritto: {len(rotation)} entries")


def anti_cluster(rotation):
    """Riordina la rotation evitando voci consecutive sugli stessi temi."""
    if len(rotation) <= 2:
        return rotation
    out = [rotation[0]]
    remaining = rotation[1:]
    while remaining:
        last_themes = set(out[-1].get("themes", []))
        # cerca il primo che ha intersezione minima con last_themes
        best_idx = 0
        best_overlap = float("inf")
        for i, e in enumerate(remaining):
            overlap = len(set(e.get("themes", [])) & last_themes)
            if overlap < best_overlap:
                best_overlap = overlap
                best_idx = i
                if overlap == 0:
                    break
        out.append(remaining.pop(best_idx))
    return out


if __name__ == "__main__":
    main()
