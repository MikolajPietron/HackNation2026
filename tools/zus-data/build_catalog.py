import sys, os, re, json
from collections import Counter
ocr_dir, out_md, out_json = sys.argv[1:4]
rot_path = os.path.join(ocr_dir, "_rotated_pages.json")
ROT = json.load(open(rot_path)) if os.path.exists(rot_path) else {}
HDR = lambda code: rf"^\s*(?:ZUS\s+)?{code}\s*$"
DOCS = {
    "ZAM": HDR("ZAM"), "ZUR": HDR("ZUR"), "ZAO": HDR("ZAO"), "ZAS-53": HDR(r"ZAS-?53"), "ZAS-12": HDR(r"ZAS-?12"),
    "Z-3": HDR(r"[Z2]-3"), "Z-3a": HDR(r"[Z2]-3a"), "Z-3b": HDR(r"[Z2]-3 ?b"),
    "POG": HDR("POG") + r"|PISMO OG[ÓO]LNE", "decyzja": r"^\s*DECYZJA\b",
    "akt urodzenia": r"[Oo]dpis (skr[óo]cony|zupe[łl]ny) aktu urodzenia",
    "poświadczenie ubezp.": r"[Ww]niosek o po[śs]wiadczenie ubezpieczenia|Odpowied[źz] na wniosek o po[śs]wiadczenie",
    "zrzut systemu ZUS": r"Tytu[łl]y ubezpieczenia|EPWD|Historia zmian ubezpieczenia|Pisma wydane w OU|Zrzut podlegania",
    "e-ZLA": r"ZA[ŚS]WIADCZENIE LEKARSKIE|ZUS ZLA", "karta szpitalna": r"KARTA INFORMACYJNA|[Kk]arta informacyjna leczenia",
    "zaśw. Za życiem": r"nieodwracaln\w* upo[śs]ledzeni|nieuleczaln\w* chorob",
    "umowa": r"^\s*UMOWA\b|UMOWA (O PRAC|ZLECENI)", "wniosek urlopowy (KP)": r"[Ww]niosek o udzielenie (urlopu|cz[ęe][śs]ci)",
    "pismo sądu": r"\bWYROK\b|[Ss][ąa]d (Rejonowy|Okr[ęe]gowy)",
    "świadectwo pracy": r"[ŚS]WIADECTWO PRACY",
}
BOILER = re.compile(r"mamy ustali|ma ustali[ćc] prawo|Je[śs]li ZUS ma|Poprzednio wyp|przyznany d\w{1,2} okre|w wysoko[śs]ci kwot wyp|sprostowani|wyp[łl]acimy|Je[śs]?l?i TA|w ci[ąa]gu 14|pracodawc\w* o odmowie|przez kogo", re.I)
GRANT = re.compile(r"przyzna(no|ny|ne|na|[ćc]|je|j[ąa]c\w*)\b|ustalono uprawnieni|ustalono prawo|dokonana wyp[łl]at|wyp[łl]acono|wyp[łl]acon[ya]j? za okres|uchyla decyzj", re.I)
REFUSE = re.compile(r"\b\w?dm[óo]wi\w*|odmawia\w*|odmown\w*", re.I)
CATS = [("Odmowa", r"odmow|odmown"), ("Martwe urodzenie", r"martw"), ("Adopcja / rodzina zastępcza", r"przyj[ęe]ci|przysposob|zast[ęe]pcz"),
        ("Zasiłek w wys. zas. macierzyńskiego", r"w wysoko[śs]ci zas"), ("Wcześniak / uzupełniający", r"uzupe[łl]n|wcze[śs]niak"),
        ("Bliźnięta / Za życiem", r"bli[źz]ni|za [żz]yciem"), ("Łączenie rodzicielskiego z pracą", r"[łl][ąęa]czenie"),
        ("Ojciec: 9 tyg. / przejęcie", r"9 tyg|dla ojca|rezygnacja|ojciec"), ("Urlop ojcowski", r"ojcowsk"),
        ("Chorobowy w ciąży", r"chorobow"), ("Macierzyński + rodzicielski", r"rodzicielsk|u\. rodz|cz[ęe][śs][ćc]"), ("Macierzyński", r"mac")]
cat = lambda f: next(c for c, p in CATS if re.search(p, f.lower()))
rows = []
for f in sorted(x for x in os.listdir(ocr_dir) if x.endswith(".txt")):
    name = f[:-4]
    pages = re.split(r"\n===== STRONA \d+ =====\n", open(os.path.join(ocr_dir, f)).read())[1:]
    rotated = ROT.get(name, {})
    for p, info in rotated.items(): pages[int(p) - 1] = info["text"]
    blank = [i + 1 for i, p in enumerate(pages) if len(re.sub(r"\s", "", p)) < 40]
    lines = [(i + 1, l.strip()) for i, p in enumerate(pages) for l in p.splitlines() if l.strip() and not BOILER.search(l)]
    clean = "\n".join(l for _, l in lines)
    docs = [k for k, pat in DOCS.items() if re.search(pat, clean, re.M)]
    raw = "\n".join(pages)
    if re.search(r"W przypadku nie\s*(do)?starczenia|nie\s*prze?d[łl]o[żz]eni|(wydamy|wyda) decyzj", raw, re.I): docs.append("wezwanie ZUS o dokumenty")
    g = [(p, l) for p, l in lines if GRANT.search(l)]
    WARN = re.compile(r"wydamy decyzj|ZUS wyda decyzj|zostanie wydana decyzj|W przypadku nie\w* ", re.I)
    r = [(p, l) for k, (p, l) in enumerate(lines) if REFUSE.search(l) and not WARN.search(l) and not (k and WARN.search(lines[k-1][1]))]
    outcome = "przyznano" if g and not r else "odmowa" if r and not g else "mieszane" if g and r else "nie znaleziono"
    ev = [f"s.{p}: {re.sub(r'\s+', ' ', l)[:150]}" for p, l in (r + g)[:3]]
    rows.append(dict(id=None, plik=name, scenariusz=cat(name), stron=len(pages), puste_strony=blank,
                     obrocone_strony=sorted(int(p) for p in rotated), dokumenty=docs, rozstrzygniecie=outcome, dowody=ev))
rows.sort(key=lambda x: ([c for c, _ in CATS].index(x["scenariusz"]), x["plik"]))
for i, r in enumerate(rows, 1): r["id"] = f"S{i:02d}"
json.dump(rows, open(out_json, "w"), ensure_ascii=False, indent=1)
with open(out_md, "w") as md:
    md.write("# Katalog spraw ZUS (HackNation)\n\nPOUFNE – tylko lokalnie, poza repo. Wygenerowane automatycznie z OCR (tesseract), rozstrzygnięcia do weryfikacji wzrokowej.\n\n")
    md.write("| ID | Scenariusz | Stron (puste) | Rozstrzygnięcie | Dokumenty | Dowód (OCR) | Plik |\n|---|---|---|---|---|---|---|\n")
    for r in rows:
        md.write(f"| {r['id']} | {r['scenariusz']} | {r['stron']} ({len(r['puste_strony'])}) | {r['rozstrzygniecie']} | {', '.join(r['dokumenty'])} | {' ⏐ '.join(d.replace('|', '/') for d in r['dowody'][:2])} | {r['plik']} |\n")
print("Rozstrzygnięcia:", Counter(r["rozstrzygniecie"] for r in rows))
print("Scenariusz x rozstrzygnięcie:")
for c, _ in CATS:
    sub = [r for r in rows if r["scenariusz"] == c]
    print(f"  {c:<38} {len(sub):2}  {dict(Counter(r['rozstrzygniecie'] for r in sub))}")
print("Dokumenty:", ", ".join(f"{k}: {v}" for k, v in Counter(d for r in rows for d in r["dokumenty"]).most_common()))
print("Strony puste:", sum(len(r["puste_strony"]) for r in rows), "| obrócone (poprawione):", sum(len(r["obrocone_strony"]) for r in rows))
