"""Step 4: the one-page PDF (front = findings, back = method and exact questions)."""
from __future__ import annotations

from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, KeepInFrame, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

from .config import Audit, load_toml
from .gaps import GAPS

INK = colors.HexColor("#1B2A3A")
MUTED = colors.HexColor("#5B6B7B")
ACCENT = colors.HexColor("#0F766E")
WARN = colors.HexColor("#B45309")
LINE = colors.HexColor("#D7DEE5")
SOFT = colors.HexColor("#F1F5F8")

S = {
    "h": ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=10.5, textColor=ACCENT, spaceBefore=7, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Helvetica", fontSize=8.6, leading=11, textColor=INK),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=7.4, leading=9.2, textColor=MUTED),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8, leading=10, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Helvetica-Bold", fontSize=8.2, leading=10, textColor=INK),
    "big": ParagraphStyle("big", fontName="Helvetica-Bold", fontSize=30, leading=32, textColor=INK, alignment=TA_CENTER),
    "bigsub": ParagraphStyle("bigsub", fontName="Helvetica", fontSize=8.2, leading=10, textColor=MUTED, alignment=TA_CENTER),
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=INK),
    "cta": ParagraphStyle("cta", fontName="Helvetica-Bold", fontSize=9.4, leading=12, textColor=colors.white),
}


def t(s) -> str:
    """Escape text for reportlab and swap characters the built-in font can't draw."""
    s = str(s).replace("’", "'").replace("“", '"').replace("”", '"').replace("…", "...")
    s = s.encode("cp1252", errors="replace").decode("cp1252")
    return escape(s)


def load_findings(audit: Audit, result: dict) -> dict:
    """findings.toml = what YOU confirmed by checking their profile/site. Falls back to suggestions."""
    if audit.findings_path.exists():
        f = load_toml(audit.findings_path)
        f["confirmed"] = True
    else:
        f = {"gap": [{"id": g} for g in result["suggested_gaps"]], "confirmed": False}
    gaps = []
    for g in f.get("gap", []):
        if g["id"] not in GAPS:
            raise SystemExit(f"findings.toml: unknown gap id '{g['id']}'. Use one of: {', '.join(GAPS)}")
        gaps.append(GAPS[g["id"]] | {"id": g["id"], "detail": g.get("detail", "")})
    f["gaps"] = gaps
    return f


def score_bar(per_model: dict) -> Table:
    rows = [[Paragraph(t(v["label"]), S["cellb"]),
             Paragraph(f"<b>{v['mentioned']}</b> of {v['questions']}" +
                       ("" if v["answered"] == v["questions"] else f" <font color='#5B6B7B'>({v['answered']} asked)</font>"),
                       S["cell"])] for v in per_model.values()]
    tb = Table(rows, colWidths=[1.45 * inch, 1.05 * inch])
    tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
    return tb


def front(audit: Audit, result: dict, findings: dict, cfg: dict) -> list:
    b, o = audit.business, result["overall"]
    brand = cfg["brand"]
    rep = cfg["report"]
    n_models = len(result["per_model"])
    story = []
    demo = " (DEMO, fictional business)" if audit.audit.get("demo") else ""
    story.append(Paragraph(f"AI Visibility Audit{t(demo)}", S["small"]))
    story.append(Paragraph(t(b["name"]), S["title"]))
    story.append(Paragraph(f"{t(result['industry'])} in {t(result['place'])} &nbsp;&middot;&nbsp; checked {t(result['date'])}"
                           f" &nbsp;&middot;&nbsp; prepared by {t(brand['name'])}", S["small"]))
    story.append(Spacer(1, 8))

    # --- Score ---------------------------------------------------------
    headline = Paragraph(f"{o['mentioned']} of {o['answered']}", S["big"])
    sub = Paragraph(f"AI answers that mentioned you.<br/>We asked {n_models} AI tools the same {o['questions']} questions "
                    f"your customers ask. You came up at least once on {o['questions_with_any_mention']} of {o['questions']} questions.",
                    S["bigsub"])
    left = Table([[headline], [sub]], colWidths=[3.6 * inch])
    left.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    box = Table([[left, score_bar(result["per_model"])]], colWidths=[3.85 * inch, 2.65 * inch])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("TOPPADDING", (0, 0), (-1, -1), 8),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.append(box)

    # --- Competitors -----------------------------------------------------
    story.append(Paragraph("Who AI recommends instead", S["h"]))
    comps = result["competitors"][: rep["top_competitors"]]
    if comps:
        rows = [[Paragraph("Business", S["cellb"]), Paragraph("Came up", S["cellb"]), Paragraph("Why AI says it picked them", S["cellb"])]]
        for c in comps:
            why = ", ".join(c["top_reasons"][:2]) or "no reason given"
            where = "all " + str(len(result["models"])) + " AI tools" if len(c["models"]) == len(result["models"]) \
                else ", ".join(audit.model_short(m) for m in c["models"])
            quote = c["snippets"][0] if c["snippets"] else ""
            quote = (quote[:150] + "...") if len(quote) > 150 else quote
            rows.append([Paragraph(f"<b>{t(c['name'])}</b>", S["cell"]),
                         Paragraph(f"{c['answers']} of {o['answered']} answers<br/><font size=6.8 color='#5B6B7B'>in {t(where)}</font>", S["cell"]),
                         Paragraph(f"{t(why)}<br/><font size=7 color='#5B6B7B'><i>\"{t(quote)}\"</i></font>", S["cell"])])
        tb = Table(rows, colWidths=[1.7 * inch, 1.05 * inch, 3.75 * inch])
        tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        story.append(tb)
    else:
        story.append(Paragraph("No competitors were picked out. Check competitors.csv and known_competitors.", S["p"]))
    cited = [s for s, _ in result["sources"][:5]]
    if cited:
        story.append(Spacer(1, 2))
        story.append(Paragraph(f"Sites the AI cited most: {t(', '.join(cited))}", S["small"]))

    # --- Gaps ------------------------------------------------------------
    story.append(Paragraph("Why you're missing", S["h"]))
    gaps = findings["gaps"][: rep["max_gaps"]]
    for i, g in enumerate(gaps, 1):
        detail = f" <font color='#B45309'>{t(g['detail'])}</font>" if g["detail"] else ""
        story.append(Paragraph(f"<b>{i}. {t(g['title'])}.</b>{detail} <font color='#5B6B7B'>{t(g['why'])}</font>", S["p"]))
        story.append(Spacer(1, 1.5))
    if not findings["confirmed"]:
        story.append(Paragraph("<i>Draft: these gaps are suggestions from the answers. Check them and write findings.toml before sending.</i>", S["small"]))

    # --- Quick wins --------------------------------------------------------
    story.append(Paragraph("3 quick wins you can do this week", S["h"]))
    wins = findings.get("quick_wins") or [g["quick_win"] for g in gaps]
    for w in wins[: rep["quick_wins"]]:
        story.append(Paragraph(f"[ ]&nbsp; {t(w)}", S["p"]))
        story.append(Spacer(1, 1.5))

    # --- 90-day plan + ask ---------------------------------------------------
    story.append(Paragraph("What a 90-day plan would fix", S["h"]))
    plan = findings.get("plan") or [g["plan"] for g in gaps[:4]]
    plan = plan + ["Re-run these same questions every month, so you can see the score move (or not)."]
    story.append(Paragraph(" &nbsp;&bull;&nbsp; ".join(t(x) for x in plan), S["p"]))
    story.append(Spacer(1, 3))
    story.append(Paragraph("No one can promise a spot in AI answers, and we don't. We measure, fix what AI tools look for, "
                           "and show you the before and after.", S["small"]))
    story.append(Spacer(1, 6))
    contact = brand.get("call_link") or brand.get("contact", "")
    cta = Table([[Paragraph(f"Want to walk through this? Book a free 15-minute call: {t(contact)}", S["cta"])]],
                colWidths=[6.5 * inch])
    cta.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT), ("TOPPADDING", (0, 0), (-1, -1), 7),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LEFTPADDING", (0, 0), (-1, -1), 9)]))
    story.append(cta)
    return [KeepInFrame(6.5 * inch, 9.9 * inch, story, mode="shrink")]


def back(audit: Audit, result: dict) -> list:
    story = [Paragraph("How we checked", S["title"]), Spacer(1, 4)]
    how = audit.audit.get("how_run", "Each question was typed into the AI tool and the full answer was saved.")
    story.append(Paragraph(f"<b>Date:</b> {t(result['date'])} &nbsp; <b>Place:</b> {t(result['place'])} &nbsp; "
                           f"<b>AI tools:</b> {t(', '.join(audit.model_label(m) for m in result['models']))}", S["p"]))
    story.append(Paragraph(f"<b>Method:</b> {t(how)} A mention counts when the business name (or a known variant) "
                           "or its website appears anywhere in the answer.", S["p"]))
    story.append(Spacer(1, 6))
    models = result["models"]
    head = [Paragraph("#", S["cellb"]), Paragraph("Question asked (word for word)", S["cellb"])] + \
           [Paragraph(t(audit.model_short(m)), S["cellb"]) for m in models]
    rows = [head]
    for q in result["questions"]:
        cells = []
        for m in models:
            if m not in q["answered_in"]:
                cells.append(Paragraph("<font color='#5B6B7B'>not asked</font>", S["cell"]))
            elif m in q["mentioned_in"]:
                cells.append(Paragraph("<font color='#0F766E'><b>YES</b></font>", S["cell"]))
            else:
                cells.append(Paragraph("<font color='#B45309'>no</font>", S["cell"]))
        rows.append([Paragraph(str(q["n"]), S["cell"]), Paragraph(t(q["question"]), S["cell"])] + cells)
    mw = 0.72 * inch
    tb = Table(rows, colWidths=[0.3 * inch, 6.5 * inch - 0.3 * inch - mw * len(models)] + [mw] * len(models), repeatRows=1)
    tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.35, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("BACKGROUND", (0, 0), (-1, 0), SOFT), ("TOPPADDING", (0, 0), (-1, -1), 2),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story.append(tb)
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Please read: AI answers vary.</b> The same question can get a different answer on a different day, "
                           "in a different location, on a different account, or simply when asked again. This audit is a snapshot "
                           "of one round of questions, not a guarantee of what any customer will see. That is why we re-check the "
                           "same questions every month and track the trend.", S["p"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Business names in this report are taken from the AI answers as written. Inclusion of a competitor is "
                           "not a judgement about their quality.", S["small"]))
    return [KeepInFrame(6.5 * inch, 9.9 * inch, story, mode="shrink")]


def build_pdf(audit: Audit, result: dict, path) -> None:
    from .config import settings
    cfg = settings()
    findings = load_findings(audit, result)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(inch, 0.45 * inch, f"{cfg['brand']['name']} - {cfg['brand'].get('tagline', '')}")
        canvas.drawRightString(7.5 * inch, 0.45 * inch, "Front: findings" if doc.page == 1 else "Back: exact questions and method")
        if audit.audit.get("demo"):
            canvas.setFillColor(colors.HexColor("#E8EDF2"))
            canvas.setFont("Helvetica-Bold", 70)
            canvas.translate(4.25 * inch, 5.5 * inch)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "DEMO")
        canvas.restoreState()

    doc = BaseDocTemplate(str(path), pagesize=letter, leftMargin=inch, rightMargin=inch, topMargin=0.55 * inch,
                          bottomMargin=0.6 * inch, title=f"AI Visibility Audit - {audit.business['name']}",
                          author=cfg["brand"]["name"])
    frame = Frame(inch, 0.6 * inch, 6.5 * inch, 9.9 * inch, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=footer)])
    doc.build(front(audit, result, findings, cfg) + [PageBreak()] + back(audit, result))
