"""PixVerse V6 LPD (Literal Physical Description) prompt component models.

The LPD method structures video prompts as six sequential components:
  [Subject] + [Action/Motion] + [Environment] + [Lighting] + [Camera/Lens] + [Audio]

Each component is a standalone Pydantic model so the bridge can manipulate
individual fields independently. The PixVersePrompt container assembles them
into the final LPD text string that PixVerse V6 consumes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Subject(BaseModel):
    """Literal physical description of the video subject.

    This is the core element of the Anchor-Repeat Protocol: the same Subject
    descriptor should appear across every shot in a multi-shot sequence
    to maintain character/product consistency.
    """

    description: str = Field(
        default="",
        description="Core physical subject descriptor (e.g. clothing, build, species, material)",
    )
    reference_image_count: int = Field(
        default=0,
        ge=0,
        le=7,
        description="Number of reference images uploaded for character/product anchoring (max 7)",
    )


class ActionMotion(BaseModel):
    """Action and motion description with parametric intensity control."""

    description: str = Field(
        default="",
        description=(
            "Action/motion phrase for LPD template "
            "(e.g. 'walks slowly', 'sprints', 'orbits')"
        ),
    )
    motion_strength: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Motion intensity: 0.0=static, 0.5=natural, 1.0=explosive",
    )


class Environment(BaseModel):
    """Physical environment and setting description."""

    description: str = Field(
        default="",
        description="Setting, location, weather, time of day, surrounding objects",
    )


class Lighting(BaseModel):
    """Lighting description derived from tone analysis and sketch context."""

    description: str = Field(
        default="",
        description="Lighting quality, direction, color temperature, and mood",
    )


class CameraLens(BaseModel):
    """Camera movement, framing, and lens selection."""

    description: str = Field(
        default="",
        description="Camera movement (e.g. 'dolly in', 'crane up'), framing, and lens choice",
    )
    formality: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Camera formality: 0.0=handheld verite, 0.5=standard tripod, 1.0=cinematic",
    )


class Audio(BaseModel):
    """Audio cues for native PixVerse V6 audio synthesis.

    PixVerse V6 generates audio in the same pass as video. Describing audio
    explicitly in the prompt ensures sync-locked sound design.
    """

    description: str = Field(
        default="",
        description="Audio description: background music, sound effects, dialogue, ambience",
    )


class PixVersePrompt(BaseModel):
    """Complete LPD prompt decomposed into its six PixVerse V6 components.

    The to_lpd_text() method assembles all non-empty components into the
    final prompt string that PixVerse V6 accepts.
    """

    subject: Subject = Field(default_factory=Subject, description="Core subject descriptor")
    action_motion: ActionMotion = Field(
        default_factory=ActionMotion, description="Action and motion intensity"
    )
    environment: Environment = Field(
        default_factory=Environment, description="Environment and setting"
    )
    lighting: Lighting = Field(default_factory=Lighting, description="Lighting description")
    camera_lens: CameraLens = Field(
        default_factory=CameraLens, description="Camera movement and lens"
    )
    audio: Audio = Field(default_factory=Audio, description="Audio cues")

    def to_lpd_text(self) -> str:
        """Render the full LPD format string for PixVerse V6.

        Joins all non-empty components with ". " and appends a final period.
        The PixVerse V6 prompt structure:
          [Subject]. [Action/Motion]. [Environment]. [Lighting]. [Camera/Lens]. [Audio].

        Empty components are silently skipped so the output is always clean.
        """
        parts: list[str] = [
            self.subject.description,
            self.action_motion.description,
            self.environment.description,
            self.lighting.description,
            self.camera_lens.description,
            self.audio.description,
        ]
        return ". ".join(p for p in parts if p) + "."
