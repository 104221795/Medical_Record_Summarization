from __future__ import annotations

from pathlib import Path

from PIL import Image
import win32com.client


HERE = Path(__file__).resolve().parent
FIGURES = HERE / "assets" / "figures"
PPTX = HERE / "Medical_Record_Summarization_Final_Enterprise_Deck.pptx"

SLIDE_W = 13.333333 * 72
SLIDE_H = 7.5 * 72

PP_LAYOUT_BLANK = 12
PP_SAVE_AS_PPTX = 24
MSO_TEXT_HORIZONTAL = 1
MSO_TRUE = -1
MSO_FALSE = 0
SHAPE_RECT = 1
SHAPE_ROUND_RECT = 5
SHAPE_OVAL = 9

NAVY = "#071B33"
TEAL = "#006D77"
CYAN = "#00B4D8"
GOLD = "#D6A84F"
OFF = "#F7FAFC"
GRAY = "#E5E7EB"
INK = "#102033"
MUTED = "#5C6B7B"
WHITE = "#FFFFFF"
RED = "#B42318"


def rgb(value: str) -> int:
    value = value.lstrip("#")
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return r + (g << 8) + (b << 16)


def pt(inches: float) -> float:
    return inches * 72


def add_shape(slide, shape_type: int, x: float, y: float, w: float, h: float, fill: str, *,
              line: str | None = None, transparency: float = 0.0):
    shp = slide.Shapes.AddShape(shape_type, x, y, w, h)
    shp.Fill.Visible = MSO_TRUE
    shp.Fill.ForeColor.RGB = rgb(fill)
    shp.Fill.Transparency = transparency
    if line:
        shp.Line.Visible = MSO_TRUE
        shp.Line.ForeColor.RGB = rgb(line)
        shp.Line.Transparency = 0.35
    else:
        shp.Line.Visible = MSO_FALSE
    return shp


def add_text(slide, text: str, x: float, y: float, w: float, h: float, *, size: float = 18,
             color: str = INK, bold: bool = False, font: str = "Segoe UI",
             align: int | None = None):
    box = slide.Shapes.AddTextbox(MSO_TEXT_HORIZONTAL, x, y, w, h)
    box.TextFrame.MarginLeft = 0
    box.TextFrame.MarginRight = 0
    box.TextFrame.MarginTop = 0
    box.TextFrame.MarginBottom = 0
    box.TextFrame.WordWrap = MSO_TRUE
    tr = box.TextFrame.TextRange
    tr.Text = text
    tr.Font.Name = font
    tr.Font.Size = size
    tr.Font.Bold = MSO_TRUE if bold else MSO_FALSE
    tr.Font.Color.RGB = rgb(color)
    if align is not None:
        tr.ParagraphFormat.Alignment = align
    return box


def add_footer(slide, section: str, n: int, *, dark: bool = False):
    color = "#D8EAF0" if dark else "#8492A2"
    add_text(slide, section, pt(0.75), SLIDE_H - pt(0.36), pt(6.0), pt(0.18), size=8.5, color=color)
    add_text(slide, f"{n:02d} / 24", SLIDE_W - pt(1.25), SLIDE_H - pt(0.36), pt(0.6), pt(0.18), size=8.5, color=color)


def add_bg(slide, *, dark: bool = False):
    add_shape(slide, SHAPE_RECT, 0, 0, SLIDE_W, SLIDE_H, NAVY if dark else OFF)
    if dark:
        add_shape(slide, SHAPE_OVAL, SLIDE_W - pt(3.1), pt(0.15), pt(3.9), pt(3.9), CYAN, transparency=0.78)
        add_shape(slide, SHAPE_OVAL, -pt(0.85), SLIDE_H - pt(2.05), pt(2.9), pt(2.9), GOLD, transparency=0.82)
    else:
        add_shape(slide, SHAPE_OVAL, SLIDE_W - pt(2.65), -pt(0.9), pt(3.4), pt(3.4), CYAN, transparency=0.88)
        add_shape(slide, SHAPE_OVAL, -pt(1.0), SLIDE_H - pt(1.9), pt(2.6), pt(2.6), GOLD, transparency=0.9)


def add_header(slide, section: str, title: str, subtitle: str = "", *, dark: bool = False):
    add_text(slide, section.upper(), pt(0.78), pt(0.52), pt(7.5), pt(0.24), size=9.5,
             color="#C7E8EF" if dark else TEAL, bold=True)
    add_text(slide, title, pt(0.78), pt(0.83), pt(10.2), pt(0.62), size=31,
             color=WHITE if dark else INK, bold=True)
    if subtitle:
        add_text(slide, subtitle, pt(0.78), pt(1.48), pt(10.4), pt(0.54), size=16.5,
                 color="#D8EAF0" if dark else MUTED)


def add_card(slide, title: str, body: str, x: float, y: float, w: float, h: float, *,
             tone: str = "default", dark: bool = False):
    fill = "#FFF8E8" if tone == "gold" else ("#163A5A" if dark else WHITE)
    line = GOLD if tone == "gold" else ("#2D5E78" if dark else "#BFD7DD")
    add_shape(slide, SHAPE_ROUND_RECT, x, y, w, h, fill, line=line, transparency=0.0 if not dark else 0.12)
    add_text(slide, title.upper(), x + pt(0.18), y + pt(0.18), w - pt(0.36), pt(0.28),
             size=8.7, color=GOLD if dark else TEAL, bold=True)
    add_text(slide, body, x + pt(0.18), y + pt(0.55), w - pt(0.36), h - pt(0.72),
             size=14.2, color="#EAF6FA" if dark else MUTED)


def add_pill(slide, text: str, x: float, y: float, w: float, *, tone: str = "teal", dark: bool = False):
    fill = GOLD if tone == "gold" else (CYAN if tone == "cyan" else ("#173A57" if dark else "#E4F3F5"))
    color = NAVY if tone == "gold" else (WHITE if dark else TEAL)
    add_shape(slide, SHAPE_ROUND_RECT, x, y, w, pt(0.32), fill, line=fill, transparency=0.0 if tone == "gold" else 0.08)
    add_text(slide, text, x + pt(0.08), y + pt(0.075), w - pt(0.16), pt(0.16), size=8.4, color=color, bold=True, align=2)


def figure_path(num: int) -> Path:
    return FIGURES / f"figure_{num:02d}.png"


def add_picture_fit(slide, num: int, title: str, x: float, y: float, w: float, h: float, *,
                    badge: str | None = None):
    add_shape(slide, SHAPE_ROUND_RECT, x, y, w, h, WHITE, line="#BFD7DD")
    path = figure_path(num)
    if not path.exists():
        add_text(slide, f"Figure {num}", x + pt(0.2), y + pt(0.35), w - pt(0.4), pt(0.35),
                 size=20, color=TEAL, bold=True, align=2)
        add_text(slide, title, x + pt(0.2), y + pt(0.83), w - pt(0.4), pt(0.4),
                 size=14, color=MUTED, align=2)
        return
    with Image.open(path) as img:
        iw, ih = img.size
    max_w, max_h = w - pt(0.16), h - pt(0.45)
    ratio = min(max_w / iw, max_h / ih)
    pic_w, pic_h = iw * ratio, ih * ratio
    pic_x = x + (w - pic_w) / 2
    pic_y = y + pt(0.08) + (max_h - pic_h) / 2
    slide.Shapes.AddPicture(str(path.resolve()), MSO_FALSE, MSO_TRUE, pic_x, pic_y, pic_w, pic_h)
    add_shape(slide, SHAPE_ROUND_RECT, x + pt(0.1), y + h - pt(0.29), w - pt(0.2), pt(0.22), NAVY, transparency=0.15)
    add_text(slide, f"Figure {num} — {title}", x + pt(0.18), y + h - pt(0.245), w - pt(0.36), pt(0.11),
             size=6.8, color=WHITE)
    if badge:
        add_shape(slide, SHAPE_ROUND_RECT, x + pt(0.13), y + pt(0.13), pt(1.18), pt(0.28), GOLD, line=GOLD)
        add_text(slide, badge, x + pt(0.23), y + pt(0.2), pt(0.98), pt(0.1), size=7.2, color=NAVY, bold=True, align=2)


def add_metric(slide, label: str, value: str, x: float, y: float, w: float, h: float, *,
               caption: str = "", tone: str = "teal"):
    fill = "#FFF8E8" if tone == "gold" else WHITE
    line = GOLD if tone == "gold" else "#BFD7DD"
    add_shape(slide, SHAPE_ROUND_RECT, x, y, w, h, fill, line=line)
    add_text(slide, value, x + pt(0.15), y + pt(0.18), w - pt(0.3), pt(0.36), size=23,
             color=TEAL, bold=True)
    add_text(slide, label, x + pt(0.15), y + pt(0.68), w - pt(0.3), pt(0.28), size=11.7,
             color=INK, bold=True)
    if caption:
        add_text(slide, caption, x + pt(0.15), y + pt(1.0), w - pt(0.3), pt(0.24), size=8.5, color=MUTED)


def add_callout(slide, idx: str, title: str, body: str, x: float, y: float, w: float, h: float):
    add_shape(slide, SHAPE_ROUND_RECT, x, y, w, h, WHITE, line="#BFD7DD")
    add_shape(slide, SHAPE_ROUND_RECT, x + pt(0.14), y + pt(0.18), pt(0.44), pt(0.44), NAVY, line=NAVY)
    add_text(slide, idx, x + pt(0.23), y + pt(0.31), pt(0.26), pt(0.12), size=8.8, color=WHITE, bold=True, align=2)
    add_text(slide, title, x + pt(0.72), y + pt(0.18), w - pt(0.9), pt(0.24), size=12.4, color=INK, bold=True)
    add_text(slide, body, x + pt(0.72), y + pt(0.5), w - pt(0.9), h - pt(0.56), size=9.8, color=MUTED)


def add_workflow(slide, labels: list[str], x: float, y: float, w: float, h: float, *, dark: bool = False):
    gap = pt(0.08)
    step_w = (w - gap * (len(labels) - 1)) / len(labels)
    for i, label in enumerate(labels):
        sx = x + i * (step_w + gap)
        add_shape(slide, SHAPE_ROUND_RECT, sx, y, step_w, h, "#163A5A" if dark else WHITE,
                  line="#2D5E78" if dark else "#BFD7DD", transparency=0.08 if dark else 0)
        add_text(slide, f"{i+1:02d}", sx + pt(0.1), y + pt(0.15), step_w - pt(0.2), pt(0.18),
                 size=8.5, color=GOLD, bold=True)
        add_text(slide, label, sx + pt(0.1), y + pt(0.46), step_w - pt(0.2), h - pt(0.55),
                 size=10 if len(labels) <= 7 else 7.5, color=WHITE if dark else INK, bold=True)


def add_notes(slide, text: str):
    try:
        slide.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange.Text = text
    except Exception:
        pass


def add_slide(prs, n: int, section: str, title: str, subtitle: str = "", *, dark: bool = False):
    slide = prs.Slides.Add(n, PP_LAYOUT_BLANK)
    add_bg(slide, dark=dark)
    add_header(slide, section, title, subtitle, dark=dark)
    add_footer(slide, section, n, dark=dark)
    return slide


def build_deck(prs):
    # 1
    s = prs.Slides.Add(1, PP_LAYOUT_BLANK)
    add_bg(s, dark=True)
    add_shape(s, SHAPE_ROUND_RECT, pt(0.85), pt(0.58), pt(2.55), pt(0.36), GOLD, line=GOLD)
    add_text(s, "ENTERPRISE-GRADE PROPOSAL DECK", pt(1.0), pt(0.69), pt(2.25), pt(0.12), size=7.6, color=NAVY, bold=True, align=2)
    add_text(s, "Vinmec × VinSmartFuture", pt(0.85), pt(1.32), pt(8.2), pt(0.65), size=39, color=WHITE, bold=True)
    add_text(s, "Citation-grounded Medical Record Summarization PoC", pt(0.85), pt(2.05), pt(8.7), pt(0.95), size=29, color="#E9F7FA", bold=True)
    add_text(s, "Evidence-first AI draft workflow with clinician review, citation validation, auditability and proxy evaluation.", pt(0.85), pt(3.05), pt(8.0), pt(0.62), size=16, color="#D7E8EE")
    add_pill(s, "local staging demo-ready PoC", pt(0.85), pt(3.92), pt(2.25), tone="gold")
    add_pill(s, "research-first pilot foundation", pt(3.27), pt(3.92), pt(2.35), tone="cyan", dark=True)
    add_pill(s, "production-readiness roadmap", pt(5.8), pt(3.92), pt(2.4), dark=True)
    add_shape(s, SHAPE_ROUND_RECT, pt(9.05), pt(1.15), pt(3.35), pt(3.8), "#173A57", line="#41657D", transparency=0.14)
    add_text(s, "Clinical boundary", pt(9.42), pt(1.55), pt(2.6), pt(0.25), size=14, color=GOLD, bold=True)
    for i, line in enumerate([
        "Clinician-review-only AI draft",
        "De-identified / mock / proxy data",
        "Not a clinical deployment",
        "No autonomous diagnosis, treatment recommendation or prescribing",
    ]):
        add_text(s, line, pt(9.42), pt(2.0 + i * 0.55), pt(2.55), pt(0.3), size=12.2, color="#EEF7FA")
    add_shape(s, SHAPE_RECT, pt(0.85), pt(6.5), pt(6.7), pt(0.035), GOLD)
    add_text(s, "Clinician-review-only PoC | De-identified/proxy data | Not a clinical deployment", pt(0.85), pt(6.78), pt(8.0), pt(0.2), size=10.5, color="#D8EAF0")
    add_footer(s, "Cover", 1, dark=True)
    add_notes(s, "Open with the positioning: this is a premium enterprise proposal for a controlled evidence-first PoC, not a hospital deployment claim. Emphasize clinician review and proxy evaluation immediately.")

    # 2
    s = add_slide(prs, 2, "01 Context & Problem", "Executive Narrative", "Medical summarization needs evidence traceability and clinician control, not only fluent AI-generated text.")
    xs = [pt(0.8), pt(3.88), pt(6.96), pt(10.04)]
    for x, title, body, tone in zip(xs, ["Problem", "Solution", "Proof", "Boundary"], [
        "Medical records are fragmented across encounters, notes, medications, timelines and prior summaries.",
        "A citation-grounded RAG workflow creates clinician-review-only AI drafts from scoped evidence.",
        "The local staging demo-ready PoC includes doctor/admin UI, benchmark visibility, test/build evidence and artifacts.",
        "Proxy evaluation only; no clinical safety, effectiveness, real EHR validation or hospital deployment claim.",
    ], ["", "", "", "gold"]):
        add_card(s, title, body, x, pt(2.48), pt(2.65), pt(2.18), tone=tone)
    add_shape(s, SHAPE_ROUND_RECT, pt(1.1), pt(5.25), pt(11.15), pt(0.62), "#E4F3F5", line="#BFD7DD")
    add_text(s, "One message: the project is designed to make evidence and uncertainty visible before a clinician decides.", pt(1.35), pt(5.45), pt(10.5), pt(0.18), size=14.5, color=TEAL, bold=True, align=2)
    add_notes(s, "Walk through the four-card story. The contrast is fluent ungrounded text versus evidence-first drafts under clinician control.")

    # 3
    s = add_slide(prs, 3, "Proposal Agenda", "Premium Enterprise Proposal Structure", "Problem assessment before solution, business proposal before technical proposal, then delivery and pilot governance.", dark=True)
    agenda = ["Context & Problem", "Proposed Solution", "Doctor Workflow", "Evaluation & Evidence", "Technical Readiness", "Research Pilot Roadmap"]
    for i, item in enumerate(agenda):
        col, row = i % 2, i // 2
        x, y = pt(1.15 + col * 5.45), pt(2.05 + row * 1.05)
        add_shape(s, SHAPE_ROUND_RECT, x, y, pt(4.95), pt(0.78), "#173A57", line="#41657D", transparency=0.08)
        add_shape(s, SHAPE_ROUND_RECT, x + pt(0.25), y + pt(0.17), pt(0.55), pt(0.45), GOLD, line=GOLD)
        add_text(s, f"{i+1:02d}", x + pt(0.39), y + pt(0.31), pt(0.25), pt(0.1), size=10, color=NAVY, bold=True, align=2)
        add_text(s, item, x + pt(1.05), y + pt(0.26), pt(3.6), pt(0.22), size=16, color=WHITE, bold=True)
    add_notes(s, "Set expectations for an enterprise proposal deck: context, solution, workflow, evidence, readiness, and roadmap.")

    # 4
    s = add_slide(prs, 4, "01 Context & Problem", "Why the Problem Matters", "Clinical summarization is risky when the system cannot show what evidence was used.")
    pains = [
        ("Fragmented medical records", "Key facts may sit across multiple notes, encounters and documents."),
        ("Hallucination / omission risk", "Generic LLM summaries can sound fluent while missing or adding critical facts."),
        ("Lack of source traceability", "Without citations, reviewers cannot quickly verify the draft against evidence."),
    ]
    for i, (title, body) in enumerate(pains):
        x = pt(0.9 + i * 4.1)
        add_shape(s, SHAPE_ROUND_RECT, x, pt(2.5), pt(3.55), pt(2.65), WHITE, line="#BFD7DD")
        add_shape(s, SHAPE_ROUND_RECT, x + pt(0.3), pt(2.9), pt(0.72), pt(0.08), CYAN, line=CYAN)
        add_text(s, title, x + pt(0.3), pt(3.28), pt(2.85), pt(0.52), size=18, color=INK, bold=True)
        add_text(s, body, x + pt(0.3), pt(4.15), pt(2.9), pt(0.6), size=13.5, color=MUTED)
    add_notes(s, "Explain why the problem is not just text summarization. The workflow must surface evidence.")

    # 5
    s = add_slide(prs, 5, "02 Proposed Solution", "Why Citation-grounded RAG", "RAG is positioned as evidence infrastructure, not a guarantee of clinical correctness.")
    pillars = [("01", "Evidence Retrieval", "Retrieve patient/encounter-scoped chunks before generation."),
               ("02", "Citation Validation", "Link important generated claims back to source evidence."),
               ("03", "Clinician Final Control", "Drafts remain editable, rejectable and review-only.")]
    for i, (num, title, body) in enumerate(pillars):
        x = pt(0.9 + i * 4.1)
        add_shape(s, SHAPE_ROUND_RECT, x, pt(2.3), pt(3.55), pt(2.55), WHITE, line="#BFD7DD")
        add_shape(s, SHAPE_ROUND_RECT, x + pt(0.3), pt(2.68), pt(0.55), pt(0.48), NAVY, line=NAVY)
        add_text(s, num, x + pt(0.43), pt(2.82), pt(0.28), pt(0.1), size=9.5, color=WHITE, bold=True, align=2)
        add_text(s, title, x + pt(0.3), pt(3.48), pt(2.85), pt(0.35), size=18, color=INK, bold=True)
        add_text(s, body, x + pt(0.3), pt(4.05), pt(2.85), pt(0.48), size=13.5, color=MUTED)
    add_shape(s, SHAPE_ROUND_RECT, pt(1.25), pt(5.35), pt(10.85), pt(0.56), "#E4F3F5", line="#BFD7DD")
    add_text(s, "RAG helps organize evidence. It does not replace clinical judgment or validate clinical correctness by itself.", pt(1.48), pt(5.53), pt(10.3), pt(0.16), size=13.5, color=INK, bold=True, align=2)
    add_notes(s, "RAG is valuable because it provides a structured evidence pathway and review surface, not because it magically makes outputs clinically safe.")

    # 6
    s = add_slide(prs, 6, "02 Proposed Solution", "Solution at a Glance", "A clean evidence-first workflow from patient scope to audit trail.")
    add_workflow(s, ["Patient / Encounter Scope", "Evidence Retrieval", "AI Draft", "Citation Validation", "Clinician Review", "Final Summary", "Audit Trail"], pt(0.72), pt(3.0), pt(11.9), pt(1.45))
    add_shape(s, SHAPE_ROUND_RECT, pt(1.4), pt(5.35), pt(10.5), pt(0.55), "#E4F3F5", line="#BFD7DD")
    add_text(s, "The workflow is deliberately gated: source evidence is retrieved and validated before the clinician accepts any final summary.", pt(1.65), pt(5.52), pt(10.0), pt(0.16), size=13, color=TEAL, bold=True, align=2)
    add_notes(s, "Explain each step in one sentence and stress that the AI output is a draft.")

    # 7
    s = add_slide(prs, 7, "03 Doctor Workflow", "Product Entry: Role-based Workspace", "Doctor and admin workspaces support an evidence-first summarization flow inside a local staging demo-ready PoC.")
    add_callout(s, "01", "Doctor and admin workspaces", "Role-specific navigation for clinical review and evaluation workflows.", pt(0.78), pt(2.05), pt(3.45), pt(0.86))
    add_callout(s, "02", "Evidence-first summarization flow", "The product entry frames summarization around reviewable evidence.", pt(0.78), pt(3.05), pt(3.45), pt(0.86))
    add_callout(s, "03", "Local staging boundary", "Demo-ready locally; no hospital deployment claim.", pt(0.78), pt(4.05), pt(3.45), pt(0.86))
    add_picture_fit(s, 1, "Product Landing Page", pt(0.78), pt(5.15), pt(1.65), pt(1.05), badge="Entry")
    add_picture_fit(s, 2, "Role-Based Login Page", pt(2.58), pt(5.15), pt(1.65), pt(1.05), badge="Access")
    add_picture_fit(s, 4, "Doctor Workspace Overview", pt(4.55), pt(2.0), pt(7.7), pt(4.3), badge="Product entry")
    add_notes(s, "Orient reviewers to product coherence and role-based entry, while keeping the message business-oriented.")

    # 8
    s = add_slide(prs, 8, "03 Doctor Workflow", "Patient and Encounter Scope", "The workflow starts from de-identified patient and encounter context.")
    add_picture_fit(s, 5, "De-identified Patient List", pt(0.85), pt(2.12), pt(5.75), pt(4.05), badge="Patient scope")
    add_picture_fit(s, 6, "Patient Context and Timeline", pt(6.85), pt(2.12), pt(5.75), pt(4.05), badge="Encounter context")
    add_notes(s, "Choose a de-identified patient, inspect encounter context, then generate or review. Avoid claiming real EHR integration.")

    # 9
    s = add_slide(prs, 9, "03 Doctor Workflow", "Evidence-first Draft Generation", "The draft is generated after patient-scoped retrieval and provider selection.")
    add_picture_fit(s, 7, "RAG Evidence-First Generate Summary", pt(0.85), pt(2.0), pt(7.4), pt(4.4), badge="Draft generation")
    add_callout(s, "A", "Patient-scoped retrieval", "Evidence is retrieved before provider inference.", pt(8.55), pt(2.1), pt(3.7), pt(0.82))
    add_callout(s, "B", "Provider selection", "Providers can be compared for proxy evaluation and demo flow.", pt(8.55), pt(3.12), pt(3.7), pt(0.82))
    add_callout(s, "C", "Draft-only generation", "The generated summary requires clinician review before use.", pt(8.55), pt(4.14), pt(3.7), pt(0.82))
    add_notes(s, "Position generation as a controlled workflow step. Keep saying draft-only.")

    # 10
    s = add_slide(prs, 10, "03 Doctor Workflow", "Evidence Quality Gate", "Citation coverage, unsupported claims, conflicts and retrieval warnings are made visible before decision.")
    add_picture_fit(s, 8, "Review and Evidence Quality Gate", pt(0.95), pt(1.95), pt(11.45), pt(4.75), badge="Key differentiator")
    add_pill(s, "Citation coverage", pt(1.25), pt(5.9), pt(1.55), tone="gold")
    add_pill(s, "Unsupported claims", pt(9.5), pt(2.2), pt(1.65), tone="gold")
    add_pill(s, "Conflicts & retrieval warnings", pt(8.6), pt(5.85), pt(2.35), tone="gold")
    add_notes(s, "This is a core differentiator: the quality gate surfaces uncertainty rather than hiding it behind a polished summary.")

    # 11
    s = add_slide(prs, 11, "03 Doctor Workflow", "Citation-first Review", "Important generated claims are linked to source evidence for clinician verification.")
    add_picture_fit(s, 9, "Citation and Claim Review", pt(0.85), pt(2.05), pt(6.15), pt(4.35), badge="Claim review")
    add_picture_fit(s, 10, "Citation Tracking Detail", pt(7.3), pt(2.05), pt(5.1), pt(4.35), badge="Evidence trace")
    add_notes(s, "Explain how the review workspace connects claims, citations and source excerpts. The clinician verifies; the system assists.")

    # 12
    s = add_slide(prs, 12, "03 Doctor Workflow", "Human-in-the-loop Decision", "The clinician can edit, approve, request revision, or reject. The AI output remains a draft.")
    add_picture_fit(s, 11, "Editable Draft and Reject Decision", pt(0.85), pt(2.05), pt(7.25), pt(4.35), badge="HITL decision")
    add_shape(s, SHAPE_ROUND_RECT, pt(8.45), pt(2.25), pt(3.65), pt(3.6), NAVY, line="#2D5E78")
    add_text(s, "Clinician remains final authority.", pt(8.75), pt(2.62), pt(3.0), pt(0.65), size=22, color=WHITE, bold=True)
    add_text(s, "• Edit the draft\n• Approve only after review\n• Request revision\n• Reject unsupported draft\n• Decision is recorded", pt(8.82), pt(3.52), pt(2.7), pt(1.45), size=13.2, color="#EAF6FA")
    add_notes(s, "The UI supports clinician decisions; it does not automate diagnosis, treatment, prescribing or discharge approval.")

    # 13
    s = add_slide(prs, 13, "03 Doctor Workflow", "Lifecycle and Auditability", "The system preserves review status, reviewer action, generated time and audit events.")
    add_picture_fit(s, 12, "Patient Summary History Status", pt(0.85), pt(2.12), pt(5.75), pt(4.05), badge="Lifecycle")
    add_picture_fit(s, 13, "Audit History Trace", pt(6.85), pt(2.12), pt(5.75), pt(4.05), badge="Audit trail")
    add_notes(s, "Summary lifecycle and audit trails are valuable for governance and research review even before any real clinical deployment is considered.")

    # 14
    s = add_slide(prs, 14, "03 Business Proposal", "Role / Value Mapping", "Each stakeholder gets a distinct workflow value, without turning the slide into a giant table.")
    roles = [
        ("Doctor", "Long records → cited draft review → faster evidence inspection."),
        ("Admin / Evaluator", "Hidden benchmark state → dashboards → visible readiness and artifacts."),
        ("Technical Reviewer", "Unverifiable runtime → Docker/test/build evidence → repeatable demo proof."),
        ("Research Evaluator", "Shallow metrics → grounding and safety proxy → better study design."),
        ("Mentor / Reviewer", "Fragmented story → enterprise deck + evidence package → fast review."),
    ]
    for i, (title, body) in enumerate(roles):
        add_card(s, title, body, pt(0.65 + i * 2.52), pt(2.45), pt(2.24), pt(2.65), tone="gold" if i == 4 else "")
    add_notes(s, "Summarize business value for each stakeholder in boardroom-readable form.")

    # 15
    s = add_slide(prs, 15, "04 Technical Readiness", "Technical Architecture", "A readable layered architecture for a local staging demo-ready PoC.")
    layers = [
        ("User Layer", "Doctor UI / Admin UI"),
        ("Application Layer", "React Frontend / FastAPI Backend"),
        ("AI/RAG Layer", "Chunking / Retrieval / Context Builder / Provider Gateway"),
        ("Safety Layer", "Citation Service / Safety Service / Review Service"),
        ("Data & Runtime Layer", "PostgreSQL / Redis-RQ / Artifacts / Docker Compose"),
    ]
    for i, (layer, comp) in enumerate(layers):
        y = pt(2.0 + i * 0.78)
        add_shape(s, SHAPE_ROUND_RECT, pt(1.65), y, pt(10.0), pt(0.55), WHITE, line="#BFD7DD")
        add_text(s, layer.upper(), pt(1.95), y + pt(0.18), pt(2.3), pt(0.12), size=8.8, color=TEAL, bold=True)
        add_text(s, comp, pt(4.35), y + pt(0.15), pt(6.75), pt(0.16), size=14.5, color=INK, bold=True)
    add_notes(s, "Explain the architecture in layers: UI, API, AI/RAG, safety and runtime.")

    # 16
    s = add_slide(prs, 16, "04 Technical Readiness", "RAG and Citation Pipeline", "Chunking happens before vector retrieval; retrieved evidence is reviewed before final use.")
    add_workflow(s, ["Clinical note", "Patient / encounter scope", "Chunking", "Retrieval", "Context builder", "Generation", "Citation matching", "Safety metrics", "Clinician review"], pt(0.65), pt(2.55), pt(12.05), pt(1.28))
    add_shape(s, SHAPE_ROUND_RECT, pt(1.25), pt(5.0), pt(10.85), pt(0.58), "#E4F3F5", line="#BFD7DD")
    add_text(s, "Design intent: citation-grounded RAG structures evidence for review. It is not a clinical correctness guarantee.", pt(1.55), pt(5.19), pt(10.25), pt(0.16), size=13.2, color=INK, bold=True, align=2)
    add_notes(s, "Walk through scoping, chunking, retrieval, context, generation, citation matching, safety proxy and clinician review.")

    # 17
    s = add_slide(prs, 17, "04 Evaluation & Evidence", "Evaluation Framework", "Proxy evaluation is layered: text similarity at the bottom, grounding and safety in the middle, human review as the future top layer.")
    add_shape(s, SHAPE_ROUND_RECT, pt(4.15), pt(2.05), pt(5.0), pt(0.55), GOLD, line=GOLD)
    add_text(s, "Human validation future", pt(4.45), pt(2.23), pt(4.4), pt(0.14), size=15, color=NAVY, bold=True, align=2)
    add_shape(s, SHAPE_ROUND_RECT, pt(2.85), pt(2.9), pt(7.6), pt(0.72), TEAL, line=TEAL)
    add_text(s, "Grounding and safety proxy: citation coverage, unsupported claims, factuality proxy, omission proxy", pt(3.2), pt(3.13), pt(6.9), pt(0.16), size=12.8, color=WHITE, bold=True, align=2)
    add_shape(s, SHAPE_ROUND_RECT, pt(1.65), pt(3.95), pt(10.0), pt(0.72), NAVY, line=NAVY)
    add_text(s, "Text similarity: ROUGE-L and BERTScore", pt(2.0), pt(4.18), pt(9.3), pt(0.16), size=15, color=WHITE, bold=True, align=2)
    for i, label in enumerate(["Text similarity", "Evidence grounding", "Safety proxy", "Workflow review", "Human validation future"]):
        add_pill(s, label, pt(1.1 + i * 2.28), pt(5.45), pt(1.9), tone="gold" if i == 4 else "teal")
    add_notes(s, "ROUGE and BERTScore are useful but insufficient; grounding and safety proxy metrics are added, with human evaluation next.")

    # 18
    s = add_slide(prs, 18, "04 Evaluation & Evidence", "Benchmark Result Summary", "Completed proxy benchmark visibility for the no-gate Flow 2.1 run.")
    metrics = [("Records", "50", ""), ("Providers", "5", ""), ("Predictions", "250/250", ""), ("Semantic metric", "BERTScore", "computed"), ("Strongest generative provider", "Qwen2.5", "proxy run"), ("Smoke/control provider", "Deterministic", "most reliable")]
    for i, (label, value, cap) in enumerate(metrics):
        add_metric(s, label, value, pt(0.75 + (i % 2) * 2.35), pt(2.0 + (i // 2) * 1.23), pt(2.05), pt(1.0), caption=cap)
    add_picture_fit(s, 16, "Provider ROUGE Leaderboard", pt(5.65), pt(2.0), pt(6.7), pt(3.6), badge="Provider ranking")
    add_shape(s, SHAPE_ROUND_RECT, pt(1.0), pt(6.05), pt(11.25), pt(0.42), "#FFF8E8", line=GOLD)
    add_text(s, "Proxy evaluation only — not clinical validation, not real EHR validation, and not a clinical safety/effectiveness claim.", pt(1.2), pt(6.19), pt(10.85), pt(0.12), size=10.5, color="#8A631D", bold=True, align=2)
    add_notes(s, "Present headline benchmark facts only. This is proxy evaluation and does not validate clinical performance.")

    # 19
    s = add_slide(prs, 19, "04 Evaluation & Evidence", "Qwen2.5 Snapshot", "Best balanced generative provider in the completed no-gate proxy run; not clinical validation.")
    qmetrics = [("ROUGE-L", "0.2122"), ("BERTScore F1", "0.8391"), ("Citation coverage", "0.8884"), ("Factuality proxy", "0.8713"), ("Critical omission", "0.4460")]
    for i, (label, value) in enumerate(qmetrics):
        add_metric(s, label, value, pt(0.65 + i * 2.52), pt(2.1), pt(2.25), pt(1.35), tone="gold" if i == 4 else "teal")
    bars = [("ROUGE-L 0.2122", 0.72), ("BERTScore F1 0.8391", 0.84), ("Citation coverage 0.8884", 0.89)]
    for i, (label, width) in enumerate(bars):
        y = pt(4.2 + i * 0.48)
        add_shape(s, SHAPE_ROUND_RECT, pt(1.45), y, pt(10.2), pt(0.26), "#E9F3F5", line="#E9F3F5")
        add_shape(s, SHAPE_ROUND_RECT, pt(1.45), y, pt(10.2 * width), pt(0.26), TEAL, line=TEAL)
        add_text(s, label, pt(1.68), y + pt(0.07), pt(4.0), pt(0.08), size=8.5, color=NAVY, bold=True)
    add_shape(s, SHAPE_ROUND_RECT, pt(1.25), pt(5.95), pt(10.85), pt(0.42), "#FFF8E8", line=GOLD)
    add_text(s, "Interpretation is limited to proxy evaluation artifacts. It does not establish clinical safety or effectiveness.", pt(1.45), pt(6.09), pt(10.45), pt(0.1), size=10, color="#8A631D", bold=True, align=2)
    add_notes(s, "Use exact metrics only. Qwen2.5 looks strongest among generative PoC providers, but this remains proxy evidence.")

    # 20
    s = add_slide(prs, 20, "04 Evaluation & Evidence", "Admin Evaluation Visibility", "Evaluation is inspectable through the Admin dashboard, not hidden inside scripts.")
    add_picture_fit(s, 14, "Admin Evaluation Readiness", pt(0.72), pt(2.05), pt(3.85), pt(3.95), badge="Readiness")
    add_picture_fit(s, 15, "RAG Best Models Admin Overview", pt(4.78), pt(2.05), pt(3.85), pt(3.95), badge="Flow 2.1 visibility")
    add_picture_fit(s, 17, "Evidence Grounding Metrics", pt(8.84), pt(2.05), pt(3.85), pt(3.95), badge="Grounding metrics")
    add_notes(s, "Show that benchmark evidence is operationalized into admin visibility, not only side scripts.")

    # 21
    s = add_slide(prs, 21, "04 Evaluation & Evidence", "Error Analysis and Reproducibility", "Per-record failure analysis and artifact files support transparent review.")
    add_picture_fit(s, 18, "RAG vs Raw Context Comparison", pt(0.72), pt(2.05), pt(3.85), pt(3.65), badge="RAG vs raw")
    add_picture_fit(s, 19, "Per-Record Failure Analysis", pt(4.78), pt(2.05), pt(3.85), pt(3.65), badge="Failure diagnosis")
    add_picture_fit(s, 20, "RAG Benchmark Artifacts and Run Files", pt(8.84), pt(2.05), pt(3.85), pt(3.65), badge="Reproducibility")
    for i, label in enumerate(["predictions", "metrics", "manifests", "reports", "failure analysis"]):
        add_pill(s, label, pt(1.6 + i * 2.05), pt(6.03), pt(1.55), tone="gold" if i == 4 else "teal")
    add_notes(s, "Artifacts make the benchmark inspectable and failure analysis makes model limitations visible at record level.")

    # 22
    s = add_slide(prs, 22, "05 Technical Readiness", "Technical Readiness Evidence", "Docker Compose local staging and evidence package support repeatable demo.")
    add_picture_fit(s, 21, "Technical System Running Checklist", pt(0.72), pt(2.05), pt(3.85), pt(3.45), badge="Runtime checklist")
    add_picture_fit(s, 22, "Evidence Package Folder Structure", pt(4.78), pt(2.05), pt(3.85), pt(3.45), badge="Evidence folder")
    add_picture_fit(s, 23, "Latest Running Test Evidence", pt(8.84), pt(2.05), pt(3.85), pt(3.45), badge="Evidence package")
    for i, label in enumerate(["/health", "/ready", "tests", "frontend build", "Docker build", "logs / artifacts"]):
        add_pill(s, label, pt(0.95 + i * 2.0), pt(5.92), pt(1.5), tone="gold" if i == 5 else "teal")
    add_notes(s, "This is demo readiness evidence, not production deployment.")

    # 23
    s = add_slide(prs, 23, "06 Research Pilot Roadmap", "Vinmec Research Pilot Roadmap", "A research-first pilot foundation before any controlled clinical workflow study.", dark=True)
    steps = ["PoC local staging", "Governance / workflow discovery", "Retrospective de-identified study", "Raw vs Structured vs RAG vs Adaptive comparison", "Clinician human evaluation", "Silent / shadow mode", "Clinician-visible usability pilot"]
    add_workflow(s, steps, pt(0.62), pt(2.5), pt(12.1), pt(1.8), dark=True)
    add_shape(s, SHAPE_ROUND_RECT, pt(0.95), pt(5.68), pt(11.5), pt(0.48), "#173A57", line="#41657D", transparency=0.08)
    add_text(s, "Governance first: no real EHR evaluation, writeback or clinical workflow use without approved data access, review protocol and audit controls.", pt(1.2), pt(5.85), pt(11.0), pt(0.12), size=10.6, color=GOLD, bold=True, align=2)
    add_notes(s, "The proposed next step is controlled research design, not uncontrolled rollout.")

    # 24
    s = add_slide(prs, 24, "06 Research Pilot Roadmap", "Risk Controls and Closing", "A research-first foundation for evidence-grounded clinical summarization — ready for controlled pilot design, not uncontrolled hospital rollout.", dark=True)
    add_shape(s, SHAPE_ROUND_RECT, pt(1.0), pt(2.2), pt(5.25), pt(3.2), "#173A57", line="#41657D", transparency=0.08)
    add_text(s, "Key risks", pt(1.35), pt(2.55), pt(4.2), pt(0.3), size=22, color=WHITE, bold=True)
    add_text(s, "• Wrong-patient evidence\n• Unsupported diagnosis\n• Medication / allergy error\n• PHI leakage\n• Over-trust", pt(1.45), pt(3.15), pt(4.2), pt(1.4), size=14, color="#EAF6FA")
    add_shape(s, SHAPE_ROUND_RECT, pt(7.0), pt(2.2), pt(5.25), pt(3.2), "#173A57", line=CYAN, transparency=0.08)
    add_text(s, "Controls", pt(7.35), pt(2.55), pt(4.2), pt(0.3), size=22, color=WHITE, bold=True)
    add_text(s, "• Patient / encounter filters\n• Citation validation\n• Unsupported-claim visibility\n• Clinician review\n• Audit trail and governance gates", pt(7.45), pt(3.15), pt(4.2), pt(1.45), size=14, color="#EAF6FA")
    add_shape(s, SHAPE_ROUND_RECT, pt(1.1), pt(6.05), pt(11.15), pt(0.48), "#173A57", line="#41657D", transparency=0.08)
    add_text(s, "Final position: a research-first pilot foundation and production-readiness roadmap — not a production clinical system.", pt(1.35), pt(6.22), pt(10.65), pt(0.12), size=11.4, color=WHITE, bold=True, align=2)
    add_notes(s, "Close by being ambitious but conservative: controlled pilot design, not uncontrolled deployment readiness.")


def main() -> int:
    app = win32com.client.DispatchEx("PowerPoint.Application")
    app.Visible = MSO_TRUE
    app.DisplayAlerts = 0
    prs = app.Presentations.Add()
    prs.PageSetup.SlideWidth = SLIDE_W
    prs.PageSetup.SlideHeight = SLIDE_H
    try:
        build_deck(prs)
        if PPTX.exists():
            PPTX.unlink()
        prs.SaveAs(str(PPTX), PP_SAVE_AS_PPTX)
        print(f"Created {PPTX}")
        return 0
    finally:
        prs.Close()
        app.Quit()


if __name__ == "__main__":
    raise SystemExit(main())
