# Koreja 2026

Itinerar puta 19.10.–2.11.2026. kao statična web stranica.

- `../Dokumenti/KorejaMain.md` i `KorejaWIP.md` — izvor plana; čita se izravno, bez kopije u repou (druga mapa: `KOREJA_SRC=… ./build.sh`).
- `src/template.html` — stranica (CSS + JS), bez podataka.
- `build/parse.py` — pretvara markdown u JSON.
- `docs/` — gotova stranica koju servira GitHub Pages.

Nakon promjene plana:

```sh
./build.sh
git commit -am "Update plan" && git push
```

