"""Dynamic Parameter Injection schemas — Phase 4.

Maps Semantic-Canvas style vectors to precise PixVerse V6 generation
parameters (motion strength, camera type, lens, lighting, render quality).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.bridge import (
    BridgeConstraints,
    BridgeGenerationParams,
    BridgeResponse,
    BridgeStyle,
)


class CameraParams(BaseModel):
    """Camera configuration derived from formality."""

    camera_type: str = Field(description="e.g. handheld, tripod, steadicam, crane/jib")
    lens_mm: int = Field(
        ge=8, le=600, description="Focal length (24=wide, 50=normal, 135=telephoto)"
    )
    stabilization: str = Field(description="Stabilization method (none, gimbal, gyro)")
    movement: str = Field(description="Camera movement pattern for PixVerse prompt")


class MotionParams(BaseModel):
    """Motion configuration derived from enthusiasm."""

    strength_pct: int = Field(ge=0, le=100, description="Motion Strength slider value (0-100)")
    speed_label: str = Field(
        description="Speed descriptor (static, slow, natural, dynamic, explosive)"
    )
    acceleration: str = Field(description="Acceleration curve for motion")


class LightingParams(BaseModel):
    """Lighting configuration derived from technical_depth."""

    setup_name: str = Field(
        description="Lighting setup (ambient, 2-point, 3-point, cinematic)"
    )
    key_light: str = Field(description="Key light description")
    fill_light: str = Field(description="Fill light description")
    back_light: str = Field(description="Back/rim light description")
    complexity: str = Field(description="Approximate light source count")


class RenderParams(BaseModel):
    """Render quality configuration derived from technical_depth."""

    tier: str = Field(description="draft, standard, high, or cinematic")
    model: str = Field(description="PixVerse model: V6 Standard, V6 Pro, or V6 Pro + C1")
    upscale: str = Field(description="Upscaling pipeline description")


class PixVerseParams(BaseModel):
    """Complete set of PixVerse V6 generation parameters."""

    motion: MotionParams = Field(description="Motion strength and speed profile")
    camera: CameraParams = Field(description="Camera type, lens, and stabilization")
    lighting: LightingParams = Field(description="Lighting setup")
    render: RenderParams = Field(description="Render quality tier and upscaling")
    aspect_ratio: str = Field(default="16:9", description="Aspect ratio (9:16, 1:1, 16:9, 21:9)")
    duration_seconds: int = Field(default=5, ge=1, le=15, description="Target video duration")


class ParameterInjectionRequest(BaseModel):
    """Request to inject style vectors into PixVerse V6 parameters."""

    prompt: str = Field(..., min_length=1, max_length=4096)
    sketch_notes: str | None = Field(default=None, max_length=65536)
    constraints: BridgeConstraints = Field(default_factory=BridgeConstraints)
    style: BridgeStyle = Field(default_factory=BridgeStyle)
    generation_params: BridgeGenerationParams = Field(default_factory=BridgeGenerationParams)
    target_duration: int = Field(
        default=5, ge=1, le=15, description="Target video duration in seconds"
    )
    aspect_ratio: str = Field(
        default="16:9",
        pattern=r"^(9:16|1:1|16:9|21:9)$",
        description="Target aspect ratio",
    )


class ParameterInjectionResponse(BaseModel):
    """Result of dynamic parameter injection."""

    generation_id: str = Field(description="Unique ID for this injection run")
    bridge_response: BridgeResponse = Field(
        description="The LPD prompt generated for these parameters"
    )
    params: PixVerseParams = Field(description="All injected PixVerse V6 parameters")
    justifications: dict[str, str] = Field(
        default_factory=dict,
        description="Human-readable justification for each parameter choice",
    )
