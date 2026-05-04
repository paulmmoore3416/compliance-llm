"""Pydantic request/response schemas for the Compliance-Llama API."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DeviceClass(str, Enum):
    I = "Class I"
    II = "Class II"
    III = "Class III"


class RiskProfile(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class ArtifactType(str, Enum):
    design_controls_sop = "design_controls_sop"
    capa_sop = "capa_sop"
    risk_management_sop = "risk_management_sop"
    complaint_handling_sop = "complaint_handling_sop"
    document_control_sop = "document_control_sop"
    clause_mapping = "clause_mapping"
    custom = "custom"


class DeviceContext(BaseModel):
    name: str = Field(..., description="Device commercial / engineering name")
    device_class: DeviceClass
    indication_for_use: str = Field(..., min_length=20)
    risk_profile: RiskProfile
    intended_user: str = Field(..., min_length=3)
    use_environment: str = Field(..., min_length=3)
    additional_notes: str | None = None

    def render(self) -> str:
        rendered = (
            f"Device Name: {self.name}\n"
            f"Device Class: {self.device_class.value}\n"
            f"Risk Profile: {self.risk_profile.value.title()}\n"
            f"Intended User: {self.intended_user}\n"
            f"Use Environment: {self.use_environment}\n"
            f"Indication for Use: {self.indication_for_use}"
        )
        if self.additional_notes:
            rendered += f"\nAdditional Notes: {self.additional_notes}"
        return rendered


_INSTRUCTION_TEMPLATES: dict[ArtifactType, str] = {
    ArtifactType.design_controls_sop: (
        "Draft a 'Design and Development Planning' SOP for the device described below, "
        "in compliance with ISO 13485:2016 §7.3 and 21 CFR 820.30. Include explicit clause citations."
    ),
    ArtifactType.capa_sop: (
        "Draft a Corrective and Preventive Action (CAPA) SOP scoped to the device below, "
        "citing ISO 13485 §8.5.2/§8.5.3 and 21 CFR 820.100."
    ),
    ArtifactType.risk_management_sop: (
        "Draft a Risk Management SOP for the device below, aligning ISO 14971 with "
        "ISO 13485 §7.1 and 21 CFR 820.30(g)."
    ),
    ArtifactType.complaint_handling_sop: (
        "Draft a Complaint Handling SOP for the device below per ISO 13485 §8.2.2 and "
        "21 CFR 820.198, including MDR/Vigilance triggers."
    ),
    ArtifactType.document_control_sop: (
        "Draft a Document Control SOP scoped to the device below per ISO 13485 §4.2.4 "
        "and 21 CFR 820.40."
    ),
    ArtifactType.clause_mapping: (
        "Map the device described below to the most relevant ISO 13485:2016 and "
        "21 CFR Part 820 clauses, with a one-sentence rationale per clause."
    ),
}


class GenerateRequest(BaseModel):
    device: DeviceContext
    artifact: ArtifactType = ArtifactType.design_controls_sop
    custom_instruction: str | None = Field(
        None,
        description="Required when artifact == 'custom'. Free-form instruction.",
    )
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(2048, ge=64, le=8192)
    compare_with_base: bool = Field(
        False,
        description="If true, the server also runs the base (un-tuned) model and "
                    "returns a side-by-side payload via the /compare endpoint.",
    )

    def instruction(self) -> str:
        if self.artifact == ArtifactType.custom:
            if not self.custom_instruction:
                raise ValueError("custom_instruction is required when artifact='custom'")
            return self.custom_instruction
        return _INSTRUCTION_TEMPLATES[self.artifact]


class GenerateResponse(BaseModel):
    artifact: ArtifactType
    model: str
    content: str
    output_tokens: int
    latency_ms: int


class CompareResponse(BaseModel):
    fine_tuned: GenerateResponse
    base: GenerateResponse


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    vllm_reachable: bool
    fine_tuned_model: str
