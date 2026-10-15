#!/usr/bin/env python3
"""
fetch-news.py — Recupera articoli da GDELT 2.0 + RSS culturali specifici.
Output: data/raw_news.json
Robustezza: ogni fonte fallita è loggata e saltata, non blocca le altre.
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml
import feedparser

# Path relativi alla root del sito
ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "data" / "sources.yaml"
OUTPUT_FILE = ROOT / "data" / "raw_news.json"


def log(msg, level="INFO"):
    print(f"[{datetime.now().isoformat()}] {level}: {msg}", file=sys.stderr)


def fetch_gdelt(config):
    """
    GDELT 2.0 Doc API
    https://api.gdeltproject.org/api/v2/doc/doc

    Strategia: fa una query "tutto" per ogni lingua per recuperare un campione
    diverso di notizie globali. Il matching tematico avverrà poi con keyword.
    """
    items = []
    endpoint = config["endpoint"]
    languages = config["languages"]
    maxrecords = config.get("maxrecords", 50)
    timespan = config.get("timespan", "6h")

    # Mappa codice GDELT (3 lettere) → codice 2 lettere (per output)
    LANG_MAP = {
        "eng": "en", "ita": "it", "deu": "de", "fra": "fr",
        "spa": "es", "por": "pt", "rus": "ru", "ara": "ar",
        "zho": "zh", "swa": "sw",
    }

    for lang_3 in languages:
        # GDELT vuole una query — uso un wildcard implicito tramite parola comune
        # In realtà GDELT richiede sempre una query: usiamo tutti gli articoli
        # filtrando per sourcelang. Tecnica: query con un termine molto generale
        # come "the" (en), "il" (it), ecc. Ma è meglio interrogare per tema.
        # Per ora: usiamo "*" non funziona, usiamo "news" che è generico
        # Soluzione: per ogni lingua usiamo la parola "news" tradotta
        QUERY_BY_LANG = {
            "eng": "news",
            "ita": "notizie",
            "deu": "Nachrichten",
            "fra": "actualités",
            "spa": "noticias",
            "por": "notícias",
            "rus": "новости",
            "ara": "أخبار",
            "zho": "新闻",
            "swa": "habari",
        }
        query_term = QUERY_BY_LANG.get(lang_3, "news")
        params = {
            "query": f"{query_term} sourcelang:{lang_3}",
            "mode": "artlist",
            "format": "json",
            "maxrecords": maxrecords,
            "timespan": timespan,
        }
        url = f"{endpoint}?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": config.get("user_agent", "carlocaloro.com/1.0")})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
            for art in data.get("articles", []):
                items.append({
                    "headline": art.get("title", "").strip(),
                    "url": art.get("url", ""),
                    "lang": LANG_MAP.get(lang_3, lang_3),
                    "source": art.get("domain", "GDELT"),
                    "timestamp": art.get("seendate", ""),
                    "_origin": "gdelt",
                })
            log(f"GDELT [{lang_3}]: {len(data.get('articles', []))} articoli")
        except Exception as e:
            log(f"GDELT [{lang_3}]: errore {e}", "WARN")
        time.sleep(0.5)  # gentle rate limit
    return items


def fetch_rss(rss_config, user_agent):
    """Parser RSS per le fonti culturali specifiche."""
    items = []
    for source in rss_config:
        try:
            # feedparser supporta agent custom
            feed = feedparser.parse(source["url"], agent=user_agent)
            if feed.bozo and not feed.entries:
                log(f"RSS [{source['id']}]: feed malformato o vuoto", "WARN")
                continue
            for entry in feed.entries[:30]:
                title = (entry.get("title") or "").strip()
                if not title:
                    continue
                published = entry.get("published") or entry.get("updated") or ""
                items.append({
                    "headline": title,
                    "url": entry.get("link", ""),
                    "lang": source.get("lang", "en"),
                    "source": source.get("name", source["id"]),
                    "timestamp": published,
                    "_origin": "rss",
                    "_category": source.get("category", ""),
                })
            log(f"RSS [{source['id']}]: {len(feed.entries[:30])} voci")
        except Exception as e:
            log(f"RSS [{source['id']}]: errore {e}", "WARN")
    return items


def main():
    if not SOURCES_FILE.exists():
        log(f"sources.yaml non trovato: {SOURCES_FILE}", "ERROR")
        sys.exit(1)
    config = yaml.safe_load(SOURCES_FILE.read_text())

    user_agent = config.get("behavior", {}).get(
        "user_agent",
        "carlocaloro.com/1.0 (artist archive reactive feed)"
    )

    all_items = []

    # GDELT
    gdelt_cfg = config.get("gdelt", {})
    if gdelt_cfg.get("enabled", False):
        gdelt_cfg["user_agent"] = user_agent
        all_items.extend(fetch_gdelt(gdelt_cfg))

    # RSS
    rss_cfg = config.get("rss", [])
    if rss_cfg:
        all_items.extend(fetch_rss(rss_cfg, user_agent))

    # Deduplicazione per URL
    seen_urls = set()
    unique = []
    for it in all_items:
        u = it.get("url") or it.get("headline")
        if u in seen_urls:
            continue
        seen_urls.add(u)
        unique.append(it)

    # Output
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": unique,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    log(f"raw_news.json scritto: {len(unique)} articoli totali")


if __name__ == "__main__":
    main()
