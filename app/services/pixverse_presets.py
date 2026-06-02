"""PixVerse V6 parameter presets — lookup tables for dynamic parameter injection.

Maps the 3 Semantic-Canvas style vectors (formality, enthusiasm, technical_depth)
to precise PixVerse V6 generation parameters:
  - enthusiasm  → motion strength, speed profile
  - formality   → camera type, lens mm, stabilization
  - technical_depth → lighting setup, render quality, aspect ratio

All tables use tiered (low, high) ranges for deterministic lookup.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Camera profiles (keyed on formality)
# ---------------------------------------------------------------------------

@dataclass
class CameraProfile:
    camera_type: str
    lens_mm: int
    stabilization: str
    movement: str
    description: str


CAMERA_TIERS: list[tuple[float, float, CameraProfile]] = [
    (0.00, 0.15, CameraProfile(
        camera_type="handheld",
        lens_mm=24,
        stabilization="none — natural shake",
        movement="verite wandering, organic sway",
        description="Raw handheld, documentary verite style — natural camera shake",
    )),
    (0.15, 0.35, CameraProfile(
        camera_type="shoulder-rig",
        lens_mm=35,
        stabilization="minimal — slight dampening",
        movement="semi-handheld, documentary float",
        description="Shoulder rig with minimal stabilization — documentary feel",
    )),
    (0.35, 0.55, CameraProfile(
        camera_type="tripod",
        lens_mm=50,
        stabilization="locked tripod",
        movement="smooth pan, tilt, standard framing",
        description="Locked tripod with smooth pans — standard professional framing",
    )),
    (0.55, 0.70, CameraProfile(
        camera_type="slider/dolly",
        lens_mm=50,
        stabilization="mechanical damped",
        movement="slow dolly push, lateral slide, controlled drift",
        description="Slider and dolly with mechanical damping — controlled camera motion",
    )),
    (0.70, 0.85, CameraProfile(
        camera_type="steadicam",
        lens_mm=35,
        stabilization="gimbal — fluid horizon lock",
        movement="steadicam glide, orbiting tracking, smooth follow",
        description="Steadicam on gimbal — fluid, floating camera with horizon lock",
    )),
    (0.85, 0.95, CameraProfile(
        camera_type="crane/jib",
        lens_mm=85,
        stabilization="counterweight crane",
        movement="crane up/down, sweeping arc, dramatic reveal",
        description="Crane or jib arm — sweeping vertical arcs and dramatic reveals",
    )),
    (0.95, 1.01, CameraProfile(
        camera_type="technocrane + remote head",
        lens_mm=135,
        stabilization="3-axis gyro-stabilized",
        movement="precision 3-axis, programmable motion control",
        description="Technocrane with remote head — precision cinematic motion control",
    )),
]


# ---------------------------------------------------------------------------
# Motion profiles (keyed on enthusiasm)
# ---------------------------------------------------------------------------

@dataclass
class MotionProfile:
    strength_pct: int
    speed_label: str
    acceleration: str
    description: str


MOTION_TIERS: list[tuple[float, float, MotionProfile]] = [
    (0.00, 0.10, MotionProfile(
        strength_pct=5, speed_label="static / barely moving",
        acceleration="none — tableau vivant",
        description="Near-static tableau — imperceptible motion, fine-art photography feel",
    )),
    (0.10, 0.25, MotionProfile(
        strength_pct=20, speed_label="slow motion",
        acceleration="gentle ease-in",
        description="Slow motion with gentle easing — dreamy, deliberate pace",
    )),
    (0.25, 0.45, MotionProfile(
        strength_pct=40, speed_label="relaxed natural pace",
        acceleration="smooth linear",
        description="Relaxed, natural movement — smooth linear acceleration",
    )),
    (0.45, 0.65, MotionProfile(
        strength_pct=60, speed_label="steady purposeful",
        acceleration="steady ramp",
        description="Purposeful, steady motion — confident pacing with steady ramp-up",
    )),
    (0.65, 0.85, MotionProfile(
        strength_pct=80, speed_label="dynamic energetic",
        acceleration="brisk snap",
        description="Dynamic, energetic movement — brisk snappy acceleration",
    )),
    (0.85, 1.01, MotionProfile(
        strength_pct=100, speed_label="explosive rapid",
        acceleration="instant peak",
        description="Explosive, rapid motion — instant peak acceleration, maximum intensity",
    )),
]


# ---------------------------------------------------------------------------
# Lighting setups (keyed on technical_depth)
# ---------------------------------------------------------------------------

@dataclass
class LightingSetup:
    name: str
    key_light: str
    fill_light: str
    back_light: str
    complexity: str
    description: str


LIGHTING_TIERS: list[tuple[float, float, LightingSetup]] = [
    (0.00, 0.20, LightingSetup(
        name="ambient natural",
        key_light="available natural light",
        fill_light="none — ambient only",
        back_light="none",
        complexity="single source",
        description="Ambient natural light only — single-source, no artificial lighting",
    )),
    (0.20, 0.40, LightingSetup(
        name="2-point basic",
        key_light="soft key from 45°",
        fill_light="bounce fill from opposite side",
        back_light="none",
        complexity="2 sources",
        description="Basic 2-point setup — soft key with bounce fill, natural look",
    )),
    (0.40, 0.60, LightingSetup(
        name="3-point standard",
        key_light="diffused key from 30°",
        fill_light="soft fill at -1.5 stops",
        back_light="rim/hair light from behind",
        complexity="3 sources",
        description="Standard 3-point — key, fill, and rim for depth separation",
    )),
    (0.60, 0.80, LightingSetup(
        name="3-point + accent",
        key_light="focused key with grid",
        fill_light="controlled fill at -2 stops",
        back_light="dual rim + overhead accent",
        complexity="5 sources",
        description="Enhanced 3-point with accent lights — dimensional, sculpted look",
    )),
    (0.80, 1.01, LightingSetup(
        name="cinematic multi-point",
        key_light="booklight / cove diffusion",
        fill_light="negative fill for contrast control",
        back_light="multi-rim + practicals + eye light",
        complexity="8+ sources",
        description="Full cinematic lighting — booklight, negative fill, multi-rim, practicals",
    )),
]


# ---------------------------------------------------------------------------
# Render quality tiers (keyed on technical_depth)
# ---------------------------------------------------------------------------

@dataclass
class RenderQuality:
    tier: str
    model: str
    upscale: str
    description: str


RENDER_TIERS: list[tuple[float, float, RenderQuality]] = [
    (0.00, 0.25, RenderQuality(
        tier="draft", model="V6 Standard",
        upscale="none — native 540p",
        description="Draft quality — V6 Standard, 540p Turbo mode for preview/testing",
    )),
    (0.25, 0.55, RenderQuality(
        tier="standard", model="V6 Standard",
        upscale="none — native 720p",
        description="Standard quality — V6 Standard, 720p for social media delivery",
    )),
    (0.55, 0.80, RenderQuality(
        tier="high", model="V6 Pro",
        upscale="1080p upscale pass",
        description="High quality — V6 Pro, 1080p upscaled for commercial delivery",
    )),
    (0.80, 1.01, RenderQuality(
        tier="cinematic", model="V6 Pro + C1",
        upscale="4K AI upscale pipeline",
        description="Cinematic quality — V6 Pro with C1 model, 4K AI upscale for broadcast",
    )),
]


# ---------------------------------------------------------------------------
# Aspect ratio presets (keyed on use case)
# ---------------------------------------------------------------------------

@dataclass
class AspectRatioPreset:
    ratio: str
    pixels: str
    use_case: str


ASPECT_RATIOS: dict[str, AspectRatioPreset] = {
    "social_vertical": AspectRatioPreset(
        ratio="9:16", pixels="1080x1920", use_case="TikTok, Reels, Shorts, Stories",
    ),
    "social_square": AspectRatioPreset(
        ratio="1:1", pixels="1080x1080", use_case="Instagram feed, Facebook, LinkedIn",
    ),
    "widescreen": AspectRatioPreset(
        ratio="16:9", pixels="1920x1080", use_case="YouTube, broadcast, web embeds",
    ),
    "cinematic": AspectRatioPreset(
        ratio="21:9", pixels="2560x1080", use_case="Cinematic trailer, film festival, theatrical",
    ),
}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def pick_from_tiers(value: float, tiers: list) -> object:
    """Select the matching tier entry for a 0.0-1.0 value."""
    for low, high, entry in tiers:
        if low <= value < high:
            return entry
    return tiers[-1][2]


def get_camera_profile(formality: float) -> CameraProfile:
    """Map formality (0–1) to a camera profile."""
    return pick_from_tiers(formality, CAMERA_TIERS)  # type: ignore[return-value]


def get_motion_profile(enthusiasm: float) -> MotionProfile:
    """Map enthusiasm (0–1) to a motion profile."""
    return pick_from_tiers(enthusiasm, MOTION_TIERS)  # type: ignore[return-value]


def get_lighting_setup(technical_depth: float) -> LightingSetup:
    """Map technical_depth (0–1) to a lighting setup."""
    return pick_from_tiers(technical_depth, LIGHTING_TIERS)  # type: ignore[return-value]


def get_render_quality(technical_depth: float) -> RenderQuality:
    """Map technical_depth (0–1) to a render quality tier."""
    return pick_from_tiers(technical_depth, RENDER_TIERS)  # type: ignore[return-value]


def get_aspect_ratio(preset: str = "widescreen") -> AspectRatioPreset:
    """Look up an aspect ratio by preset name."""
    return ASPECT_RATIOS.get(preset, ASPECT_RATIOS["widescreen"])
