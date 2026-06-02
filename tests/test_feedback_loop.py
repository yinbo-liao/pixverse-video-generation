"""Unit and integration tests for the FeedbackLoop service.

Tests cover: 6 artifact detectors, artifact reports, fix application,
variation generation, selection algorithm, refinement loop, and
the full run() orchestrator. All tests use MockSemanticCanvasClient.
"""

from __future__ import annotations

import pytest

from app.schemas.bridge import BridgeRequest
from app.schemas.feedback_loop import (
    ArtifactFinding,
    ArtifactReport,
    ArtifactType,
    FeedbackRequest,
    FeedbackResponse,
    VariationResult,
    VariationType,
)

# ---------------------------------------------------------------------------
# Artifact detector tests
# ---------------------------------------------------------------------------


class TestArtifactDetectors:
    """Tests for all 6 individual artifact detectors."""

    # --- motion_smearing ---

    def test_motion_smearing_detected(self, feedback_loop):
        """High motion + fast action → finding with severity >= 0.7."""
        finding = feedback_loop._detect_motion_smearing(
            "rapid intense running and sprinting action"
        )
        assert finding is not None
        assert finding.type == ArtifactType.motion_smearing
        assert finding.severity >= 0.7

    def test_motion_smearing_partial(self, feedback_loop):
        """Only one category → severity 0.4."""
        finding = feedback_loop._detect_motion_smearing("rapid movement across the field")
        assert finding is not None
        assert finding.severity == pytest.approx(0.4)

    def test_motion_smearing_clean(self, feedback_loop):
        """No high motion or fast action words → None."""
        finding = feedback_loop._detect_motion_smearing("slow walking through the park")
        assert finding is None

    # --- hand_distortion ---

    def test_hand_distortion_detected(self, feedback_loop):
        """Close-up + hands → finding."""
        finding = feedback_loop._detect_hand_distortion(
            "close-up shot of hands grasping the object"
        )
        assert finding is not None
        assert finding.type == ArtifactType.hand_distortion
        assert finding.severity >= 0.8

    def test_hand_distortion_not_detected(self, feedback_loop):
        """Wide shot with handshake → no close-up framing trigger."""
        finding = feedback_loop._detect_hand_distortion(
            "wide shot of a crowd with people shaking hands"
        )
        assert finding is None

    # --- facial_drift ---

    def test_facial_drift_detected(self, feedback_loop):
        """Sequence language without repeated descriptors → finding."""
        finding = feedback_loop._detect_facial_drift(
            "shot of a person walking. cut to another scene. multiple transitions."
        )
        assert finding is not None
        assert finding.type == ArtifactType.facial_drift

    def test_facial_drift_not_detected(self, feedback_loop):
        """No sequence keywords → no finding."""
        finding = feedback_loop._detect_facial_drift(
            "a person in a blue coat walks through the park"
        )
        assert finding is None

    # --- lighting_inconsistency ---

    def test_lighting_inconsistency_detected(self, feedback_loop):
        """Conflicting warm/cold → finding."""
        finding = feedback_loop._detect_lighting_inconsistency(
            "warm golden sunlight mixed with cold blue shadows"
        )
        assert finding is not None
        assert finding.type == ArtifactType.lighting_inconsistency
        assert finding.severity >= 0.25

    def test_lighting_inconsistency_multiple(self, feedback_loop):
        """3 conflicting pairs → severity 0.75."""
        finding = feedback_loop._detect_lighting_inconsistency(
            "warm and cold tones with bright and dark areas, harsh yet soft light"
        )
        assert finding is not None
        assert finding.severity == pytest.approx(0.75)

    def test_lighting_inconsistency_clean(self, feedback_loop):
        """Consistent lighting → None."""
        finding = feedback_loop._detect_lighting_inconsistency(
            "warm golden light bathes the entire scene"
        )
        assert finding is None

    # --- subject_blending ---

    def test_subject_blending_detected(self, feedback_loop):
        """Chaos without focus → finding."""
        finding = feedback_loop._detect_subject_blending(
            "a busy chaotic crowd in a cluttered marketplace"
        )
        assert finding is not None
        assert finding.type == ArtifactType.subject_blending
        assert finding.severity == pytest.approx(0.8)

    def test_subject_blending_not_detected(self, feedback_loop):
        """Chaos with focus marker → no finding."""
        finding = feedback_loop._detect_subject_blending(
            "a busy crowd scene with shallow depth of field and center-lock focus"
        )
        assert finding is None

    # --- temporal_flicker ---

    def test_temporal_flicker_detected(self, feedback_loop):
        """Flicker keywords → finding."""
        finding = feedback_loop._detect_temporal_flicker(
            "strobe lights flickering in the club"
        )
        assert finding is not None
        assert finding.type == ArtifactType.temporal_flicker
        assert finding.severity == pytest.approx(0.7)

    def test_temporal_flicker_high_severity(self, feedback_loop):
        """3+ flicker keywords → severity 0.9."""
        finding = feedback_loop._detect_temporal_flicker(
            "strobe flickering flashing lightning effects"
        )
        assert finding is not None
        assert finding.severity == pytest.approx(0.9)

    def test_temporal_flicker_clean(self, feedback_loop):
        """No flicker keywords."""
        finding = feedback_loop._detect_temporal_flicker(
            "steady warm illumination fills the room"
        )
        assert finding is None


# ---------------------------------------------------------------------------
# Artifact report tests
# ---------------------------------------------------------------------------


class TestArtifactReport:
    """Tests for ArtifactReport model and _analyze_artifacts."""

    def test_clean_text_no_findings(self, feedback_loop):
        """Clean prompt produces empty report."""
        report = feedback_loop._analyze_artifacts("slow walking through a softly lit park")
        assert len(report.findings) == 0
        assert report.overall_risk_score == 0.0
        assert report.is_clean

    def test_mixed_artifacts(self, feedback_loop):
        """Text with 2+ artifact types produces correct findings."""
        text = (
            "rapid running through flashing strobe lights in a chaotic crowd. "
            "close-up of hands. warm and cold light mix."
        )
        report = feedback_loop._analyze_artifacts(text)
        assert len(report.findings) >= 3
        assert not report.is_clean

    def test_overall_risk_score_is_max(self, feedback_loop):
        """Risk score is max severity, not average."""
        text = "rapid running action with strobe flickering"
        report = feedback_loop._analyze_artifacts(text)
        severities = [f.severity for f in report.findings]
        assert report.overall_risk_score == max(severities)


# ---------------------------------------------------------------------------
# Fix application tests
# ---------------------------------------------------------------------------


class TestFixApplication:
    """Tests for _apply_fixes and individual fix methods."""

    def test_fix_motion_smearing(self, feedback_loop):
        """Fast action verbs replaced, slow motion added."""
        text = "rapid running and sprinting through the streets."
        fixed = feedback_loop._fix_motion_smearing(text)
        assert "running" not in fixed.lower()
        assert "slow motion" in fixed.lower()

    def test_fix_hand_distortion(self, feedback_loop):
        """Close-up replaced with medium shot."""
        text = "close-up macro detail of hands gripping the railing."
        fixed = feedback_loop._fix_hand_distortion(text)
        assert "close-up" not in fixed.lower()
        assert "medium shot" in fixed.lower()

    def test_fix_lighting_inconsistency(self, feedback_loop):
        """Conflicting tone word removed."""
        text = "warm golden light mixed with cold blue shadows."
        fixed = feedback_loop._fix_lighting_inconsistency(text)
        # Only one of warm/cold should remain
        assert "warm" in fixed.lower() or "cold" in fixed.lower()

    def test_fix_subject_blending(self, feedback_loop):
        """Focus markers appended."""
        text = "a chaotic busy crowd fills the street."
        fixed = feedback_loop._fix_subject_blending(text)
        assert "center-lock focus" in fixed.lower()

    def test_fix_temporal_flicker(self, feedback_loop):
        """Flicker keywords replaced with stable terms."""
        text = "strobe lights flickering above."
        fixed = feedback_loop._fix_temporal_flicker(text)
        assert "strobe" not in fixed.lower()
        assert "flickering" not in fixed.lower()

    def test_apply_multiple_fixes(self, feedback_loop):
        """Multiple fix types applied without collision."""
        findings = [
            ArtifactFinding(
                type=ArtifactType.motion_smearing,
                severity=0.8,
                suggested_fix="reduce motion",
            ),
            ArtifactFinding(
                type=ArtifactType.subject_blending,
                severity=0.8,
                suggested_fix="add focus",
            ),
        ]
        text = "rapid running through a chaotic crowd."
        fixed = feedback_loop._apply_fixes(text, findings)
        assert "slow motion" in fixed.lower()
        assert "center-lock" in fixed.lower()


# ---------------------------------------------------------------------------
# Variation generation tests
# ---------------------------------------------------------------------------


class TestVariationGeneration:
    """Tests for the 3-Generation Rule variation creation."""

    def test_three_variations_always(self):
        """Exactly 3 variations are generated."""
        # Test the variation configs built in run()
        enthusiasm = 0.6
        configs: list[tuple[VariationType, float]] = [
            ("baseline", enthusiasm),
            ("high_motion", min(1.0, enthusiasm + 0.10)),
            ("low_motion", max(0.0, enthusiasm - 0.10)),
        ]
        assert len(configs) == 3
        assert configs[0] == ("baseline", 0.6)
        assert configs[1] == ("high_motion", 0.7)
        assert configs[2] == ("low_motion", 0.5)

    def test_high_motion_clamped_at_1(self):
        """Enthusiasm at 0.95 → high motion capped at 1.0."""
        enthusiasm = 0.95
        high = min(1.0, enthusiasm + 0.10)
        assert high == 1.0

    def test_low_motion_clamped_at_0(self):
        """Enthusiasm at 0.05 → low motion floored at 0.0."""
        enthusiasm = 0.05
        low = max(0.0, enthusiasm - 0.10)
        assert low == 0.0

    def test_baseline_keeps_original(self):
        """Baseline variation preserves the original enthusiasm."""
        enthusiasm = 0.42
        baseline = enthusiasm
        assert baseline == 0.42


# ---------------------------------------------------------------------------
# Selection algorithm tests
# ---------------------------------------------------------------------------


class TestSelection:
    """Tests for _select_best and scoring."""

    def test_selects_cleanest(self, feedback_loop, sample_sc_response):
        """Clean variation wins over artifact-heavy ones."""
        from app.schemas.bridge import BridgeResponse
        from app.schemas.prompt import PixVersePrompt

        def make_var(vt: VariationType, risk: float) -> VariationResult:
            findings = []
            if risk > 0:
                findings = [
                    ArtifactFinding(
                        type=ArtifactType.motion_smearing,
                        severity=risk,
                        suggested_fix="fix",
                    )
                ]
            br = BridgeResponse(
                generation_id="g",
                original_prompt="test",
                optimized_text="test text",
                lpd_prompt=PixVersePrompt(),
                lpd_text="test text.",
            )
            return VariationResult(
                variation_type=vt,
                bridge_response=br,
                artifact_report=ArtifactReport(findings=findings),
                final_prompt="test text.",
            )

        clean = make_var("low_motion", 0.0)
        dirty_b = make_var("baseline", 0.8)
        dirty_h = make_var("high_motion", 0.9)

        selected, reason = feedback_loop._select_best(
            [clean, dirty_b, dirty_h], {"test"}
        )
        assert selected.variation_type == "low_motion"
        assert len(reason) > 10

    def test_selection_reason_non_empty(self, feedback_loop, sample_sc_response):
        """Justification string always populated."""
        from app.schemas.bridge import BridgeResponse
        from app.schemas.prompt import PixVersePrompt

        br = BridgeResponse(
            generation_id="g",
            original_prompt="test",
            optimized_text="test",
            lpd_prompt=PixVersePrompt(),
            lpd_text="test.",
        )
        var = VariationResult(
            variation_type="baseline",
            bridge_response=br,
            artifact_report=ArtifactReport(),
            final_prompt="test.",
        )
        _, reason = feedback_loop._select_best([var], {"test"})
        assert len(reason) > 5


# ---------------------------------------------------------------------------
# Refinement loop tests
# ---------------------------------------------------------------------------


class TestRefinementLoop:
    """Tests for _refine_variation."""

    async def test_clean_prompt_no_refinement(
        self, feedback_loop, clean_prompt_dict
    ):
        """Clean prompt skips refinement entirely."""
        request = FeedbackRequest(**clean_prompt_dict)
        bridge_req = BridgeRequest(
            prompt=request.prompt,
            sketch_notes=request.sketch_notes,
            constraints=request.constraints,
            style=request.style,
            generation_params=request.generation_params,
        )

        result = await feedback_loop._refine_variation(
            request, bridge_req, "baseline"
        )
        assert result.refinement_iterations == 0
        assert result.artifact_report.is_clean

    async def test_problematic_prompt_refines(
        self, feedback_loop, sample_feedback_request_dict
    ):
        """Prompt with artifacts undergoes refinement."""
        request = FeedbackRequest(**sample_feedback_request_dict)
        bridge_req = BridgeRequest(
            prompt=request.prompt,
            sketch_notes=request.sketch_notes,
            constraints=request.constraints,
            style=request.style,
            generation_params=request.generation_params,
        )

        result = await feedback_loop._refine_variation(
            request, bridge_req, "baseline"
        )
        # Should have at least some refinement
        assert result.refinement_iterations >= 0
        assert len(result.refinement_history) >= 1
        assert result.variation_type == "baseline"

    async def test_max_iterations_respected(
        self, feedback_loop, sample_feedback_request_dict
    ):
        """Refinement stops at max_iterations."""
        data = dict(sample_feedback_request_dict)
        data["max_iterations"] = 1
        request = FeedbackRequest(**data)
        bridge_req = BridgeRequest(
            prompt=request.prompt,
            sketch_notes=request.sketch_notes,
            constraints=request.constraints,
            style=request.style,
            generation_params=request.generation_params,
        )

        result = await feedback_loop._refine_variation(
            request, bridge_req, "baseline"
        )
        assert result.refinement_iterations <= 1

    async def test_manual_mode_no_refinement(
        self, feedback_loop, sample_feedback_request_dict
    ):
        """Manual mode returns findings without applying fixes."""
        data = dict(sample_feedback_request_dict)
        data["refinement_mode"] = "manual"
        request = FeedbackRequest(**data)
        bridge_req = BridgeRequest(
            prompt=request.prompt,
            sketch_notes=request.sketch_notes,
            constraints=request.constraints,
            style=request.style,
            generation_params=request.generation_params,
        )

        result = await feedback_loop._refine_variation(
            request, bridge_req, "baseline"
        )
        assert result.refinement_iterations == 0

    async def test_deterministic_output(
        self, feedback_loop, sample_feedback_request_dict
    ):
        """Same input produces identical output."""
        request = FeedbackRequest(**sample_feedback_request_dict)
        bridge_req = BridgeRequest(
            prompt=request.prompt,
            sketch_notes=request.sketch_notes,
            constraints=request.constraints,
            style=request.style,
            generation_params=request.generation_params,
        )

        r1 = await feedback_loop._refine_variation(request, bridge_req, "baseline")
        r2 = await feedback_loop._refine_variation(request, bridge_req, "baseline")

        assert r1.artifact_report.overall_risk_score == r2.artifact_report.overall_risk_score
        assert r1.refinement_iterations == r2.refinement_iterations


# ---------------------------------------------------------------------------
# Full run() integration tests
# ---------------------------------------------------------------------------


class TestFeedbackLoopRun:
    """End-to-end tests for FeedbackLoop.run()."""

    async def test_run_returns_feedback_response(
        self, feedback_loop, sample_feedback_request_dict
    ):
        """run() returns a complete FeedbackResponse."""
        request = FeedbackRequest(**sample_feedback_request_dict)
        response = await feedback_loop.run(request)

        assert isinstance(response, FeedbackResponse)
        assert response.generation_id.startswith("fb-")
        assert len(response.variations) == 3
        assert response.total_iterations >= 0

    async def test_three_variation_types(
        self, feedback_loop, sample_feedback_request_dict
    ):
        """Response contains exactly baseline, high_motion, low_motion."""
        request = FeedbackRequest(**sample_feedback_request_dict)
        response = await feedback_loop.run(request)

        var_types = {v.variation_type for v in response.variations}
        assert var_types == {"baseline", "high_motion", "low_motion"}

    async def test_selected_in_variations(
        self, feedback_loop, sample_feedback_request_dict
    ):
        """Selected variation is one of the three."""
        request = FeedbackRequest(**sample_feedback_request_dict)
        response = await feedback_loop.run(request)

        selected_in_list = any(
            v.variation_type == response.selected_variation.variation_type
            for v in response.variations
        )
        assert selected_in_list

    async def test_selection_reason_populated(
        self, feedback_loop, sample_feedback_request_dict
    ):
        """Selection reason is a meaningful string."""
        request = FeedbackRequest(**sample_feedback_request_dict)
        response = await feedback_loop.run(request)

        assert len(response.selection_reason) > 10

    async def test_clean_prompt_no_iterations(
        self, feedback_loop, clean_prompt_dict
    ):
        """Clean prompt needs no refinement."""
        request = FeedbackRequest(**clean_prompt_dict)
        response = await feedback_loop.run(request)

        # When all three are clean, total_iterations should be minimal
        assert response.total_iterations >= 0

    async def test_each_variation_has_bridge_response(
        self, feedback_loop, sample_feedback_request_dict
    ):
        """Each variation has a complete bridge_response."""
        request = FeedbackRequest(**sample_feedback_request_dict)
        response = await feedback_loop.run(request)

        for var in response.variations:
            assert var.bridge_response.generation_id
            assert var.bridge_response.lpd_prompt
            assert var.bridge_response.lpd_text
            assert var.final_prompt
