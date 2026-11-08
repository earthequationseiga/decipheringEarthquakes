"""Save a finished job as a saved analysis in examples/, which the page lists and anyone can open
(also on GitHub Pages, where no server runs). To remove one, delete its file and its line in
examples/index.json.

    python save_example.py JOB_ID NAME "Title shown on the page" ["one-line note"]
"""
import json
import re
import sys

import server

if __name__ == "__main__":
    if len(sys.argv) not in (4, 5) or not re.fullmatch(r"[A-Za-z0-9_-]+", sys.argv[2]):
        sys.exit(__doc__)
    jid, name, title = sys.argv[1:4]
    d = server.JOBS / jid
    res = json.loads((d / "out" / "result.json").read_text(encoding="utf-8"))
    res["request"] = json.loads((d / "request.json").read_text())          # same as GET /jobs/{id}/result
    res["events"]["uploaded"] = server.uploaded_values(d, len(res["events"]["lon"]))
    ex = server.HERE / "examples"
    ex.mkdir(exist_ok=True)
    (ex / f"{name}.json").write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
    idx_file = ex / "index.json"
    idx = [e for e in (json.loads(idx_file.read_text()) if idx_file.exists() else []) if e["file"] != f"{name}.json"]
    idx.append({"file": f"{name}.json", "title": title, "note": sys.argv[4] if len(sys.argv) == 5 else ""})
    idx_file.write_text(json.dumps(idx, indent=1) + "\n")
    print(f"saved examples/{name}.json ({(ex / f'{name}.json').stat().st_size // 1024} KB)")
