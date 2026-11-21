import sys, os, re, json
vocab_src, ocr_dir, out = sys.argv[1], sys.argv[2], sys.argv[3]
tok = lambda s: re.findall(r"[a-ząćęłńóśźż]{4,}", s.lower())
vocab = set(tok(open(vocab_src).read()))
# dorzuć słowa z formularzy/zrzutów, które nie występują w ustawach
vocab |= {"zakład","ubezpieczeń","społecznych","wniosek","zaświadczenie","płatnika","składek","tytuły","ubezpieczenia","konto","podgląd","zamknij","kryterium","wyszukiwania","szukaj","odśwież","rodzaj","płatnik","okres","data","przerwy","świadczenia","kwota","nazwa","liczba","wierszy","rzeczpospolita","polska","odpis","skrócony","aktu","urodzenia","dziecka","kategoria","informacji","wewnętrzne","strona"}
res = {}
for f in sorted(os.listdir(ocr_dir)):
    if not f.endswith(".txt"): continue
    pages = re.split(r"\n===== STRONA \d+ =====\n", open(os.path.join(ocr_dir, f)).read())[1:]
    sc = []
    for i, p in enumerate(pages, 1):
        chars = len(re.sub(r"\s", "", p)); t = tok(p)
        score = round(sum(w in vocab for w in t) / len(t), 2) if t else 0.0
        sc.append((i, chars, score))
    res[f[:-4]] = sc
json.dump(res, open(out, "w"), ensure_ascii=False)
allp = [(k, i, c, s) for k, v in res.items() for i, c, s in v]
nonblank = [x for x in allp if x[2] >= 40]
import collections
b = collections.Counter(min(int(x[3]*10), 9) for x in nonblank)
print("vocab:", len(vocab), "| stron niepustych:", len(nonblank))
print("rozkład trafień słownikowych (0.0-0.9):", dict(sorted(b.items())))
low = [x for x in nonblank if x[3] < 0.30]
print("stron do poprawy (<0.30):", len(low), "w", len({x[0] for x in low}), "sprawach")
