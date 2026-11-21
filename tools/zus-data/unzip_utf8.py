import sys, zipfile, os, unicodedata, shutil
src, dest = sys.argv[1], sys.argv[2]
os.makedirs(dest, exist_ok=False)  # must be a new, empty dir
dest_real = os.path.realpath(dest)
with zipfile.ZipFile(src, metadata_encoding="utf-8") as z:
    for info in z.infolist():
        name = unicodedata.normalize("NFC", info.filename)
        parts = [p.strip() for p in name.replace("\\", "/").split("/") if p.strip()]
        if not parts or info.is_dir():
            continue
        parts = parts[1:] if len(parts) > 1 else parts  # drop top-level folder
        if any(p in ("..", ".") for p in parts) or name.startswith("/"):
            print("SKIP suspicious:", name); continue
        out = os.path.realpath(os.path.join(dest, *parts))
        if not out.startswith(dest_real + os.sep):
            print("SKIP outside dest:", name); continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with z.open(info) as fsrc, open(out, "wb") as fdst:
            shutil.copyfileobj(fsrc, fdst)
        print(os.path.relpath(out, dest))
