"""PixVerse V6 Feedback Loop schemas — Phase 3.

Defines the request/response contracts for POST /v1/bridge/feedback-loop,
which implements the 3-Generation Rule with artifact analysis, iterative
prompt refinement, and best-variation selection.

The feedback loop:
  1. Generates 3 motion-strength variations (baseline, +10%, -10%).
  2. Analyzes each for 6 artifact types using text heuristics.
  3. Iteratively refines flagged prompts (up to max_iterations).
  4. Selects the best variation by cleanliness, stability, and coherence.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.bridge import (
    BridgeConstraints,
    BridgeGenerationParams,
    BridgeResponse,
    BridgeStyle,
)


class ArtifactType(StrEnum):
    """Six artifact categories from the PixVerse V6 QA guideline."""

    motion_smearing = "motion_smearing"
    hand_distortion = "hand_distortion"
    facial_drift = "facial_drift"
    lighting_inconsistency = "lighting_inconsistency"
    subject_blending = "subject_blending"
    temporal_flicker = "temporal_flicker"


class ArtifactFinding(BaseModel):
    """A single detected artifact with severity, location, and suggested fix."""

    type: ArtifactType = Field(description="Category of detected artifact")
    severity: float = Field(
        ge=0.0,
        le=1.0,
        description="How severe this artifact is (0=negligible, 1=critical)",
    )
    location: str = Field(
        default="",
        description="Which keywords or phrase triggered the detection",
    )
    suggested_fix: str = Field(
        default="",
        description="Natural-language instruction for fixing this artifact",
    )


class ArtifactReport(BaseModel):
    """Aggregated artifact analysis for a single prompt variation."""

    findings: list[ArtifactFinding] = Field(
        default_factory=list,
        description="All detected artifacts",
    )
    overall_risk_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Worst-case severity across all findings (max, not avg)",
    )
    is_clean: bool = Field(
        default=True,
        description="True if no artifacts were detected",
    )

    @model_validator(mode="after")
    def compute_derived_fields(self) -> ArtifactReport:
        """Compute overall_risk_score and is_clean from findings."""
        if self.findings:
            self.overall_risk_score = max(f.severity for f in self.findings)
            self.is_clean = False
        else:
            self.overall_risk_score = 0.0
            self.is_clean = True
        return self


VariationType = Literal["baseline", "high_motion", "low_motion"]
RefinementMode = Literal["auto", "manual"]


class VariationResult(BaseModel):
    """Result for a single motion-strength variation after refinement."""

    variation_type: VariationType = Field(
        description="Which motion variant: baseline, high_motion, or low_motion"
    )
    bridge_response: BridgeResponse = Field(
        description="Final bridge result (LPD prompt + optimized text)"
    )
    artifact_report: ArtifactReport = Field(
        description="Artifact analysis of the final (post-refinement) prompt"
    )
    refinement_iterations: int = Field(
        default=0,
        ge=0,
        description="Number of refinement iterations applied",
    )
    final_prompt: str = Field(
        description="LPD text after all refinements, ready for PixVerse V6"
    )
    refinement_history: list[ArtifactReport] = Field(
        default_factory=list,
        description="Artifact report snapshot at each refinement step (for audit trail)",
    )


class FeedbackRequest(BaseModel):
    """Request to run the PixVerse V6 Feedback Loop on a narrative concept."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Core narrative concept to optimize and analyze",
    )
    sketch_notes: str | None = Field(
        default=None,
        max_length=65536,
        description="World/context notes for the prompt",
    )
    constraints: BridgeConstraints = Field(
        default_factory=BridgeConstraints,
        description="Output constraints and anchor keywords",
    )
    style: BridgeStyle = Field(
        default_factory=BridgeStyle,
        description="Base style sliders (enthusiasm drives motion variation)",
    )
    generation_params: BridgeGenerationParams = Field(
        default_factory=BridgeGenerationParams,
        description="Semantic-Canvas diffusion parameters",
    )
    max_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum refinement iterations per variation (prevents infinite loops)",
    )
    refinement_mode: RefinementMode = Field(
        default="auto",
        description="auto = apply fixes automatically; manual = report findings only",
    )


class FeedbackResponse(BaseModel):
    """Complete feedback loop result with all variations and selection."""

    generation_id: str = Field(
        description="Unique ID for this feedback loop run"
    )
    original_prompt: str = Field(
        description="The prompt as originally submitted"
    )
    variations: list[VariationResult] = Field(
        description="Exactly 3 variations: baseline, high_motion, low_motion"
    )
    selected_variation: VariationResult = Field(
        description="The best variation chosen by the selection algorithm"
    )
    selection_reason: str = Field(
        description="Human-readable justification for the selection"
    )
    total_iterations: int = Field(
        default=0,
        ge=0,
        description="Total refinement iterations across all variations"
    )
