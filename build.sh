#!/bin/sh
# Builds docs/index.html from KorejaMain.md (+ KorejaWIP.md) and src/template.html.
# The plan is read straight from the Dokumenti folder next to this repo; set KOREJA_SRC to use another folder.
set -e
cd "$(dirname "$0")"
SRC="${KOREJA_SRC:-../Dokumenti}"
if [ ! -f "$SRC/KorejaMain.md" ]; then echo "missing $SRC/KorejaMain.md (set KOREJA_SRC)" >&2; exit 1; fi
python3 build/parse.py "$SRC/KorejaMain.md" build/data.json
python3 - <<'PY'
tpl = open('src/template.html', encoding='utf-8').read()
data = open('build/data.json', encoding='utf-8').read().replace('</', '<\\/')
open('docs/index.html', 'w', encoding='utf-8').write(tpl.replace('/*DATA*/', data))
PY
echo "built docs/index.html"
