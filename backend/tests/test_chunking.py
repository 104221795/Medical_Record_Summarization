from backend.app.schemas import ClinicalDocument
from backend.app.services.chunking import ClinicalChunker


def test_chunk_offsets_return_exact_source_text() -> None:
    document = ClinicalDocument(
        document_id="doc-1",
        document_type="progress-note",
        text=(
            "ASSESSMENT:\nNo pulmonary edema. Symptoms improved.\n\n"
            "PLAN:\nContinue treatment. Follow up in four weeks."
        ),
    )

    chunks = ClinicalChunker(max_chars=200, overlap_sentences=1).chunk_document(
        "tenant-a", "patient-a", document
    )

    assert chunks
    assert {item.section for item in chunks} == {"Assessment", "Plan"}
    for item in chunks:
        assert item.text == document.text[item.char_start : item.char_end]


def test_overlap_never_loops_when_previous_sentence_is_large() -> None:
    document = ClinicalDocument(
        document_id="doc-large",
        text=f"ASSESSMENT:\n{'Long clinical text ' * 20}.\nShort follow-up statement.",
    )

    chunks = ClinicalChunker(max_chars=200, overlap_sentences=1).chunk_document(
        "tenant-a", "patient-a", document
    )

    assert 1 <= len(chunks) <= 3


def test_vietnamese_clinical_sections_are_preserved() -> None:
    document = ClinicalDocument(
        document_id="doc-vi",
        text=(
            "CH\u1ea8N \u0110O\u00c1N:\nT\u0103ng huy\u1ebft \u00e1p nguy\u00ean ph\u00e1t.\n\n"
            "K\u1ebe HO\u1ea0CH:\nTheo d\u00f5i huy\u1ebft \u00e1p t\u1ea1i nh\u00e0."
        ),
    )

    chunks = ClinicalChunker(max_chars=200).chunk_document("tenant-a", "patient-a", document)

    assert [item.section for item in chunks] == ["Ch\u1ea9n \u0110o\u00e1n", "K\u1ebf Ho\u1ea1ch"]
    assert all(item.text == document.text[item.char_start : item.char_end] for item in chunks)
