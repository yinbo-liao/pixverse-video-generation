"""Production Pipeline schemas — Phase 5.

Chains all 4 phases into a single end-to-end production workflow.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.bridge import BridgeConstraints, BridgeGenerationParams, BridgeStyle
from app.schemas.concept_fusion import ConceptInput, FusionResponse
from app.schemas.feedback_loop import FeedbackResponse
from app.schemas.parameter_injection import ParameterInjectionResponse
from app.schemas.shot_sequence import ShotSequenceResponse


class PipelineRequest(BaseModel):
    """Single request to run the full production pipeline."""

    prompt: str = Field(..., min_length=1, max_length=4096, description="Core narrative concept")
    sketch_notes: str | None = Field(default=None, max_length=65536)
    concepts: list[ConceptInput] | None = Field(
        default=None,
        min_length=2,
        max_length=5,
        description="Optional: fuse multiple concepts before generation",
    )
    unifying_theme: str = Field(default="", max_length=1024)
    style: BridgeStyle = Field(default_factory=BridgeStyle)
    constraints: BridgeConstraints | None = Field(
        default=None, description="Output constraints shared across all pipeline stages"
    )
    generation_params: BridgeGenerationParams | None = Field(
        default=None, description="Diffusion parameters shared across all stages"
    )
    target_duration: int = Field(default=5, ge=1, le=15)
    aspect_ratio: str = Field(default="16:9", pattern=r"^(9:16|1:1|16:9|21:9)$")
    shot_count: int = Field(default=3, ge=2, le=12, description="Number of shots in sequence")
    max_feedback_iterations: int = Field(default=2, ge=0, le=5)


class PipelineStage(BaseModel):
    """Result snapshot from one pipeline stage."""

    stage: str = Field(
        description="Stage name: fusion, parameter_injection, shot_sequence, feedback"
    )
    status: str = Field(description="completed, skipped, or failed")
    duration_ms: float = Field(default=0.0, description="Stage execution time in ms")


class PipelineResponse(BaseModel):
    """Complete production pipeline deliverable."""

    generation_id: str
    # Stage results
    fusion_result: FusionResponse | None = Field(default=None)
    parameter_result: ParameterInjectionResponse | None = Field(default=None)
    shot_sequence_result: ShotSequenceResponse | None = Field(default=None)
    feedback_result: FeedbackResponse | None = Field(default=None)
    # Pipeline metadata
    stages: list[PipelineStage] = Field(default_factory=list)
    total_duration_ms: float = Field(default=0.0)
    estimated_credits: float = Field(
        default=0.0, description="Estimated PixVerse V6 credit cost"
    )
    final_lpd_prompts: list[str] = Field(
        default_factory=list,
        description="Final LPD prompts ready for PixVerse V6 generation",
    )
