from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FhirModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class FhirIdentifier(FhirModel):
    system: str | None = None
    value: str = Field(min_length=1)


class FhirReference(FhirModel):
    reference: str = Field(min_length=1)
    display: str | None = None


class FhirCoding(FhirModel):
    system: str | None = None
    code: str | None = None
    display: str | None = None


class FhirCodeableConcept(FhirModel):
    coding: list[FhirCoding] = Field(default_factory=list)
    text: str | None = None

    @model_validator(mode="after")
    def require_code_or_text(self) -> "FhirCodeableConcept":
        if not self.coding and not self.text:
            raise ValueError("CodeableConcept requires coding or text.")
        return self


class FhirNarrative(FhirModel):
    status: Literal["generated", "extensions", "additional", "empty"] = "generated"
    div: str = Field(pattern=r"^<div xmlns=\"http://www\.w3\.org/1999/xhtml\">.*</div>$")


class Patient(FhirModel):
    resource_type: Literal["Patient"] = Field("Patient", alias="resourceType")
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9.-]+$")
    identifier: list[FhirIdentifier] = Field(default_factory=list)
    active: bool | None = None


class Encounter(FhirModel):
    resource_type: Literal["Encounter"] = Field("Encounter", alias="resourceType")
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9.-]+$")
    status: Literal[
        "planned",
        "arrived",
        "triaged",
        "in-progress",
        "onleave",
        "finished",
        "cancelled",
        "entered-in-error",
        "unknown",
    ]
    subject: FhirReference


class ObservationQuantity(FhirModel):
    value: float
    unit: str | None = None
    system: str | None = None
    code: str | None = None


class Observation(FhirModel):
    resource_type: Literal["Observation"] = Field("Observation", alias="resourceType")
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9.-]+$")
    status: Literal[
        "registered",
        "preliminary",
        "final",
        "amended",
        "corrected",
        "cancelled",
        "entered-in-error",
        "unknown",
    ]
    code: FhirCodeableConcept
    subject: FhirReference
    encounter: FhirReference | None = None
    effective_date_time: datetime | None = Field(default=None, alias="effectiveDateTime")
    value_string: str | None = Field(default=None, alias="valueString", max_length=10000)
    value_quantity: ObservationQuantity | None = Field(default=None, alias="valueQuantity")
    interpretation: list[FhirCodeableConcept] = Field(default_factory=list)
    note: list[dict[str, str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_observed_value(self) -> "Observation":
        if self.value_string is None and self.value_quantity is None and not self.note:
            raise ValueError("Observation requires valueString, valueQuantity, or note.")
        return self


class CompositionSection(FhirModel):
    title: str | None = None
    code: FhirCodeableConcept | None = None
    text: FhirNarrative | None = None
    entry: list[FhirReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_section_content(self) -> "CompositionSection":
        if self.text is None and not self.entry:
            raise ValueError("FHIR Composition section requires text or an entry.")
        return self


class Composition(FhirModel):
    resource_type: Literal["Composition"] = Field("Composition", alias="resourceType")
    id: str
    identifier: FhirIdentifier | None = None
    status: Literal["preliminary", "final", "amended", "entered-in-error"]
    type: FhirCodeableConcept
    subject: FhirReference
    encounter: FhirReference | None = None
    date: datetime
    author: list[FhirReference] = Field(min_length=1)
    title: str = Field(min_length=1)
    text: FhirNarrative | None = None
    section: list[CompositionSection] = Field(min_length=1)


class ConditionEvidence(FhirModel):
    code: list[FhirCodeableConcept] = Field(default_factory=list)
    detail: list[FhirReference] = Field(default_factory=list)


class Condition(FhirModel):
    resource_type: Literal["Condition"] = Field("Condition", alias="resourceType")
    id: str
    clinical_status: FhirCodeableConcept | None = Field(default=None, alias="clinicalStatus")
    verification_status: FhirCodeableConcept | None = Field(default=None, alias="verificationStatus")
    category: list[FhirCodeableConcept] = Field(default_factory=list)
    code: FhirCodeableConcept
    subject: FhirReference
    encounter: FhirReference | None = None
    recorded_date: datetime | None = Field(default=None, alias="recordedDate")
    evidence: list[ConditionEvidence] = Field(default_factory=list)
    note: list[dict[str, str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_clinical_status(self) -> "Condition":
        is_problem_item = any(
            coding.code == "problem-list-item"
            for category in self.category
            for coding in category.coding
        )
        entered_in_error = any(
            coding.code == "entered-in-error"
            for coding in (self.verification_status.coding if self.verification_status else [])
        )
        if entered_in_error and self.clinical_status is not None:
            raise ValueError("clinicalStatus must not be set for an entered-in-error Condition.")
        if is_problem_item and not entered_in_error and self.clinical_status is None:
            raise ValueError("Problem-list Conditions require clinicalStatus.")
        return self


class ClinicalImpressionFinding(FhirModel):
    item_codeable_concept: FhirCodeableConcept = Field(alias="itemCodeableConcept")
    basis: str | None = None


class ClinicalImpression(FhirModel):
    resource_type: Literal["ClinicalImpression"] = Field("ClinicalImpression", alias="resourceType")
    id: str
    status: Literal["in-progress", "completed", "entered-in-error"]
    description: str | None = None
    subject: FhirReference
    encounter: FhirReference | None = None
    date: datetime
    assessor: FhirReference | None = None
    supporting_info: list[FhirReference] = Field(default_factory=list, alias="supportingInfo")
    summary: str | None = None
    finding: list[ClinicalImpressionFinding] = Field(default_factory=list)
    note: list[dict[str, str]] = Field(default_factory=list)


FhirResource = Annotated[
    Union[Composition, Condition, ClinicalImpression],
    Field(discriminator="resource_type"),
]


FhirClinicalInputResource = Annotated[
    Union[Patient, Encounter, Observation],
    Field(discriminator="resource_type"),
]


class FhirClinicalInputEntry(FhirModel):
    full_url: str | None = Field(default=None, alias="fullUrl")
    resource: FhirClinicalInputResource


class FhirClinicalInputBundle(FhirModel):
    resource_type: Literal["Bundle"] = Field("Bundle", alias="resourceType")
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9.-]+$")
    type: Literal["collection", "document", "message", "transaction", "batch"]
    entry: list[FhirClinicalInputEntry] = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def require_clinical_resources(self) -> "FhirClinicalInputBundle":
        types = [item.resource.resource_type for item in self.entry]
        if types.count("Patient") != 1:
            raise ValueError("Input FHIR Bundle must contain exactly one Patient.")
        if "Encounter" not in types or "Observation" not in types:
            raise ValueError("Input FHIR Bundle must contain Encounter and Observation resources.")
        return self


class BundleRequest(FhirModel):
    method: Literal["POST", "PUT"]
    url: str = Field(min_length=1)


class BundleEntry(FhirModel):
    full_url: str = Field(alias="fullUrl", pattern=r"^urn:uuid:[0-9a-f-]{36}$")
    resource: FhirResource
    request: BundleRequest


class FhirTransactionBundle(FhirModel):
    resource_type: Literal["Bundle"] = Field("Bundle", alias="resourceType")
    id: str
    type: Literal["transaction"] = "transaction"
    timestamp: datetime
    entry: list[BundleEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_full_urls(self) -> "FhirTransactionBundle":
        urls = [item.full_url for item in self.entry]
        if len(urls) != len(set(urls)):
            raise ValueError("Bundle entry fullUrl values must be unique.")
        return self
