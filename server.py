"""Local server: serves index.html and runs steqpy fits for it, on this machine only.

The page sends the parsed catalogue, polygon, time window and magnitude cutoff; the server
checks them again (browser input cannot be trusted), writes a job folder (catalogue, polygon,
steqpy config.toml, request.json), runs `python -m steqpy` in a subprocess with a time limit,
one job at a time, and the page polls until result.json is ready. Job folders are kept in
jobs/, so a run's polygon and config can be reused.

Same API shape as the planned FastAPI server (Prompt 3): POST /jobs, GET /jobs/{id},
GET /jobs/{id}/result. shortcut: standard library only, jobs held in memory (finished jobs
are re-read from disk), no limits per user; replace with the Prompt 3 server before hosting.

Run with the steqpy environment's Python (it runs steqpy with the same interpreter):
    python server.py            then open http://127.0.0.1:8765/
"""
import json
import math
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEQPY_SRC = HERE.parent / "stochastic_declustering_improvement" / "src"
JOBS = HERE / "jobs"
HOST, PORT = "127.0.0.1", 8765          # local only
TIME_LIMIT = 1800                       # seconds per fit
MAX_EVENTS = 200_000                    # shortcut: placeholder caps until Prompt 5
MAX_BODY = 60 * 2 ** 20
THREADS = 10
DAY_MS = 864e5
# Start values for the optimiser: steqpy's JMA example (configs/jma.toml).
START = {"mu": 0.592844590, "A": 0.204288231, "c": 0.022692883, "alpha": 1.495169224,
         "p": 1.109752319, "D": "0.001175925 deg2", "q": 1.860044210, "gamma": 1.041549634}
JOB_ID = re.compile(r"^[A-Za-z0-9_-]{6,32}$")

jobs = {}                               # id -> {"state", "message"}
work = queue.Queue()
lock = threading.Lock()


def check_request(req):
    """The page's request, checked: events (lon, lat, t in ms, m), polygon [[lon, lat], ...],
    from_ms / to_ms (target window, `to` day included), mc. Raises ValueError."""
    ev = req.get("events") or {}
    cols = [ev.get(k) for k in ("lon", "lat", "t", "m")]
    if not all(isinstance(c, list) for c in cols) or len({len(c) for c in cols}) != 1:
        raise ValueError("events must have lon, lat, t, m lists of equal length")
    n = len(cols[0])
    if not 0 < n <= MAX_EVENTS:
        raise ValueError(f"need 1 to {MAX_EVENTS} events, got {n}")
    for name, c, lo, hi in (("lon", cols[0], -180, 180), ("lat", cols[1], -90, 90),
                            ("t", cols[2], -1e15, 1e15), ("m", cols[3], -5, 12)):
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and lo <= v <= hi for v in c):
            raise ValueError(f"events.{name}: values must be numbers in [{lo}, {hi}]")
    poly = req.get("polygon")
    if (not isinstance(poly, list) or not 3 <= len(poly) <= 200
            or not all(isinstance(p, list) and len(p) == 2 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p) for p in poly)):
        raise ValueError("polygon must be 3 to 200 [lon, lat] pairs")
    f, t, mc = req.get("from_ms"), req.get("to_ms"), req.get("mc")
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (f, t, mc)) or not f <= t:
        raise ValueError("need numbers from_ms <= to_ms and mc")
    mo, hess = req.get("max_outer", 11), req.get("hessian", False)
    if not (isinstance(mo, int) and not isinstance(mo, bool) and 1 <= mo <= 100) or not isinstance(hess, bool):
        raise ValueError("max_outer must be a whole number in [1, 100] and hessian true or false")
    return (cols, poly, float(f), float(t) + DAY_MS, float(mc), check_jitter(req.get("jitter") or {}),
            {"max_outer": mo, "hessian": hess})


def check_jitter(j):
    """Optional jitter (steqpy's jitter_* settings): lon, lat, mag = 0, a half-width, or
    "precision" (half the last decimal of each value); t_s = half-width in seconds; seed."""
    num = lambda v, hi: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= hi
    out = {}
    for k, hi in (("lon", 5), ("lat", 5), ("mag", 1)):
        v = j.get(k, 0)
        if not (v == "precision" or num(v, hi)):
            raise ValueError(f'jitter.{k} must be "precision" or a number in [0, {hi}]')
        out[k] = v
    if not num(j.get("t_s", 0), 86400):
        raise ValueError("jitter.t_s must be a number of seconds in [0, 86400]")
    seed = j.get("seed", 0)
    if not (isinstance(seed, int) and not isinstance(seed, bool) and 0 <= seed < 2 ** 32):
        raise ValueError("jitter.seed must be a whole number >= 0")
    out.update(t_s=j.get("t_s", 0), seed=seed)
    return out


def write_job(jid, req):
    """Job folder: catalogue.etas (steqpy's catalogue format: id lon lat mag t-in-days),
    polygon.txt, config.toml, request.json. Events after the window or below mc are left out;
    earlier events and events outside the polygon stay, as possible triggers."""
    (lon, lat, t, m), poly, t_from, t_to, mc, jit, fit = check_request(req)
    # steqpy applies the cuts after jittering, so keep events that the jitter could move in
    m_slack = 0.5 if jit["mag"] == "precision" else jit["mag"]
    keep = sorted((ti, i) for i, ti in enumerate(t)
                  if ti < t_to + jit["t_s"] * 1000 and m[i] >= mc - m_slack - 1e-9)
    if not keep:
        raise ValueError("no events at or above the magnitude cutoff before the end date")
    t0 = keep[0][0] - DAY_MS            # day 0 one day before the first event (t > t_min)
    d = JOBS / jid
    d.mkdir(parents=True)
    with open(d / "catalogue.etas", "w") as fh:
        fh.write("'uploaded catalogue: id lon lat mag t(days since t0)'\n")
        for k, (ti, i) in enumerate(keep):
            fh.write(f"{k + 1} {lon[i]:.6f} {lat[i]:.6f} {m[i]:.3f} {(ti - t0) / DAY_MS:.8f}\n")
    (d / "polygon.txt").write_text("".join(f"{x:.6f} {y:.6f}\n" for x, y in poly))
    cfg = ["# Written by the website's local server", "[input]",
           'catalog = "catalogue.etas"', 'polygon = "polygon.txt"', "t_min = 0.0",
           f"t_start = {(t_from - t0) / DAY_MS:.8f}", f"t_end = {(t_to - t0) / DAY_MS:.8f}",
           f"mag_min = {mc}"]
    toml = lambda v: '"precision"' if v == "precision" else repr(float(v))
    cfg += [f"jitter_{k} = {toml(jit[k])}" for k in ("lon", "lat", "mag") if jit[k]]
    if jit["t_s"]:
        cfg.append(f"jitter_t = {jit['t_s'] / 86400!r}")
    if any(jit[k] for k in ("lon", "lat", "mag", "t_s")):
        cfg.append(f"jitter_seed = {jit['seed']}")
    cfg += ["", "[params]"]
    cfg += [f'{k} = "{v}"' if isinstance(v, str) else f"{k} = {v}" for k, v in START.items()]
    cfg += ["", "[convergence]", f"max_outer = {fit['max_outer']}",
            "", "[run]", f"threads = {THREADS}", f"hessian_errors = {'true' if fit['hessian'] else 'false'}", ""]
    (d / "config.toml").write_text("\n".join(cfg))
    (d / "request.json").write_text(json.dumps({"polygon": poly, "from_ms": t_from, "to_ms": t_to - DAY_MS,
                                                 "mc": mc, "jitter": jit, **fit, "t0_ms": t0, "n_events_sent": len(t),
                                                 "n_events_used": len(keep)}))


def worker():
    env = dict(os.environ, PYTHONPATH=str(STEQPY_SRC))
    # conda env DLLs (numpy's LAPACK) must be on PATH when the env is not activated
    p = Path(sys.prefix)
    env["PATH"] = os.pathsep.join(str(p / s) for s in ("", "Library/mingw-w64/bin", "Library/usr/bin",
                                                       "Library/bin", "Scripts")) + os.pathsep + env.get("PATH", "")
    while True:
        jid = work.get()
        d = JOBS / jid
        with lock:
            jobs[jid] = {"state": "running", "message": "Starting"}
        try:
            r = subprocess.run([sys.executable, "-m", "steqpy", "config.toml", "--out", "out"], cwd=d,
                               env=env, capture_output=True, text=True, timeout=TIME_LIMIT)
            ok = r.returncode == 0 and (d / "out" / "result.json").exists()
            msg = "Done" if ok else (r.stderr.strip().splitlines() or ["steqpy failed"])[-1][:300]
            (d / "stderr.txt").write_text(r.stderr)
        except subprocess.TimeoutExpired:
            ok, msg = False, f"Stopped: the fit took longer than {TIME_LIMIT // 60} minutes"
        with lock:
            jobs[jid] = {"state": "done" if ok else "failed", "message": msg}


def status(jid):
    d = JOBS / jid
    with lock:
        j = dict(jobs.get(jid) or {})
        if j.get("state") == "queued":
            j["position"] = list(work.queue).index(jid) + 1 if jid in work.queue else 0
    if not j:                           # e.g. after a server restart: read the folder
        if (d / "out" / "result.json").exists():
            return {"state": "done", "message": "Done"}
        return None
    if j["state"] == "running":         # progress from steqpy's run.log
        try:
            outers = re.findall(r"^ outer (\d+)", (d / "out" / "run.log").read_text(), re.M)
            most = json.loads((d / "request.json").read_text()).get("max_outer", 11)
            j["message"] = (f"Fitting the model, outer iteration {min(int(outers[-1]) + 1, most)} of at most {most}"
                            if outers else "Fitting the model")
        except OSError:
            pass
    return j


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self.send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        m = re.match(r"^/jobs/([^/]+)(/result)?$", path)
        if not m or not JOB_ID.match(m.group(1)):
            return self.send(404, {"error": "not found"})
        jid = m.group(1)
        if m.group(2):
            f = JOBS / jid / "out" / "result.json"
            if not f.exists():
                return self.send(404, {"error": "no result yet"})
            res = json.loads(f.read_text(encoding="utf-8"))
            res["request"] = json.loads((JOBS / jid / "request.json").read_text())   # t0, settings
            return self.send(200, res)
        s = status(jid)
        return self.send(200, s) if s else self.send(404, {"error": "unknown job"})

    def do_POST(self):
        if self.path != "/jobs":
            return self.send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 < n <= MAX_BODY:
            return self.send(413, {"error": "request too large"})
        try:
            jid = secrets.token_urlsafe(9)
            write_job(jid, json.loads(self.rfile.read(n)))
        except (ValueError, json.JSONDecodeError) as e:
            return self.send(400, {"error": str(e)})
        with lock:
            jobs[jid] = {"state": "queued", "message": "Queued"}
        work.put(jid)
        return self.send(201, {"id": jid})

    def log_message(self, fmt, *args):  # quieter console: requests other than polls
        if "GET /jobs/" not in (args[0] if args else ""):
            sys.stderr.write("%s\n" % (fmt % args))


if __name__ == "__main__":
    JOBS.mkdir(exist_ok=True)
    threading.Thread(target=worker, daemon=True).start()
    print(f"Serving on http://{HOST}:{PORT}/  (jobs in {JOBS})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
