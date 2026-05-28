from __future__ import annotations

import json
import re
import unicodedata
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..medical_guardrail_schemas import (
    ExtractedMedicalEntity,
    MedicalGuardrailResult,
    MedicalSafetyIssue,
    NliContradiction,
)


MEDICATION_DOSE_RE = re.compile(
    r"\b(?P<med>[A-Za-zÀ-ỹ][A-Za-zÀ-ỹ0-9-]{2,})\s+"
    r"(?P<dose>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>mg|mcg|µg|g|ml|mL|iu|IU|units?|đv|vien|viên)\b",
    re.IGNORECASE,
)
MEDICATION_CONTEXT_RE = re.compile(
    r"\b(?:thu[oố]c|d[uù]ng|u[oố]ng|ti[eê]m|medication|prescribed?|start|continue)\s*"
    r"[:\-]?\s*(?P<med>[A-Za-zÀ-ỹ][A-Za-zÀ-ỹ0-9-]{2,})\b",
    re.IGNORECASE,
)
KNOWN_MEDICATIONS = {
    "acetaminophen",
    "amoxicillin",
    "amlodipine",
    "aspirin",
    "atorvastatin",
    "ceftriaxone",
    "furosemide",
    "insulin",
    "lisinopril",
    "losartan",
    "metformin",
    "omeprazole",
    "paracetamol",
    "prednisone",
    "warfarin",
}
METRIC_PATTERNS = {
    "blood_pressure": re.compile(
        r"\b(?:bp|blood\s+pressure|ha|huy[eế]t\s+[aá]p)\s*[:=]?\s*"
        r"(?P<value>\d{2,3}\s*/\s*\d{2,3})\s*(?P<unit>mmhg)?\b",
        re.IGNORECASE,
    ),
    "hba1c": re.compile(
        r"\b(?:hba1c)\s*[:=]?\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>%)?",
        re.IGNORECASE,
    ),
    "spo2": re.compile(
        r"\b(?:spo2|oxygen\s+saturation)\s*[:=]?\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>%)?",
        re.IGNORECASE,
    ),
    "glucose": re.compile(
        r"\b(?:glucose|blood\s+sugar|[dđ][uư][oờ]ng\s+huy[eế]t)\s*[:=]?\s*"
        r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>mg/dl|mmol/l)?",
        re.IGNORECASE,
    ),
    "temperature": re.compile(
        r"\b(?:temperature|temp|nhi[eệ]t\s+[dđ][oộ])\s*[:=]?\s*"
        r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>°?c)?",
        re.IGNORECASE,
    ),
    "heart_rate": re.compile(
        r"\b(?:hr|heart\s+rate|m[aạ]ch)\s*[:=]?\s*(?P<value>\d{2,3})\s*"
        r"(?P<unit>bpm|l[aầ]n/ph[uú]t)?",
        re.IGNORECASE,
    ),
    "creatinine": re.compile(
        r"\bcreatinine\s*[:=]?\s*(?P<value>\d+(?:[.,]\d+)?)\s*"
        r"(?P<unit>mg/dl|µmol/l|umol/l)?",
        re.IGNORECASE,
    ),
}


class ContradictionDetector(ABC):
    name: str

    @abstractmethod
    def find_contradictions(
        self,
        premise: str,
        hypotheses: list[str],
    ) -> list[NliContradiction]:
        raise NotImplementedError


class OnnxNliContradictionDetector(ContradictionDetector):
    """Runs a locally provisioned sequence-classification NLI model via ONNX Runtime."""

    name = "onnx-nli"

    def __init__(
        self,
        model_directory: Path,
        execution_provider: str = "CPUExecutionProvider",
        contradiction_threshold: float = 0.80,
    ):
        if not model_directory.exists():
            raise RuntimeError(f"NLI model directory does not exist: {model_directory}")
        try:
            import numpy as np
            import onnxruntime as ort
            from transformers import AutoConfig, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "ONNX NLI requires onnxruntime, numpy and transformers. "
                "Install requirements-multimodal.txt and requirements-rag-onnx.txt."
            ) from exc

        model_path = model_directory / "model.onnx"
        if not model_path.exists():
            raise RuntimeError(f"NLI ONNX model file is missing: {model_path}")
        self.np = np
        self.tokenizer = AutoTokenizer.from_pretrained(model_directory, local_files_only=True)
        configuration = AutoConfig.from_pretrained(model_directory, local_files_only=True)
        self.session = ort.InferenceSession(
            str(model_path),
            providers=[execution_provider],
        )
        self.threshold = contradiction_threshold
        self.contradiction_index = self._find_contradiction_index(configuration.id2label)

    def find_contradictions(
        self,
        premise: str,
        hypotheses: list[str],
    ) -> list[NliContradiction]:
        contradictions: list[NliContradiction] = []
        input_names = {item.name for item in self.session.get_inputs()}
        for hypothesis in hypotheses:
            encoded = self.tokenizer(
                premise,
                hypothesis,
                truncation=True,
                max_length=512,
                return_tensors="np",
            )
            inputs = {
                key: value.astype("int64")
                for key, value in encoded.items()
                if key in input_names
            }
            logits = self.session.run(None, inputs)[0][0]
            probabilities = self._softmax(logits)
            probability = float(probabilities[self.contradiction_index])
            if probability >= self.threshold:
                contradictions.append(NliContradiction(claim=hypothesis, confidence=probability))
        return contradictions

    def _softmax(self, logits: Any):
        shifted = logits - self.np.max(logits)
        values = self.np.exp(shifted)
        return values / values.sum()

    @staticmethod
    def _find_contradiction_index(id_to_label: dict[int, str] | dict[str, str]) -> int:
        for index, label in id_to_label.items():
            if "contradiction" in label.casefold():
                return int(index)
        raise RuntimeError("NLI model config must expose a CONTRADICTION label.")


class MedicalGuardrail:
    """Fail-closed validation gate before an AI summary is written to EMR/FHIR."""

    def __init__(
        self,
        raw_clinical_text: str,
        ai_summary_json: dict[str, Any] | BaseModel | str,
        nli_detector: ContradictionDetector | None = None,
        require_nli: bool = False,
    ):
        if not raw_clinical_text.strip():
            raise ValueError("raw_clinical_text must contain clinical evidence.")
        self.raw_clinical_text = raw_clinical_text
        self.ai_summary_json = ai_summary_json
        self.summary_text, self.summary_claims = self._summary_text(ai_summary_json)
        self.nli_detector = nli_detector
        self.require_nli = require_nli

    def validate(self) -> MedicalGuardrailResult:
        source_entities = self.extract_entities(self.raw_clinical_text)
        summary_entities = self.extract_entities(self.summary_text)
        issues = self._unsupported_entities(source_entities, summary_entities)
        checks = [
            "medication_entity_presence_check",
            "medication_dosage_exact_match_check",
            "clinical_measurement_exact_match_check",
        ]
        if self.nli_detector is None:
            checks.append("nli_not_configured")
            if self.require_nli:
                issues.append(
                    MedicalSafetyIssue(
                        code="NLI_VALIDATION_UNAVAILABLE",
                        message="Local NLI validation is required before EMR writeback but is not configured.",
                    )
                )
        else:
            checks.append(self.nli_detector.name)
            for contradiction in self.nli_detector.find_contradictions(
                self.raw_clinical_text,
                self.summary_claims,
            ):
                issues.append(
                    MedicalSafetyIssue(
                        code="NLI_CONTRADICTION",
                        message="NLI model identified a contradiction between source evidence and summary.",
                        summary_claim=contradiction.claim,
                        confidence=contradiction.confidence,
                    )
                )
        failed = bool(issues)
        return MedicalGuardrailResult(
            status="failed" if failed else "passed",
            allow_emr_writeback=not failed,
            checks_applied=checks,
            source_entities=source_entities,
            summary_entities=summary_entities,
            issues=issues,
        )

    @classmethod
    def extract_entities(cls, text: str) -> list[ExtractedMedicalEntity]:
        entities: list[ExtractedMedicalEntity] = []
        medications_seen: set[tuple[str, int, int]] = set()
        for match in MEDICATION_DOSE_RE.finditer(text):
            medication = cls._normalize(match.group("med"))
            dose = cls._normalize_dose(match.group("dose"), match.group("unit"))
            entities.append(
                ExtractedMedicalEntity(
                    entity_type="medication",
                    name=match.group("med"),
                    normalized_key=medication,
                    start_idx=match.start("med"),
                    end_idx=match.end("med"),
                )
            )
            entities.append(
                ExtractedMedicalEntity(
                    entity_type="medication_dose",
                    name=match.group("med"),
                    value=f"{match.group('dose')} {match.group('unit')}",
                    normalized_key=f"{medication}|{dose}",
                    start_idx=match.start(),
                    end_idx=match.end(),
                )
            )
            medications_seen.add((medication, match.start("med"), match.end("med")))
        for match in MEDICATION_CONTEXT_RE.finditer(text):
            medication = cls._normalize(match.group("med"))
            key = (medication, match.start("med"), match.end("med"))
            if key not in medications_seen:
                entities.append(
                    ExtractedMedicalEntity(
                        entity_type="medication",
                        name=match.group("med"),
                        normalized_key=medication,
                        start_idx=match.start("med"),
                        end_idx=match.end("med"),
                    )
                )
        normalized_text = cls._normalize(text)
        for medication in KNOWN_MEDICATIONS:
            if re.search(rf"\b{re.escape(medication)}\b", normalized_text):
                for match in re.finditer(rf"\b{re.escape(medication)}\b", normalized_text):
                    key = (medication, match.start(), match.end())
                    if key not in medications_seen:
                        entities.append(
                            ExtractedMedicalEntity(
                                entity_type="medication",
                                name=text[match.start() : match.end()],
                                normalized_key=medication,
                                start_idx=match.start(),
                                end_idx=match.end(),
                            )
                        )
                        medications_seen.add(key)
        for name, pattern in METRIC_PATTERNS.items():
            for match in pattern.finditer(text):
                value = cls._normalize_value(match.group("value"), match.groupdict().get("unit"))
                entities.append(
                    ExtractedMedicalEntity(
                        entity_type="clinical_measurement",
                        name=name,
                        value=value,
                        normalized_key=f"{name}|{value}",
                        start_idx=match.start(),
                        end_idx=match.end(),
                    )
                )
        return entities

    @staticmethod
    def _summary_text(summary: dict[str, Any] | BaseModel | str) -> tuple[str, list[str]]:
        if isinstance(summary, BaseModel):
            summary = summary.model_dump(mode="json")
        if isinstance(summary, str):
            try:
                parsed = json.loads(summary)
            except json.JSONDecodeError:
                return summary, [summary]
            summary = parsed
        claims: list[str] = []
        if isinstance(summary, dict) and isinstance(summary.get("claims"), list):
            claims = [
                item.get("text", "")
                for item in summary["claims"]
                if isinstance(item, dict) and item.get("text")
            ]
        if not claims and isinstance(summary, dict) and isinstance(summary.get("sentences"), list):
            claims = [
                item.get("summary_sentence", "")
                for item in summary["sentences"]
                if isinstance(item, dict) and item.get("summary_sentence")
            ]
        if not claims:
            claims = [json.dumps(summary, ensure_ascii=False)]
        return "\n".join(claims), claims

    @staticmethod
    def _unsupported_entities(
        source: list[ExtractedMedicalEntity],
        summary: list[ExtractedMedicalEntity],
    ) -> list[MedicalSafetyIssue]:
        source_keys = {(item.entity_type, item.normalized_key) for item in source}
        issues: list[MedicalSafetyIssue] = []
        code_by_type = {
            "medication": "UNSUPPORTED_MEDICATION",
            "medication_dose": "UNSUPPORTED_MEDICATION_DOSAGE",
            "clinical_measurement": "UNSUPPORTED_CLINICAL_MEASUREMENT",
        }
        for entity in summary:
            if (entity.entity_type, entity.normalized_key) not in source_keys:
                issues.append(
                    MedicalSafetyIssue(
                        code=code_by_type[entity.entity_type],
                        message=(
                            f"Summary contains {entity.entity_type} not exactly supported "
                            "by submitted clinical text."
                        ),
                        entity=entity,
                    )
                )
        return issues

    @staticmethod
    def _normalize(text: str) -> str:
        folded = unicodedata.normalize("NFKD", text.casefold())
        return "".join(item for item in folded if not unicodedata.combining(item))

    @classmethod
    def _normalize_dose(cls, amount: str, unit: str) -> str:
        return f"{amount.replace(',', '.')} {cls._normalize(unit)}"

    @classmethod
    def _normalize_value(cls, value: str, unit: str | None) -> str:
        normalized_value = re.sub(r"\s+", "", value.replace(",", "."))
        return f"{normalized_value} {cls._normalize(unit or '')}".strip()
