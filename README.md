# Koreja 2026

Itinerar puta 19.10.–2.11.2026. kao statična web stranica.

- `content/KorejaMain.md` — izvor plana (kopija iz iCloud mape).
- `src/template.html` — stranica (CSS + JS), bez podataka.
- `build/parse.py` — pretvara markdown u JSON.
- `docs/` — gotova stranica koju servira GitHub Pages.

Nakon promjene plana:

```sh
cp "$HOME/Library/Mobile Documents/com~apple~CloudDocs/SouKo Claude/Dokumenti/"Koreja{Main,WIP}.md content/
./build.sh
git commit -am "Update plan" && git push
```

