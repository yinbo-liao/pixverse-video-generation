"""Bridge API request and response models.

These define the complete Phase 1 API contract:
  - BridgeRequest:  what callers send to the bridge (a narrative concept)
  - BridgeResponse: what the bridge returns (optimized text + LPD prompt)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.prompt import PixVersePrompt

# ---- Nested sub-models for BridgeRequest ----


class BridgeConstraints(BaseModel):
    """Constraints forwarded to Semantic-Canvas and used for LPD mapping.

    These map directly to Semantic-Canvas ConstraintConfig fields.
    """

    tone: str | None = Field(
        default=None,
        description="Tone descriptor parsed for lighting cues (e.g. 'noir', 'warm', 'clinical')",
    )
    max_length: int = Field(
        default=800, ge=1, le=4096, description="Maximum output character count"
    )
    must_include: list[str] = Field(
        default_factory=list,
        description="Keywords/phrases that must appear — mapped to LPD Subject component",
    )
    must_exclude: list[str] = Field(
        default_factory=list, description="Keywords/phrases to avoid in output"
    )
    brand_voice_id: str | None = Field(default=None, description="Semantic-Canvas brand voice ID")


class BridgeStyle(BaseModel):
    """Style vector sliders controlling LPD motion, camera, and tone output.

    These map directly to Semantic-Canvas StyleConfig fields, with
    additional semantics for the PixVerse LPD mapping.
    """

    formality: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Camera formality: 0.0=handheld/casual verite, 0.5=standard, 1.0=cinematic",
    )
    enthusiasm: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Motion intensity: 0.0=slow/dramatic, 0.5=natural, 1.0=rapid/dynamic",
    )
    technical_depth: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Semantic detail level for prompt optimization",
    )
    description: str | None = Field(default=None, description="Free-text style guidance")


class BridgeGenerationParams(BaseModel):
    """Parameters forwarded to Semantic-Canvas diffusion generation."""

    num_steps: int = Field(
        default=12,
        ge=4,
        le=24,
        description="Denoising steps (higher = more coherent, lower = faster)",
    )
    temperature: float = Field(
        default=0.8, ge=0.1, le=2.0, description="Output diversity (higher = more creative)"
    )
    seed: int | None = Field(default=None, description="Random seed for reproducible generation")


# ---- Top-level Bridge API models ----


class BridgeRequest(BaseModel):
    """Inbound request: a narrative concept with optimization parameters.

    The bridge sends this to Semantic-Canvas for diffusion-based optimization,
    then decomposes the result into PixVerse LPD components.
    """

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Core narrative concept or rough prompt to optimize",
    )
    sketch_notes: str | None = Field(
        default=None,
        max_length=65536,
        description="Extended world/context notes — mapped to LPD Environment + Lighting",
    )
    constraints: BridgeConstraints = Field(
        default_factory=BridgeConstraints,
        description="Output constraints and anchor keywords",
    )
    style: BridgeStyle = Field(
        default_factory=BridgeStyle, description="Style sliders for motion/camera/tone"
    )
    generation_params: BridgeGenerationParams = Field(
        default_factory=BridgeGenerationParams,
        description="Semantic-Canvas diffusion parameters",
    )


class BridgeResponse(BaseModel):
    """Bridge output: the optimized text plus the assembled PixVerse LPD prompt.

    Callers can use `lpd_text` directly as the PixVerse V6 prompt, or
    inspect `lpd_prompt` for individual component tuning before rendering.
    """

    generation_id: str = Field(description="Unique ID for this generation (from Semantic-Canvas)")
    original_prompt: str = Field(description="The prompt as originally submitted")
    optimized_text: str = Field(description="Semantic-Canvas optimized narrative text")
    lpd_prompt: PixVersePrompt = Field(description="Decomposed LPD prompt components")
    lpd_text: str = Field(description="Assembled LPD format string ready for PixVerse V6")
    metadata: dict = Field(
        default_factory=dict,
        description="Generation metadata (timing, tokens, constraint compliance, cache info)",
    )
