"""make_zip.py - builds the submission ZIP (evidence package only; never includes .env / credential files).

    python code/make_zip.py --tag final
"""
import argparse
import hashlib
import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKIP_NAMES = {".env", ".env.txt", "__pycache__"}


def forecast_block(tag):
    """Markdown block for the ZIP's README, read from the record in this package, so it cannot go stale."""
    path = ROOT / "outputs" / tag / "forecast_record.json"
    rec = json.loads(path.read_text(encoding="utf-8"))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    approved = [a for a in rec.get("approved_by", []) if a]
    rows = [("Status", rec.get("status", "")), ("Market and unit", f"{rec['market']}, {rec['unit']}"), ("Target", rec["target"]),
            ("Information cutoff", f"{rec['information_cutoff_utc']} UTC"),
            ("Last usable close", f"{rec['last_usable_close_date']} = {rec['last_usable_close']:,.2f}"),
            ("**Forecast**", f"**{rec['forecast']:,.2f}**"), ("Reference source", rec["reference_source"]),
            ("Discretionary adjustment", f"{rec.get('discretionary_adjustment_pct', 0):.2f}%"),
            ("Approved by", ", ".join(approved) + (f" at {rec['approval_utc']}" if rec.get("approval_utc") else "") if approved else "NOT YET APPROVED"),
            ("Record", f"`outputs/{tag}/forecast_record.json`, SHA-256 {sha}...")]
    return "| Final forecast record | |\n|---|---|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows) + "\n"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tag", required=True, choices=["final", "rehearsal", "preview", "now"])
    a = ap.parse_args()
    out = ROOT / f"evidence_{a.tag}.zip"
    raw = {"final": "data/raw_final", "rehearsal": "data/raw_live", "preview": "data/raw_live", "now": "data/raw_now"}[a.tag]
    # outputs/rehearsal is the rehearsal against a known outcome; build_slides.py quotes it on slide 5 in every build.
    keep = list(dict.fromkeys(["README.md", "requirements.txt", "group_info.json", "code", "agent", "outputs/" + a.tag, "outputs/rehearsal", "report",
                               "data/news_digest.json", "data/price_corrections.json", "data/group_tests.json", "data/workbook_screen_note.json", "data/group_evidence", "outputs/extra", raw]))
    missing = [k for k in ["README.md", "requirements.txt", "group_info.json", "outputs/" + a.tag, "data/group_tests.json", raw] if not (ROOT / k).exists()]
    if missing:
        raise SystemExit(f"STOP: required for the ZIP but not found: {missing}")
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for k in keep:
            p = ROOT / k
            files = [p] if p.is_file() else [q for q in p.rglob("*") if q.is_file()]
            for q in files:
                if q.name == "zaki_data.xlsx":      # supporting workbook is a helper, not part of the submission
                    continue
                if q.name.lower().startswith(".env") or "__pycache__" in q.parts or q.suffix == ".pyc" or q.name.startswith("_leak_"):
                    continue
                # final ZIP: drop the preview and the rehearsal's report/slides, but keep the rehearsal outputs and its run transcript as evidence
                if a.tag == "final" and ("preview" in q.parts or q.name.startswith(("report_rehearsal", "report_preview", "slides_rehearsal", "slides_preview", "speaker_script_rehearsal", "speaker_script_preview")) or "transcript_preview" in q.name):
                    continue
                if a.tag != "final" and q.name.startswith(("report_", "slides_", "speaker_script_")) and a.tag not in q.name:
                    continue
                if q == ROOT / "README.md":     # the forecast block is filled from the record in this package
                    txt = q.read_text(encoding="utf-8")
                    if "<!-- FORECAST_BLOCK -->" in txt:
                        txt = txt.replace("<!-- FORECAST_BLOCK -->", forecast_block(a.tag))
                    z.writestr("README.md", txt); n += 1
                    continue
                z.write(q, q.relative_to(ROOT).as_posix()); n += 1
    print(f"wrote {out} ({n} files, {out.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
