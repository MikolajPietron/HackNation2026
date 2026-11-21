import sys, os, subprocess, tempfile, glob, shutil
pdf, outdir, tmproot = sys.argv[1], sys.argv[2], sys.argv[3]
name = os.path.splitext(os.path.basename(pdf))[0]
out = os.path.join(outdir, name + ".txt")
if os.path.exists(out): sys.exit(0)
tmp = tempfile.mkdtemp(dir=tmproot)
try:
    subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", pdf, os.path.join(tmp, "p")], check=True)
    pages = sorted(glob.glob(os.path.join(tmp, "p-*.png")))
    parts = []
    for i, png in enumerate(pages, 1):
        r = subprocess.run(["tesseract", png, "stdout", "-l", "pol"], capture_output=True, text=True,
                           env={**os.environ, "OMP_THREAD_LIMIT": "1"})
        parts.append(f"\n===== STRONA {i} =====\n" + r.stdout)
    with open(out + ".part", "w") as f: f.write("".join(parts))
    os.rename(out + ".part", out)
    print("done", name, len(pages), flush=True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
