from __future__ import annotations

import html
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
ASSETS = OUT / "assets" / "figures"
INDEX = OUT / "index.html"
CSS = OUT / "styles.css"
EXPORT = OUT / "export_pdf.py"
README = OUT / "README.md"
PDF = OUT / "Medical_Record_Summarization_Final_Enterprise_Deck.pdf"


def find_figures() -> dict[int, Path]:
    figures: dict[int, Path] = {}
    for path in ROOT.glob("**/Figure_*.png"):
        parts = path.name.split("_", 2)
        if len(parts) < 3:
            continue
        try:
            number = int(parts[1])
        except ValueError:
            continue
        figures[number] = path
    return figures


FIGURES = find_figures()


def h(value: str) -> str:
    return html.escape(value, quote=True)


def copy_figure(number: int) -> str | None:
    src = FIGURES.get(number)
    if not src or not src.exists():
        return None
    ASSETS.mkdir(parents=True, exist_ok=True)
    dst = ASSETS / f"figure_{number:02d}.png"
    shutil.copy2(src, dst)
    return f"assets/figures/{dst.name}"


def fig(number: int, title: str, *, crop: str = "contain", badge: str | None = None) -> str:
    path = copy_figure(number)
    if not path:
        return f"""
        <div class="figure-frame placeholder">
          <div class="placeholder-label">Figure {number}</div>
          <div class="placeholder-title">{h(title)}</div>
          <div class="placeholder-hint">Expected screenshot not found in FIGURE_INDEX assets.</div>
        </div>
        """
    badge_html = f'<div class="figure-badge">{h(badge)}</div>' if badge else ""
    return f"""
      <figure class="figure-frame {crop}">
        {badge_html}
        <img src="{h(path)}" alt="Figure {number}: {h(title)}" />
        <figcaption>Figure {number} — {h(title)}</figcaption>
      </figure>
    """


def note(text: str) -> str:
    return f'<aside class="speaker-note">{h(text)}</aside>'


def footer(section: str, n: int) -> str:
    return f"""
      <div class="slide-footer">
        <span>{h(section)}</span>
        <span>{n:02d} / 24</span>
      </div>
    """


def shell(slide_no: int, section: str, title: str, subtitle: str, body: str, *, dark: bool = False, classes: str = "") -> str:
    klass = "slide dark" if dark else "slide"
    if classes:
        klass += f" {classes}"
    return f"""
    <section class="{klass}" id="slide-{slide_no:02d}">
      <div class="slide-bg-lines"></div>
      <header class="slide-header">
        <div class="eyebrow">{h(section)}</div>
        <h1>{h(title)}</h1>
        {f'<p class="subtitle">{h(subtitle)}</p>' if subtitle else ''}
      </header>
      {body}
      {footer(section, slide_no)}
    </section>
    """


def card(title: str, body: str, *, tone: str = "") -> str:
    return f"""
    <div class="card {tone}">
      <div class="card-kicker">{h(title)}</div>
      <p>{h(body)}</p>
    </div>
    """


def metric(label: str, value: str, caption: str = "", *, tone: str = "") -> str:
    return f"""
    <div class="metric {tone}">
      <div class="metric-value">{h(value)}</div>
      <div class="metric-label">{h(label)}</div>
      {f'<div class="metric-caption">{h(caption)}</div>' if caption else ''}
    </div>
    """


def pill(text: str, tone: str = "") -> str:
    return f'<span class="pill {tone}">{h(text)}</span>'


def bullets(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{h(item)}</li>" for item in items) + "</ul>"


def workflow(items: list[str], *, compact: bool = False) -> str:
    klass = "workflow compact" if compact else "workflow"
    return f"""
    <div class="{klass}">
      {''.join(f'<div class="flow-step"><span>{i+1:02d}</span><strong>{h(item)}</strong></div>' for i, item in enumerate(items))}
    </div>
    """


def roadmap(items: list[tuple[str, str]]) -> str:
    return f"""
    <div class="roadmap">
      {''.join(f'<div class="roadmap-step"><span>{h(k)}</span><strong>{h(v)}</strong></div>' for k, v in items)}
    </div>
    """


def slides() -> list[str]:
    deck: list[str] = []

    deck.append(f"""
    <section class="slide cover dark" id="slide-01">
      <div class="network-pattern"></div>
      <div class="cover-grid">
        <div>
          <div class="cover-kicker">enterprise-grade proposal deck</div>
          <h1>Vinmec × VinSmartFuture</h1>
          <h2>Citation-grounded Medical Record Summarization PoC</h2>
          <p>Evidence-first AI draft workflow with clinician review, citation validation, auditability and proxy evaluation.</p>
          <div class="cover-pills">
            {pill("local staging demo-ready PoC", "gold")}
            {pill("research-first pilot foundation", "cyan")}
            {pill("production-readiness roadmap", "ghost")}
          </div>
        </div>
        <div class="cover-panel">
          <div class="panel-title">Clinical boundary</div>
          <div class="boundary-line">Clinician-review-only AI draft</div>
          <div class="boundary-line">De-identified / mock / proxy data</div>
          <div class="boundary-line">Not a clinical deployment</div>
          <div class="boundary-line">No autonomous diagnosis, treatment recommendation or prescribing</div>
        </div>
      </div>
      <div class="gold-line"></div>
      <div class="cover-footer">Clinician-review-only PoC | De-identified/proxy data | Not a clinical deployment</div>
      {note("Open with the positioning: this is a premium enterprise proposal for a controlled evidence-first PoC, not a hospital deployment claim. Emphasize clinician review and proxy evaluation immediately.")}
    </section>
    """)

    deck.append(shell(2, "01 Context & Problem", "Executive Narrative", "Medical summarization needs evidence traceability and clinician control, not only fluent AI-generated text.", f"""
      <div class="four-cards">
        {card("Problem", "Medical records are fragmented across encounters, notes, medications, timelines and prior summaries.")}
        {card("Solution", "A citation-grounded RAG workflow creates clinician-review-only AI drafts from scoped evidence.")}
        {card("Proof", "The local staging demo-ready PoC includes doctor/admin UI, benchmark visibility, test/build evidence and artifacts.")}
        {card("Boundary", "The deck uses proxy evaluation only; it does not claim clinical safety, effectiveness, real EHR validation or hospital deployment.", tone="gold")}
      </div>
      <div class="message-band">One message: the project is designed to make evidence and uncertainty visible before a clinician decides.</div>
      {note("Walk through the four-card story. The important contrast is not AI versus doctors; it is fluent ungrounded text versus evidence-first drafts under clinician control.")}
    """))

    deck.append(shell(3, "Proposal Agenda", "Premium Enterprise Proposal Structure", "Problem assessment before solution, business proposal before technical proposal, then delivery and pilot governance.", f"""
      <div class="agenda-grid">
        {''.join(f'<div class="agenda-item"><span>{num}</span><strong>{h(title)}</strong></div>' for num, title in [
            ("01", "Context & Problem"),
            ("02", "Proposed Solution"),
            ("03", "Doctor Workflow"),
            ("04", "Evaluation & Evidence"),
            ("05", "Technical Readiness"),
            ("06", "Research Pilot Roadmap"),
        ])}
      </div>
      {note("Set expectations for an enterprise proposal deck. The structure mirrors a consulting-style solution proposal: context, solution, workflow, evidence, readiness, and roadmap.")}
    """, dark=True, classes="divider"))

    deck.append(shell(4, "01 Context & Problem", "Why the Problem Matters", "Clinical summarization is risky when the system cannot show what evidence was used.", f"""
      <div class="three-pain-cards">
        <div class="pain-card"><div class="icon-line"></div><h3>Fragmented medical records</h3><p>Key facts may sit across multiple notes, encounters and documents.</p></div>
        <div class="pain-card"><div class="icon-line"></div><h3>Hallucination / omission risk</h3><p>Generic LLM summaries can sound fluent while missing or adding critical facts.</p></div>
        <div class="pain-card"><div class="icon-line"></div><h3>Lack of source traceability</h3><p>Without citations, reviewers cannot quickly verify the draft against evidence.</p></div>
      </div>
      {note("Explain why the problem is not just text summarization. In medical records, omitted or unsupported information can affect trust, so the workflow must surface evidence.")}
    """))

    deck.append(shell(5, "02 Proposed Solution", "Why Citation-grounded RAG", "RAG is positioned as evidence infrastructure, not a guarantee of clinical correctness.", f"""
      <div class="pillar-grid">
        <div class="pillar"><span>01</span><h3>Evidence Retrieval</h3><p>Retrieve patient/encounter-scoped chunks before generation.</p></div>
        <div class="pillar"><span>02</span><h3>Citation Validation</h3><p>Link important generated claims back to source evidence.</p></div>
        <div class="pillar"><span>03</span><h3>Clinician Final Control</h3><p>Drafts remain editable, rejectable and review-only.</p></div>
      </div>
      <div class="message-band dark-text">RAG helps organize evidence. It does not replace clinical judgment or validate clinical correctness by itself.</div>
      {note("Keep the RAG explanation precise. RAG is valuable because it provides a structured evidence pathway and review surface, not because it magically makes outputs clinically safe.")}
    """))

    deck.append(shell(6, "02 Proposed Solution", "Solution at a Glance", "A clean evidence-first workflow from patient scope to audit trail.", f"""
      {workflow(["Patient / Encounter Scope", "Evidence Retrieval", "AI Draft", "Citation Validation", "Clinician Review", "Final Summary", "Audit Trail"])}
      <div class="glance-note">The workflow is deliberately gated: source evidence is retrieved and validated before the clinician accepts any final summary.</div>
      {note("This is the cleanest process slide. Explain each step in one sentence and stress that the AI output is a draft, not a final clinical decision.")}
    """))

    deck.append(shell(7, "03 Doctor Workflow", "Product Entry: Role-based Workspace", "Doctor and admin workspaces support an evidence-first summarization flow inside a local staging demo-ready PoC.", f"""
      <div class="split screenshot-right">
        <div class="stack-with-mini">
          <div class="callout-stack">
            <div class="callout"><span>01</span><strong>Doctor and admin workspaces</strong><p>Role-specific navigation for clinical review and evaluation workflows.</p></div>
            <div class="callout"><span>02</span><strong>Evidence-first summarization flow</strong><p>The product entry frames summarization around reviewable evidence.</p></div>
            <div class="callout"><span>03</span><strong>Local staging boundary</strong><p>Demo-ready locally; no hospital deployment claim.</p></div>
          </div>
          <div class="mini-shot-row">
            {fig(1, "Product Landing Page", crop="cover", badge="Entry")}
            {fig(2, "Role-Based Login Page", crop="cover", badge="Access")}
          </div>
        </div>
        {fig(4, "Doctor Workspace Overview", crop="cover", badge="Product entry")}
      </div>
      {note("Use this slide to orient reviewers. The screenshot demonstrates product coherence and role-based entry, while the callouts keep the message business-oriented.")}
    """))

    deck.append(shell(8, "03 Doctor Workflow", "Patient and Encounter Scope", "The workflow starts from de-identified patient and encounter context.", f"""
      <div class="two-shot">
        {fig(5, "De-identified Patient List", crop="contain", badge="Patient scope")}
        {fig(6, "Patient Context and Timeline", crop="contain", badge="Encounter context")}
      </div>
      <div class="message-band">Patient/encounter scope is the first safety guardrail against wrong-patient evidence and context mixing.</div>
      {note("Describe the left-to-right clinical flow: choose a de-identified patient, inspect encounter context, then generate or review. Avoid claiming real EHR integration.")}
    """))

    deck.append(shell(9, "03 Doctor Workflow", "Evidence-first Draft Generation", "The draft is generated after patient-scoped retrieval and provider selection.", f"""
      <div class="split screenshot-left">
        {fig(7, "RAG Evidence-First Generate Summary", crop="cover", badge="Draft generation")}
        <div class="callout-stack compact">
          <div class="callout"><span>A</span><strong>Patient-scoped retrieval</strong><p>Evidence is retrieved before provider inference.</p></div>
          <div class="callout"><span>B</span><strong>Provider selection</strong><p>Providers can be compared for proxy evaluation and demo flow.</p></div>
          <div class="callout"><span>C</span><strong>Draft-only generation</strong><p>The generated summary requires clinician review before use.</p></div>
        </div>
      </div>
      {note("Position generation as a controlled workflow step. The slide should not sound like autonomous clinical summarization; keep saying draft-only.")}
    """))

    deck.append(shell(10, "03 Doctor Workflow", "Evidence Quality Gate", "Citation coverage, unsupported claims, conflicts and retrieval warnings are made visible before decision.", f"""
      <div class="hero-shot">
        {fig(8, "Review and Evidence Quality Gate", crop="cover", badge="Key differentiator")}
      </div>
      <div class="floating-label label-a">Citation coverage</div>
      <div class="floating-label label-b">Unsupported claims</div>
      <div class="floating-label label-c">Conflicts & retrieval warnings</div>
      {note("This is a core differentiator. Explain that the quality gate is designed to surface uncertainty rather than hide it behind a polished summary.")}
    """, classes="quality-slide"))

    deck.append(shell(11, "03 Doctor Workflow", "Citation-first Review", "Important generated claims are linked to source evidence for clinician verification.", f"""
      <div class="two-shot emphasis">
        {fig(9, "Citation and Claim Review", crop="cover", badge="Claim review")}
        {fig(10, "Citation Tracking Detail", crop="contain", badge="Evidence trace")}
      </div>
      <div class="caption-band">Citation is not decoration; it is the review mechanism that lets a clinician inspect the source behind a generated claim.</div>
      {note("Explain how the review workspace connects claims, citations and source excerpts. Keep the language conservative: the clinician verifies; the system assists.")}
    """))

    deck.append(shell(12, "03 Doctor Workflow", "Human-in-the-loop Decision", "The clinician can edit, approve, request revision, or reject. The AI output remains a draft.", f"""
      <div class="split screenshot-left">
        {fig(11, "Editable Draft and Reject Decision", crop="cover", badge="HITL decision")}
        <div class="authority-panel">
          <h3>Clinician remains final authority.</h3>
          {bullets(["Edit the draft", "Approve only after review", "Request revision", "Reject unsupported draft", "Decision is recorded"])}
        </div>
      </div>
      {note("Use this slide to make the safety boundary concrete. The UI supports clinician decisions; it does not automate diagnosis, treatment, prescribing or discharge approval.")}
    """))

    deck.append(shell(13, "03 Doctor Workflow", "Lifecycle and Auditability", "The system preserves review status, reviewer action, generated time and audit events.", f"""
      <div class="two-shot">
        {fig(12, "Patient Summary History Status", crop="cover", badge="Lifecycle")}
        {fig(13, "Audit History Trace", crop="cover", badge="Audit trail")}
      </div>
      <div class="message-band">Auditability turns the PoC from a simple demo into a reviewable enterprise workflow foundation.</div>
      {note("Point out summary lifecycle and audit trails. This is valuable for governance and research review even before any real clinical deployment is considered.")}
    """))

    deck.append(shell(14, "03 Business Proposal", "Role / Value Mapping", "Each stakeholder gets a distinct workflow value, without turning the slide into a giant table.", f"""
      <div class="role-grid">
        {''.join(card(role, body, tone=tone) for role, body, tone in [
          ("Doctor", "Pain: long records → Feature: cited draft review → Value: faster evidence inspection.", ""),
          ("Admin / Evaluator", "Pain: hidden benchmark state → Feature: dashboards → Value: visible readiness and artifacts.", ""),
          ("Technical Reviewer", "Pain: unverifiable runtime → Feature: Docker/test/build evidence → Value: repeatable demo proof.", ""),
          ("Research Evaluator", "Pain: shallow metrics → Feature: grounding and safety proxy → Value: better study design.", ""),
          ("Mentor / Reviewer", "Pain: fragmented delivery story → Feature: enterprise deck + evidence package → Value: fast high-level review.", "gold"),
        ])}
      </div>
      {note("Summarize the business value for each stakeholder. This slide replaces a dense requirements table with a boardroom-readable value map.")}
    """))

    deck.append(shell(15, "04 Technical Readiness", "Technical Architecture", "A readable layered architecture for a local staging demo-ready PoC.", f"""
      <div class="architecture">
        <div class="arch-layer"><span>User Layer</span><strong>Doctor UI / Admin UI</strong></div>
        <div class="arch-layer"><span>Application Layer</span><strong>React Frontend / FastAPI Backend</strong></div>
        <div class="arch-layer"><span>AI/RAG Layer</span><strong>Chunking / Retrieval / Context Builder / Provider Gateway</strong></div>
        <div class="arch-layer"><span>Safety Layer</span><strong>Citation Service / Safety Service / Review Service</strong></div>
        <div class="arch-layer"><span>Data & Runtime Layer</span><strong>PostgreSQL / Redis-RQ / Artifacts / Docker Compose</strong></div>
      </div>
      {note("Explain the architecture in layers. Avoid implementation rabbit holes; focus on the enterprise separation between UI, API, AI/RAG, safety and runtime.")}
    """))

    deck.append(shell(16, "04 Technical Readiness", "RAG and Citation Pipeline", "Chunking happens before vector retrieval; retrieved evidence is reviewed before final use.", f"""
      {workflow(["Clinical note", "Patient / encounter scope", "Chunking", "Retrieval", "Context builder", "Generation", "Citation matching", "Safety metrics", "Clinician review"], compact=True)}
      <div class="pipeline-note">
        <strong>Design intent:</strong> citation-grounded RAG structures evidence for review. It is not a clinical correctness guarantee.
      </div>
      {note("Walk through the pipeline: notes are scoped, chunked, retrieved, assembled, generated, matched to citations, scored by safety proxy and reviewed by clinicians.")}
    """))

    deck.append(shell(17, "04 Evaluation & Evidence", "Evaluation Framework", "Proxy evaluation is layered: text similarity at the bottom, grounding and safety in the middle, human review as the future top layer.", f"""
      <div class="metric-pyramid">
        <div class="pyramid-row top">Human validation future</div>
        <div class="pyramid-row mid">Grounding and safety proxy: citation coverage, unsupported claims, factuality proxy, omission proxy</div>
        <div class="pyramid-row base">Text similarity: ROUGE-L and BERTScore</div>
      </div>
      <div class="metric-groups">
        {pill("Text similarity")}
        {pill("Evidence grounding")}
        {pill("Safety proxy")}
        {pill("Workflow review")}
        {pill("Human validation future", "gold")}
      </div>
      {note("Explain that ROUGE and BERTScore are useful but insufficient. The project adds grounding and safety proxy metrics, with human evaluation as the next research layer.")}
    """))

    deck.append(shell(18, "04 Evaluation & Evidence", "Benchmark Result Summary", "Completed proxy benchmark visibility for the no-gate Flow 2.1 run.", f"""
      <div class="summary-with-shot">
        <div class="metric-grid six compact">
          {metric("Records", "50")}
          {metric("Providers", "5")}
          {metric("Predictions", "250/250")}
          {metric("Semantic metric", "BERTScore", "computed")}
          {metric("Strongest generative provider", "Qwen2.5", "proxy run")}
          {metric("Smoke/control provider", "Deterministic", "most reliable")}
        </div>
        {fig(16, "Provider ROUGE Leaderboard", crop="contain", badge="Provider ranking")}
      </div>
      <div class="disclaimer-tile">Proxy evaluation only — not clinical validation, not real EHR validation, and not a clinical safety/effectiveness claim.</div>
      {note("Present the headline benchmark facts only. State clearly that this is a proxy evaluation on completed artifacts and does not validate clinical performance.")}
    """))

    deck.append(shell(19, "04 Evaluation & Evidence", "Qwen2.5 Snapshot", "Best balanced generative provider in the completed no-gate proxy run; not clinical validation.", f"""
      <div class="metric-grid five">
        {metric("ROUGE-L", "0.2122")}
        {metric("BERTScore F1", "0.8391")}
        {metric("Citation coverage", "0.8884")}
        {metric("Factuality proxy", "0.8713")}
        {metric("Critical omission", "0.4460", tone="gold")}
      </div>
      <div class="bar-card">
        <div><span style="width: 72%"></span><label>ROUGE-L 0.2122</label></div>
        <div><span style="width: 84%"></span><label>BERTScore F1 0.8391</label></div>
        <div><span style="width: 89%"></span><label>Citation coverage 0.8884</label></div>
      </div>
      <div class="disclaimer-tile compact">Interpretation is limited to proxy evaluation artifacts. It does not establish clinical safety or effectiveness.</div>
      {note("Use exact metrics only. Emphasize the interpretation: Qwen2.5 looks strongest among generative PoC providers, but this remains proxy evidence.")}
    """))

    deck.append(shell(20, "04 Evaluation & Evidence", "Admin Evaluation Visibility", "Evaluation is inspectable through the Admin dashboard, not hidden inside scripts.", f"""
      <div class="three-shot evidence">
        {fig(14, "Admin Evaluation Readiness", crop="cover", badge="Readiness")}
        {fig(15, "RAG Best Models Admin Overview", crop="cover", badge="Flow 2.1 visibility")}
        {fig(17, "Evidence Grounding Metrics", crop="contain", badge="Grounding metrics")}
      </div>
      <div class="caption-band">Admin users can inspect provider completion, ranking signals and evidence-grounding metrics from the product surface.</div>
      {note("Show that benchmark evidence is operationalized into admin visibility. This helps reviewers see the evaluation discipline as part of the system, not a side script.")}
    """))

    deck.append(shell(21, "04 Evaluation & Evidence", "Error Analysis and Reproducibility", "Per-record failure analysis and artifact files support transparent review.", f"""
      <div class="three-shot evidence">
        {fig(18, "RAG vs Raw Context Comparison", crop="contain", badge="RAG vs raw")}
        {fig(19, "Per-Record Failure Analysis", crop="cover", badge="Failure diagnosis")}
        {fig(20, "RAG Benchmark Artifacts and Run Files", crop="cover", badge="Reproducibility")}
      </div>
      <div class="artifact-list">
        {pill("predictions")}
        {pill("metrics")}
        {pill("manifests")}
        {pill("reports")}
        {pill("failure analysis", "gold")}
      </div>
      {note("Explain why reproducibility matters: artifacts make the benchmark inspectable and failure analysis makes model limitations visible at record level.")}
    """))

    deck.append(shell(22, "05 Technical Readiness", "Technical Readiness Evidence", "Docker Compose local staging and evidence package support repeatable demo.", f"""
      <div class="three-shot technical">
        {fig(21, "Technical System Running Checklist", crop="contain", badge="Runtime checklist")}
        {fig(22, "Evidence Package Folder Structure", crop="contain", badge="Evidence folder")}
        {fig(23, "Latest Running Test Evidence", crop="contain", badge="Evidence package")}
      </div>
      <div class="metric-strip">
        {pill("/health")}
        {pill("/ready")}
        {pill("tests")}
        {pill("frontend build")}
        {pill("Docker build")}
        {pill("logs / artifacts", "gold")}
      </div>
      {note("This slide is demo readiness evidence, not production deployment. State that the local staging path has logs and build/test proof for repeatable review.")}
    """))

    deck.append(shell(23, "06 Research Pilot Roadmap", "Vinmec Research Pilot Roadmap", "A research-first pilot foundation before any controlled clinical workflow study.", f"""
      {roadmap([
        ("01", "PoC local staging"),
        ("02", "Governance / workflow discovery"),
        ("03", "Retrospective de-identified study"),
        ("04", "Raw vs Structured vs RAG vs Adaptive comparison"),
        ("05", "Clinician human evaluation"),
        ("06", "Silent / shadow mode"),
        ("07", "Clinician-visible usability pilot"),
      ])}
      <div class="disclaimer-tile">Governance first: no real EHR evaluation, writeback or clinical workflow use without approved data access, review protocol and audit controls.</div>
      {note("Frame the Vinmec roadmap carefully. The proposed next step is controlled research design, not uncontrolled rollout. Mention governance, workflow discovery and clinician human evaluation.")}
    """, dark=True, classes="roadmap-slide"))

    deck.append(shell(24, "06 Research Pilot Roadmap", "Risk Controls and Closing", "A research-first foundation for evidence-grounded clinical summarization — ready for controlled pilot design, not uncontrolled hospital rollout.", f"""
      <div class="risk-grid">
        <div class="risk-panel">
          <h3>Key risks</h3>
          {bullets(["Wrong-patient evidence", "Unsupported diagnosis", "Medication / allergy error", "PHI leakage", "Over-trust"])}
        </div>
        <div class="risk-panel control">
          <h3>Controls</h3>
          {bullets(["Patient / encounter filters", "Citation validation", "Unsupported-claim visibility", "Clinician review", "Audit trail and governance gates"])}
        </div>
      </div>
      <div class="closing-line">Final position: a research-first pilot foundation and production-readiness roadmap — not a production clinical system.</div>
      {note("Close by being ambitious but conservative. The project is credible because it controls risk and proposes a disciplined pilot path rather than overclaiming deployment readiness.")}
    """, dark=True, classes="closing-slide"))

    return deck


STYLES = r"""
:root {
  --navy: #071B33;
  --teal: #006D77;
  --cyan: #00B4D8;
  --gold: #D6A84F;
  --off: #F7FAFC;
  --gray: #E5E7EB;
  --ink: #102033;
  --muted: #5C6B7B;
  --shadow: 0 24px 60px rgba(7, 27, 51, .16);
}

@page { size: 16in 9in; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; background: #dbe7ec; color: var(--ink); font-family: Inter, "Segoe UI", Arial, sans-serif; }
body { counter-reset: slide; }
.deck { width: 1600px; margin: 0 auto; }
.slide {
  position: relative;
  width: 1600px;
  height: 900px;
  overflow: hidden;
  padding: 58px 76px 68px;
  background: radial-gradient(circle at 88% 12%, rgba(0,180,216,.11), transparent 28%), linear-gradient(135deg, #fff 0%, #f7fafc 100%);
  page-break-after: always;
  break-after: page;
}
.slide.dark {
  color: white;
  background: radial-gradient(circle at 76% 18%, rgba(0,180,216,.22), transparent 25%), linear-gradient(135deg, #071B33 0%, #0b2d4f 56%, #062034 100%);
}
.slide-bg-lines { position:absolute; inset:0; pointer-events:none; opacity:.45; background-image: linear-gradient(120deg, transparent 0 70%, rgba(0,109,119,.08) 70% 70.3%, transparent 70.3%), radial-gradient(circle at 12% 80%, rgba(214,168,79,.12), transparent 22%); }
.slide-header { position: relative; z-index: 2; max-width: 1060px; }
.eyebrow { color: var(--teal); font-size: 15px; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; margin-bottom: 12px; }
.dark .eyebrow { color: #c7e8ef; }
h1 { margin: 0; font-size: 50px; line-height: 1.05; letter-spacing: -.035em; color: var(--ink); }
.dark h1 { color: white; }
.subtitle { margin: 16px 0 0; max-width: 980px; color: var(--muted); font-size: 25px; line-height: 1.3; }
.dark .subtitle { color: #d8eaf0; }
.slide-footer { position: absolute; left: 76px; right: 76px; bottom: 28px; display: flex; justify-content: space-between; align-items: center; color: #8492a2; font-size: 14px; letter-spacing:.02em; z-index: 5; }
.dark .slide-footer { color: rgba(255,255,255,.72); }
.speaker-note { display:none; }

.cover { padding: 72px 86px; }
.network-pattern { position:absolute; inset:0; opacity:.58; background-image: radial-gradient(circle, rgba(0,180,216,.34) 1.5px, transparent 2px), linear-gradient(115deg, transparent 0 60%, rgba(214,168,79,.12) 60.2% 60.4%, transparent 60.6%); background-size: 80px 80px, 100% 100%; }
.cover-grid { position: relative; z-index:2; display:grid; grid-template-columns: 1.3fr .72fr; gap: 72px; height: 690px; align-items:center; }
.cover-kicker { display:inline-block; color:#071B33; background:#D6A84F; padding: 10px 16px; border-radius:999px; font-weight:800; text-transform:uppercase; letter-spacing:.12em; font-size:14px; margin-bottom:28px; }
.cover h1 { font-size: 66px; color:white; max-width: 940px; }
.cover h2 { color:#E9F7FA; font-size: 42px; line-height:1.08; max-width: 980px; margin: 22px 0 0; letter-spacing:-.03em; }
.cover p { color:#d7e8ee; font-size: 26px; line-height:1.35; max-width: 860px; margin: 30px 0; }
.cover-pills, .metric-strip, .artifact-list, .metric-groups { display:flex; gap: 14px; flex-wrap:wrap; align-items:center; }
.pill { display:inline-flex; align-items:center; justify-content:center; padding: 10px 15px; border-radius:999px; background:rgba(0,109,119,.1); color:var(--teal); font-size:16px; font-weight:800; border:1px solid rgba(0,109,119,.16); }
.pill.gold { background:rgba(214,168,79,.18); border-color:rgba(214,168,79,.42); color:#9d7422; }
.pill.cyan { background:rgba(0,180,216,.14); border-color:rgba(0,180,216,.28); color:#006D77; }
.pill.ghost { background:rgba(255,255,255,.10); border-color:rgba(255,255,255,.18); color:white; }
.cover-panel { background:rgba(255,255,255,.09); border:1px solid rgba(255,255,255,.18); border-radius:32px; box-shadow: 0 30px 90px rgba(0,0,0,.25); padding:34px; backdrop-filter: blur(12px); }
.panel-title { color:#D6A84F; font-size:20px; font-weight:900; margin-bottom:20px; }
.boundary-line { border-top:1px solid rgba(255,255,255,.16); padding:18px 0; font-size:22px; color:#EEF7FA; }
.gold-line { position:absolute; left:86px; right:86px; bottom:96px; height:3px; background:linear-gradient(90deg, var(--gold), transparent); }
.cover-footer { position:absolute; left:86px; right:86px; bottom:48px; color:rgba(255,255,255,.8); font-size:18px; }

.four-cards, .three-pain-cards, .pillar-grid, .role-grid { position:relative; z-index:2; display:grid; gap:24px; margin-top:58px; }
.four-cards { grid-template-columns: repeat(4, 1fr); }
.three-pain-cards, .pillar-grid { grid-template-columns: repeat(3, 1fr); }
.role-grid { grid-template-columns: repeat(5, 1fr); gap:18px; }
.card, .pain-card, .pillar, .metric, .callout, .risk-panel, .arch-layer, .roadmap-step {
  background: rgba(255,255,255,.88);
  border:1px solid rgba(0,109,119,.16);
  border-radius: 26px;
  box-shadow: var(--shadow);
}
.dark .card, .dark .roadmap-step, .dark .risk-panel { background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.16); box-shadow: 0 28px 70px rgba(0,0,0,.22); }
.card { min-height: 230px; padding: 26px; }
.card.gold { background: linear-gradient(135deg, #fff8e8, #ffffff); border-color: rgba(214,168,79,.34); }
.card-kicker { color:var(--teal); text-transform:uppercase; letter-spacing:.1em; font-size:15px; font-weight:900; margin-bottom:18px; }
.card p, .pain-card p, .pillar p, .callout p { color:var(--muted); font-size:22px; line-height:1.35; margin:0; }
.message-band, .caption-band, .glance-note, .pipeline-note, .disclaimer-tile, .closing-line {
  position: relative;
  z-index: 3;
  margin-top: 46px;
  padding: 22px 30px;
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(0,109,119,.10), rgba(0,180,216,.10));
  border:1px solid rgba(0,109,119,.18);
  color:var(--teal);
  font-size:24px;
  font-weight:800;
  line-height:1.25;
}
.message-band.dark-text { color:var(--ink); }
.divider .slide-header { max-width:none; }
.agenda-grid { display:grid; grid-template-columns: repeat(2, 1fr); gap: 24px; margin-top: 72px; max-width:1180px; }
.agenda-item { display:flex; gap:24px; align-items:center; padding: 26px 32px; border-radius:26px; background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.14); box-shadow:0 18px 44px rgba(0,0,0,.18); }
.agenda-item span { color:#071B33; background:#D6A84F; width:64px; height:64px; border-radius:20px; display:grid; place-items:center; font-size:22px; font-weight:900; }
.agenda-item strong { color:white; font-size:28px; }
.pain-card, .pillar { min-height: 290px; padding: 34px; }
.pain-card h3, .pillar h3 { font-size: 31px; line-height:1.08; margin: 24px 0 16px; letter-spacing:-.03em; }
.icon-line { width:74px; height:8px; border-radius:999px; background:linear-gradient(90deg, var(--teal), var(--cyan), var(--gold)); }
.pillar span { display:inline-grid; place-items:center; width:56px; height:56px; border-radius:18px; background:var(--navy); color:white; font-size:20px; font-weight:900; }
.workflow { position:relative; z-index:2; display:grid; grid-template-columns: repeat(7, 1fr); gap:14px; margin-top:120px; }
.workflow.compact { grid-template-columns: repeat(9, 1fr); gap:10px; margin-top:74px; }
.flow-step { min-height: 150px; border-radius: 24px; padding: 20px 16px; background:white; border:1px solid rgba(0,109,119,.16); box-shadow:var(--shadow); position:relative; display:flex; flex-direction:column; justify-content:center; gap:16px; }
.workflow.compact .flow-step { min-height: 128px; padding: 14px 11px; }
.flow-step:not(:last-child)::after { content:""; position:absolute; right:-14px; top:50%; width:14px; height:2px; background:var(--cyan); }
.flow-step span { color:var(--gold); font-weight:900; font-size:16px; }
.flow-step strong { font-size:21px; line-height:1.12; letter-spacing:-.02em; }
.workflow.compact .flow-step strong { font-size:16px; }
.split { position:relative; z-index:2; display:grid; gap:36px; margin-top:42px; align-items:center; }
.screenshot-right { grid-template-columns: .62fr 1.38fr; }
.screenshot-left { grid-template-columns: 1.35fr .65fr; }
.callout-stack { display:flex; flex-direction:column; gap:22px; }
.callout-stack.compact { gap:18px; }
.callout { padding:22px; display:grid; grid-template-columns: 52px 1fr; gap: 8px 16px; align-items:start; }
.callout span { grid-row:1 / span 2; width:48px; height:48px; border-radius:16px; display:grid; place-items:center; background:var(--navy); color:white; font-weight:900; }
.callout strong { font-size:23px; line-height:1.08; }
.callout p { grid-column:2; font-size:18px; }
.stack-with-mini { display:flex; flex-direction:column; gap:18px; }
.mini-shot-row { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.mini-shot-row .figure-frame { height:156px; min-height:156px; border-radius:22px; }
.mini-shot-row .figure-frame figcaption { left:10px; right:10px; bottom:8px; padding:6px 9px; font-size:10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mini-shot-row .figure-badge { top:8px; left:8px; padding:5px 8px; font-size:11px; }
.figure-frame { position:relative; margin:0; border:1px solid rgba(0,109,119,.18); border-radius:30px; background:white; box-shadow:var(--shadow); overflow:hidden; min-height:250px; }
.figure-frame img { width:100%; height:100%; display:block; object-position:center; }
.figure-frame.contain img { object-fit:contain; background:#f8fbfc; }
.figure-frame.cover img { object-fit:cover; }
.figure-frame figcaption { position:absolute; left:18px; bottom:14px; right:18px; padding:8px 12px; border-radius:999px; background:rgba(7,27,51,.72); color:white; font-size:14px; backdrop-filter: blur(7px); }
.figure-badge { position:absolute; z-index:4; top:16px; left:16px; background:#D6A84F; color:#071B33; padding:8px 13px; border-radius:999px; font-weight:900; font-size:14px; box-shadow:0 10px 24px rgba(0,0,0,.14); }
.two-shot { position:relative; z-index:2; display:grid; grid-template-columns: 1fr 1fr; gap:30px; margin-top:44px; }
.two-shot .figure-frame { height: 485px; }
.two-shot.emphasis .figure-frame { height: 510px; }
.two-shot.technical .figure-frame { height: 430px; }
.three-shot { position:relative; z-index:2; display:grid; grid-template-columns: repeat(3, 1fr); gap:22px; margin-top:38px; }
.three-shot.evidence .figure-frame { height:430px; }
.three-shot.technical .figure-frame { height:390px; }
.three-shot .figure-frame figcaption { font-size:12px; }
.hero-shot { position:relative; z-index:2; margin-top:42px; }
.hero-shot .figure-frame { height: 610px; }
.quality-slide .slide-header { max-width:980px; }
.floating-label { position:absolute; z-index:6; background:rgba(7,27,51,.86); color:white; border:1px solid rgba(255,255,255,.18); padding:13px 18px; border-radius:999px; font-size:18px; font-weight:900; box-shadow:0 12px 32px rgba(0,0,0,.18); }
.label-a { left: 180px; bottom: 226px; }
.label-b { right: 212px; top: 236px; background:rgba(180,35,24,.88); }
.label-c { right: 140px; bottom: 176px; background:rgba(214,168,79,.95); color:#071B33; }
.authority-panel { padding:36px; border-radius:30px; background:linear-gradient(135deg, #071B33, #0b3d55); color:white; box-shadow:var(--shadow); }
.authority-panel h3 { margin:0 0 22px; font-size:38px; line-height:1.08; color:white; }
ul { margin:0; padding-left:24px; }
li { margin:12px 0; font-size:22px; line-height:1.25; }
.authority-panel li, .risk-panel li { color:rgba(255,255,255,.9); }
.role-grid .card { min-height: 270px; padding:22px; }
.role-grid .card p { font-size:18px; }
.architecture { position:relative; z-index:2; display:flex; flex-direction:column; gap:20px; margin:48px auto 0; max-width:1150px; }
.arch-layer { display:grid; grid-template-columns: 290px 1fr; align-items:center; padding:22px 30px; background:white; }
.arch-layer span { color:var(--teal); font-weight:900; font-size:18px; letter-spacing:.07em; text-transform:uppercase; }
.arch-layer strong { font-size:28px; color:var(--ink); }
.pipeline-note { margin-top:62px; font-size:23px; color:var(--ink); }
.metric-pyramid { position:relative; z-index:2; margin:58px auto 0; width:980px; display:flex; flex-direction:column; align-items:center; gap:18px; }
.pyramid-row { border-radius:24px; color:white; font-size:28px; font-weight:900; text-align:center; padding:24px 34px; box-shadow:var(--shadow); }
.pyramid-row.top { width:55%; background:linear-gradient(135deg, var(--gold), #b8862f); color:#071B33; }
.pyramid-row.mid { width:78%; background:linear-gradient(135deg, var(--teal), #0a7f8a); }
.pyramid-row.base { width:100%; background:linear-gradient(135deg, var(--navy), #123b63); }
.metric-groups { justify-content:center; margin-top:36px; }
.metric-grid { position:relative; z-index:2; display:grid; gap:22px; margin-top:48px; }
.metric-grid.six { grid-template-columns: repeat(3, 1fr); }
.metric-grid.five { grid-template-columns: repeat(5, 1fr); }
.summary-with-shot { position:relative; z-index:2; display:grid; grid-template-columns: .92fr 1.08fr; gap:28px; margin-top:42px; align-items:stretch; }
.summary-with-shot .metric-grid { margin-top:0; }
.metric-grid.six.compact { grid-template-columns: repeat(2, 1fr); gap:16px; }
.metric-grid.six.compact .metric { min-height:122px; padding:18px; }
.metric-grid.six.compact .metric-value { font-size:34px; }
.metric-grid.six.compact .metric-label { font-size:17px; }
.metric-grid.six.compact .metric-caption { font-size:14px; }
.summary-with-shot .figure-frame { height:398px; }
.metric { min-height:160px; padding:24px; background:white; border-radius:28px; }
.metric.gold { background:linear-gradient(135deg, #fff8e8, white); border-color:rgba(214,168,79,.4); }
.metric-value { font-size:44px; line-height:1; color:var(--teal); font-weight:950; letter-spacing:-.04em; }
.metric-label { margin-top:12px; color:var(--ink); font-size:20px; font-weight:900; }
.metric-caption { margin-top:8px; color:var(--muted); font-size:16px; }
.disclaimer-tile { background:#fff6df; border-color:rgba(214,168,79,.34); color:#8a631d; font-size:22px; }
.disclaimer-tile.compact { margin-top:20px; font-size:18px; padding:16px 22px; }
.bar-card { margin-top:36px; padding:24px; border-radius:28px; background:white; border:1px solid rgba(0,109,119,.15); box-shadow:var(--shadow); }
.bar-card div { position:relative; height:34px; margin:16px 0; border-radius:999px; background:#e9f3f5; overflow:hidden; }
.bar-card span { display:block; height:100%; border-radius:999px; background:linear-gradient(90deg, var(--teal), var(--cyan)); }
.bar-card label { position:absolute; left:18px; top:5px; color:#071B33; font-weight:900; font-size:16px; }
.artifact-list { justify-content:center; margin-top:24px; }
.metric-strip { justify-content:center; margin-top:30px; }
.roadmap-slide .slide-header { max-width:1180px; }
.roadmap { position:relative; z-index:2; display:grid; grid-template-columns: repeat(7, 1fr); gap:14px; margin-top:80px; }
.roadmap-step { min-height:210px; padding:22px 16px; }
.roadmap-step span { display:inline-grid; place-items:center; width:46px; height:46px; border-radius:16px; background:#D6A84F; color:#071B33; font-weight:900; margin-bottom:18px; }
.roadmap-step strong { display:block; font-size:19px; line-height:1.18; color:white; }
.risk-grid { position:relative; z-index:2; display:grid; grid-template-columns: 1fr 1fr; gap:34px; margin-top:70px; }
.risk-panel { min-height:380px; padding:36px; background:rgba(255,255,255,.08); }
.risk-panel.control { border-color:rgba(0,180,216,.35); }
.risk-panel h3 { margin:0 0 22px; font-size:38px; color:white; }
.closing-line { color:white; background:rgba(255,255,255,.10); border-color:rgba(255,255,255,.18); margin-top:38px; }
.placeholder { display:grid; place-items:center; min-height:420px; padding:30px; text-align:center; }
.placeholder-label { font-size:32px; color:var(--teal); font-weight:900; }
.placeholder-title { font-size:24px; font-weight:900; }
.placeholder-hint { color:var(--muted); font-size:18px; }

@media print {
  html, body { background:white; }
  .deck { width: 16in; }
  .slide { width:16in; height:9in; padding:.58in .76in .68in; }
}
"""


def build_index(deck: list[str]) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Vinmec × VinSmartFuture — Medical Record Summarization PoC</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <main class="deck">
    {''.join(deck)}
  </main>
</body>
</html>
"""


EXPORT_SCRIPT = r'''from __future__ import annotations

import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
HTML = HERE / "index.html"
PDF = HERE / "Medical_Record_Summarization_Final_Enterprise_Deck.pdf"


def find_edge() -> Path | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ]
    return next((p for p in candidates if p.exists()), None)


def main() -> int:
    browser = find_edge()
    if not browser:
        print("No Edge/Chrome executable found. Open index.html and print to PDF manually.")
        return 1
    if PDF.exists():
        PDF.unlink()
    cmd = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--print-to-pdf=" + str(PDF),
        HTML.resolve().as_uri(),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=HERE, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if not PDF.exists():
        print("PDF was not created.")
        return result.returncode or 1
    print(f"Created {PDF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build_readme(deck_count: int, used: list[int], missing: list[int]) -> str:
    slide_list = "\n".join([
        "1. Premium Cover",
        "2. Executive Narrative",
        "3. Proposal Agenda",
        "4. Context: Why the Problem Matters",
        "5. Why Citation-grounded RAG",
        "6. Solution at a Glance",
        "7. Product Entry: Role-based Workspace",
        "8. Doctor Workflow: Patient and Encounter Scope",
        "9. Doctor Workflow: Evidence-first Draft Generation",
        "10. Evidence Quality Gate",
        "11. Citation-first Review",
        "12. Human-in-the-loop Decision",
        "13. Lifecycle and Auditability",
        "14. Role / Value Mapping",
        "15. Technical Architecture",
        "16. RAG and Citation Pipeline",
        "17. Evaluation Framework",
        "18. Benchmark Result Summary",
        "19. Qwen2.5 Snapshot",
        "20. Admin Evaluation Visibility",
        "21. Error Analysis and Reproducibility",
        "22. Technical Readiness Evidence",
        "23. Vinmec Research Pilot Roadmap",
        "24. Risk Controls and Closing",
    ])
    return f"""# Final Enterprise Healthcare AI Pitch Deck

Project: **Vinmec × VinSmartFuture — Citation-grounded Medical Record Summarization PoC**

This is a premium English HTML/CSS proposal deck for a **local staging demo-ready PoC** and **research-first pilot foundation**. It does not claim production clinical readiness, hospital deployment, real EHR validation, clinical safety, clinical effectiveness, autonomous diagnosis, treatment recommendation or prescribing.

## Created files

- `index.html` — 24-slide fixed 16:9 HTML deck.
- `styles.css` — premium enterprise healthcare visual system.
- `export_pdf.py` — Edge/Chrome headless PDF export helper.
- `export_pptx.py` — Microsoft PowerPoint automation export helper.
- `Medical_Record_Summarization_Final_Enterprise_Deck.pdf` — generated if export succeeds.
- `Medical_Record_Summarization_Final_Enterprise_Deck.pptx` — editable PowerPoint version for final adjustments.
- `assets/figures/` — copied screenshots used in the deck.

## Preview command

```powershell
Start-Process docs\\proposal_deck_final\\index.html
```

## Export command

```powershell
python docs\\proposal_deck_final\\export_pdf.py
```

## Editable PowerPoint export command

```powershell
python docs\\proposal_deck_final\\export_pptx.py
```

## Slides ({deck_count})

{slide_list}

## Screenshots used

{', '.join(f'Figure {n}' for n in used)}

## Placeholders

{', '.join(f'Figure {n}' for n in missing) if missing else 'None. All required screenshots were found.'}

## Claims softened or avoided

- Uses “enterprise-grade proposal deck”, not “production-ready system”.
- Uses “local staging demo-ready PoC”, not “hospital deployment”.
- Uses “clinician-review-only AI draft”, not autonomous clinical decision-making.
- Uses “proxy evaluation”, not clinical safety/effectiveness validation.
- Uses “research-first pilot foundation” and “production-readiness roadmap”, not real EHR validation.

## Sources

- `docs/proposal/MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md`
- `docs/research/VINMEC_MEDICAL_RECORD_SUMMARIZATION_PROPOSAL.md`
- `ảnh artifacts/FIGURE_INDEX.md`
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    for old in ASSETS.glob("figure_*.png"):
        old.unlink()
    deck = slides()
    required_figures = [1,2,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23]
    used = sorted({n for n in required_figures if n in FIGURES})
    missing = sorted({n for n in required_figures if n not in FIGURES})
    INDEX.write_text(build_index(deck), encoding="utf-8")
    CSS.write_text(STYLES, encoding="utf-8")
    EXPORT.write_text(EXPORT_SCRIPT, encoding="utf-8")
    README.write_text(build_readme(len(deck), used, missing), encoding="utf-8-sig")
    print(f"Created {INDEX}")
    print(f"Created {CSS}")
    print(f"Created {EXPORT}")
    print(f"Created {README}")
    print(f"Slides: {len(deck)}")
    print("Screenshots used:", ", ".join(f"Figure {n}" for n in used))
    print("Placeholders:", ", ".join(f"Figure {n}" for n in missing) if missing else "None")


if __name__ == "__main__":
    main()
