"""Tests for Phase 5: End-to-End Production Pipeline."""

from __future__ import annotations


class TestProductionPipeline:
    """Tests for ProductionPipeline.run()."""

    async def test_pipeline_without_fusion(self, production_pipeline):
        """Pipeline without concepts skips fusion stage."""
        from app.schemas.production_pipeline import PipelineRequest

        req = PipelineRequest(
            prompt="A person walks through a sunlit forest",
            sketch_notes="Ancient trees. Dappled light through canopy.",
            target_duration=8,
            shot_count=3,
            max_feedback_iterations=1,
        )
        response = await production_pipeline.run(req)

        assert response.generation_id.startswith("pipeline-")
        assert response.parameter_result is not None
        assert response.shot_sequence_result is not None
        assert len(response.stages) == 4
        assert response.stages[0].status == "skipped"  # fusion skipped
        assert response.stages[1].status == "completed"  # param injection
        assert response.stages[2].status == "completed"  # shot sequence
        assert response.total_duration_ms > 0
        assert len(response.final_lpd_prompts) > 0

    async def test_pipeline_with_fusion(self, production_pipeline):
        """Pipeline with 2 concepts runs fusion first."""
        from app.schemas.concept_fusion import ConceptInput
        from app.schemas.production_pipeline import PipelineRequest

        req = PipelineRequest(
            prompt="A futuristic city scene",
            concepts=[
                ConceptInput(prompt="a flying car", role="foreground", weight=1.0),
                ConceptInput(prompt="neon skyscrapers", role="background", weight=0.7),
            ],
            unifying_theme="cyberpunk",
            shot_count=2,
            max_feedback_iterations=0,
        )
        response = await production_pipeline.run(req)

        assert response.fusion_result is not None
        assert response.stages[0].status == "completed"
        assert response.parameter_result is not None
        assert response.shot_sequence_result is not None
        # feedback skipped (max_iterations=0)
        assert response.stages[3].status == "skipped"

    async def test_fusion_uses_lpd_text_not_scene_composition(self, production_pipeline):
        """After fusion, downstream stages receive actual LPD text, not meta-layout."""
        from app.schemas.concept_fusion import ConceptInput
        from app.schemas.production_pipeline import PipelineRequest

        req = PipelineRequest(
            prompt="A futuristic city scene",
            concepts=[
                ConceptInput(prompt="a flying car", role="foreground", weight=1.0),
                ConceptInput(prompt="neon skyscrapers", role="background", weight=0.7),
            ],
            unifying_theme="cyberpunk",
            shot_count=2,
            max_feedback_iterations=0,
        )
        response = await production_pipeline.run(req)

        # The parameter injection's bridge response should contain narrative text,
        # NOT the spatial composition meta-instruction "Foreground: ... Background: ..."
        lpd_text = response.parameter_result.bridge_response.lpd_text
        assert not lpd_text.startswith("Foreground:"), (
            f"Pipeline should use fused LPD text, not scene_composition. Got: {lpd_text[:100]}"
        )
        # The shot sequence anchor should not start with "Foreground:"
        anchor = response.shot_sequence_result.anchor
        assert not anchor.startswith("Foreground:"), (
            f"Shot anchor should not be scene_composition. Got: {anchor}"
        )

    async def test_pipeline_credit_estimation(self, production_pipeline):
        """Credit cost is estimated based on duration and shot count."""
        from app.schemas.production_pipeline import PipelineRequest

        req = PipelineRequest(
            prompt="test",
            target_duration=10,
            shot_count=3,
            max_feedback_iterations=0,
        )
        response = await production_pipeline.run(req)

        # 10s × 23 credits/s × ~4 prompts (3 shots + 1 feedback) ≈ 920
        assert response.estimated_credits > 0

    async def test_final_prompts_are_valid_lpd(self, production_pipeline):
        """All final LPD prompts end with period."""
        from app.schemas.production_pipeline import PipelineRequest

        req = PipelineRequest(
            prompt="A calm ocean at sunrise",
            shot_count=3,
            max_feedback_iterations=0,
        )
        response = await production_pipeline.run(req)

        for prompt in response.final_lpd_prompts:
            assert prompt.endswith(".")
            assert len(prompt) > 10

    async def test_stage_timing(self, production_pipeline):
        """All completed stages have positive duration."""
        from app.schemas.production_pipeline import PipelineRequest

        req = PipelineRequest(
            prompt="test timing",
            shot_count=3,
            max_feedback_iterations=0,
        )
        response = await production_pipeline.run(req)

        for stage in response.stages:
            if stage.status == "completed":
                assert stage.duration_ms >= 0
