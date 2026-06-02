"""Multi-shot sequence schemas for the PixVerse Bridge Phase 2 chainer.

Defines the request/response contracts for POST /v1/bridge/shot-sequence,
which generates multiple PixVerse V6 LPD prompts from a shared anchor
subject with per-shot camera, motion, and framing variations.

Implements the PixVerse V6 Anchor-Repeat Protocol: a common anchor subject
descriptor is repeated across every shot to maintain character/product
consistency, while each shot varies camera distance, motion, and framing.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.bridge import (
    BridgeConstraints,
    BridgeGenerationParams,
    BridgeResponse,
    BridgeStyle,
)


class ShotSpec(BaseModel):
    """Specification for a single shot within a multi-shot sequence.

    Each shot shares the same anchor subject but varies in camera distance,
    framing, and optional transition notes. The shot_type drives LPD
    camera/lens selection and prompt framing.
    """

    shot_index: int = Field(
        ge=0,
        description="Zero-based position in the shot sequence (must be sequential)",
    )
    shot_type: Literal["wide", "medium", "close-up"] = Field(
        description=(
            "Framing distance: wide (establishing), medium (detail), "
            "close-up (intimate)"
        ),
    )
    style_overrides: BridgeStyle | None = Field(
        default=None,
        description="Shot-specific style overrides merged on top of the sequence base style",
    )
    transition_notes: str | None = Field(
        default=None,
        max_length=1024,
        description="How this shot transitions from the previous (e.g. 'cut on action')",
    )
    custom_instruction: str | None = Field(
        default=None,
        max_length=2048,
        description="Extra narrative or technical instruction for this specific shot",
    )


class ShotSequenceRequest(BaseModel):
    """Request to generate a coherent multi-shot video sequence.

    All shots share a common anchor subject (the Anchor-Repeat Protocol core),
    base narrative concept, and world context. Each shot varies camera distance,
    motion, and framing while keeping the anchor constant to maintain
    character/product consistency across the sequence.
    """

    anchor: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="Core physical subject descriptor repeated across all shots",
    )
    base_prompt: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Overall narrative concept serving as the foundation for all shots",
    )
    sketch_notes: str | None = Field(
        default=None,
        max_length=65536,
        description="World/context notes shared across all shots",
    )
    constraints: BridgeConstraints | None = Field(
        default=None,
        description="Shared output constraints; anchor is automatically added to must_include",
    )
    style: BridgeStyle | None = Field(
        default=None,
        description="Base style sliders; individual shots may override via style_overrides",
    )
    generation_params: BridgeGenerationParams | None = Field(
        default=None,
        description="Semantic-Canvas diffusion parameters shared across all shots",
    )
    shots: list[ShotSpec] = Field(
        ...,
        min_length=2,
        max_length=12,
        description="Ordered shot specifications (2–12 shots)",
    )
    drift_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Shots with semantic drift above this threshold are flagged for re-prompting",
    )

    @model_validator(mode="after")
    def validate_shot_indices_sequential(self) -> ShotSequenceRequest:
        """Ensure shot indices are sequential starting from 0."""
        indices = [s.shot_index for s in self.shots]
        expected = list(range(len(indices)))
        if indices != expected:
            raise ValueError(
                f"Shot indices must be sequential starting from 0. "
                f"Expected {expected}, got {indices}"
            )
        return self


class ShotResult(BaseModel):
    """Result for a single shot within a sequence, including drift analysis."""

    shot_index: int = Field(description="Zero-based position in the shot sequence")
    shot_type: str = Field(description="Framing distance: wide, medium, or close-up")
    bridge_response: BridgeResponse = Field(
        description="Full bridge result including LPD prompt and optimized text"
    )
    drift_from_previous: float | None = Field(
        default=None,
        description="Semantic distance from the previous shot (None for the first shot)",
    )
    flagged: bool = Field(
        default=False,
        description="True if drift_from_previous exceeds the configured threshold",
    )


class ShotSequenceResponse(BaseModel):
    """Result of a multi-shot sequence generation with coherence analysis.

    Includes per-shot LPD prompts, drift metrics between consecutive shots,
    and an overall coherence score indicating how well the sequence holds
    together semantically.
    """

    anchor: str = Field(description="The shared subject descriptor used across all shots")
    shots: list[ShotResult] = Field(
        description="Ordered shot results, one per requested shot"
    )
    coherence_score: float = Field(
        description=(
            "Overall semantic coherence: 1.0 - average_drift. "
            "Range ~0–1; higher is better."
        )
    )
    flagged_shots: list[int] = Field(
        default_factory=list,
        description="Zero-based indices of shots flagged for re-prompting (drift > threshold)",
    )
