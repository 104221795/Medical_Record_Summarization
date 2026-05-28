import re
import uuid
from dataclasses import dataclass

from ..schemas import ClinicalDocument, EvidenceChunk


HEADING_RE = re.compile(
    r"(?im)^(?P<header>"
    r"assessment(?:\s+and\s+plan)?|plan|history(?:\s+of\s+present\s+illness)?|"
    r"hpi|findings|impression|diagnosis|medications?|allergies|laboratory|"
    r"labs?|vitals?|procedure|follow[- ]?up|chief complaint|"
    r"ch[a\u1ea9]n \u0111o[a\u00e1]n|[d\u0111][a\u00e1]nh gi[a\u00e1]|"
    r"k[e\u1ebf] ho[a\u1ea1]ch|tri[e\u1ec7]u ch[u\u1ee9]ng|ti[e\u1ec1]n s[u\u1eed]|"
    r"thu[o\u1ed1]c|d[i\u1ecb] [u\u1ee9]ng|x[e\u00e9]t nghi[e\u1ec7]m|k[e\u1ebf]t lu[a\u1ead]n"
    r")\s*:?\s*$"
)
SENTENCE_RE = re.compile(r".+?(?:[.!?](?=\s|$)|\n|$)", re.DOTALL)


@dataclass(frozen=True)
class TextSpan:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class SectionSpan:
    title: str
    start: int
    end: int


class ClinicalChunker:
    """Section-aware chunker that retains exact source offsets for evidence."""

    def __init__(self, max_chars: int = 1200, overlap_sentences: int = 1):
        if max_chars < 200:
            raise ValueError("max_chars must be at least 200.")
        if overlap_sentences < 0:
            raise ValueError("overlap_sentences cannot be negative.")
        self.max_chars = max_chars
        self.overlap_sentences = overlap_sentences

    def chunk_document(
        self,
        tenant_id: str,
        patient_id: str,
        document: ClinicalDocument,
    ) -> list[EvidenceChunk]:
        chunks: list[EvidenceChunk] = []
        for section in self._sections(document.text):
            sentences = self._sentences(document.text, section)
            for span in self._windows(sentences):
                chunk_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        (
                            f"{tenant_id}/{patient_id}/{document.document_id}/"
                            f"{span.start}/{span.end}"
                        ),
                    )
                )
                chunks.append(
                    EvidenceChunk(
                        chunk_id=chunk_id,
                        patient_id=patient_id,
                        document_id=document.document_id,
                        document_type=document.document_type,
                        title=document.title,
                        encounter_id=document.encounter_id,
                        authored_at=document.authored_at,
                        section=section.title,
                        text=document.text[span.start : span.end],
                        char_start=span.start,
                        char_end=span.end,
                    )
                )
        return chunks

    def _sections(self, text: str) -> list[SectionSpan]:
        matches = list(HEADING_RE.finditer(text))
        if not matches:
            return [SectionSpan(title="Narrative", start=0, end=len(text))]
        sections: list[SectionSpan] = []
        if matches[0].start() > 0 and text[: matches[0].start()].strip():
            sections.append(SectionSpan("Narrative", 0, matches[0].start()))
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            if text[start:end].strip():
                sections.append(SectionSpan(match.group("header").title(), start, end))
        return sections

    def _sentences(self, text: str, section: SectionSpan) -> list[TextSpan]:
        content = text[section.start : section.end]
        sentences: list[TextSpan] = []
        for match in SENTENCE_RE.finditer(content):
            raw = match.group(0)
            left_trim = len(raw) - len(raw.lstrip())
            right_trimmed = raw.rstrip()
            if not right_trimmed.strip():
                continue
            start = section.start + match.start() + left_trim
            end = section.start + match.start() + len(right_trimmed)
            sentences.append(TextSpan(text=text[start:end], start=start, end=end))
        if not sentences and content.strip():
            start = section.start + (len(content) - len(content.lstrip()))
            end = section.end - (len(content) - len(content.rstrip()))
            sentences.append(TextSpan(text=text[start:end], start=start, end=end))
        return sentences

    def _windows(self, sentences: list[TextSpan]) -> list[TextSpan]:
        windows: list[TextSpan] = []
        current: list[TextSpan] = []
        index = 0
        while index < len(sentences):
            candidate = sentences[index]
            current_size = (
                candidate.end - current[0].start if current else candidate.end - candidate.start
            )
            if current and current_size > self.max_chars:
                windows.append(self._merge(current))
                current = current[-self.overlap_sentences :] if self.overlap_sentences else []
                if current and candidate.end - current[0].start > self.max_chars:
                    current = []
                continue
            current.append(candidate)
            index += 1
        if current:
            merged = self._merge(current)
            if not windows or merged.start != windows[-1].start or merged.end != windows[-1].end:
                windows.append(merged)
        return windows

    @staticmethod
    def _merge(spans: list[TextSpan]) -> TextSpan:
        start, end = spans[0].start, spans[-1].end
        return TextSpan(text="", start=start, end=end)
