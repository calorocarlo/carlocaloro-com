#!/usr/bin/env python3
"""
build-works-json.py — converte data/works.yaml in static/data/works.json
così il client può accedere al catalogo via /data/works.json.
"""

import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "works.yaml"
DST = ROOT / "static" / "data" / "works.json"

def main():
    data = yaml.safe_load(SRC.read_text())
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"works.json scritto: {len(data.get('works', []))} opere")

if __name__ == "__main__":
    main()
