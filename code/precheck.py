"""precheck.py - pre-submission consistency check: does everything we are about to submit say the same thing, and does it meet
the brief's hard rules? Read-only; prints PASS / FAIL / WARN per item and exits 1 if anything FAILs.

    python code/precheck.py --tag final                       # after run_all --final, build_report, build_slides
    python code/precheck.py --tag final --zip evidence_final.zip   # also inspect the ZIP made by make_zip.py
    python code/precheck.py --tag preview                      # mechanics test: the binding items are expected to FAIL

Checks (the brief's wording in brackets):
  record   market, unit, target, cutoff 13 Nov 12:00 UTC, status not preview, approved by all four before 17:00 UTC
           ["the evidence record must match [the cover]"; "Group members approve and take responsibility"]
  cover    the report cover, the slides and the speaker script all carry the record's value to two decimals
           ["The point forecast on the report cover is the binding forecast"; "slides must correspond to the submitted forecast"]
  report   at most 2,400 main-body words; no placeholders left
  checks   independent_check.json PASS_ALL and forecast matches the record
  data     snapshot files match the SHA-256 in manifest.json (frozen), fetched after the cutoff, last close = Thu 12 Nov;
           news digest dated before the cutoff ["no future information"]
  group    four members with names, IDs, responsibilities, checks and AI-use statements
  zip      README, requirements, record, manifest and report inside; no licensed or credential files; record identical
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CUTOFF = dt.datetime(2026, 11, 13, 12, 0, tzinfo=dt.timezone.utc)
DEADLINE = dt.datetime(2026, 11, 13, 17, 0, tzinfo=dt.timezone.utc)      # 17:00 London = 17:00 UTC in November
LICENSED = re.compile(r"zaki|\.xlsx$|ES1_|CME_|bbg-drop|\.env|credential|secret", re.I)       # matched on the file name or path
PLACEHOLDER = re.compile(r"\[(?:group number|surname|id)\]|to confirm|TODO|TBD|placeholder|edit group_info|lorem", re.I)
RESULTS = []


def say(level, what, detail=""):
    RESULTS.append(level)
    print(f"{level:<5} {what}" + (f" - {detail}" if detail else ""))


def check(ok, what, detail="", warn=False):
    say("PASS" if ok else ("WARN" if warn else "FAIL"), what, detail)


def docx_chunks(path):
    import docx
    d = docx.Document(path)
    out = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        for r in t.rows:
            out.append(" | ".join(dict.fromkeys(c.text.strip() for c in r.cells)))
    return out


def load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, choices=["final", "preview", "rehearsal", "now"])
    ap.add_argument("--zip", default=None, help="evidence ZIP built by make_zip.py")
    a = ap.parse_args()
    tag, out = a.tag, ROOT / "outputs" / a.tag
    if tag != "final":
        print(f"NOTE  tag is '{tag}': the binding items (status, cutoff, approval, snapshot date) are expected to FAIL.\n")
    rec, R = load(out / "forecast_record.json"), load(out / "results.json")
    F = f"{rec['forecast']:,.2f}"

    # ---- record
    check(rec.get("market", "").startswith("S&P 500") and rec.get("unit") == "index points", "record names the market and unit", f"{rec.get('market')}, {rec.get('unit')}")
    check("2026-11-20" in rec.get("target", "") and "16:00" in rec.get("target", ""), "record names the target", rec.get("target", ""))
    cut = dt.datetime.fromisoformat(rec["information_cutoff_utc"])
    check(cut == CUTOFF, "cutoff is Fri 13 Nov 2026 12:00 UTC", rec["information_cutoff_utc"])
    st = rec.get("status", "")
    check(not re.search(r"PREVIEW|REHEARSAL|NOT BINDING", st, re.I), "status is not preview or rehearsal", st)
    appr = rec.get("approved_by", [])
    check(len([x for x in appr if x]) == 4, "all four members have approved", f"{[x for x in appr if x]}")
    try:
        when = dt.datetime.fromisoformat(rec.get("approval_utc", "").replace("Z", "+00:00"))
        check(CUTOFF <= when <= DEADLINE, "approval time is between the cutoff and the 17:00 deadline", rec["approval_utc"])
    except ValueError:
        check(False, "approval time recorded", repr(rec.get("approval_utc", "")))
    check(abs(R["forecast_final"] - rec["forecast"]) < 0.005, "record equals results.json", f"{rec['forecast']} vs {R['forecast_final']}")
    check(rec.get("discretionary_adjustment_pct", 0) == 0, "no discretionary adjustment")

    # ---- cover, slides, script
    rep = sorted((ROOT / "report").glob(f"report_{tag}.docx"))
    if not rep:
        check(False, "report .docx exists", f"report/report_{tag}.docx")
    else:
        chunks = docx_chunks(rep[0])
        cover = "\n".join(chunks[:20])
        check(F in cover, f"report cover carries {F}", "first page")
        other = set(re.findall(r"\b\d,\d{3}\.\d{2}\b", "\n".join(c for c in chunks[:14] if "last usable" not in c.lower() and "interval" not in c.lower()))) - {F}
        check(not other, "no other level on the cover besides the forecast, last close and interval", ", ".join(sorted(other)))
        body = "\n".join(chunks)
        m = re.search(r"Main-body words \| ([\d,]+) of ([\d,]+)", body)
        check(bool(m) and int(m.group(1).replace(",", "")) <= 2400, "main body at most 2,400 words", m.group(0) if m else "count line not found")
        ph = PLACEHOLDER.findall(body)
        check(not ph, "no placeholders in the report", str(ph[:3]))
        check((ROOT / "report" / f"report_{tag}.pdf").exists(), "report PDF exists (the brief asks for a PDF)")
        pdf, docx_p = ROOT / "report" / f"report_{tag}.pdf", rep[0]
        if pdf.exists():
            check(pdf.stat().st_mtime >= docx_p.stat().st_mtime - 5, "report PDF is not older than the .docx", warn=True)
    sl = ROOT / "report" / f"slides_{tag}.pptx"
    if sl.exists():
        from pptx import Presentation
        txt = "\n".join(sh.text_frame.text for s in Presentation(sl).slides for sh in s.shapes if sh.has_text_frame)
        check(F in txt, f"slides carry {F}")
        check(not re.search(r"PREVIEW|NOT BINDING", txt) or tag != "final", "slides are not marked preview")
    else:
        check(False, "slides exist", str(sl.relative_to(ROOT)))
    sp = ROOT / "report" / f"speaker_script_{tag}.md"
    check(sp.exists() and F in sp.read_text(encoding="utf-8"), f"speaker script carries {F}")

    # ---- independent check
    k = load(out / "independent_check.json")
    check(k.get("PASS_ALL") is True, "independent check PASS_ALL", str(k.get("PASS_ALL")))
    check(k.get("forecast_matches_record") is True, "independent check matches the record", str(k.get("forecast_matches_record")), warn=True)
    check(k.get("leak_test_pass") is True, "leak test passed")

    # ---- data
    snap = ROOT / ("data/raw_final" if tag == "final" else "data/raw_live")
    man = load(snap / "manifest.json")
    bad = []
    for name, f in man["files"].items():
        if name == "zaki_data.xlsx":        # the supporting workbook is never shipped; the final build does not use it
            continue
        p = snap / name
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != f["sha256"]:
            bad.append(name)
    check(not bad, f"every snapshot file matches its SHA-256 ({len(man['files'])} files)", ", ".join(bad))
    got = dt.datetime.fromisoformat(man["retrieved_utc"])
    check(got >= CUTOFF if tag == "final" else True, "snapshot retrieved after the cutoff (the 07:00 New York bar exists only then)", man["retrieved_utc"])
    check(R["last_close_date"] == "2026-11-12" if tag == "final" else True, "last usable close is Thu 12 Nov", R["last_close_date"])
    dig = load(ROOT / "data" / "news_digest.json")
    late = [f"{i['date']}: {i['event'][:50]}" for i in dig["items"] if i["date"] > "2026-11-13"]
    check(not late, "news digest: items dated after 13 Nov are scheduled events only (read them: no outcomes)", "; ".join(late), warn=True)
    check(dig.get("researched_utc", "") <= "2026-11-13T12:00" or tag != "final", "news digest researched before the cutoff", dig.get("researched_utc", "?"), warn=True)
    nourl = [i["date"] for i in dig["items"] if not i.get("url")]
    check(not nourl, "every news item has a URL", ", ".join(nourl), warn=True)

    # ---- group
    g = load(ROOT / "group_info.json")
    mem = g.get("members", [])
    check(len(mem) == 4 and all(m.get("name") and m.get("id") and m.get("responsibilities") and m.get("checks") for m in mem), "four members with names, IDs, responsibilities, checks")
    check(len(g.get("ai_use_detail", [])) >= 3 and len(g.get("ai_tools", [])) == 4, "AI-use statements for all four members", f"{len(g.get('ai_tools', []))} tool lines, {len(g.get('ai_use_detail', []))} detail entries")
    check(bool(g.get("group")), "group number set", str(g.get("group")))

    # ---- zip
    if a.zip:
        z = zipfile.ZipFile(a.zip)
        names = z.namelist()
        need = ["README.md", "requirements.txt", f"outputs/{tag}/forecast_record.json", f"outputs/{tag}/results.json", "agent/AGENT_INSTRUCTIONS.md",
                "agent/agent_log.md", "group_info.json", ("data/raw_final" if tag == "final" else "data/raw_live") + "/manifest.json", f"report/report_{tag}.docx"]
        miss = [n for n in need if n not in names]
        check(not miss, "ZIP has the required files", ", ".join(miss))
        check(any(n.startswith("agent/run_transcript_") for n in names), "ZIP has a run transcript")
        lic = [n for n in names if LICENSED.search(n) and not n.startswith("data/group_evidence/")] + \
              [n for n in names if n.startswith("data/group_evidence/") and re.search(r"\.xlsx$|ES1_|CME_|\.env|bbg-drop", n, re.I)]
        check(not lic, "ZIP has no licensed or credential files", ", ".join(lic[:5]))
        rd = z.read("README.md").decode("utf-8") if "README.md" in names else ""
        check(F in rd and "<!-- FORECAST_BLOCK -->" not in rd, "ZIP README shows the forecast", "block filled from the record")
        if f"outputs/{tag}/forecast_record.json" in names:
            same = z.read(f"outputs/{tag}/forecast_record.json") == (out / "forecast_record.json").read_bytes()
            check(same, "ZIP record is identical to the signed record")
        size = pathlib.Path(a.zip).stat().st_size / 1e6
        check(size < 50, "ZIP size is reasonable", f"{size:.1f} MB", warn=True)
    else:
        say("WARN", "ZIP not inspected", "pass --zip evidence_final.zip")

    n = {x: RESULTS.count(x) for x in ("PASS", "WARN", "FAIL")}
    print(f"\n{n['PASS']} pass, {n['WARN']} warn, {n['FAIL']} fail")
    sys.exit(1 if n["FAIL"] else 0)


if __name__ == "__main__":
    main()
