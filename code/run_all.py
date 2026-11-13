"""run_all.py - one command reproduces every number, table, figure, the report and the slides.
Everything printed is also saved to agent/run_transcript_<tag>.txt (the run transcript the brief asks for).

    python code/run_all.py --rehearsal              # cutoff 30 Oct 2026 12:00 UTC, target 6 Nov (outcome known, kept out by the cutoff filter)
    python code/run_all.py --preview                # information to 10 Nov 12:00 UTC (07:00 New York, the cutoff's clock time), target 20 Nov: NON-BINDING
    python code/run_all.py --final --fetch          # on 13 Nov AFTER 12:00 UTC: download the public snapshot, then run (no --zaki: public data only)
    python code/run_all.py --final                  # reproduce the submitted forecast from the saved snapshot (no internet, no AI account)
"""
import argparse
import datetime as dt
import os
import pathlib
import platform
import subprocess
import sys

CODE = pathlib.Path(__file__).resolve().parent
ROOT = CODE.parent
PY = sys.executable
LOG = None   # open transcript file (agent/run_transcript_<tag>.txt); every line printed below is also written there

PRESETS = {
    "rehearsal": dict(snapshot="data/raw_live", cutoff="2026-10-30T12:00:00Z", target="2026-11-06", extra=[]),
    "preview": dict(snapshot="data/raw_live", cutoff="2026-11-10T12:00:00Z", target="2026-11-20", extra=["--allow-stale"]),   # same clock time as the real cutoff (07:00 New York)
    "final": dict(snapshot="data/raw_final", cutoff="2026-11-13T12:00:00Z", target="2026-11-20", extra=[]),
    # on-demand look-ahead: information up to the moment the command is run (NOT binding before the 13 Nov cutoff)
    "now": dict(snapshot="data/raw_now", cutoff=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:00Z"),
                target="2026-11-20", extra=["--allow-stale"]),
}


def say(line: str):
    print(line, flush=True)
    if LOG:
        LOG.write(line + "\n"); LOG.flush()


def rel(x):
    p = pathlib.Path(str(x))
    try:
        return p.relative_to(ROOT).as_posix()      # no personal folder names in the transcript
    except ValueError:
        return p.name if p.is_absolute() else str(x)   # e.g. the workbook path: file name only


def run(*args):
    say(">> python " + " ".join(rel(x) for x in args))
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    p = subprocess.Popen([PY, *map(str, args)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    for line in p.stdout:
        say(line.rstrip("\n"))
    if p.wait() != 0:
        say(f"!! exit code {p.returncode}: run stopped")
        raise subprocess.CalledProcessError(p.returncode, args)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearsal", action="store_true"); g.add_argument("--preview", action="store_true"); g.add_argument("--final", action="store_true")
    g.add_argument("--now", action="store_true", help="non-binding run with information up to this moment (use with --fetch)")
    ap.add_argument("--fetch", action="store_true", help="download a fresh raw snapshot first (needs internet)")
    ap.add_argument("--zaki", default=None, help="Zaki's workbook, copied into the snapshot when --fetch is used")
    ap.add_argument("--es-manual", nargs=2, metavar=("ES_1600_PREV", "ES_CUTOFF"), help="Bloomberg backup for the ES prices (see run_model.py)")
    ap.add_argument("--es-manual-source", default="", help="where and when the --es-manual prices were read")
    a = ap.parse_args()
    tag = "final" if a.final else "preview" if a.preview else "now" if a.now else "rehearsal"
    p = PRESETS[tag]
    global LOG
    (ROOT / "agent").mkdir(exist_ok=True)
    LOG = open(ROOT / "agent" / f"run_transcript_{tag}.txt", "w", encoding="utf-8")
    say(f"# Run transcript ({tag}), written by code/run_all.py")
    say(f"# started {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S} UTC | Python {platform.python_version()} on {platform.system()} {platform.release()}")
    say(f"# command: python code/run_all.py --{tag}" + (" --fetch" if a.fetch else "") + (" --zaki <workbook>" if a.zaki else ""))
    if a.fetch:
        run(CODE / "fetch_data.py", "--out", p["snapshot"], *(["--zaki", a.zaki] if a.zaki else []))
    es_args = ["--es-manual", *a.es_manual, "--es-manual-source", a.es_manual_source] if a.es_manual else []
    run(CODE / "run_model.py", "--snapshot", p["snapshot"], "--cutoff", p["cutoff"], "--target", p["target"], "--tag", tag, *p["extra"], *es_args)
    run(CODE / "make_figures.py", "--tag", tag, "--snapshot", p["snapshot"])
    run(CODE / "independent_check.py", "--snapshot", p["snapshot"], "--tag", tag)
    run(CODE / "build_report.py", "--tag", tag)
    run(CODE / "build_slides.py", "--tag", tag)
    say(f"# finished {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
    LOG.close()


if __name__ == "__main__":
    main()
