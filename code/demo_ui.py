"""demo_ui.py - local web page for the live agent demo (Python standard library only).

    python code/demo_ui.py                  # then open http://127.0.0.1:8765
    python code/demo_ui.py --port 8800

Run it in an UNZIPPED COPY of the evidence package, not in the submission folder: the `check` tool rewrites
outputs/<tag>/independent_check.json (same content) and live runs are saved under agent/demo_runs/.

What it does
- LIVE: runs Claude Code headless in this folder with one of the prompts in agent/demo_prompts/
  (check, whatif, ask). In check and ask the agent writes its own plan and chooses its own tools and what-if
  values. Permission mode dontAsk: only `python code/demo_tools.py ...`, Read and Claude Code's read-only commands
  (ls, cat...) run; writes, network commands and other programs are refused; web tools are disabled;
  only those prompts can be started. The model's text and reasoning are streamed as the CLI delivers them;
  tool calls and their outputs appear as they happen. Every event is saved to agent/demo_runs/ for replay.
- FAULT DRILL: copies the package to a temporary folder, plants ONE error in that copy of
  forecast_record.json, chosen at random (forecast shifted 12-40 points; last close shifted 3-15 points;
  cutoff moved to 13:45 UTC), and runs the normal check there. Neither the agent nor the room is told which
  until the end. The real record is never touched and the copy is deleted afterwards.
- REPLAY: plays a saved run back with its original timing (the brief allows a recorded walkthrough).
Binds to 127.0.0.1 only. The page never changes the forecast record; "sign-off" is display only.
Test hook: CLAUDE_BIN may point to a .py file (run with this Python), e.g. a mock CLI.
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import random
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CODE = pathlib.Path(__file__).resolve().parent
ROOT = CODE.parent
sys.path.insert(0, str(CODE))
import demo_tools  # noqa: E402

RUNS = ROOT / "agent" / "demo_runs"
LOCK = threading.Lock()
CURRENT = {"proc": None}
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
SHELL_NOTE = re.compile(r"^\s*Shell cwd was reset to .*$\n?", re.M)
TOOLS_ALLOWED = ["Bash(python code/demo_tools.py:*)", "Read"]
DRILLS = ("forecast", "close", "cutoff")
MODES = {
    "demo": {
        "label": "Demo: fresh data, information cutoff applied",
        "goal": "Check and explain the group's forecast of the S&P 500 official close on Fri 20 Nov 2026, then recommend whether to submit it.",
        "boundary": "This folder only. Fresh public data pulled by the agent's fetch tool, but the information cutoff (Fri 13 Nov 2026 12:00 UTC, 07:00 New York) still applies: anything published later is dropped.",
        "text_boundary": ("Mode: DEMO. Pull fresh public data with `fetch`; the information cutoff (Fri 13 Nov 2026 12:00 UTC, 07:00 New York) still applies and the tools drop "
                          "everything published later. The only network access is `fetch`, which contacts a fixed list of public sources."),
        "text_goal": ("You are the group's research agent. Goal: decide whether the group should submit the forecast record in this folder "
                      "(S&P 500 official close on Fri 20 Nov 2026, S&P Dow Jones Indices, index points)."),
        "text_finish": ('Finish with one line "Recommendation:" (submit or not, and why) and one line "Would change my mind:" (one concrete thing). '
                        'You recommend; the group decides.'),
        "fetchlines": ("- `python code/demo_tools.py --mode demo fetch`: pull fresh public data now (the only tool that uses the internet; fixed sources, writes only to data/agent_demo)\n"
                       "- `python code/demo_tools.py --mode demo compare`: the fresh pull against the frozen snapshot, row by row"),
        "checkline": "- `python code/demo_tools.py --mode demo check`: the package's independent second code path and leak test",
    },
    "full": {
        "label": "Full: all data to now, no cutoff (look-ahead)",
        "goal": "Using everything published up to now, report how the group's signed forecast of the S&P 500 official close on Fri 20 Nov 2026 compares with what the same frozen model gives now, and what has happened since the cutoff.",
        "boundary": "This folder only. Fresh public data pulled by the agent's fetch tool, with no information cutoff: a NON-BINDING look-ahead. The signed forecast record is never changed.",
        "text_boundary": ("Mode: FULL. Pull everything published up to now with `fetch`. There is no information cutoff here, so every result is a NON-BINDING look-ahead; "
                          "the signed forecast record is the one that is marked and must not be changed. Say clearly whenever a number uses data from after the cutoff. "
                          "The only network access is `fetch`, which contacts a fixed list of public sources."),
        "text_goal": ("You are the group's research agent. Goal: with all data up to now, report how the group's signed forecast record in this folder "
                      "(S&P 500 official close on Fri 20 Nov 2026, S&P Dow Jones Indices, index points) compares with what the same frozen model gives now "
                      "and with what has happened since the cutoff, and whether anything in the record looks wrong."),
        "text_finish": ('Finish with one line "Recommendation:" (whether the signed forecast needs attention, and why; the model is frozen and the record cannot change here) '
                        'and one line "Would change my mind:" (one concrete thing). You recommend; the group decides.'),
        "fetchlines": ("- `python code/demo_tools.py --mode full fetch`: pull everything published up to now (the only tool that uses the internet; fixed sources, writes only to data/agent_full)\n"
                       "- `python code/demo_tools.py --mode full compare`: fresh pull against the frozen snapshot, and what has moved since the cutoff"),
        "checkline": "",
    },
}


def given_for(dm):
    m = MODES[dm]
    return {
        "goal": m["goal"], "boundary": m["boundary"],
        "tools": "python code/demo_tools.py (fetch, compare, record, recompute, " + ("check, " if dm == "demo" else "") + "data, explain, whatif); reading files, including read-only commands such as ls and cat.",
        "not_allowed": "Any internet except the fetch tool (web tools off; network commands refused), writing or editing any file, any other program, trading.",
        "human": "The agent recommends. A group member reads the check and signs the record." if dm == "demo" else "The agent reports. The signed forecast is unchanged and cannot be changed by a look-ahead.",
    }


def mode_of(x):
    return x if x in MODES else "demo"


# ---------------------------------------------------------------------------------------------- helpers
def claude_cmd():
    b = os.environ.get("CLAUDE_BIN") or shutil.which("claude")
    if not b:   # the Claude desktop app on Windows bundles the CLI here; take the newest version
        pat = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Claude-Data", "*", "claude-code", "*", "*", "claude.exe")
        key = lambda p: [int(x) if x.isdigit() else x for x in re.split(r"[.\\/]", p)]
        hits = sorted(glob.glob(pat), key=key)
        b = hits[-1] if hits else None
    if not b:
        return None
    return [sys.executable, b] if b.endswith(".py") else [b]


def prompt_for(root, cmd, arg, dm="demo"):
    m = MODES[mode_of(dm)]
    text = (root / "agent" / "demo_prompts" / f"{cmd}.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    for tok, val in (("$FETCHLINES", m["fetchlines"]), ("$CHECKLINE", m["checkline"]), ("$GOAL", m["text_goal"]),
                     ("$BOUNDARY", m["text_boundary"]), ("$FINISH", m["text_finish"]), ("$MODE", "--mode " + mode_of(dm))):
        text = text.replace(tok, val)
    text = re.sub(r"\n\s*\n(?=- )", "\n", text)       # an empty tool line (no check tool in Full mode) leaves no gap
    return text.replace("$ARGUMENTS", arg or "").strip()


def clean_question(q):
    q = re.sub(r"[\x00-\x1f\x7f]", " ", q or "")
    return re.sub(r"\s+", " ", q).strip()[:300]


def run_meta(path):
    """Label, command and outcome of a saved run, for the replay list."""
    meta, ok, model = {}, None, ""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                ev = json.loads(line)
                if ev.get("k") == "meta" and not meta:
                    meta = ev
                elif ev.get("k") == "init":
                    model = ev.get("model") or ""
                elif ev.get("k") == "end":
                    ok = ev.get("ok")
    except (OSError, ValueError):
        pass
    what = {"check": "/check", "whatif": f"/whatif {meta.get('opt', '')}", "ask": "Ask", "drill": "Fault drill"}.get(meta.get("cmd"), meta.get("cmd", "?"))
    when = meta.get("label", "") if path.name.startswith("sample_") else f"Recorded {meta.get('label', '')}"
    return {"file": path.name, "label": f"{when} · {what} · {model or 'model unknown'}" + ("" if ok else "  (did not finish)"),
            "ok": bool(ok), "mtime": path.stat().st_mtime}


def info(dm="demo"):
    dm = mode_of(dm)
    try:
        c = demo_tools.ctx(None, dm)
        rec = c["rec"]
        if c["fresh"]:
            data = f"fresh pull {c['got']:%d %b %H:%M} UTC in data/agent_{dm}"
        elif dm == "full":
            data = "no data yet: the agent's first step is to fetch"
        else:
            data = f"frozen snapshot {c['frozen'].name} until the agent fetches"
        record = {"tag": c["tag"], "forecast": rec["forecast"], "status": rec.get("status", ""), "target": rec["target"],
                  "cutoff": f"{c['ref_cut']:%a %d %b %Y %H:%M} UTC ({c['ref_cut'].tz_convert('America/New_York'):%H:%M} New York)",
                  "sha12": hashlib.sha256(c["rec_path"].read_bytes()).hexdigest()[:12], "snapshot": data}
    except Exception as e:      # noqa: BLE001
        record = {"error": str(e)}
    # finished runs first, newest first (file names start with the UTC start time, so they sort by time even after copying)
    runs = sorted((run_meta(p) for p in RUNS.glob("*.jsonl")), key=lambda r: (r["ok"], r["file"]), reverse=True) if RUNS.exists() else []
    return {"given": given_for(dm), "dm": dm, "modes": {k: v["label"] for k, v in MODES.items()}, "record": record, "whatif": demo_tools.WHATIF, "runs": runs, "claude": bool(claude_cmd()), "drills": list(DRILLS)}


class Stream:
    """Claude Code stream-json -> small events for the page. With partial messages, text and reasoning arrive
    as deltas; the complete assistant message that follows is then used only for its tool calls."""

    def __init__(self):
        self.msg, self.streamed, self.opened = None, set(), set()

    def block(self, mid, b, model):
        ty = b.get("type")
        if ty in ("text", "thinking") and mid in self.streamed:
            return []
        if ty == "text" and b.get("text", "").strip():
            return [{"k": "error" if model == "<synthetic>" else "text", "text": b["text"].strip()}]
        if ty == "thinking" and b.get("thinking", "").strip():
            return [{"k": "thinking", "text": b["thinking"].strip()}]
        if ty == "tool_use":
            inp = b.get("input", {})
            cmd = inp.get("command") or inp.get("file_path") or json.dumps(inp)
            # the model sometimes prefixes `cd "<this folder>" &&`; it changes nothing, so it is hidden on screen
            cmd = re.sub(r'^cd\s+("[^"]*"|\'[^\']*\'|\S+)\s*&&\s*', "", cmd)
            return [{"k": "tool", "id": b.get("id"), "name": b.get("name"), "command": cmd}]
        return []

    def events(self, ev):
        ty = ev.get("type")
        if ev.get("parent_tool_use_id"):
            return []
        if ty == "system" and ev.get("subtype") == "init":
            return [{"k": "init", "model": ev.get("model")}]
        if ty == "stream_event":
            e = ev.get("event", {}); et = e.get("type"); blk = f"{self.msg}:{e.get('index')}"
            if et == "message_start":
                self.msg = e.get("message", {}).get("id")
            elif et == "content_block_start":
                kind = e.get("content_block", {}).get("type")
                if kind in ("text", "thinking"):
                    self.streamed.add(self.msg); self.opened.add(blk)
                    return [{"k": "open", "blk": blk, "kind": kind}]
                if kind == "tool_use":
                    return [{"k": "preparing", "name": e["content_block"].get("name")}]
            elif et == "content_block_delta":
                d = e.get("delta", {})
                if d.get("type") in ("text_delta", "thinking_delta"):
                    return [{"k": "delta", "blk": blk, "text": d.get("text") or d.get("thinking") or ""}]
            elif et == "content_block_stop" and blk in self.opened:
                self.opened.discard(blk)
                return [{"k": "close", "blk": blk}]
            return []
        if ty == "assistant":
            msg = ev.get("message", {})
            return [x for b in msg.get("content", []) for x in self.block(msg.get("id"), b, msg.get("model"))]
        if ty == "user":
            out = []
            for b in ev.get("message", {}).get("content", []):
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    c = b.get("content")
                    c = c if isinstance(c, str) else "\n".join(x.get("text", "") for x in (c or []) if isinstance(x, dict))
                    c = SHELL_NOTE.sub("", c)   # Claude Code's own "Shell cwd was reset to <path>" notice: noise, and a local path
                    out.append({"k": "result", "id": b.get("tool_use_id"), "text": c.strip(), "error": bool(b.get("is_error"))})
            return out
        if ty == "result":
            return [{"k": "end", "ok": not ev.get("is_error"), "turns": ev.get("num_turns"), "api_s": round((ev.get("duration_api_ms") or 0) / 1000, 1),
                     "cost_usd": ev.get("total_cost_usd"), "reason": ev.get("terminal_reason") or ev.get("subtype")}]
        return []


def make_drill(variant=None):
    """Copy the package to a temp folder and plant ONE error, chosen at random, in the copy's forecast record."""
    variant = variant if variant in DRILLS else random.choice(DRILLS)
    sb = pathlib.Path(tempfile.mkdtemp(prefix="agent_drill_"))
    shutil.copytree(ROOT, sb, dirs_exist_ok=True, ignore=shutil.ignore_patterns("report", "demo_runs", "*.zip", "__pycache__", "*.pdf", "*.docx", "*.pptx"))
    tag = "final" if (sb / "outputs" / "final" / "forecast_record.json").exists() else "preview"
    rp = sb / "outputs" / tag / "forecast_record.json"
    rec = json.loads(rp.read_text(encoding="utf-8"))
    sign = random.choice((-1, 1))
    if variant == "forecast":
        was, d = rec["forecast"], sign * round(random.uniform(12, 40), 2)
        rec["forecast"] = round(was + d, 2)
        what = f"forecast changed from {was:,.2f} to {rec['forecast']:,.2f} ({d:+.2f} points)"
    elif variant == "close":
        was, d = rec["last_usable_close"], sign * round(random.uniform(3, 15), 2)
        rec["last_usable_close"] = round(was + d, 2)
        what = f"last usable close changed from {was:,.2f} to {rec['last_usable_close']:,.2f} ({d:+.2f}); the forecast itself was left as it was"
    else:
        was = rec["information_cutoff_utc"]
        new = dt.datetime.fromisoformat(was) + dt.timedelta(hours=1, minutes=45)
        rec["information_cutoff_utc"] = new.isoformat(" ")
        what = f"information cutoff moved from {was} to {rec['information_cutoff_utc']} (later than the brief's 12:00 UTC)"
    rp.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return sb, {"variant": variant, "field": f"outputs/{tag}/forecast_record.json", "what": what}


# ---------------------------------------------------------------------------------------------- server
class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)

    def _sse_start(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache"); self.end_headers()

    def _send(self, ev):
        self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode()); self.wfile.flush()

    def do_GET(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/":
            b = (CODE / "demo_ui.html").read_bytes()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers()
            self.wfile.write(b)
        elif u.path == "/api/info":
            self._json(info(q.get("dm", "demo")))
        elif u.path == "/api/run":
            self.live(q.get("cmd", "check"), q.get("opt", ""), q.get("model", "sonnet"), q.get("depth", "fast"), q.get("q", ""), mode_of(q.get("dm")))
        elif u.path == "/api/stop":
            p = CURRENT["proc"]
            if p and p.poll() is None:
                p.kill()
            self._json({"stopped": bool(p)})
        elif u.path == "/api/replay":
            try:
                speed = float(q.get("speed", "1") or 1)
            except ValueError:
                speed = 1.0
            self.replay(q.get("file", ""), speed)
        else:
            self._json({"error": "not found"}, 404)

    # ------------------------------------------------------------------ live run
    def live(self, cmd, opt, model, depth, question, dm="demo"):
        self._sse_start()
        question = clean_question(question)
        opts = opt.split()
        if cmd == "drill" and dm == "full":
            self._send({"k": "error", "t": 0, "text": "The fault drill tests the signed record under the information cutoff, so it runs in Demo mode only."}); return
        bad = (cmd not in ("check", "whatif", "ask", "drill") or (cmd == "whatif" and (not opts or not all(demo_tools.OPT_RE.match(o) for o in opts)))
               or (cmd == "ask" and not question) or model not in ("sonnet", "haiku", "opus") or depth not in ("fast", "deep"))
        if bad:
            self._send({"k": "error", "t": 0, "text": "Unknown command, option or empty question."}); return
        exe = claude_cmd()
        if not exe:
            self._send({"k": "error", "t": 0, "text": "Claude Code CLI not found. Install it or set CLAUDE_BIN, or use a replay."}); return
        if not LOCK.acquire(blocking=False):
            self._send({"k": "error", "t": 0, "text": "Another live run is in progress. Press Stop first."}); return
        p, sandbox, t0 = None, None, time.time()
        try:
            root, drill = ROOT, None
            if cmd == "drill":
                sandbox, drill = make_drill(opt or None)   # opt may name a variant (testing); default random
                root = sandbox
            pcmd = {"drill": "check"}.get(cmd, cmd)
            prompt = prompt_for(root, pcmd, question if cmd == "ask" else opt, dm)
            args = [*exe, "-p", prompt, "--model", model, "--effort", "low" if depth == "fast" else "medium",
                    "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                    "--tools", "Bash,Read", "--allowedTools", *TOOLS_ALLOWED, "--disallowedTools", "WebFetch", "WebSearch",
                    "--strict-mcp-config", "--no-session-persistence", "--permission-mode", "dontAsk"]
            RUNS.mkdir(parents=True, exist_ok=True)
            slug = opt if cmd == "whatif" else (question[:30] if cmd == "ask" else "")
            name = f"{dt.datetime.now(dt.timezone.utc):%Y%m%d-%H%M%S}_{cmd}{('_' + re.sub(r'[^A-Za-z0-9]+', '-', slug).strip('-')) if slug else ''}.jsonl"
            with open(RUNS / name, "w", encoding="utf-8") as log:
                def emit(ev):
                    ev["t"] = round(time.time() - t0, 2)
                    log.write(json.dumps(ev) + "\n"); log.flush(); self._send(ev)
                emit({"k": "meta", "mode": "live", "dm": dm, "cmd": cmd, "opt": opt, "question": question, "model": model, "depth": depth, "prompt": prompt,
                      "drill": drill, "label": f"{dt.datetime.now(dt.timezone.utc):%d %b %H:%M} UTC", "file": name})
                env = dict(os.environ, PYTHONIOENCODING="utf-8", DEMO_MODE=dm)
                # stdin closed: otherwise the CLI waits 3 s for piped input before starting
                p = subprocess.Popen(args, cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", env=env)
                CURRENT["proc"] = p
                st = Stream()
                for raw in p.stdout:
                    try:
                        evs = st.events(json.loads(raw))
                    except ValueError:
                        line = ANSI.sub("", raw).strip()
                        # the "workspace not trusted" notice is harmless here: the tools are pre-approved on the command line
                        evs = [{"k": "log", "text": line}] if line and not line.startswith("Ignoring") else []
                    for ev in evs:
                        emit(ev)
                emit({"k": "exit", "code": p.wait()})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:      # noqa: BLE001  (report anything else on the page instead of hanging)
            try:
                self._send({"k": "error", "t": round(time.time() - t0, 2), "text": f"Demo server error: {e}"})
            except OSError:
                pass
        finally:
            if p and p.poll() is None:
                p.kill()
            CURRENT["proc"] = None
            if sandbox:
                shutil.rmtree(sandbox, ignore_errors=True)
            LOCK.release()

    # ------------------------------------------------------------------ replay
    def replay(self, file, speed):
        self._sse_start()
        path = RUNS / pathlib.Path(file).name
        if not path.is_file():
            self._send({"k": "error", "t": 0, "text": f"No saved run called {file}."}); return
        evs = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        t0, last = time.time(), 0.0
        try:
            for ev in evs:
                if ev.get("k") == "meta":
                    ev = dict(ev, mode="replay", sample=path.name.startswith("sample_"))
                wait = (ev.get("t", last) - last) / max(speed, 0.1)
                if wait > 0:
                    time.sleep(min(wait, 8))
                last = ev.get("t", last)
                self._send(ev)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    exe = claude_cmd()
    print(f"Agent demo UI: http://127.0.0.1:{a.port}  (folder: {ROOT}; Claude CLI: {' '.join(exe) if exe else 'not found'})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
