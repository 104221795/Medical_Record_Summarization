from __future__ import annotations

import html
import posixpath
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PPTX = OUT / "Medical_Record_Summarization_Enterprise_Proposal.pptx"
PDF = OUT / "Medical_Record_Summarization_Enterprise_Proposal.pdf"
HTML = OUT / "index.html"
README = OUT / "README.md"
ASSET_DIR = OUT / "assets" / "figures"

EMU_PER_INCH = 914400
SLIDE_W = 13.333333
SLIDE_H = 7.5
SLIDE_CX = int(SLIDE_W * EMU_PER_INCH)
SLIDE_CY = int(SLIDE_H * EMU_PER_INCH)

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

NAVY = "073B4C"
TEAL = "0E8796"
DEEP_TEAL = "075E69"
MINT = "EAF7F5"
PALE = "F6FBFC"
GOLD = "D9A441"
LIGHT_GOLD = "FFF5D6"
INK = "132235"
MUTED = "60758A"
WHITE = "FFFFFF"
RED = "B42318"
GREEN = "0B7A3B"


def emu(v: float) -> int:
    return int(round(v * EMU_PER_INCH))


def xml_text(value: str) -> str:
    return escape(value, {"'": "&apos;", '"': "&quot;"})


def find_figures() -> dict[int, Path]:
    figures: dict[int, Path] = {}
    for path in ROOT.glob("**/Figure_*.png"):
        name = path.name
        try:
            number = int(name.split("_", 2)[1])
        except Exception:
            continue
        figures[number] = path
    return figures


FIG = find_figures()


@dataclass
class Element:
    kind: str
    data: dict


@dataclass
class Slide:
    title: str
    section: str
    subtitle: str | None = None
    background: str = WHITE
    elements: list[Element] = field(default_factory=list)
    notes: str = ""

    def text(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        text: str | list[str],
        *,
        size: int = 22,
        color: str = INK,
        bold: bool = False,
        fill: str | None = None,
        line: str | None = None,
        align: str = "l",
        radius: bool = False,
        margin: float = 0.08,
        name: str = "Text",
    ) -> None:
        lines = text if isinstance(text, list) else [text]
        self.elements.append(
            Element(
                "text",
                dict(
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    lines=lines,
                    size=size,
                    color=color,
                    bold=bold,
                    fill=fill,
                    line=line,
                    align=align,
                    radius=radius,
                    margin=margin,
                    name=name,
                ),
            )
        )

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: str = MINT,
        line: str | None = None,
        radius: bool = True,
    ) -> None:
        self.elements.append(Element("rect", dict(x=x, y=y, w=w, h=h, fill=fill, line=line, radius=radius)))

    def image(self, fig: int, x: float, y: float, w: float, h: float, *, caption: str | None = None) -> None:
        path = FIG.get(fig)
        self.elements.append(Element("image", dict(fig=fig, path=path, x=x, y=y, w=w, h=h, caption=caption)))

    def pill(self, x: float, y: float, w: float, text: str, *, fill: str = MINT, color: str = DEEP_TEAL) -> None:
        self.text(x, y, w, 0.32, text, size=10, color=color, bold=True, fill=fill, line=None, align="c", radius=True)


def base_slide(title: str, section: str, subtitle: str | None = None, background: str = WHITE) -> Slide:
    s = Slide(title, section, subtitle, background)
    if background == WHITE:
        s.text(0.45, 0.25, 1.6, 0.28, section, size=8, color=TEAL, bold=True)
        s.text(0.45, 0.58, 8.6, 0.55, title, size=25, color=INK, bold=True)
        if subtitle:
            s.text(0.47, 1.05, 7.7, 0.42, subtitle, size=11, color=MUTED)
        s.rect(12.55, 0.28, 0.35, 0.35, fill=MINT, line="BFE6E3")
        s.text(10.15, 0.24, 2.1, 0.28, "local staging PoC", size=8, color=MUTED, align="r")
    return s


def cards(slide: Slide, items: list[tuple[str, str, str]], x: float, y: float, w: float, h: float, cols: int = 3) -> None:
    gap = 0.16
    cw = (w - gap * (cols - 1)) / cols
    rows = (len(items) + cols - 1) // cols
    ch = (h - gap * (rows - 1)) / rows
    for i, (head, body, color) in enumerate(items):
        cx = x + (i % cols) * (cw + gap)
        cy = y + (i // cols) * (ch + gap)
        slide.rect(cx, cy, cw, ch, fill=color, line="CFE4E7")
        slide.text(cx + 0.16, cy + 0.13, cw - 0.32, 0.25, head, size=12, color=INK, bold=True)
        slide.text(cx + 0.16, cy + 0.45, cw - 0.32, ch - 0.5, body, size=9, color=MUTED)


def add_disclaimer(slide: Slide, text: str | None = None) -> None:
    slide.text(
        0.55,
        7.05,
        12.2,
        0.25,
        text
        or "Ranh giới: dữ liệu mock/de-identified/proxy; AI chỉ tạo bản nháp; bác sĩ duyệt; không chẩn đoán/tư vấn điều trị/kê đơn; không phải triển khai bệnh viện hay xác nhận an toàn/hiệu quả lâm sàng.",
        size=7,
        color=MUTED,
        align="c",
    )


def build_slides() -> list[Slide]:
    slides: list[Slide] = []

    s = Slide("Cover", "00", background=NAVY)
    s.rect(0, 0, SLIDE_W, SLIDE_H, fill=NAVY, line=NAVY, radius=False)
    s.text(0.75, 0.55, 4.6, 0.36, "enterprise-grade proposal deck", size=10, color=LIGHT_GOLD, bold=True)
    s.text(0.75, 1.25, 8.0, 0.8, "Vinmec × VinSmartFuture", size=32, color=WHITE, bold=True)
    s.text(0.75, 2.05, 9.0, 1.0, "Citation-grounded Medical Record Summarization PoC", size=28, color=WHITE, bold=True)
    s.text(
        0.78,
        3.28,
        7.2,
        0.75,
        "Evidence-first AI draft workflow with clinician review, citation validation, auditability and proxy evaluation",
        size=15,
        color="D8EEF0",
    )
    s.text(0.78, 4.55, 3.2, 0.55, "Local staging PoC", size=15, color=NAVY, bold=True, fill=LIGHT_GOLD, align="c", radius=True)
    s.text(4.2, 4.55, 3.4, 0.55, "Research/pilot foundation", size=15, color=NAVY, bold=True, fill=WHITE, align="c", radius=True)
    s.text(
        0.8,
        6.55,
        11.8,
        0.42,
        "Clinician-review-only PoC. Không hàm ý Vinmec đã phê duyệt, không phải triển khai bệnh viện, không xác nhận an toàn/hiệu quả lâm sàng.",
        size=9,
        color="D8EEF0",
        align="c",
    )
    slides.append(s)

    s = base_slide("Agenda", "01 PROPOSAL STRUCTURE", "Cấu trúc theo style enterprise proposal: vấn đề trước, giải pháp sau, rồi kỹ thuật và lộ trình.")
    agenda = [
        ("01", "Solution Introduction"),
        ("02", "Problem Assessment"),
        ("03", "Business Proposal"),
        ("04", "Technical Proposal"),
        ("05", "Delivery & Demo Readiness"),
        ("06", "Research Pilot Roadmap & Governance"),
    ]
    for i, (num, txt) in enumerate(agenda):
        x = 0.85 + (i % 3) * 4.1
        y = 1.9 + (i // 3) * 1.65
        s.rect(x, y, 3.55, 1.15, fill=Pale(i), line="CDE5E7")
        s.text(x + 0.18, y + 0.14, 0.55, 0.3, num, size=14, color=TEAL, bold=True)
        s.text(x + 0.85, y + 0.18, 2.35, 0.45, txt, size=15, color=INK, bold=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Executive Summary", "01 SOLUTION INTRODUCTION", "Một PoC có định hướng enterprise: evidence-first, review-first, audit-first.")
    cards(
        s,
        [
            ("Problem", "Hồ sơ bệnh án phân mảnh; tóm tắt thủ công tốn thời gian; generic LLM dễ bỏ sót hoặc suy diễn.", MINT),
            ("Solution", "RAG citation-grounded tạo AI draft theo patient/encounter scope, có citation validation và review workspace.", "EFF8FF"),
            ("Evidence", "Local staging PoC có UI doctor/admin, Flow 2.1 benchmark, artifacts, tests/build/runtime evidence.", "F2F6FF"),
            ("Boundary", "Chỉ dùng mock/de-identified/proxy data; clinician-review-only; không claim real EHR/clinical validation.", LIGHT_GOLD),
        ],
        0.75,
        1.75,
        11.8,
        3.2,
        cols=4,
    )
    s.text(0.9, 5.55, 11.3, 0.55, "Thông điệp chính: PoC không cố thay bác sĩ; PoC làm bằng chứng, citation và rủi ro trở nên nhìn thấy được trước khi bác sĩ quyết định.", size=15, color=DEEP_TEAL, bold=True, fill=PALE, align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Why This Matters", "02 PROBLEM ASSESSMENT", "Medical summarization không chỉ là rút gọn văn bản; đó là bài toán bằng chứng và trách nhiệm review.")
    cards(
        s,
        [
            ("Fragmented records", "Thông tin nằm rải rác giữa note, encounter, medication, timeline và prior summaries.", MINT),
            ("LLM risk", "Generic summarization có thể hallucinate, bỏ sót diagnosis/medication hoặc trộn ngữ cảnh sai bệnh nhân.", "FFF7E8"),
            ("Clinical need", "Bác sĩ cần nhìn được nguồn chứng cứ, claim nào unsupported và lịch sử ai đã duyệt/sửa.", "F2F6FF"),
        ],
        0.8,
        1.7,
        11.6,
        1.5,
        cols=3,
    )
    s.text(1.2, 4.0, 10.9, 0.95, "Thiết kế đúng không phải “AI tự kết luận”, mà là một evidence-first workflow giúp bác sĩ kiểm tra bản nháp nhanh hơn và có dấu vết kiểm toán rõ hơn.", size=22, color=WHITE, bold=True, fill=DEEP_TEAL, align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Current Challenge Assessment", "02 PROBLEM ASSESSMENT", "Bảng vấn đề chuyển thành năng lực cần có trong một PoC enterprise-grade.")
    table(
        s,
        0.65,
        1.55,
        12.0,
        4.6,
        ["Challenge", "Impact", "Required capability"],
        [
            ["Hồ sơ nhiều nguồn", "Bác sĩ mất thời gian tìm ngữ cảnh", "Patient/encounter scoping + retrieval"],
            ["Generic summary không có nguồn", "Khó tin và khó review", "Citation-first draft + evidence panel"],
            ["Unsupported claim", "Nguy cơ over-trust", "Unsupported/conflict visibility"],
            ["Benchmark chỉ ROUGE", "Không đo grounding/safety proxy", "Citation, omission, hallucination proxy"],
            ["Demo thiếu audit", "Khó bàn giao/kiểm tra", "Review lifecycle + audit trail"],
        ],
        col_widths=[3.0, 3.3, 5.7],
    )
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Proposed Solution Overview", "03 BUSINESS PROPOSAL", "Một luồng nghiệp vụ ngắn: từ scope bệnh nhân đến draft có citation và audit.")
    workflow(s, ["Patient / Encounter Scope", "Evidence Retrieval", "AI Draft", "Citation Validation", "Clinician Review", "Final Summary", "Audit"], 0.55, 2.25, 12.2)
    s.text(0.95, 4.35, 11.4, 0.85, "Giá trị business của PoC: giảm ambiguity khi review, chuẩn hóa evidence visibility, và tạo nền để đo lường pilot nghiên cứu thay vì claim triển khai lâm sàng.", size=17, color=DEEP_TEAL, bold=True, fill=PALE, align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Product Entry — Role-based Workspace", "03 BUSINESS PROPOSAL", "Entry point cho doctor/admin demo với role-based navigation.")
    s.image(1, 0.55, 1.45, 6.2, 4.5, caption="Figure 1 — Product landing page")
    s.image(2, 7.05, 1.45, 2.65, 2.05, caption="Figure 2 — Role-based login")
    s.image(4, 9.88, 1.45, 2.85, 2.05, caption="Figure 4 — Doctor workspace")
    bullets(s, 7.05, 4.05, 5.65, ["Workspace tách vai trò doctor/admin.", "Thông điệp safety boundary xuất hiện từ đầu.", "Clean text branding; không hàm ý phê duyệt chính thức."], title="Main message")
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Doctor Workflow — Patient Selection", "03 BUSINESS PROPOSAL", "Bác sĩ bắt đầu từ danh sách bệnh nhân de-identified và chọn đúng patient/encounter scope.")
    s.image(5, 0.6, 1.35, 7.4, 4.95, caption="Figure 5 — De-identified patient list")
    bullets(s, 8.35, 1.65, 4.15, ["Chỉ dùng mock/de-identified patient records.", "Search theo patient ID/hash/gender/source.", "Scope đúng bệnh nhân trước khi generate.", "Tránh trộn evidence sai bệnh nhân."], title="What it proves")
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Doctor Workflow — Clinical Context", "03 BUSINESS PROPOSAL", "Patient context gom profile, timeline, source documents và previous summaries.")
    s.image(6, 0.6, 1.35, 7.9, 4.95, caption="Figure 6 — Patient context and timeline")
    bullets(s, 8.85, 1.65, 3.75, ["Profile + encounter timeline.", "Source document list.", "Previous summary history.", "Context được xem trước generation/review."], title="Clinical context layer")
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Doctor Workflow — Generate AI Draft", "03 BUSINESS PROPOSAL", "RAG evidence-first: retrieve trước, generate sau, draft luôn cần review.")
    s.image(7, 0.55, 1.3, 8.2, 5.05, caption="Figure 7 — RAG evidence-first generate summary")
    cards(
        s,
        [
            ("1. Scope", "Patient + encounter + source document", MINT),
            ("2. Retrieve", "MiniLM + Qdrant / evidence search", "F2F6FF"),
            ("3. Draft", "Provider tạo AI-generated draft", LIGHT_GOLD),
        ],
        9.05,
        1.55,
        3.55,
        3.1,
        cols=1,
    )
    s.text(9.08, 5.1, 3.5, 0.75, "Draft only — bác sĩ review evidence trước khi approve/reject.", size=14, color=WHITE, bold=True, fill=DEEP_TEAL, align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Evidence Quality Gate", "04 TECHNICAL PROPOSAL", "Gate làm rủi ro hiển thị trước khi bác sĩ quyết định.")
    s.image(8, 0.55, 1.35, 8.1, 4.95, caption="Figure 8 — Review and evidence quality gate")
    bullets(s, 8.95, 1.65, 3.75, ["Citation coverage.", "Unsupported claims.", "Conflicts.", "Retrieval warning.", "Review status."], title="Quality signals")
    s.text(8.98, 5.3, 3.7, 0.6, "Không ép generation khi evidence yếu; cảnh báo phải visible.", size=13, color=RED, bold=True, fill="FFF0F0", align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Citation-first Review", "04 TECHNICAL PROPOSAL", "Mỗi claim quan trọng cần trace được về evidence source.")
    s.image(9, 0.55, 1.35, 5.95, 4.9, caption="Figure 9 — Citation and claim review")
    s.image(10, 6.8, 1.35, 5.95, 4.9, caption="Figure 10 — Citation tracking detail")
    s.text(1.25, 6.35, 11.0, 0.42, "Main message: citation không chỉ để trang trí; citation là cơ chế review, debug và giảm unsupported claim.", size=13, color=DEEP_TEAL, bold=True, fill=PALE, align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Human-in-the-loop Decision", "04 TECHNICAL PROPOSAL", "Bác sĩ là người quyết định cuối; AI chỉ tạo draft có thể sửa hoặc từ chối.")
    s.image(11, 0.55, 1.35, 8.0, 4.95, caption="Figure 11 — Editable draft and reject decision")
    bullets(s, 8.9, 1.55, 3.8, ["Edit draft.", "Approve draft.", "Request changes.", "Reject draft.", "Review decision captured."], title="Clinician authority")
    s.text(8.95, 5.25, 3.75, 0.72, "Không có autonomous diagnosis, treatment recommendation hoặc prescribing.", size=12, color=RED, bold=True, fill="FFF0F0", align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Summary Lifecycle and Audit", "04 TECHNICAL PROPOSAL", "Lifecycle + audit trail giúp reviewer thấy ai làm gì, khi nào, trên summary nào.")
    s.image(12, 0.55, 1.35, 5.95, 4.9, caption="Figure 12 — Patient summary history status")
    s.image(13, 6.85, 1.35, 5.75, 4.9, caption="Figure 13 — Audit history trace")
    s.text(1.0, 6.35, 11.4, 0.42, "Auditability là yêu cầu nền cho nghiên cứu/pilot: không chỉ output tốt, mà phải trace được hành động và trạng thái review.", size=13, color=DEEP_TEAL, bold=True, fill=PALE, align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("User / Role / Function Mapping", "03 BUSINESS PROPOSAL", "Map nhu cầu người dùng sang feature và giá trị đề xuất.")
    table(
        s,
        0.55,
        1.45,
        12.25,
        4.95,
        ["User", "Pain point", "Feature", "Value"],
        [
            ["Doctor", "Mất thời gian đọc record dài", "Citation-grounded draft + review", "Review nhanh hơn, evidence visible"],
            ["Admin", "Khó nhìn benchmark/provider", "Admin evaluation dashboards", "Theo dõi readiness và artifacts"],
            ["Technical Reviewer", "Cần kiểm chứng runtime", "Docker/test/build evidence", "Demo readiness rõ ràng"],
            ["Research Evaluator", "Cần proxy metrics sâu", "ROUGE, BERTScore, grounding, omission", "Đánh giá có chiều nghiên cứu"],
            ["Mentor/Reviewer", "Cần câu chuyện end-to-end", "Proposal deck + evidence package", "Dễ review nhanh và phản biện"],
        ],
        col_widths=[1.55, 3.1, 3.5, 4.1],
        font=8,
    )
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Technical Architecture", "04 TECHNICAL PROPOSAL", "Kiến trúc staging demo: frontend, FastAPI, services, storage/artifacts và worker.")
    arch(s)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("RAG and Citation Pipeline", "04 TECHNICAL PROPOSAL", "RAG trong bài toán này là hạ tầng bằng chứng, không chỉ là cách gọi LLM.")
    workflow(s, ["Clinical note", "Patient / encounter scope", "Chunking", "Retrieval", "Context builder", "Provider", "Citation matching", "Safety metrics", "Clinician review"], 0.45, 1.85, 12.4, compact=True)
    cards(
        s,
        [
            ("Chunking", "Tách note dài thành đoạn có thể retrieve và cite.", MINT),
            ("Embedding/Qdrant", "Lưu vector để truy xuất evidence theo meaning, không chỉ keyword.", "F2F6FF"),
            ("Citation validation", "So khớp claim với source excerpt và flag unsupported.", LIGHT_GOLD),
        ],
        0.85,
        4.2,
        11.6,
        1.35,
        cols=3,
    )
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Evaluation Framework", "04 TECHNICAL PROPOSAL", "Proxy evaluation phải đo cả chất lượng summary lẫn evidence grounding.")
    metrics = [
        ("ROUGE-L", "Similarity proxy"),
        ("BERTScore", "Semantic similarity"),
        ("Citation coverage", "Evidence coverage"),
        ("Unsupported claim rate", "Safety proxy"),
        ("Factuality proxy", "Grounding quality"),
        ("Timeline completeness", "Clinical structure"),
        ("Hallucination proxy", "Unsupported content"),
        ("Critical omission proxy", "Missing key facts"),
    ]
    cards(s, [(a, b, MINT if i % 2 == 0 else "F2F6FF") for i, (a, b) in enumerate(metrics)], 0.6, 1.55, 7.2, 4.7, cols=2)
    s.image(14, 8.1, 1.55, 4.5, 3.35, caption="Figure 14 — Admin evaluation readiness")
    s.text(8.25, 5.2, 4.1, 0.6, "Không chỉ ROUGE/BERTScore: citation và unsupported claim là phần bắt buộc trong medical summarization proxy evaluation.", size=12, color=DEEP_TEAL, bold=True, fill=PALE, align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Benchmark Result Summary", "04 TECHNICAL PROPOSAL", "Flow 2.1 no-gate: 50 records × 5 providers = 250/250 predictions.")
    s.image(16, 0.65, 1.35, 5.6, 4.25, caption="Figure 16 — Provider ROUGE leaderboard")
    table(
        s,
        6.55,
        1.42,
        5.95,
        3.35,
        ["Qwen2.5 metric", "Value"],
        [
            ["ROUGE-L", "0.2122"],
            ["BERTScore F1", "0.8391"],
            ["Citation coverage", "0.8884"],
            ["Factuality proxy", "0.8713"],
            ["Critical omission", "0.4460"],
        ],
        col_widths=[3.1, 2.85],
        font=10,
    )
    bullets(s, 6.55, 5.05, 5.95, ["Qwen2.5 là strongest generative PoC provider trong proxy run.", "Deterministic là smoke/control provider đáng tin cậy nhất.", "Kết quả là proxy evaluation, không phải clinical validation."], title="Interpretation")
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Admin Evaluation Dashboard", "05 DELIVERY & DEMO READINESS", "Admin nhìn được Flow 2.1 benchmark visibility và provider completion.")
    s.image(15, 0.55, 1.25, 8.2, 5.15, caption="Figure 15 — RAG best models admin overview")
    bullets(s, 9.0, 1.65, 3.65, ["5/5 target providers found.", "Provider completion visible.", "ROUGE/BERTScore/citation summary visible.", "Artifacts path visible for reproducibility."], title="Admin value")
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Grounding Metrics and Error Analysis", "05 DELIVERY & DEMO READINESS", "Không chỉ biết model nào thắng; reviewer thấy vì sao model fail.")
    s.image(17, 0.55, 1.35, 5.8, 4.9, caption="Figure 17 — Evidence grounding metrics")
    s.image(19, 6.65, 1.35, 5.9, 4.9, caption="Figure 19 — Per-record failure analysis")
    s.text(0.95, 6.35, 11.6, 0.42, "Error analysis giúp chuyển benchmark thành research discussion: omission, hallucination proxy, retrieval failure, source limitation.", size=13, color=DEEP_TEAL, bold=True, fill=PALE, align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("RAG vs Raw Context Comparison", "05 DELIVERY & DEMO READINESS", "Raw có thể tốt với note ngắn; RAG hữu ích hơn khi cần evidence-first, multi-document và citation review.")
    s.image(18, 0.55, 1.35, 8.2, 5.05, caption="Figure 18 — RAG vs raw/context comparison")
    bullets(s, 9.05, 1.65, 3.55, ["RAG là evidence infrastructure.", "Raw context vẫn là baseline hữu ích.", "Adaptive strategy nên được nghiên cứu ở pilot.", "Không claim RAG luôn tốt hơn mọi trường hợp."], title="Balanced interpretation")
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Reproducibility and Artifacts", "05 DELIVERY & DEMO READINESS", "Benchmark không chỉ là screenshot; artifacts giúp reviewer kiểm tra lại.")
    s.image(20, 0.55, 1.3, 5.8, 4.95, caption="Figure 20 — RAG benchmark artifacts and run files")
    s.image(22, 6.65, 1.3, 2.85, 2.2, caption="Figure 22 — Evidence package folder")
    s.image(23, 9.75, 1.3, 2.85, 2.2, caption="Figure 23 — Latest running evidence")
    bullets(s, 6.65, 3.9, 5.95, ["Prediction JSONL, metrics CSV, manifests.", "Health/readiness responses.", "Backend/frontend/docker logs.", "Evidence package supports repeatability."], title="Artifact package")
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Demo Staging Architecture", "05 DELIVERY & DEMO READINESS", "Docker Compose local staging path validates app, worker, PostgreSQL, Redis, /health và /ready.")
    s.image(21, 0.75, 1.35, 5.0, 4.7, caption="Figure 21 — Technical system running checklist")
    arch_compose(s, 6.2, 1.55)
    s.text(6.35, 5.78, 5.75, 0.45, "Runtime proof supports demo readiness only; not public hospital deployment.", size=12, color=DEEP_TEAL, bold=True, fill=PALE, align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Delivery Schedule", "05 DELIVERY & DEMO READINESS", "Timeline Week 1–Week 6 theo artifact/delivery hiện tại.")
    timeline(s, [
        ("Week 1", "BART/Pegasus Evaluation & UI"),
        ("Week 2", "Weekly review + demo preparation"),
        ("Week 3", "PRD & workflow"),
        ("Week 4", "EHR/proxy dataset + PoC integration"),
        ("Week 5", "Summarization baseline + benchmark"),
        ("Week 6", "Citation pipeline + evaluation completion"),
    ])
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Vinmec Research Pilot Appendix", "06 RESEARCH PILOT ROADMAP & GOVERNANCE", "Bước hợp lý là research-first pilot, không phải rollout hospital workflow.")
    workflow(s, ["PoC local staging", "Governance / workflow discovery", "Retrospective de-identified study", "Raw / Structured / RAG / Adaptive comparison", "Clinician human evaluation", "Silent / shadow mode", "Clinician-visible usability pilot"], 0.55, 1.8, 12.1, compact=True)
    cards(
        s,
        [
            ("Governance first", "Dữ liệu, pháp lý, DPO/IRB và access control phải rõ trước khi study.", MINT),
            ("Evaluation first", "Rubric bác sĩ + stratified error analysis trước khi bàn clinical workflow.", "F2F6FF"),
            ("No writeback", "Không writeback EMR/FHIR trước khi có approval, audit và safety gates.", LIGHT_GOLD),
        ],
        0.85,
        4.25,
        11.6,
        1.35,
        cols=3,
    )
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Limitations and Risk Controls", "06 RESEARCH PILOT ROADMAP & GOVERNANCE", "Risk table cho proposal enterprise: mitigation rõ, limitation còn lại rõ.")
    table(
        s,
        0.55,
        1.35,
        12.25,
        5.05,
        ["Risk", "Mitigation", "Remaining limitation"],
        [
            ["Wrong-patient evidence", "Patient/encounter scope + audit", "Cần kiểm thử real workflow"],
            ["Unsupported diagnosis", "Unsupported/conflict flag", "Proxy metric chưa thay bác sĩ"],
            ["Medication/allergy error", "Citation review + critical omission proxy", "Cần human clinical rubric"],
            ["PHI leakage", "Mock/de-identified data + private-by-default", "Cần governance trước real data"],
            ["Over-trust", "Draft-only UI + reviewer action", "Cần training và policy"],
            ["Citation mismatch", "Citation matching + evidence panel", "Cần manual validation sample"],
        ],
        col_widths=[3.0, 4.6, 4.65],
        font=8,
    )
    add_disclaimer(s)
    slides.append(s)

    s = base_slide("Roadmap and Conclusion", "06 RESEARCH PILOT ROADMAP & GOVERNANCE", "Kết luận bảo thủ: tăng evidence, human review và governance trước khi mở rộng.")
    cards(
        s,
        [
            ("1. Final demo evidence", "Record demo + package logs/screenshots/artifacts.", MINT),
            ("2. Human evaluation", "Rubric bác sĩ, blinded samples, disagreement review.", "F2F6FF"),
            ("3. Data diversity", "Stratified error analysis theo note type, specialty, length.", MINT),
            ("4. Adaptive routing", "So sánh Raw / Structured / RAG / Adaptive.", "F2F6FF"),
            ("5. Optional public demo", "Chỉ khi resources/governance cho phép.", LIGHT_GOLD),
            ("6. Real EHR study", "Chỉ dưới approved governance, de-identification và audit.", LIGHT_GOLD),
        ],
        0.65,
        1.55,
        12.05,
        3.65,
        cols=3,
    )
    s.text(1.0, 5.75, 11.3, 0.62, "Final positioning: local staging demo-ready PoC + production-readiness roadmap + research/pilot foundation.", size=17, color=WHITE, bold=True, fill=DEEP_TEAL, align="c", radius=True)
    add_disclaimer(s)
    slides.append(s)

    s = Slide("Q&A", "END", background=NAVY)
    s.rect(0, 0, SLIDE_W, SLIDE_H, fill=NAVY, line=NAVY, radius=False)
    s.text(0.8, 0.75, 3.8, 0.32, "Q&A", size=13, color=LIGHT_GOLD, bold=True)
    s.text(0.8, 1.65, 8.6, 0.75, "Discussion focus", size=34, color=WHITE, bold=True)
    cards(
        s,
        [
            ("Scope", "PoC evidence-first, not clinical deployment.", "0C4F5C"),
            ("Evaluation", "Proxy metrics + clinician rubric next.", "0C4F5C"),
            ("Governance", "Real data only under approved process.", "0C4F5C"),
        ],
        0.85,
        3.0,
        11.6,
        1.35,
        cols=3,
    )
    s.text(0.8, 6.45, 11.7, 0.35, "Thank you — cảm ơn thầy/cô và mentor đã review.", size=13, color="D8EEF0", align="c")
    slides.append(s)

    return slides


def Pale(i: int) -> str:
    return [MINT, "F2F6FF", LIGHT_GOLD, "EEF9FF", "F7FBF9", "FFF8EF"][i % 6]


def bullets(slide: Slide, x: float, y: float, w: float, items: list[str], *, title: str) -> None:
    slide.rect(x, y, w, 3.0, fill=PALE, line="CFE4E7")
    slide.text(x + 0.18, y + 0.16, w - 0.36, 0.28, title, size=13, color=INK, bold=True)
    slide.text(x + 0.2, y + 0.55, w - 0.4, 2.2, [f"• {item}" for item in items], size=10, color=MUTED)


def table(slide: Slide, x: float, y: float, w: float, h: float, headers: list[str], rows: list[list[str]], *, col_widths: list[float], font: int = 9) -> None:
    header_h = 0.45
    row_h = (h - header_h) / len(rows)
    scale = w / sum(col_widths)
    col_w = [cw * scale for cw in col_widths]
    cx = x
    for j, head in enumerate(headers):
        slide.text(cx, y, col_w[j], header_h, head, size=font + 1, color=WHITE, bold=True, fill=DEEP_TEAL, align="c", line=DEEP_TEAL)
        cx += col_w[j]
    for i, row in enumerate(rows):
        cx = x
        fill = PALE if i % 2 == 0 else WHITE
        for j, cell in enumerate(row):
            slide.text(cx, y + header_h + i * row_h, col_w[j], row_h, cell, size=font, color=INK if j == 0 else MUTED, bold=(j == 0), fill=fill, line="D8E8EA")
            cx += col_w[j]


def workflow(slide: Slide, steps: list[str], x: float, y: float, w: float, *, compact: bool = False) -> None:
    gap = 0.08 if compact else 0.12
    box_w = (w - gap * (len(steps) - 1)) / len(steps)
    box_h = 0.82 if compact else 0.95
    for i, step in enumerate(steps):
        cx = x + i * (box_w + gap)
        fill = MINT if i % 2 == 0 else "F2F6FF"
        if i in {2, 5}:
            fill = LIGHT_GOLD
        slide.text(cx, y, box_w, box_h, step, size=8 if compact else 10, color=INK, bold=True, fill=fill, line="CDE5E7", align="c", radius=True)
        if i < len(steps) - 1:
            slide.text(cx + box_w - 0.05, y + box_h / 2 - 0.1, 0.18, 0.25, "→", size=13, color=TEAL, bold=True, align="c")


def arch(slide: Slide) -> None:
    layers = [
        ("Frontend", "React/Vite\nDoctor/Admin UI"),
        ("Backend/API", "FastAPI\nAuth, routes, state"),
        ("RAG/Citation/Safety", "Retrieval\nCitation validation\nUnsupported claim flags"),
        ("Data/Runtime", "PostgreSQL\nArtifacts\nRedis/RQ worker"),
    ]
    x = 0.65
    y = 2.0
    for i, (head, body) in enumerate(layers):
        cx = x + i * 3.15
        fill = [MINT, "F2F6FF", LIGHT_GOLD, PALE][i]
        slide.text(cx, y, 2.65, 1.25, [head, body], size=12, color=INK, bold=True, fill=fill, line="CFE4E7", align="c", radius=True)
        if i < len(layers) - 1:
            slide.text(cx + 2.72, y + 0.45, 0.35, 0.3, "→", size=22, color=TEAL, bold=True, align="c")
    slide.text(0.9, 4.3, 11.5, 0.7, "Boundary: local staging architecture prepared for demo evidence; public cloud deployment and real EHR integration are future/governed work.", size=15, color=DEEP_TEAL, bold=True, fill=PALE, align="c", radius=True)


def arch_compose(slide: Slide, x: float, y: float) -> None:
    boxes = [
        ("app", "FastAPI + static frontend\n/health, /ready"),
        ("worker", "RQ background worker\njob readiness"),
        ("db", "PostgreSQL\nmetadata/state"),
        ("redis", "Queue backend\nworker coordination"),
    ]
    for i, (head, body) in enumerate(boxes):
        cx = x + (i % 2) * 3.1
        cy = y + (i // 2) * 1.45
        slide.text(cx, cy, 2.75, 1.05, [head, body], size=11, color=INK, bold=True, fill=MINT if i % 2 == 0 else "F2F6FF", line="CFE4E7", align="c", radius=True)
    slide.text(x, y + 3.15, 5.85, 0.45, "Evidence: HTTP 200 health/ready + tests/build logs + Docker image.", size=11, color=DEEP_TEAL, bold=True, fill=PALE, align="c", radius=True)


def timeline(slide: Slide, items: list[tuple[str, str]]) -> None:
    y = 2.0
    for i, (week, desc) in enumerate(items):
        x = 0.75 + i * 2.05
        slide.text(x, y, 1.55, 0.45, week, size=13, color=WHITE, bold=True, fill=DEEP_TEAL, align="c", radius=True)
        slide.text(x - 0.12, y + 0.62, 1.8, 1.3, desc, size=9, color=INK, fill=Pale(i), line="CFE4E7", align="c", radius=True)
        if i < len(items) - 1:
            slide.text(x + 1.62, y + 0.1, 0.35, 0.3, "→", size=18, color=TEAL, bold=True, align="c")
    slide.text(0.9, 5.25, 11.3, 0.62, "Delivery narrative: UI + workflow + proxy data + RAG benchmark + citation/evaluation completion.", size=15, color=DEEP_TEAL, bold=True, fill=PALE, align="c", radius=True)


def shape_xml(idx: int, el: Element) -> str:
    d = el.data
    x, y, w, h = map(emu, [d["x"], d["y"], d["w"], d["h"]])
    prst = "roundRect" if d.get("radius") else "rect"
    fill = d.get("fill")
    line = d.get("line")
    fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
    line_xml = f'<a:ln w="6350"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>' if line else '<a:ln><a:noFill/></a:ln>'
    return f"""
<p:sp>
  <p:nvSpPr><p:cNvPr id="{idx}" name="Shape {idx}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="{prst}"><a:avLst/></a:prstGeom>{fill_xml}{line_xml}</p:spPr>
</p:sp>"""


def text_xml(idx: int, el: Element) -> str:
    d = el.data
    x, y, w, h = map(emu, [d["x"], d["y"], d["w"], d["h"]])
    prst = "roundRect" if d.get("radius") else "rect"
    fill = d.get("fill")
    line = d.get("line")
    fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
    line_xml = f'<a:ln w="6350"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>' if line else '<a:ln><a:noFill/></a:ln>'
    margin = emu(d.get("margin", 0.08))
    paras = []
    for line_text in d["lines"]:
        safe = xml_text(str(line_text))
        b = ' b="1"' if d.get("bold") else ""
        align = d.get("align", "l")
        paras.append(
            f'<a:p><a:pPr algn="{align}"/><a:r><a:rPr lang="vi-VN" sz="{int(d["size"]*100)}"{b}><a:solidFill><a:srgbClr val="{d["color"]}"/></a:solidFill><a:latin typeface="Arial"/><a:ea typeface="Arial"/><a:cs typeface="Arial"/></a:rPr><a:t>{safe}</a:t></a:r><a:endParaRPr lang="vi-VN" sz="{int(d["size"]*100)}"/></a:p>'
        )
    return f"""
<p:sp>
  <p:nvSpPr><p:cNvPr id="{idx}" name="{xml_text(d.get('name','Text'))} {idx}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm><a:prstGeom prst="{prst}"><a:avLst/></a:prstGeom>{fill_xml}{line_xml}</p:spPr>
  <p:txBody><a:bodyPr wrap="square" lIns="{margin}" rIns="{margin}" tIns="{margin}" bIns="{margin}"><a:spAutoFit/></a:bodyPr><a:lstStyle/>{''.join(paras)}</p:txBody>
</p:sp>"""


def image_xml(idx: int, rid: str, path: Path | None, box: tuple[float, float, float, float]) -> str:
    x, y, w, h = fit_image(path, *box) if path else box
    x_e, y_e, w_e, h_e = map(emu, [x, y, w, h])
    return f"""
<p:pic>
  <p:nvPicPr><p:cNvPr id="{idx}" name="Figure {idx}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>
  <p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
  <p:spPr><a:xfrm><a:off x="{x_e}" y="{y_e}"/><a:ext cx="{w_e}" cy="{h_e}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:ln><a:solidFill><a:srgbClr val="D8E8EA"/></a:solidFill></a:ln></p:spPr>
</p:pic>"""


def fit_image(path: Path | None, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
    if not path or not path.exists():
        return x, y, w, h
    with Image.open(path) as img:
        iw, ih = img.size
    ratio = min(w / iw, h / ih)
    nw, nh = iw * ratio, ih * ratio
    return x + (w - nw) / 2, y + (h - nh) / 2, nw, nh


def slide_xml(slide: Slide, slide_no: int, media_counter: list[int]) -> tuple[str, str, list[tuple[Path, str]]]:
    elems = []
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
    ]
    media: list[tuple[Path, str]] = []
    shape_id = 2
    # background
    elems.append(shape_xml(shape_id, Element("rect", dict(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=slide.background, line=slide.background, radius=False))))
    shape_id += 1
    for el in slide.elements:
        if el.kind == "rect":
            elems.append(shape_xml(shape_id, el))
            shape_id += 1
        elif el.kind == "text":
            elems.append(text_xml(shape_id, el))
            shape_id += 1
        elif el.kind == "image":
            path = el.data.get("path")
            if path and Path(path).exists():
                media_counter[0] += 1
                media_name = f"image{media_counter[0]}.png"
                rid = f"rId{len(rels)+1}"
                rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{media_name}"/>')
                media.append((Path(path), media_name))
                elems.append(image_xml(shape_id, rid, Path(path), (el.data["x"], el.data["y"], el.data["w"], el.data["h"])))
                shape_id += 1
                if el.data.get("caption"):
                    cap = Element("text", dict(x=el.data["x"], y=el.data["y"] + el.data["h"] + 0.05, w=el.data["w"], h=0.22, lines=[el.data["caption"]], size=7, color=MUTED, bold=False, fill=None, line=None, align="c", radius=False, margin=0.02, name="Caption"))
                    elems.append(text_xml(shape_id, cap))
                    shape_id += 1
            else:
                placeholder = Element("text", dict(x=el.data["x"], y=el.data["y"], w=el.data["w"], h=el.data["h"], lines=[f"Missing Figure {el.data.get('fig')}"], size=14, color=RED, bold=True, fill="FFF0F0", line=RED, align="c", radius=True, margin=0.08, name="Missing"))
                elems.append(text_xml(shape_id, placeholder))
                shape_id += 1
    xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="{NS["a"]}" xmlns:r="{NS["r"]}" xmlns:p="{NS["p"]}">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {''.join(elems)}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>'''
    rel_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{''.join(rels)}</Relationships>'''
    return xml, rel_xml, media


def build_pptx(slides: list[Slide]) -> None:
    media_counter = [0]
    with zipfile.ZipFile(PPTX, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types(len(slides)))
        z.writestr("_rels/.rels", package_rels())
        z.writestr("docProps/core.xml", core_props())
        z.writestr("docProps/app.xml", app_props(len(slides)))
        z.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slides)))
        z.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels())
        z.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels())
        z.writestr("ppt/theme/theme1.xml", theme_xml())
        z.writestr("ppt/presProps.xml", pres_props())
        z.writestr("ppt/viewProps.xml", view_props())
        z.writestr("ppt/tableStyles.xml", table_styles())
        written_media: dict[Path, str] = {}
        for i, slide in enumerate(slides, start=1):
            sx, rx, media = slide_xml(slide, i, media_counter)
            z.writestr(f"ppt/slides/slide{i}.xml", sx)
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", rx)
            for src, name in media:
                if name not in written_media.values():
                    z.write(src, f"ppt/media/{name}")


def rgb(hex_color: str) -> int:
    value = hex_color.strip("#")
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return r + (g << 8) + (b << 16)


def build_pptx_powerpoint(slides: list[Slide]) -> bool:
    """Build an editable PPTX through native PowerPoint COM when available."""
    try:
        import pythoncom
        import win32com.client
    except Exception:
        return False

    pythoncom.CoInitialize()
    pp = None
    pres = None
    try:
        pp = win32com.client.DispatchEx("PowerPoint.Application")
        pp.Visible = True
        pres = pp.Presentations.Add()
        pres.PageSetup.SlideWidth = SLIDE_W * 72
        pres.PageSetup.SlideHeight = SLIDE_H * 72

        pp_layout_blank = 12
        mso_shape_rect = 1
        mso_shape_round_rect = 5
        mso_text_horizontal = 1
        mso_true = -1
        mso_false = 0
        pp_align = {"l": 1, "c": 2, "r": 3}

        def add_rect(slide_obj, x, y, w, h, fill, line=None, rounded=False):
            shape_type = mso_shape_round_rect if rounded else mso_shape_rect
            shp = slide_obj.Shapes.AddShape(shape_type, x * 72, y * 72, w * 72, h * 72)
            shp.Fill.Visible = mso_true
            shp.Fill.ForeColor.RGB = rgb(fill)
            if line:
                shp.Line.Visible = mso_true
                shp.Line.ForeColor.RGB = rgb(line)
                shp.Line.Weight = 0.75
            else:
                shp.Line.Visible = mso_false
            return shp

        def add_text(slide_obj, d):
            x, y, w, h = d["x"], d["y"], d["w"], d["h"]
            fill = d.get("fill")
            line = d.get("line")
            rounded = bool(d.get("radius"))
            if fill or line:
                shp = add_rect(slide_obj, x, y, w, h, fill or WHITE, line, rounded)
            else:
                shp = slide_obj.Shapes.AddTextbox(mso_text_horizontal, x * 72, y * 72, w * 72, h * 72)
                shp.Fill.Visible = mso_false
                shp.Line.Visible = mso_false
            text = "\r".join(str(item) for item in d["lines"])
            shp.TextFrame.WordWrap = mso_true
            shp.TextFrame.MarginLeft = d.get("margin", 0.08) * 72
            shp.TextFrame.MarginRight = d.get("margin", 0.08) * 72
            shp.TextFrame.MarginTop = d.get("margin", 0.08) * 72
            shp.TextFrame.MarginBottom = d.get("margin", 0.08) * 72
            tr = shp.TextFrame.TextRange
            tr.Text = text
            tr.Font.Name = "Arial"
            tr.Font.Size = d["size"]
            tr.Font.Color.RGB = rgb(d["color"])
            tr.Font.Bold = mso_true if d.get("bold") else mso_false
            tr.ParagraphFormat.Alignment = pp_align.get(d.get("align", "l"), 1)
            return shp

        def add_image(slide_obj, d):
            path = d.get("path")
            if path and Path(path).exists():
                fx, fy, fw, fh = fit_image(Path(path), d["x"], d["y"], d["w"], d["h"])
                slide_obj.Shapes.AddPicture(str(Path(path).resolve()), mso_false, mso_true, fx * 72, fy * 72, fw * 72, fh * 72)
                if d.get("caption"):
                    add_text(
                        slide_obj,
                        dict(
                            x=d["x"],
                            y=d["y"] + d["h"] + 0.05,
                            w=d["w"],
                            h=0.22,
                            lines=[d["caption"]],
                            size=7,
                            color=MUTED,
                            bold=False,
                            fill=None,
                            line=None,
                            align="c",
                            radius=False,
                            margin=0.02,
                        ),
                    )
            else:
                add_text(
                    slide_obj,
                    dict(
                        x=d["x"],
                        y=d["y"],
                        w=d["w"],
                        h=d["h"],
                        lines=[f"Missing Figure {d.get('fig')}"],
                        size=14,
                        color=RED,
                        bold=True,
                        fill="FFF0F0",
                        line=RED,
                        align="c",
                        radius=True,
                        margin=0.08,
                    ),
                )

        for idx, slide in enumerate(slides, start=1):
            slide_obj = pres.Slides.Add(idx, pp_layout_blank)
            add_rect(slide_obj, 0, 0, SLIDE_W, SLIDE_H, slide.background, slide.background)
            for el in slide.elements:
                if el.kind == "rect":
                    d = el.data
                    add_rect(slide_obj, d["x"], d["y"], d["w"], d["h"], d["fill"], d.get("line"), bool(d.get("radius")))
                elif el.kind == "text":
                    add_text(slide_obj, el.data)
                elif el.kind == "image":
                    add_image(slide_obj, el.data)

        if PPTX.exists():
            PPTX.unlink()
        if PDF.exists():
            PDF.unlink()
        pres.SaveAs(str(PPTX.resolve()))
        pres.SaveAs(str(PDF.resolve()), 32)
        return True
    finally:
        if pres is not None:
            pres.Close()
        if pp is not None:
            pp.Quit()
        pythoncom.CoUninitialize()


def content_types(count: int) -> str:
    slides = "\n".join(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' for i in range(1, count + 1))
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>
<Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>
<Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>
{slides}
</Types>'''


def package_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def presentation_xml(count: int) -> str:
    ids = "\n".join(f'<p:sldId id="{255+i}" r:id="rId{1+i}"/>' for i in range(1, count + 1))
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="{NS["a"]}" xmlns:r="{NS["r"]}" xmlns:p="{NS["p"]}">
<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
<p:sldIdLst>{ids}</p:sldIdLst>
<p:sldSz cx="{SLIDE_CX}" cy="{SLIDE_CY}" type="screen16x9"/>
<p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>'''


def presentation_rels(count: int) -> str:
    rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>']
    for i in range(1, count + 1):
        rels.append(f'<Relationship Id="rId{1+i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>')
    rels.extend([
        f'<Relationship Id="rId{count+2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>',
        f'<Relationship Id="rId{count+3}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps" Target="viewProps.xml"/>',
        f'<Relationship Id="rId{count+4}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>',
    ])
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{''.join(rels)}</Relationships>'''


def slide_master_xml() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="{NS["a"]}" xmlns:r="{NS["r"]}" xmlns:p="{NS["p"]}">
<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>'''


def slide_master_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>'''


def slide_layout_xml() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="{NS["a"]}" xmlns:r="{NS["r"]}" xmlns:p="{NS["p"]}" type="blank" preserve="1">
<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>'''


def slide_layout_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>'''


def theme_xml() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="{NS["a"]}" name="Clinical Enterprise">
<a:themeElements>
<a:clrScheme name="Clinical Enterprise">
<a:dk1><a:srgbClr val="{INK}"/></a:dk1><a:lt1><a:srgbClr val="{WHITE}"/></a:lt1>
<a:dk2><a:srgbClr val="{NAVY}"/></a:dk2><a:lt2><a:srgbClr val="{PALE}"/></a:lt2>
<a:accent1><a:srgbClr val="{TEAL}"/></a:accent1><a:accent2><a:srgbClr val="{GOLD}"/></a:accent2>
<a:accent3><a:srgbClr val="{DEEP_TEAL}"/></a:accent3><a:accent4><a:srgbClr val="{MINT}"/></a:accent4>
<a:accent5><a:srgbClr val="{RED}"/></a:accent5><a:accent6><a:srgbClr val="{MUTED}"/></a:accent6>
<a:hlink><a:srgbClr val="{TEAL}"/></a:hlink><a:folHlink><a:srgbClr val="{DEEP_TEAL}"/></a:folHlink>
</a:clrScheme>
<a:fontScheme name="Clinical Fonts"><a:majorFont><a:latin typeface="Arial"/><a:ea typeface="Arial"/><a:cs typeface="Arial"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/><a:ea typeface="Arial"/><a:cs typeface="Arial"/></a:minorFont></a:fontScheme>
<a:fmtScheme name="Clinical Format"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:gradFill rotWithShape="1"/><a:gradFill rotWithShape="1"/></a:fillStyleLst><a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln><a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle/><a:effectStyle/><a:effectStyle/></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
</a:themeElements>
</a:theme>'''


def core_props() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>Medical Record Summarization Enterprise Proposal</dc:title><dc:creator>Codex</dc:creator><cp:keywords>clinical summarization, RAG, citation, PoC</cp:keywords><dc:description>Vietnamese enterprise-grade proposal deck for local staging PoC.</dc:description></cp:coreProperties>'''


def app_props(count: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft PowerPoint</Application><PresentationFormat>On-screen Show (16:9)</PresentationFormat><Slides>{count}</Slides><Company>Vinmec × VinSmartFuture proposal framing</Company></Properties>'''


def pres_props() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentationPr xmlns:p="{NS["p"]}"/>'''


def view_props() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:viewPr xmlns:p="{NS["p"]}" xmlns:a="{NS["a"]}"><p:normalViewPr/></p:viewPr>'''


def table_styles() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:tblStyleLst xmlns:a="{NS["a"]}" def="{{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}}"/>'''


def copy_assets(slides: list[Slide]) -> dict[int, str]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    used: dict[int, str] = {}
    for slide in slides:
        for el in slide.elements:
            if el.kind == "image":
                fig = el.data["fig"]
                path = el.data.get("path")
                if path and Path(path).exists():
                    name = f"Figure_{fig:02d}.png"
                    shutil.copy2(path, ASSET_DIR / name)
                    used[fig] = f"assets/figures/{name}"
    return used


def build_html(slides: list[Slide]) -> None:
    used = copy_assets(slides)
    sections = []
    for i, slide in enumerate(slides, start=1):
        media = []
        for el in slide.elements:
            if el.kind == "image" and el.data["fig"] in used:
                media.append(f'<img src="{html.escape(used[el.data["fig"]])}" alt="Figure {el.data["fig"]}">')
        bullets_html = f"<p>{html.escape(slide.subtitle or '')}</p>" if slide.subtitle else ""
        sections.append(
            f'''<section class="slide {'dark' if slide.background == NAVY else ''}">
<div class="kicker">{html.escape(slide.section)}</div>
<h1>{html.escape(slide.title)}</h1>
{bullets_html}
<div class="media">{''.join(media[:3])}</div>
<div class="foot">Clinician-review-only PoC • proxy/de-identified data • not clinical deployment</div>
</section>'''
        )
    HTML.write_text(
        f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Medical Record Summarization Enterprise Proposal</title>
<style>
@page {{ size: 16in 9in; margin: 0; }}
body {{ margin:0; background:#eef6f8; font-family: Arial, sans-serif; color:#132235; }}
.slide {{ width: 16in; height: 9in; box-sizing:border-box; padding:0.7in; page-break-after:always; background:#fff; position:relative; overflow:hidden; }}
.slide.dark {{ background:#073B4C; color:white; }}
.kicker {{ color:#0E8796; font-weight:800; letter-spacing:.08em; font-size:14px; }}
.dark .kicker {{ color:#FFF5D6; }}
h1 {{ font-size:42px; margin:.18in 0 .12in; line-height:1.05; }}
p {{ font-size:20px; max-width:10in; color:#60758A; }}
.dark p {{ color:#d8eef0; }}
.media {{ display:flex; gap:.18in; align-items:center; margin-top:.35in; }}
.media img {{ max-width:4.8in; max-height:4.2in; border:1px solid #d8e8ea; border-radius:12px; object-fit:contain; background:white; }}
.foot {{ position:absolute; bottom:.28in; left:.7in; right:.7in; text-align:center; font-size:12px; color:#60758A; }}
.dark .foot {{ color:#d8eef0; }}
</style></head><body>{''.join(sections)}</body></html>''',
        encoding="utf-8-sig",
    )


def build_readme(slides: list[Slide]) -> None:
    used_figs = sorted({el.data["fig"] for s in slides for el in s.elements if el.kind == "image" and el.data.get("path")})
    missing = sorted({el.data["fig"] for s in slides for el in s.elements if el.kind == "image" and not el.data.get("path")})
    slide_list = "\n".join(f"{i}. {s.title}" for i, s in enumerate(slides, start=1))
    README.write_text(
        f"""# Medical Record Summarization Enterprise Proposal Deck

Vietnamese enterprise-grade proposal deck for:

**Vinmec × VinSmartFuture — Citation-grounded Medical Record Summarization PoC**

This is a local staging PoC / research-pilot foundation deck. It does not claim production clinical deployment, real EHR validation, clinical safety, or clinical effectiveness.

## Created files

- `Medical_Record_Summarization_Enterprise_Proposal.pptx` — editable 16:9 presentation.
- `Medical_Record_Summarization_Enterprise_Proposal.pdf` — generated if local export succeeds.
- `index.html` — polished HTML backup for browser/PDF printing.
- `assets/figures/` — copied screenshots used by the HTML backup.
- `build_deck.py` — reproducible deck generator.

## Slide list

{slide_list}

## Images used

{', '.join(f'Figure {i}' for i in used_figs)}

## Missing images/placeholders

{', '.join(f'Figure {i}' for i in missing) if missing else 'None. Figure 1–23 inputs used where relevant.'}

## Sources

- `docs/proposal/MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md`
- `docs/research/VINMEC_MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md`
- `ảnh artifacts/FIGURE_INDEX.md`

## Export guidance

Open the PPTX in Microsoft PowerPoint and export to PDF using **File → Export → Create PDF/XPS** if automated export is unavailable. The `index.html` file can also be opened in Edge/Chrome and printed to PDF.

Safety wording is intentionally conservative: clinician-review-only AI drafts, mock/de-identified/proxy data, no autonomous diagnosis, no treatment recommendation, no prescribing, no hospital deployment claim, no real-EHR validation claim, and no clinical safety/effectiveness claim.
""",
        encoding="utf-8-sig",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    slides = build_slides()
    built_with_powerpoint = build_pptx_powerpoint(slides)
    if not built_with_powerpoint:
        build_pptx(slides)
    build_html(slides)
    build_readme(slides)
    print(f"Created {PPTX}")
    if PDF.exists():
        print(f"Created {PDF}")
    else:
        print("PDF export not available from this environment.")
    print(f"Created {HTML}")
    print(f"Created {README}")
    print(f"Builder: {'PowerPoint COM' if built_with_powerpoint else 'OpenXML fallback'}")
    print(f"Slides: {len(slides)}")


if __name__ == "__main__":
    main()
