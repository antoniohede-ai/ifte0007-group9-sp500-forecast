"""render.py - renders one block list to both .docx (python-docx) and .pdf (reportlab); counts words of 'main' blocks.

Block tuples (all text supports **bold** and *italic*):
  ("h1", text, main) ("h2", text, main) ("p", text, main) ("bullets", [text...], main)
  ("table", header[list], rows[list[list]], col_widths_cm, caption, main, {"font": 8})   ("fig", path, width_cm, caption, main)
  ("cover", dict) ("banner", text) ("pagebreak",) ("note", text, main)
"""
from __future__ import annotations

import html
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

INK = "1f2933"
ACCENT = "1d4e89"
GREY = "6b7280"
BAND = "e8eef6"
WARN = "fff4e0"


def words(text: str) -> int:
    return len(re.findall(r"\S+", re.sub(r"[*`]+", "", text)))


def count_main(blocks) -> int:
    n = 0
    for b in blocks:
        k = b[0]
        if k in ("h1", "h2", "p", "note") and b[2]:
            n += words(b[1])
        elif k == "bullets" and b[2]:
            n += sum(words(t) for t in b[1])
        elif k == "table" and b[5]:
            n += sum(words(c) for c in b[1]) + sum(words(str(c)) for r in b[2] for c in r) + words(b[4])
        elif k == "fig" and b[4]:
            n += words(b[3])
    return n


# ------------------------------------------------------------------------------------------------ DOCX
def _runs(par, text, size=None, color=None, bold_all=False):
    text = text.replace("`", "")
    for tok in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", text):
        if not tok:
            continue
        b = i = False
        if tok.startswith("**"):
            tok, b = tok[2:-2], True
        elif tok.startswith("*"):
            tok, i = tok[1:-1], True
        r = par.add_run(tok)
        r.bold, r.italic = b or bold_all, i
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor.from_string(color)


def _shade(cell, hex_):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_)
    tcPr.append(shd)


def _cell_margins(table, top=40, bottom=40, left=70, right=70):
    tblPr = table._tbl.tblPr
    m = OxmlElement("w:tblCellMar")
    for k, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        e = OxmlElement(f"w:{k}"); e.set(qn("w:w"), str(v)); e.set(qn("w:type"), "dxa"); m.append(e)
    tblPr.append(m)


def _borders(table, color="c7ced6"):
    tblPr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for k in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{k}"); e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:color"), color); b.append(e)
    tblPr.append(b)


def to_docx(blocks, path, title):
    d = Document()
    sec = d.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.0); sec.top_margin = Cm(1.9); sec.bottom_margin = Cm(1.9)
    st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    st.paragraph_format.space_after = Pt(5); st.paragraph_format.line_spacing = 1.08
    for lvl, sz in (("Heading 1", 14.5), ("Heading 2", 11.5)):
        s = d.styles[lvl]; s.font.name = "Calibri"; s.font.size = Pt(sz); s.font.bold = True
        s.font.color.rgb = RGBColor.from_string(ACCENT); s.paragraph_format.space_before = Pt(12 if lvl == "Heading 1" else 8)
        s.paragraph_format.space_after = Pt(4); s.paragraph_format.keep_with_next = True
    # footer page number
    fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run(f"{title}  |  page "); r.font.size = Pt(8); r.font.color.rgb = RGBColor.from_string(GREY)
    for t, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        run = fp.add_run(); run.font.size = Pt(8)
        if t:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), t); run._r.append(e)
        else:
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt; run._r.append(e)

    for b in blocks:
        k = b[0]
        if k == "cover":
            c = b[1]
            p = d.add_paragraph(); _runs(p, c["kicker"], 9.5, GREY)
            p = d.add_paragraph(); p.paragraph_format.space_after = Pt(2); _runs(p, c["title"], 22, ACCENT, True)
            p = d.add_paragraph(); _runs(p, c["subtitle"], 11.5, INK)
            t = d.add_table(rows=len(c["group"]), cols=2); t.alignment = WD_TABLE_ALIGNMENT.LEFT; _borders(t); _cell_margins(t)
            for i, (a_, b_) in enumerate(c["group"]):
                t.cell(i, 0).width, t.cell(i, 1).width = Cm(4.2), Cm(12.8)
                _runs(t.cell(i, 0).paragraphs[0], a_, 9.5, INK, True); _shade(t.cell(i, 0), BAND)
                _runs(t.cell(i, 1).paragraphs[0], b_, 9.5)
            d.add_paragraph()
            p = d.add_paragraph(); _runs(p, c.get("label", "BINDING FINAL POINT FORECAST"), 9, GREY, True); p.paragraph_format.space_after = Pt(0)
            p = d.add_paragraph(); _runs(p, c["forecast"], 30, ACCENT, True); p.paragraph_format.space_after = Pt(2)
            p = d.add_paragraph(); _runs(p, c["unit_line"], 10.5, INK)
            t = d.add_table(rows=len(c["record"]), cols=2); _borders(t); _cell_margins(t)
            for i, (a_, b_) in enumerate(c["record"]):
                t.cell(i, 0).width, t.cell(i, 1).width = Cm(4.2), Cm(12.8)
                _runs(t.cell(i, 0).paragraphs[0], a_, 9.5, INK, True); _shade(t.cell(i, 0), BAND)
                _runs(t.cell(i, 1).paragraphs[0], b_, 9.5)
        elif k == "banner":
            t = d.add_table(rows=1, cols=1); _borders(t, "e0a64a"); _cell_margins(t, 90, 90, 140, 140)
            _shade(t.cell(0, 0), WARN); t.cell(0, 0).width = Cm(17)
            _runs(t.cell(0, 0).paragraphs[0], b[1], 9.5)
            d.add_paragraph()
        elif k in ("h1", "h2"):
            d.add_heading(b[1], level=1 if k == "h1" else 2)
        elif k == "p":
            _runs(d.add_paragraph(), b[1])
        elif k == "note":
            _runs(d.add_paragraph(), b[1], 9, GREY)
        elif k == "bullets":
            for t_ in b[1]:
                p = d.add_paragraph(style="List Bullet"); p.paragraph_format.space_after = Pt(2); _runs(p, t_)
        elif k == "table":
            _, header, rows, widths, cap, main, *opt = b
            fs = (opt[0] if opt else {}).get("font", 8.5)
            if cap:
                p = d.add_paragraph(); p.paragraph_format.keep_with_next = True; p.paragraph_format.space_after = Pt(2)
                _runs(p, cap, 9, INK, True)
            t = d.add_table(rows=1 + len(rows), cols=len(header)); t.alignment = WD_TABLE_ALIGNMENT.CENTER; _borders(t); _cell_margins(t)
            for j, h_ in enumerate(header):
                c_ = t.cell(0, j); c_.width = Cm(widths[j]); _shade(c_, ACCENT)
                _runs(c_.paragraphs[0], h_, fs, "ffffff", True); c_.paragraphs[0].paragraph_format.space_after = Pt(0)
            for i, r_ in enumerate(rows):
                for j, v in enumerate(r_):
                    c_ = t.cell(i + 1, j); c_.width = Cm(widths[j])
                    _runs(c_.paragraphs[0], str(v), fs); c_.paragraphs[0].paragraph_format.space_after = Pt(0)
                    if i % 2 == 1:
                        _shade(c_, "f6f8fb")
            d.add_paragraph().paragraph_format.space_after = Pt(2)
        elif k == "fig":
            _, path_, wcm, cap, main = b
            p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.keep_with_next = True
            p.add_run().add_picture(str(path_), width=Cm(wcm))
            p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; _runs(p, cap, 8.5, GREY)
        elif k == "pagebreak":
            d.add_page_break()
    d.core_properties.title = title
    d.save(str(path))


# ------------------------------------------------------------------------------------------------ PDF
def to_pdf(blocks, path, title):
    import matplotlib
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle, ListFlowable, ListItem)
    import os
    fd = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
    for nm, fn in (("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"), ("DV-I", "DejaVuSans-Oblique.ttf"), ("DV-BI", "DejaVuSans-BoldOblique.ttf")):
        pdfmetrics.registerFont(TTFont(nm, os.path.join(fd, fn)))
    pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")
    ink, acc, grey = colors.HexColor("#" + INK), colors.HexColor("#" + ACCENT), colors.HexColor("#" + GREY)

    def S(name, **kw):
        base = dict(fontName="DV", fontSize=8.6, leading=12.2, textColor=ink, spaceAfter=4)
        base.update(kw)
        return ParagraphStyle(name, **base)
    sty = {"p": S("p"), "h1": S("h1", fontName="DV-B", fontSize=12.6, leading=15.5, textColor=acc, spaceBefore=10, spaceAfter=4, keepWithNext=1),
           "h2": S("h2", fontName="DV-B", fontSize=10, leading=13, textColor=acc, spaceBefore=6, spaceAfter=3, keepWithNext=1),
           "note": S("note", fontSize=7.6, textColor=grey), "cap": S("cap", fontSize=7.6, textColor=grey, alignment=TA_CENTER),
           "tcap": S("tcap", fontName="DV-B", fontSize=7.8, spaceAfter=2, keepWithNext=1),
           "cell": S("cell", fontSize=7.3, leading=9.4, spaceAfter=0), "hcell": S("hcell", fontName="DV-B", fontSize=7.3, leading=9.4, textColor=colors.white, spaceAfter=0)}

    def mk(text):
        t = html.escape(text.replace("`", ""))
        t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", t)
        return t

    story = []
    for b in blocks:
        k = b[0]
        if k == "cover":
            c = b[1]
            story += [Paragraph(mk(c["kicker"]), S("k", fontSize=8, textColor=grey)),
                      Paragraph(mk(c["title"]), S("t", fontName="DV-B", fontSize=19, leading=23, textColor=acc, spaceAfter=3)),
                      Paragraph(mk(c["subtitle"]), S("st", fontSize=10, leading=13.5, spaceAfter=8))]
            for rows in (c["group"], None):
                if rows is None:
                    story += [Spacer(1, 8), Paragraph(c.get("label", "BINDING FINAL POINT FORECAST"), S("bf", fontName="DV-B", fontSize=7.6, textColor=grey, spaceAfter=0)),
                              Paragraph(mk(c["forecast"]), S("fc", fontName="DV-B", fontSize=27, leading=32, textColor=acc, spaceAfter=1)),
                              Paragraph(mk(c["unit_line"]), S("ul", fontSize=9, spaceAfter=5))]
                    rows = c["record"]
                tb = Table([[Paragraph(mk(a_), S("kb", fontName="DV-B", fontSize=7.8, leading=10, spaceAfter=0)), Paragraph(mk(b_), S("kv", fontSize=7.8, leading=10, spaceAfter=0))] for a_, b_ in rows],
                           colWidths=[4.2 * cm, 12.8 * cm])
                tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c7ced6")), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#" + BAND)),
                                        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
                story.append(tb)
        elif k == "banner":
            tb = Table([[Paragraph(mk(b[1]), S("bn", fontSize=8, leading=11, spaceAfter=0))]], colWidths=[17 * cm])
            tb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#e0a64a")), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#" + WARN)),
                                    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
            story += [Spacer(1, 6), tb, Spacer(1, 6)]
        elif k in ("h1", "h2", "p", "note"):
            story.append(Paragraph(mk(b[1]), sty[k]))
        elif k == "bullets":
            story.append(ListFlowable([ListItem(Paragraph(mk(t_), S("li", spaceAfter=1)), leftIndent=10) for t_ in b[1]], bulletType="bullet", start="•", leftIndent=12, bulletFontSize=7))
        elif k == "table":
            _, header, rows, widths, cap, main, *opt = b
            fs = (opt[0] if opt else {}).get("font", 8.5)
            data = [[Paragraph(mk(h_), sty["hcell"]) for h_ in header]] + [[Paragraph(mk(str(v)), sty["cell"]) for v in r_] for r_ in rows]
            tb = Table(data, colWidths=[w * cm for w in widths], repeatRows=1)
            ts = [("BACKGROUND", (0, 0), (-1, 0), acc), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c7ced6")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                  ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]
            for i in range(2, len(data), 2):
                ts.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f6f8fb")))
            tb.setStyle(TableStyle(ts))
            story.append(KeepTogether(([Paragraph(mk(cap), sty["tcap"])] if cap else []) + [tb, Spacer(1, 5)]))
        elif k == "fig":
            from PIL import Image as PI
            _, path_, wcm, cap, main = b
            w, h_ = PI.open(path_).size
            story.append(KeepTogether([Image(str(path_), width=wcm * cm, height=wcm * cm * h_ / w), Paragraph(mk(cap), sty["cap"]), Spacer(1, 4)]))
        elif k == "pagebreak":
            story.append(PageBreak())

    def footer(cv, doc):
        cv.saveState(); cv.setFont("DV", 7); cv.setFillColor(grey)
        cv.drawCentredString(A4[0] / 2, 1.0 * cm, f"{title}  |  page {doc.page}"); cv.restoreState()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm, title=title)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
