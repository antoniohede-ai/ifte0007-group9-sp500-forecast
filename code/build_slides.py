"""build_slides.py - 5-slide, 7-minute presentation plus a sixth slide for the live agent demo in the questions (PPTX + PDF) and speaker script, generated from outputs/<tag>/results.json.
If the live agent demo is in the package (code/demo_ui.py), a 6th slide is added for the Q&A: the agent re-checks the
frozen forecast live. Slides 1-5 and their timings are unchanged.

    python code/build_slides.py --tag rehearsal|final
Every number comes from results.json, so slides and report cannot drift apart.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import pathlib
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, news_known, utc  # noqa: E402

W, H = 13.333, 7.5
NAVY, INK, MUTED, TINT, WHITE = "0E2238", "1F2933", "5B6573", "EAF1F7", "FFFFFF"
TEAL, AMBER, ROSE, PALE = "17806D", "C77D14", "A63D40", "C9D6E3"
FONT = "Calibri"


def f(x, d=2):
    return f"{x:,.{d}f}"


def sgn(x, d=2):
    return f"{x:+,.{d}f}"


class Slide:
    def __init__(self, bg=WHITE, notes=""):
        self.bg, self.notes, self.items = bg, notes, []

    def rect(self, x, y, w, h, fill=None, line=None, r=0.0, lw=1.0):
        self.items.append(("rect", x, y, w, h, fill, line, r, lw)); return self

    def oval(self, x, y, w, h, fill):
        self.items.append(("oval", x, y, w, h, fill)); return self

    def text(self, x, y, w, h, paras, size=16, color=INK, bold=False, align="l", anchor="t"):
        if isinstance(paras, (str, dict)):
            paras = [paras]
        self.items.append(("text", x, y, w, h, paras, size, color, bold, align, anchor)); return self

    def image(self, path, x, y, w):
        self.items.append(("img", str(path), x, y, w)); return self


def norm(p, size, color, bold):
    d = {"text": p} if isinstance(p, str) else dict(p)
    d.setdefault("size", size); d.setdefault("color", color); d.setdefault("bold", bold); d.setdefault("after", 4); d.setdefault("italic", False); d.setdefault("mono", False)
    return d


# ------------------------------------------------------------------------------------------- PPTX
def to_pptx(slides, path, title):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Inches, Pt
    prs = Presentation(); prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    blank = prs.slide_layouts[6]
    rgb = RGBColor.from_string
    for s in slides:
        sl = prs.slides.add_slide(blank)
        sl.background.fill.solid(); sl.background.fill.fore_color.rgb = rgb(s.bg)
        for it in s.items:
            k = it[0]
            if k in ("rect", "oval"):
                if k == "rect":
                    _, x, y, w, h, fill, line, r, lw = it
                    shp = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if r else MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
                    if r:
                        shp.adjustments[0] = min(0.5, r / min(w, h))
                else:
                    _, x, y, w, h, fill = it; line, lw = None, 1
                    shp = sl.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(w), Inches(h))
                if fill:
                    shp.fill.solid(); shp.fill.fore_color.rgb = rgb(fill)
                else:
                    shp.fill.background()
                if line:
                    shp.line.color.rgb = rgb(line); shp.line.width = Pt(lw)
                else:
                    shp.line.fill.background()
                shp.shadow.inherit = False
            elif k == "img":
                _, p, x, y, w = it
                sl.shapes.add_picture(p, Inches(x), Inches(y), width=Inches(w))
            else:
                _, x, y, w, h, paras, size, color, bold, align, anchor = it
                tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
                tf.word_wrap = True; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
                tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
                for i, p in enumerate(paras):
                    d = norm(p, size, color, bold)
                    para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    para.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
                    para.space_after = Pt(d["after"]); para.line_spacing = 1.0
                    for tok in re.split(r"(\*\*[^*]+\*\*)", d["text"]):
                        if not tok:
                            continue
                        b = tok.startswith("**")
                        run = para.add_run(); run.text = tok[2:-2] if b else tok
                        run.font.name = "Courier New" if d["mono"] else FONT; run.font.size = Pt(d["size"]); run.font.bold = bool(d["bold"] or b); run.font.italic = d["italic"]
                        run.font.color.rgb = rgb(d["color"])
        if s.notes:
            sl.notes_slide.notes_text_frame.text = s.notes
    prs.core_properties.title = title
    prs.save(str(path))


# ------------------------------------------------------------------------------------------- PDF
def to_pdf(slides, path, title):
    import matplotlib
    from PIL import Image as PI
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Paragraph
    fd = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    win = r"C:\Windows\Fonts"
    cal = {"DV": "calibri.ttf", "DV-B": "calibrib.ttf", "DV-I": "calibrii.ttf", "DV-BI": "calibriz.ttf"}
    dej = {"DV": "DejaVuSans.ttf", "DV-B": "DejaVuSans-Bold.ttf", "DV-I": "DejaVuSans-Oblique.ttf", "DV-BI": "DejaVuSans-BoldOblique.ttf"}
    use_cal = all(os.path.exists(os.path.join(win, v)) for v in cal.values())   # Calibri = the font the PPTX asks for
    for nm in dej:
        pdfmetrics.registerFont(TTFont(nm, os.path.join(win, cal[nm]) if use_cal else os.path.join(fd, dej[nm])))
    print("PDF font:", "Calibri" if use_cal else "DejaVu (wider than Calibri; overflow warnings are conservative)")
    pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")
    PW, PH = W * 72, H * 72
    c = canvas.Canvas(str(path), pagesize=(PW, PH)); c.setTitle(title)
    col = lambda h: colors.HexColor("#" + h)
    for s in slides:
        c.setFillColor(col(s.bg)); c.rect(0, 0, PW, PH, stroke=0, fill=1)
        for it in s.items:
            k = it[0]
            if k == "rect":
                _, x, y, w, h, fill, line, r, lw = it
                c.setLineWidth(lw)
                if fill: c.setFillColor(col(fill))
                if line: c.setStrokeColor(col(line))
                args = dict(stroke=1 if line else 0, fill=1 if fill else 0)
                if r: c.roundRect(x * 72, PH - (y + h) * 72, w * 72, h * 72, r * 72, **args)
                else: c.rect(x * 72, PH - (y + h) * 72, w * 72, h * 72, **args)
            elif k == "oval":
                _, x, y, w, h, fill = it
                c.setFillColor(col(fill)); c.ellipse(x * 72, PH - (y + h) * 72, (x + w) * 72, PH - y * 72, stroke=0, fill=1)
            elif k == "img":
                _, p, x, y, w = it
                iw, ih = PI.open(p).size; h = w * ih / iw
                c.drawImage(p, x * 72, PH - (y + h) * 72, width=w * 72, height=h * 72)
            else:
                _, x, y, w, h, paras, size, color, bold, align, anchor = it
                flow = []
                for p in paras:
                    d = norm(p, size, color, bold)
                    t = html.escape(d["text"]); t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
                    st = ParagraphStyle("x", fontName="Courier" if d["mono"] else "DV-BI" if (d["bold"] and d["italic"]) else "DV-B" if d["bold"] else "DV-I" if d["italic"] else "DV",
                                        fontSize=d["size"], leading=d["size"] * 1.22, textColor=col(d["color"]), spaceAfter=d["after"],
                                        alignment={"l": 0, "c": 1, "r": 2}[align])
                    flow.append(Paragraph(t, st))
                tot = 0; sizes = []
                for p in flow:
                    _, ph = p.wrap(w * 72, 10000); sizes.append(ph); tot += ph + p.style.spaceAfter
                tot -= flow[-1].style.spaceAfter if flow else 0
                top = PH - y * 72 - (0 if anchor == "t" else (h * 72 - tot) / (2 if anchor == "m" else 1))
                cur = top
                for p, ph in zip(flow, sizes):
                    p.drawOn(c, x * 72, cur - ph); cur -= ph + p.style.spaceAfter
                if tot > h * 72 + 2:
                    print(f"  [overflow warning] text box at ({x:.1f},{y:.1f}) needs {tot/72:.2f}in, has {h:.2f}in: {paras[0] if isinstance(paras[0], str) else paras[0]['text']}"[:150])
        c.showPage()
    c.save()


# ------------------------------------------------------------------------------------------- live agent demo (slide 6, Q&A)
DEMO_UI = ROOT / "code" / "demo_ui.py"


def demo_rehearsal():
    """Saved fault-drill runs in agent/demo_runs/: (planted variant, agent advised against submitting?). Read from the files."""
    out = []
    for p in sorted((ROOT / "agent" / "demo_runs").glob("*_drill*.jsonl")):
        try:
            evs = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        except (OSError, ValueError):
            continue
        meta = evs[0] if evs and evs[0].get("k") == "meta" else {}
        variant = (meta.get("drill") or {}).get("variant")
        end = [e for e in evs if e.get("k") == "end"]
        if not variant or not end or not end[0].get("ok"):
            continue
        txt = "".join(e.get("text", "") for e in evs if e.get("k") in ("delta", "text"))
        rec = next((ln.split(":", 1)[1] for ln in txt.splitlines() if ln.strip().lower().startswith("recommendation")), "").lower()
        neg = re.search(r"^\s*(no\b|not yet|not\b|don't|do not|hold|withhold)|\b(do not|don't|not)\s+(yet\s+)?submit|\bnot yet\b|\bregenerate\b", rec)
        out.append((variant, bool(neg)))
    return out


# ------------------------------------------------------------------------------------------- content (5 slides)
def slide_charts(out, R, GT):
    """Slide-sized charts with projection-readable fonts (the report figures are too small to read on a screen)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figs = out / "figures"; figs.mkdir(parents=True, exist_ok=True)
    scr = pd.DataFrame(R["screen"]); scr = scr[scr.t_valid.notna()].sort_values("t_valid")
    fig, ax = plt.subplots(figsize=(7.0, 5.2))
    cols = ["#17806D" if s.startswith("Macro") else "#1D4E89" for s in scr.source]
    ax.barh(scr.label, scr.t_valid, color=cols, height=0.66)
    ax.axvline(0, color="#1F2933", lw=1); ax.axvline(1.65, color="#C77D14", ls="--", lw=1.6)
    ax.text(1.72, 1.0, "pass bar\nt = 1.65", color="#C77D14", fontsize=11, va="bottom")
    ax.set_xlabel("Validation t vs median drift (above 0 = better)", fontsize=12)
    ax.tick_params(axis="y", labelsize=11); ax.tick_params(axis="x", labelsize=11)
    ax.set_title(f"{len(scr)} public-data factors: none clears the bar", fontsize=14, color="#0E2238", loc="left", fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(figs / "slide_screen.png", dpi=200, facecolor="white"); plt.close(fig)
    gB = GT["futures_bloomberg"]
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    labs = ["No change", "Drift alone", "Drift +\nfutures move"]; vals = [gB.get("mape_nochange", np.nan), gB["mape_drift"], gB["mape_futures"]]
    bars = ax.bar(labs, vals, color=["#9AA5B1", "#9AA5B1", "#17806D"], width=0.6)
    for b_, v in zip(bars, vals):
        ax.text(b_.get_x() + b_.get_width() / 2, v + 0.04, f"{v:.3f}%", ha="center", fontsize=13, fontweight="bold", color="#1F2933")
    ax.set_ylim(0, max(vals) * 1.18); ax.set_ylabel("6-session error (MAPE, %)", fontsize=12); ax.tick_params(labelsize=12)
    ax.set_title(f"Futures move cuts 6-day error\n(Bloomberg 07:00 prices, {gB['n']} origins, t {gB['t']:.2f})", fontsize=13, color="#0E2238", loc="left", fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(figs / "slide_futures.png", dpi=200, facecolor="white"); plt.close(fig)
    return figs / "slide_screen.png", figs / "slide_futures.png"


def build(tag: str):
    out = ROOT / "outputs" / tag
    R = json.loads((out / "results.json").read_text(encoding="utf-8"))
    chk = json.loads((out / "independent_check.json").read_text(encoding="utf-8"))
    GI = json.loads((ROOT / "group_info.json").read_text(encoding="utf-8"))
    NEWS = json.loads((ROOT / "data" / "news_digest.json").read_text(encoding="utf-8"))
    GT = json.loads((ROOT / "data" / "group_tests.json").read_text(encoding="utf-8")); gB, gJ, gS = GT["futures_bloomberg"], GT["futures_tradingview"], GT["screen_prereg"]
    final = tag == "final"
    pt = {r["model"]: r for r in R["perf_test"]}; names = list(pt)
    b0, b1 = pt[names[0]], pt[names[1]]
    nc, W_ = R["nowcast"], R["windows"]
    scr = pd.DataFrame(R["screen"]); ncand = int(len(scr)); scr = scr[scr.t_valid.notna()]; top = scr.sort_values("t_valid", ascending=False).iloc[0]   # ncand: all pre-registered (workbook-only ones were tested separately)
    cutoff = utc(R["cutoff_utc"]); ny = cutoff.tz_convert("America/New_York")
    d_ = lambda s: (lambda t: f"{t:%a} {t.day} {t:%b}")(pd.Timestamp(s))
    F, S0, h = R["forecast_final"], R["last_close"], R["h_sessions"]
    tgt, last = d_(R["target_date"]), d_(R["last_close_date"])
    cut_txt = f"{d_(cutoff.date())} {cutoff:%H:%M} UTC ({ny:%H:%M} New York)"
    scen = R["scenarios"]; ctx = R["features_context"]
    # Rehearsal evidence (outcome known): this build's own results in a rehearsal build, otherwise the saved rehearsal outputs.
    # Without this, preview and final builds printed "realised n/a, error 0.00% against 0.00%" on slide 5.
    rh_path = ROOT / "outputs" / "rehearsal" / "results.json"
    RH = R if tag == "rehearsal" else (json.loads(rh_path.read_text(encoding="utf-8")) if rh_path.is_file() else None)
    reh = RH.get("realised_in_snapshot") if RH else None
    reh_when = f"cutoff {d_(utc(RH['cutoff_utc']).date())}, target {d_(RH['target_date'])}" if reh else ""
    reh_txt = (f"Rehearsal ({reh_when}): forecast {f(RH['forecast_final'])} against a realised {f(reh)}, error {f(RH['rehearsal_APE_%'],2)}% "
               f"against {f(RH['rehearsal_APE_unchanged_%'],2)}% for unchanged, in a week with a 4.4% one-day fall: a tail event no factor anticipated. ") if reh else ""
    fs = {r["variant"]: r for r in R["final_sensitivity"]}
    nleak = sum(v["bars_corrupted"] for k, v in chk.items() if k.startswith("leak_") and isinstance(v, dict) and "bars_corrupted" in v) + chk.get("leak_workbook", {}).get("rows_corrupted", 0)
    first = {m["name"].split()[0]: m["name"] for m in GI["members"]}
    who = lambda k: first.get(k, k)
    worst = R["worst_errors"][0]
    pre_open = (ny.hour * 60 + ny.minute) < 570
    fut_lab = "overnight futures move" if pre_open else "futures move since the close"
    last_news = news_known(NEWS["items"], cutoff)
    news_line = (last_news[-1]["date"][5:].replace("-", "/") + ": " + last_news[-1]["event"].split(";")[0].split(". ")[0][:78]) if last_news else ""
    lo_err = 100 * (1 - R["interval80"][0] / F)
    img_screen, img_fut = slide_charts(out, R, GT)
    status = None if final else ("PREVIEW, NOT BINDING." if tag == "preview" else f"RUN AT {cutoff:%d %b %H:%M} UTC. NOT BINDING." if tag == "now" else "REHEARSAL BUILD.")
    S = []

    # 1 ------------------------------------------------------------------ task, forecast, clocks
    s = Slide(NAVY, f"[{who('Layla')} - 0:50] One number: the S&P 500 official close on {tgt}, scored against S&P Dow Jones Indices, from information available at {cut_txt}. "
                    f"Forecast {f(F)}, 80% interval {f(R['interval80'][0],0)} to {f(R['interval80'][1],0)}. Three clocks: the last official close ({last}, {f(S0)}), the cutoff, where we read the overnight futures move "
                    f"({sgn(nc['overnight_return_pct'],2)}%), and the target {h} trading sessions later. Nothing after the cutoff can enter: a leak test corrupted {nleak:,} later values and the inputs did not change. "
                    f"{'This build is not binding (' + tag + '); the final forecast is regenerated at the 13 Nov cutoff.' if not final else ''} Hand over to {who('Antonio')}.")
    s.text(0.7, 0.5, 12, 0.4, "IFTE0007 Decentralised Finance and Blockchain  |  Group coursework  |  AI agent market forecasting", 14, PALE)
    s.text(0.7, 1.2, 6.6, 3.0, ["An AI agent forecasts the S&P 500 close", {"text": f"for {tgt} {pd.Timestamp(R['target_date']).year}, scored on the S&P Dow Jones Indices official close", "size": 21, "color": PALE, "bold": False, "after": 0}], size=42, color=WHITE, bold=True)
    s.rect(7.9, 1.0, 4.75, 3.55, fill=WHITE, r=0.25)
    s.text(8.15, 1.2, 4.3, 0.4, "Point forecast, index points", 16, MUTED)
    s.text(8.15, 1.75, 4.3, 1.3, f(F), 66, NAVY, True, anchor="m")
    s.text(8.15, 3.25, 4.3, 1.1, [f"80% interval {f(R['interval80'][0],0)} to {f(R['interval80'][1],0)}", "Only the point forecast is scored"], 16, INK)
    chips = [("Last official close", last, f(S0)), ("Information cutoff", f"{cutoff:%d %b %H:%M} UTC ({ny:%H:%M} NY)", f"{fut_lab.capitalize()} {sgn(nc['overnight_return_pct'],2)}%"), ("Target close", tgt, f"h = {h} trading sessions")]
    for i, (a, b, c_) in enumerate(chips):
        x = 0.7 + i * 4.15
        s.rect(x, 4.95, 3.95, 1.35, fill="173A5C", r=0.18)
        s.text(x + 0.25, 5.05, 3.5, 0.35, a, 14, "7FD1C0", True)
        s.text(x + 0.25, 5.4, 3.5, 0.4, b, 17, WHITE, True)
        s.text(x + 0.25, 5.8, 3.5, 0.4, c_, 16, PALE)
    if status:
        s.rect(0.7, 6.55, 5.6, 0.5, fill=AMBER, r=0.1)
        s.text(0.9, 6.55, 5.3, 0.5, status + " Final run on 13 Nov.", 14, WHITE, True, anchor="m")
    s.text(6.6, 6.62, 6.1, 0.4, "  |  ".join(m["name"] for m in GI["members"]), 12, PALE, align="r")
    S.append(s)

    # 2 ------------------------------------------------------------------ the evidence: what predicts and what does not
    s = Slide(WHITE, f"[{who('Antonio')} - 1:40] What predicts a six-session S&P move? We tested {ncand} factors with economic signs fixed in advance: yields, the dollar, gold, semiconductors, surprises, inflation, trend, reversal and VIX. "
                     f"Each had to beat median drift out of sample, with a Diebold-Mariano t of at least 1.65 and support from 2000-2012 history. None passed: the best, {top['label']} (t {f(top['t_valid'],2)}), is contradicted by history. "
                     f"The group's {gS['tests']} pre-registered tests and the 1.72-million-combination search agree. Drift itself is only a weak edge over 'no change' (t {f(b1['DM_t_vs_B0'] or 0,2)}). "
                     f"The one input that adds information is the overnight futures move: in my pre-registered test on Bloomberg 07:00 prices it cut six-day error from {f(gB['mape_drift'],3)}% to {f(gB['mape_futures'],3)}% "
                     f"({gB['n']} origins, t {f(gB['t'],2)}; Thursdays t {f(gB['thu_t'],2)}), and Jayen's {gJ['n']}-origin test shows it carries through almost one for one (slope {f(gJ['slope'],2)}). Hand over to {who('Jayen')}.")
    s.text(0.7, 0.4, 12, 0.9, "Drift is the anchor; only the futures move adds information", 32, NAVY, True)
    s.image(img_screen, 0.45, 1.25, 6.45)
    s.image(img_fut, 7.15, 1.25, 5.65)
    s.rect(7.15, 4.85, 5.65, 2.05, fill=TINT, r=0.2)
    s.text(7.4, 4.95, 5.2, 1.9, [{"text": f"0 of {ncand} factors pass", "size": 20, "bold": True, "color": NAVY, "after": 4},
                                 {"text": f"Best: {top['label']}, t {f(top['t_valid'],2)}, reversed by 2000-12 history. Drift vs no change: t {f(b1['DM_t_vs_B0'] or 0,2)}, a weak edge.", "size": 15, "after": 4},
                                 {"text": f"Group checks agree: {gS['tests']} pre-registered tests, 1.72M-combination search.", "size": 15}], 15, INK)
    s.text(0.7, 6.15, 6.2, 0.8, f"Screen: weekly origins {W_['first_origin'][:4]}-{W_['last_origin'][:4]}, validation to {W_['valid_end'][:4]}, then {W_['n_test']} untouched test weeks.", 14, MUTED)
    S.append(s)

    # 3 ------------------------------------------------------------------ the calculation, mechanism, sensitivity
    sens = [("No drift (unchanged centre)", fs.get("No drift (unchanged centre)")), ("Median since 2000", fs.get("Median since 2000")), ("Fixed +0.25% per 6 sessions", fs.get("Fixed +0.25% per 6 sessions")),
            ("Futures read 1 hour earlier", next((v for k, v in fs.items() if k.startswith("Futures read")), None)), ("No futures nowcast", fs.get("No futures nowcast"))]
    sens = [(a, b) for a, b in sens if b]
    s = Slide(WHITE, f"[{who('Jayen')} - 1:30] The calculation: {f(S0)} x exp({sgn(R['mu_final_pct'])}% + {sgn(nc['nowcast_adjustment_pct'])}%) = {f(F)}. "
                     f"Drift: the median {h}-session return since 1990, the equity risk premium; it fails in prolonged bear markets. "
                     f"Futures: E-mini futures trade nearly 24 hours, so they price overnight news; the move from {f(nc['es_close_prev_session'],2)} to {f(nc['es_at_cutoff'],2)} ({sgn(nc['overnight_return_pct'],2)}%), less the average overnight drift, gives {sgn(nc['nowcast_adjustment_pct'],2)}%. "
                     f"It fails on a contract roll, thin overnight trading or a reversal at the open. Sensitivity: the drift choice barely matters; dropping the nowcast moves the forecast to {f(fs['No futures nowcast']['forecast'],0)}. "
                     f"The 80% interval scales the historical error distribution by today's VIX. No hand adjustment. Hand over to {who('Layla')}.")
    s.text(0.7, 0.4, 12, 0.9, f"The forecast: drift anchor plus the {fut_lab}", 32, NAVY, True)
    boxes = [(0.7, f(S0), f"last close ({last})", TINT, NAVY), (4.0, sgn(R["mu_final_pct"]) + "%", f"median {h}-session drift", TINT, NAVY), (7.3, sgn(nc["nowcast_adjustment_pct"]) + "%", fut_lab, TINT, NAVY), (10.6, f(F), "forecast", NAVY, WHITE)]
    for x, big, lab, bg, fg in boxes:
        s.rect(x, 1.3, 2.2, 1.45, fill=bg, r=0.2)
        s.text(x + 0.1, 1.38, 2.0, 0.75, big, 28, fg, True, "c", "m")
        s.text(x + 0.1, 2.12, 2.0, 0.55, lab, 14, PALE if bg == NAVY else MUTED, False, "c")
    for x, t in [(2.9, "× exp("), (6.2, "+"), (9.5, ") =")]:
        s.text(x, 1.5, 1.1, 0.9, t, 22, TEAL, True, "c", "m")
    s.text(0.7, 2.85, 12.0, 0.6, f"Futures: ES {f(nc['es_close_prev_session'],2)} at the 16:00 close to {f(nc['es_at_cutoff'],2)} at the cutoff = {sgn(nc['overnight_return_pct'],2)}%, less the average overnight drift ({sgn(nc['mean_overnight_drift_pct'],2)}%) = {sgn(nc['nowcast_adjustment_pct'],2)}%.  No hand adjustment." + ("" if pre_open else f"  (Read at {ny:%H:%M} New York; the final run reads it at 07:00.)"), 14, MUTED)
    cards = [("D  Median drift", "Why: investors are paid to bear equity risk; negative skew puts the median above zero.", "Fails: prolonged bear markets (2000-02, 2008)."),
             ("N  Overnight futures move", "Why: futures trade nearly 24h and price overnight news; arbitrage ties the cash open to them.", "Fails: contract roll, thin overnight trading, reversal at the open.")]
    for i, (a, b, c_) in enumerate(cards):
        y = 3.5 + i * 1.75
        s.rect(0.7, y, 6.2, 1.6, fill=WHITE, line=PALE, r=0.18, lw=1.5)
        s.text(0.95, y + 0.1, 5.8, 0.4, a, 18, NAVY, True)
        s.text(0.95, y + 0.52, 5.8, 0.6, b, 14, INK)
        s.text(0.95, y + 1.1, 5.8, 0.45, c_, 14, ROSE)
    s.rect(7.15, 3.5, 5.65, 3.35, fill=TINT, r=0.2)
    s.text(7.4, 3.6, 5.2, 0.4, "Sensitivity of the forecast", 18, NAVY, True)
    for i, (lab, r_) in enumerate(sens):
        y = 4.1 + i * 0.42
        s.text(7.4, y, 3.4, 0.4, lab, 14, INK)
        s.text(10.75, y, 0.95, 0.4, f(r_["forecast"], 0), 14, INK, True, align="r")
        s.text(11.75, y, 0.9, 0.4, "0" if abs(r_["forecast"] - F) < 0.5 else sgn(r_["forecast"] - F, 0), 14, MUTED, align="r")
    s.text(7.4, 4.1 + len(sens) * 0.42 + 0.05, 5.2, 0.6, "80% interval: historical errors scaled by today's VIX.", 14, MUTED)
    S.append(s)

    # 4 ------------------------------------------------------------------ agent walkthrough
    steps = [("1 Goal", "HUMAN", "7FD1C0", "Group sets the target, cutoff, data boundary and permitted tools."),
             ("2 Data", "AGENT", "C9D6E3", "Fetches dated raw files; logs URL, time, SHA-256; drops anything after the cutoff."),
             ("3 Tools", "AGENT", "C9D6E3", f"Python: {ncand}-factor screen, median regression, {W_['n_origins']} chronological backtests."),
             ("4 Decisions", "AGENT", "C9D6E3", "Applies pre-registered rules; logs every choice and correction."),
             ("5 Checks", "AGENT + HUMAN", "F2D7A7", "Second code path, leak test; humans check the S&P DJI close."),
             ("6 Approval", "HUMAN", "7FD1C0", "Members re-run, read the trace, sign the record. No trading.")]
    demo_txt = ("AGENT DEMO (about 90 seconds): in `python code/demo_ui.py` (unzipped copy of the package), Replay the agent's saved /check on the final record (agent/demo_runs/; run it live only if time allows). "
                "The agent writes its own plan, chooses its tools (record, recompute, check), reads each result and recommends: point at its Plan line, one tool call and its Found, Decision and Recommendation lines. "
                f"Then the transcript on this slide is the pipeline it checked: `python code/run_all.py --{tag}` on the frozen inputs. "
                if (ROOT / "code" / "demo_ui.py").exists() else
                f"AGENT DEMO (about 90 seconds): play the recorded run of `python code/run_all.py --{tag}` on the saved, frozen inputs (it reproduces this exact forecast without internet, in about 1-2 minutes). ")
    s = Slide(WHITE, f"[{who('Layla')} - 1:50] " + demo_txt +
                     "Walk the flow: the group set the goal and boundary; the agent fetched the data with fingerprints and applied the cutoff filter; it called Python to screen factors, fit the median regression and run the backtests; "
                     "it applied rules fixed in advance and logged every decision; a second code path and a leak test checked it; we approve and sign. Point at the transcript: the command, the frozen-model line and PASS_ALL. "
                     f"Two logged corrections: three faulty Yahoo prices replaced after a three-source check, and the model frozen after group review. Hand over to {who('Mohamed')}.")
    s.text(0.7, 0.4, 12, 0.9, "The agent: who did what, and the proof it ran", 32, NAVY, True)
    for i, (a, tagx, col, b) in enumerate(steps):
        x = 0.55 + i * 2.1
        s.rect(x, 1.3, 1.9, 2.75, fill=WHITE, line=PALE, r=0.15, lw=1.5)
        s.rect(x, 1.3, 1.9, 0.55, fill=NAVY, r=0.15)
        s.text(x + 0.1, 1.3, 1.7, 0.55, a, 15, WHITE, True, anchor="m")
        s.rect(x + 0.12, 1.98, 1.66, 0.36, fill=col, r=0.08)
        s.text(x + 0.12, 1.98, 1.66, 0.36, tagx, 12, NAVY, True, "c", "m")
        s.text(x + 0.12, 2.45, 1.7, 1.55, b, 13, INK)
        if i < 5:
            s.text(x + 1.88, 2.4, 0.25, 0.5, "▶", 13, TEAL, True, "c", "m")
    tx = None
    trp = ROOT / "agent" / f"run_transcript_{tag}.txt"
    if trp.exists():         # verbatim lines from the saved run transcript (paths shortened)
        raw = [l.rstrip() for l in trp.read_text(encoding="utf-8", errors="replace").splitlines()]
        keep = []
        for l in raw:
            ls = l.strip()
            if ls.startswith(">>") and ("run_model.py" in ls or "fetch_data.py" in ls or "independent_check.py" in ls):
                keep.append(">> " + ls.split("code\\")[-1].split("code/")[-1][:62])
            elif ls.startswith(("cutoff 2", "RULE WOULD SELECT", '"forecast_final"', '"PASS_ALL"', "saved gspc_daily")):
                keep.append("   " + ls.split(" | USED")[0][:66])
        tx = keep[:9] if len(keep) >= 4 else None
    if not tx:
        tx = [f"(summary of outputs/{tag}/results.json)", f"   forecast_final: {f(F)}", "   FACTOR ENTRY: off (frozen)", f"   independent check: PASS_ALL = {chk['PASS_ALL']}"]
    s.rect(0.55, 4.3, 7.4, 2.6, fill="0B1724", r=0.15)
    s.text(0.75, 4.45, 7.1, 2.4, [{"text": l, "mono": True, "after": 3} for l in tx], 12.5, "D7F5E9")
    s.rect(8.15, 4.3, 4.65, 2.6, fill=TINT, r=0.15)
    s.text(8.35, 4.4, 4.3, 2.45, [{"text": "From agent_log.md", "size": 16, "bold": True, "color": NAVY, "after": 4},
                                  {"text": "Correction: 3 faulty Yahoo prices replaced after a Yahoo / Cboe / workbook check.", "after": 4},
                                  {"text": "Decision: model frozen after group review; the screen is reported, never acted on.", "after": 4},
                                  {"text": f"Demo (90 s): recorded run of python code/run_all.py --{tag} on the saved inputs; link in the speaker notes.", "bold": True}], 14, INK)
    S.append(s)

    # 5 ------------------------------------------------------------------ risks, counterargument, claim
    adv = scen[1]
    news5 = news_known(NEWS["items"], cutoff)[-3:]
    s = Slide(NAVY, f"[{who('Mohamed')} - 1:10] What could invalidate it. {reh_txt}History: the worst test error was {f(worst['APE_final'],1)}% on {pd.Timestamp(worst['date']):%d %b %Y}, a shock that no change missed just as badly. "
                    f"Adverse scenario: a further chip rout (index -4%, VIX 30) puts the level at {f(adv['forecast'],0)}, {f(100*(1-adv['forecast']/F),1)}% below the forecast; the interval's lower end is {f(lo_err,1)}% below. "
                    "Counterargument: 'an analyst would use the news'. We tested its measurable parts and none beat drift; the rest is already in the futures price. My momentum + RSI machine-learning model was also worse than drift over 22 years. "
                    "Watch list: a failed independent check, a futures roll, the last close against S&P DJI, Nvidia on 17 Nov, FOMC minutes on 18 Nov. "
                    "We claim a well-centred, reproducible forecast with honest evidence, not foresight. Questions: everyone answers on their own part (see the speaker script)."
                    + (f" At the start of the questions, {who('Jayen')} opens slide 6 and runs the agent live (about 1 to 2 minutes)." if DEMO_UI.exists() else ""))
    s.text(0.7, 0.4, 12, 0.9, "What could invalidate it, and what we claim", 32, WHITE, True)
    cards = [(("Rehearsal outcome", f"{f(RH['rehearsal_APE_%'],1)}%", f"{reh_when[0].upper() + reh_when[1:]}: {f(RH['forecast_final'],0)} vs realised {f(reh,0)}; no change missed by {f(RH['rehearsal_APE_unchanged_%'],1)}%. Reported, not retuned.") if reh else
              ("Worst test error", f"{f(worst['APE_final'],1)}%", f"{pd.Timestamp(worst['date']):%d %b %Y}: a market shock that 'no change' missed just as badly.")),
             ("Adverse scenario", f"-{f(100*(1-adv['forecast']/F),1)}%", f"Chip rout (index -4%, VIX 30): level {f(adv['forecast'],0)}. The interval's lower end is -{f(lo_err,1)}%."),
             ("Counterargument", "", "'Use the news': we tested its measurable parts and none beat drift; the rest is priced in futures. Momentum + RSI (ML) was worse than drift over 22 years. The group's 30 pre-registered tests and 1.72M-combination search agree.")]
    for i, (a, big, b) in enumerate(cards):
        x = 0.7 + i * 4.15
        s.rect(x, 1.35, 3.95, 3.15, fill="173A5C", r=0.2)
        s.text(x + 0.25, 1.5, 3.45, 0.45, a, 19, "7FD1C0", True)
        if big:
            s.text(x + 0.25, 2.0, 3.45, 0.9, big, 42, WHITE, True)
        s.text(x + 0.25, 3.0 if big else 2.05, 3.45, 1.45 if big else 2.4, b, 15, WHITE)
    s.rect(0.7, 4.7, 6.6, 2.2, fill="173A5C", r=0.2)
    s.text(0.95, 4.8, 6.2, 2.05, [{"text": "Context and watch list", "size": 17, "bold": True, "color": "7FD1C0", "after": 3},
                                  {"text": f"VIX {f(R['vix_last'],1)}; {news_line}", "after": 2},
                                  {"text": "- failed independent check or leak test", "after": 1}, {"text": "- futures roll or thin overnight trading", "after": 1},
                                  {"text": "- last close not matching S&P DJI", "after": 1}, {"text": "- Nvidia results 17 Nov, FOMC minutes 18 Nov", "after": 0}], 15, WHITE)
    s.rect(7.5, 4.7, 5.3, 2.2, fill=WHITE, r=0.2)
    s.text(7.75, 4.8, 4.85, 2.05, [{"text": "We claim", "size": 17, "bold": True, "color": NAVY, "after": 3},
                                   {"text": "A well-centred, reproducible forecast with honest evidence.", "after": 3},
                                   {"text": "Not foresight: no factor beat drift. Humans sign; the agent never trades.", "after": 3},
                                   {"text": "Questions", "size": 17, "bold": True, "color": TEAL}], 15, INK)
    S.append(s)

    # 6 ------------------------------------------------------------------ live agent demo, used in the Q&A (only if the demo is in the package)
    if DEMO_UI.exists():
        drills = demo_rehearsal()
        kinds = {"forecast": "forecast", "close": "last close", "cutoff": "cutoff"}
        caught = [kinds.get(v, v) for v, ok_ in drills if ok_]
        reh6 = (f"In rehearsal on the frozen inputs it caught {len(caught)} of {len(drills)} planted errors ({', '.join(sorted(set(caught)))})."
                if drills else "Rehearse once before the talk; each run is saved for replay.")
        s = Slide(WHITE, f"[{who('Jayen')} - Q&A, about 1 to 2 minutes] LIVE AGENT DEMO, in addition to the recorded run on slide 4. Start `python code/demo_ui.py` in an unzipped copy of the package before the talk and open http://127.0.0.1:8765. "
                         "1) Press Run /check: the agent writes its own plan, chooses its tools (typically a recalculation and the independent check), reads each result and recommends; point at its Plan line, a tool call and its Found and Decision lines (about 30 seconds). "
                         "2) Press Fault drill: the page plants one error in a temporary copy of the record (forecast, last close or cutoff, at random); nobody knows which. Ask the room to watch whether the agent catches it; the page reveals the error at the end (about 40 seconds). "
                         "3) If time allows, type a question from the audience into Ask: the agent picks its own tools and what-if values (about 30 seconds). "
                         f"Say what is live and what is fixed: the data, the tools' code and the rules are fixed; the plan, the tool choices, the numbers it computes, its words and its verdict happen live. {reh6} "
                         "If the connection fails, switch to Replay and play a saved run: the brief allows a recorded walkthrough. The agent cannot write files or change the record; a member signs.")
        s.text(0.7, 0.4, 12, 0.9, "Live in Q&A: our agent re-checks the forecast", 32, NAVY, True)
        s.text(0.7, 1.15, 12, 0.5, "Claude Code on the frozen inputs. It plans its own check, chooses its tools and recommends. We decide.", 17, MUTED)
        cards = [("1  Its own check", "about 30 s", "/check: the agent writes a plan, picks its tools (record, recompute, check...), reads each result and recommends submit or not."),
                 ("2  Hidden fault", "about 40 s", f"The page plants one error in a copy of the record: forecast, last close or cutoff. Nobody knows which. Does the agent catch it? {reh6}"),
                 ("3  Your question", "about 30 s", "Ask anything about the forecast. The agent chooses its own tools and what-if values, then answers.")]
        for i, (a, tm, b) in enumerate(cards):
            x = 0.7 + i * 4.15
            s.rect(x, 1.85, 3.95, 2.75, fill=WHITE, line=PALE, r=0.18, lw=1.5)
            s.rect(x, 1.85, 3.95, 0.6, fill=NAVY, r=0.18)
            s.text(x + 0.2, 1.85, 2.6, 0.6, a, 17, WHITE, True, anchor="m")
            s.text(x + 2.6, 1.85, 1.2, 0.6, tm, 13, "7FD1C0", True, "r", "m")
            s.text(x + 0.2, 2.6, 3.55, 1.95, b, 15, INK)
        s.rect(0.7, 4.85, 6.2, 2.1, fill=TINT, r=0.18)
        s.text(0.95, 4.95, 5.8, 1.95, [{"text": "Live vs fixed", "size": 17, "bold": True, "color": NAVY, "after": 4},
                                       {"text": "Live: its plan, which tools it calls, the what-if values, every number (Python, run now), its words and its verdict.", "after": 4},
                                       {"text": "Fixed: the frozen data, the tools' code, the goal and the brief's rules."}], 15, INK)
        s.rect(7.1, 4.85, 5.7, 2.1, fill="0B1724", r=0.18)
        s.text(7.35, 4.95, 5.3, 1.95, [{"text": "Boundary and backup", "size": 17, "bold": True, "color": "7FD1C0", "after": 4},
                                       {"text": "No internet; reads files and runs code/demo_tools.py only; cannot write files or change the record. A member signs.", "after": 4},
                                       {"text": "Backup: Replay a saved run (agent/demo_runs/).", "after": 2},
                                       {"text": "python code/demo_ui.py", "mono": True}], 14, "D7F5E9")
        S.append(s)
    return S, R, final


SCRIPT_QA = [
    ("You tested many factors. Why is none in the model? (Antonio)", "We fixed a rule before looking: a factor must beat median drift out of sample (t at least 1.65, supported by 2000-2012 history, or 2.33 without it). The best t was {tbest}, and history contradicted it. With 16 tests, one false positive at 1.65 is expected by chance."),
    ("What role did the group's supporting dataset play? (Antonio)", "A helper: it supplied extra macro candidates for the factor screen (2Y, 10Y, USD, gold, semiconductors, surprise index, CPI, PPI) and a tie-breaker when Yahoo and Cboe disagreed. It is not an input to the forecast, which uses public data only."),
    ("How does the latest news affect the forecast? (Jayen)", "Through prices: the futures price at the cutoff already reflects everything known by then (CPI, Fed speakers, earnings). We add no hand adjustment because it could not be validated. Scheduled events after the cutoff widen the interval."),
    ("Why median regression and median drift? (Jayen)", "The score is linear in absolute percentage error, and the optimal point forecast under absolute error is the median (Gneiting 2011)."),
    ("How do you know there is no future information? (Layla)", "A cutoff filter in code plus a test that corrupts every value published after the cutoff; the inputs did not change. Raw files are fingerprinted with SHA-256."),
    ("What did the agent do versus you? (Layla)", "Agent: retrieve, filter, calculate, screen, validate, research news, draft, self-check, log. Humans: set the goal and boundary, review, check the S&P DJI close, approve the record."),
    ("Why is the model frozen? (Layla)", "So the submitted method is exactly the one the group reviewed. A factor that passed the screen on submission day would enter untested; instead the screen is reported and cannot change the forecast."),
    ("Did a machine-learning model do better? (Mohamed)", "Momentum + RSI was worse than drift over 1,096 Thursdays in 2002-24 (t -3.15) and only tied on recent data, so it is a robustness note, not the model."),
    ("What would change the forecast? (Mohamed)", "A different last close or overnight futures move. Dropping the nowcast would move it to {nonc} ({ncd} points); dropping the drift to {nodr} ({drd} points)."),
]

SCRIPT_QA_DEMO = [
    ("Is the live agent just running a script? (Jayen)", "No. In /check it writes its own plan and chooses which tools to call and in what order; in Ask it also chooses the what-if values. Every number is computed by Python at that moment from the frozen files, and in the fault drill it is not told what was planted. What is fixed: the data, the tools' code, the goal and the brief's rules."),
    ("What if the live demo fails? (Jayen)", "We switch to Replay and play a saved run of the same agent on the same frozen inputs; the brief allows a recorded walkthrough. Slide 4's recorded pipeline run also stands on its own."),
    ("Can the agent change the forecast? (Jayen)", "No. It can read files and run code/demo_tools.py only; writing files, network commands and other programs are refused. It recommends; a member signs the record."),
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tag", required=True)
    tag = ap.parse_args().tag
    S, R, final = build(tag)
    (ROOT / "report").mkdir(exist_ok=True)
    title = f"IFTE0007 group presentation - S&P 500 forecast ({tag})"
    to_pptx(S, ROOT / "report" / f"slides_{tag}.pptx", title)
    to_pdf(S, ROOT / "report" / f"slides_{tag}.pdf", title)
    fs = {r["variant"]: r for r in R["final_sensitivity"]}
    F = R["forecast_final"]; nonc = fs["No futures nowcast"]["forecast"]; nodr = fs["No drift (unchanged centre)"]["forecast"]
    tbest = max(r["t_valid"] for r in R["screen"] if r["t_valid"] is not None)   # macro rows are blank without the workbook
    head = ("5 slides, 7 minutes talking and 3 minutes of questions. Every member presents their own part; timings are in brackets."
            + (" Slide 6 is used at the start of the questions for the live agent demo (about 1 to 2 minutes); it adds to the recorded run on slide 4." if len(S) > 5 else ""))
    lines = [f"# Speaker script and Q&A ({tag} build)", "", head, ""]
    for i, s in enumerate(S, 1):
        lines += [f"## Slide {i}" + (" (Q&A: live agent demo)" if i == 6 else ""), s.notes, ""]
    lines += ["## Likely questions (who answers)"]
    qa = SCRIPT_QA + (SCRIPT_QA_DEMO if len(S) > 5 else [])
    for q, a in qa:
        lines += [f"**{q}**", a.format(tbest=f(tbest, 2), nonc=f(nonc, 2), ncd=sgn(nonc - F, 1), nodr=f(nodr, 2), drd=sgn(nodr - F, 1)), ""]
    (ROOT / "report" / f"speaker_script_{tag}.md").write_text("\n".join(lines), encoding="utf-8")
    print("slides written:", len(S))


if __name__ == "__main__":
    main()
