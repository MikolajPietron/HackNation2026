import sys, os, re, json, subprocess, tempfile, shutil
from multiprocessing import Pool
VOCAB_SRC, SCORES, PDF_DIR, OUT, TMP = sys.argv[1:6]
tok = lambda s: re.findall(r"[a-ząćęłńóśźż]{4,}", s.lower())
VOCAB = set(tok(open(VOCAB_SRC).read())) | {"zakład","ubezpieczeń","społecznych","wniosek","zaświadczenie","płatnika","składek","tytuły","ubezpieczenia","konto","podgląd","zamknij","kryterium","wyszukiwania","szukaj","odśwież","rodzaj","płatnik","okres","data","przerwy","świadczenia","kwota","nazwa","liczba","wierszy","rzeczpospolita","polska","odpis","skrócony","aktu","urodzenia","dziecka","kategoria","informacji","wewnętrzne","strona"}
def score(t):
    w = tok(t); return (sum(x in VOCAB for x in w) / len(w)) if w else 0.0
def work(job):
    case, page, orig = job
    d = tempfile.mkdtemp(dir=TMP)
    try:
        base = os.path.join(d, "p")
        subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", "-f", str(page), "-l", str(page), "-singlefile",
                        os.path.join(PDF_DIR, case + ".pdf"), base], check=True)
        best = (orig, 0, None)
        for rot in (90, 180, 270):
            out = os.path.join(d, f"r{rot}.png")
            subprocess.run(["sips", "-r", str(rot), base + ".png", "--out", out], capture_output=True, check=True)
            txt = subprocess.run(["tesseract", out, "stdout", "-l", "pol"], capture_output=True, text=True,
                                 env={**os.environ, "OMP_THREAD_LIMIT": "1"}).stdout
            s = score(txt)
            if s > best[0]: best = (s, rot, txt)
        return case, page, orig, best
    finally:
        shutil.rmtree(d, ignore_errors=True)
if __name__ == "__main__":
    scores = json.load(open(SCORES))
    jobs = [(case, i, s) for case, pages in scores.items() for i, c, s in pages if c >= 40 and s < 0.30]
    results = {}
    with Pool(8) as pool:
        for case, page, orig, (s, rot, txt) in pool.imap_unordered(work, jobs):
            if rot and s >= orig + 0.15:
                results.setdefault(case, {})[str(page)] = {"rotation": rot, "score": round(s, 2), "orig": orig, "text": txt}
    json.dump(results, open(OUT, "w"), ensure_ascii=False, indent=1)
    fixed = sum(len(v) for v in results.values())
    print(f"stron poprawionych obrotem: {fixed} z {len(jobs)}; spraw: {len(results)}")
