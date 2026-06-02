"""Multi-Concept Fusion schemas — Phase 4.

Blends multiple independent narrative concepts into a single cohesive
PixVerse V6 prompt using latent embedding fusion.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.bridge import BridgeGenerationParams, BridgeResponse, BridgeStyle

ConceptRole = Literal["foreground", "background", "ambient"]


class ConceptInput(BaseModel):
    """A single concept to fuse into the unified scene."""

    prompt: str = Field(..., min_length=1, max_length=2048)
    weight: float = Field(
        default=1.0,
        ge=0.1,
        le=2.0,
        description="Blend weight for this concept (0.1=trace, 1.0=equal, 2.0=dominant)",
    )
    role: ConceptRole = Field(
        default="foreground",
        description="Spatial role: foreground, background, or ambient atmosphere",
    )


class FusionRequest(BaseModel):
    """Request to fuse multiple concepts into one cohesive prompt."""

    concepts: list[ConceptInput] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="2-5 concepts to blend into a unified scene",
    )
    unifying_theme: str = Field(
        default="",
        max_length=1024,
        description="Optional overarching theme to bind concepts together",
    )
    style: BridgeStyle = Field(
        default_factory=BridgeStyle,
        description="Shared style for the unified scene",
    )
    generation_params: BridgeGenerationParams = Field(
        default_factory=BridgeGenerationParams,
    )


class ConceptResult(BaseModel):
    """Result for an individual concept within the fusion."""

    concept_index: int = Field(description="Index into the original concepts list")
    concept_prompt: str = Field(description="Original concept prompt")
    optimized_text: str = Field(description="Semantic-Canvas optimized text for this concept")
    weight: float = Field(description="Blend weight used")
    role: str = Field(description="Spatial role assigned")


class FusionResponse(BaseModel):
    """Result of multi-concept fusion."""

    generation_id: str = Field(description="Unique ID for this fusion run")
    unified_prompt: BridgeResponse = Field(
        description="Full bridge result for the unified scene"
    )
    concept_results: list[ConceptResult] = Field(
        description="Individual concept results before fusion"
    )
    blend_coherence: float = Field(
        ge=0.0,
        le=1.0,
        description="How well the concepts blend together (1.0=seamless)",
    )
    scene_composition: str = Field(
        description="Natural-language scene composition directive describing spatial layout"
    )
