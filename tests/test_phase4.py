"""Tests for Phase 4: Parameter Injection and Concept Fusion."""

from __future__ import annotations

from app.schemas.bridge import BridgeStyle

# ---------------------------------------------------------------------------
# PixVerse Presets
# ---------------------------------------------------------------------------


class TestPresets:
    """Verify preset lookup tables produce correct mappings."""

    def test_camera_tiers_all_boundaries(self):
        """Each formality boundary maps to the expected camera type."""
        from app.services.pixverse_presets import get_camera_profile

        expected = [
            (0.00, "handheld"), (0.15, "shoulder-rig"), (0.35, "tripod"),
            (0.55, "slider/dolly"), (0.70, "steadicam"), (0.85, "crane/jib"),
            (0.95, "technocrane + remote head"), (1.00, "technocrane + remote head"),
        ]
        for value, cam_type in expected:
            profile = get_camera_profile(value)
            assert profile.camera_type == cam_type, f"At {value}: expected {cam_type}"

    def test_motion_tiers_all_boundaries(self):
        """Each enthusiasm boundary maps to the expected motion profile."""
        from app.services.pixverse_presets import get_motion_profile

        expected = [
            (0.00, 5), (0.10, 20), (0.25, 40), (0.45, 60), (0.65, 80), (0.85, 100),
        ]
        for value, pct in expected:
            profile = get_motion_profile(value)
            assert profile.strength_pct == pct, f"At {value}: expected {pct}%"

    def test_lighting_tiers_all_boundaries(self):
        """Each technical_depth boundary maps to expected lighting."""
        from app.services.pixverse_presets import get_lighting_setup

        expected = [
            (0.00, "ambient natural"), (0.20, "2-point basic"),
            (0.40, "3-point standard"), (0.60, "3-point + accent"),
            (0.80, "cinematic multi-point"),
        ]
        for value, name in expected:
            setup = get_lighting_setup(value)
            assert setup.name == name, f"At {value}: expected {name}"

    def test_render_tiers(self):
        """Technical depth maps to render quality."""
        from app.services.pixverse_presets import get_render_quality

        assert get_render_quality(0.1).tier == "draft"
        assert get_render_quality(0.4).tier == "standard"
        assert get_render_quality(0.7).tier == "high"
        assert get_render_quality(0.9).tier == "cinematic"

    def test_aspect_ratios(self):
        """Aspect ratio presets are correct."""
        from app.services.pixverse_presets import get_aspect_ratio

        assert get_aspect_ratio("social_vertical").ratio == "9:16"
        assert get_aspect_ratio("widescreen").ratio == "16:9"
        assert get_aspect_ratio("cinematic").ratio == "21:9"


# ---------------------------------------------------------------------------
# Parameter Injection service
# ---------------------------------------------------------------------------


class TestParameterInjection:
    """Tests for ParameterInjector.inject()."""

    async def test_inject_returns_complete_response(
        self, parameter_injector, sample_feedback_request_dict
    ):
        """inject() returns a ParameterInjectionResponse with all fields."""
        from app.schemas.parameter_injection import ParameterInjectionRequest

        req = ParameterInjectionRequest(
            prompt="A person walks through a park",
            style=BridgeStyle(formality=0.8, enthusiasm=0.6, technical_depth=0.7),
            target_duration=8,
            aspect_ratio="16:9",
        )
        response = await parameter_injector.inject(req)

        assert response.generation_id.startswith("pi-")
        assert response.bridge_response.lpd_prompt
        assert response.params.motion.strength_pct > 0
        assert response.params.camera.lens_mm > 0
        assert response.params.lighting.setup_name
        assert response.params.render.tier
        assert "motion" in response.justifications
        assert "camera" in response.justifications

    async def test_style_vectors_map_correctly(self, parameter_injector):
        """High formality → cinematic camera, high enthusiasm → explosive motion."""
        from app.schemas.parameter_injection import ParameterInjectionRequest

        req = ParameterInjectionRequest(
            prompt="test",
            style=BridgeStyle(formality=0.9, enthusiasm=0.9, technical_depth=0.9),
        )
        response = await parameter_injector.inject(req)

        assert response.params.camera.camera_type in ("crane/jib", "technocrane + remote head")
        assert response.params.motion.strength_pct == 100
        assert response.params.lighting.setup_name == "cinematic multi-point"
        assert response.params.render.tier == "cinematic"

    async def test_low_style_maps_minimal(self, parameter_injector):
        """Low style values → basic parameters."""
        from app.schemas.parameter_injection import ParameterInjectionRequest

        req = ParameterInjectionRequest(
            prompt="test",
            style=BridgeStyle(formality=0.05, enthusiasm=0.05, technical_depth=0.1),
        )
        response = await parameter_injector.inject(req)

        assert response.params.camera.camera_type == "handheld"
        assert response.params.motion.strength_pct == 5
        assert response.params.lighting.setup_name == "ambient natural"
        assert response.params.render.tier == "draft"


# ---------------------------------------------------------------------------
# Concept Fusion service
# ---------------------------------------------------------------------------


class TestConceptFusion:
    """Tests for ConceptFusion.fuse()."""

    async def test_fuse_two_concepts(self, concept_fusion):
        """Fusing 2 concepts produces a FusionResponse."""
        from app.schemas.concept_fusion import ConceptInput, FusionRequest

        req = FusionRequest(
            concepts=[
                ConceptInput(prompt="a woman in a red dress", role="foreground", weight=1.0),
                ConceptInput(prompt="a rainy city street at night", role="background", weight=0.8),
            ],
            unifying_theme="noir atmosphere",
        )
        response = await concept_fusion.fuse(req)

        assert response.generation_id.startswith("fusion-")
        assert response.unified_prompt.lpd_prompt
        assert len(response.concept_results) == 2
        assert 0.0 <= response.blend_coherence <= 1.0
        assert "Foreground" in response.scene_composition
        assert "Background" in response.scene_composition

    async def test_fuse_with_ambient(self, concept_fusion):
        """Ambient role concept is placed correctly in composition."""
        from app.schemas.concept_fusion import ConceptInput, FusionRequest

        req = FusionRequest(
            concepts=[
                ConceptInput(prompt="a detective", role="foreground", weight=1.5),
                ConceptInput(prompt="fog and mist", role="ambient", weight=0.5),
            ],
        )
        response = await concept_fusion.fuse(req)

        assert "Ambient atmosphere" in response.scene_composition

    async def test_concept_results_preserved(self, concept_fusion):
        """Each concept's original prompt and optimized text are preserved."""
        from app.schemas.concept_fusion import ConceptInput, FusionRequest

        req = FusionRequest(
            concepts=[
                ConceptInput(prompt="a racing car", role="foreground"),
                ConceptInput(prompt="desert landscape", role="background"),
            ],
        )
        response = await concept_fusion.fuse(req)

        for i, cr in enumerate(response.concept_results):
            assert cr.concept_prompt == req.concepts[i].prompt
            assert cr.optimized_text
            assert cr.weight == req.concepts[i].weight
            assert cr.role == req.concepts[i].role
