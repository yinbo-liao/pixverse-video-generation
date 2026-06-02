"""Schema validation tests for Phase 2 shot sequence models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.shot_sequence import (
    ShotResult,
    ShotSequenceRequest,
    ShotSequenceResponse,
    ShotSpec,
)


class TestShotSpec:
    """Tests for ShotSpec validation."""

    def test_valid_shot_spec_minimal(self):
        """Minimal ShotSpec with required fields parses correctly."""
        spec = ShotSpec(shot_index=0, shot_type="wide")
        assert spec.shot_index == 0
        assert spec.shot_type == "wide"
        assert spec.style_overrides is None
        assert spec.transition_notes is None
        assert spec.custom_instruction is None

    def test_valid_shot_spec_full(self):
        """ShotSpec with all optional fields."""
        spec = ShotSpec(
            shot_index=1,
            shot_type="close-up",
            style_overrides={"formality": 0.9},
            transition_notes="Cross-fade from previous",
            custom_instruction="Focus on facial expression",
        )
        assert spec.shot_index == 1
        assert spec.transition_notes == "Cross-fade from previous"

    def test_invalid_shot_type(self):
        """Literal validation rejects invalid shot types."""
        with pytest.raises(ValidationError):
            ShotSpec(shot_index=0, shot_type="extreme-close-up")

    def test_negative_shot_index(self):
        """Shot index must be >= 0."""
        with pytest.raises(ValidationError):
            ShotSpec(shot_index=-1, shot_type="wide")


class TestShotSequenceRequest:
    """Tests for ShotSequenceRequest validation."""

    def test_minimal_valid_request(self):
        """Minimal request with anchor, base_prompt, and 2 shots."""
        req = ShotSequenceRequest(
            anchor="a red sports car",
            base_prompt="driving along a coastal highway",
            shots=[
                {"shot_index": 0, "shot_type": "wide"},
                {"shot_index": 1, "shot_type": "close-up"},
            ],
        )
        assert req.anchor == "a red sports car"
        assert len(req.shots) == 2
        assert req.drift_threshold == 0.3  # default

    def test_too_few_shots(self):
        """At least 2 shots required."""
        with pytest.raises(ValidationError):
            ShotSequenceRequest(
                anchor="test",
                base_prompt="test",
                shots=[{"shot_index": 0, "shot_type": "wide"}],
            )

    def test_too_many_shots(self):
        """At most 12 shots allowed."""
        shots = [{"shot_index": i, "shot_type": "wide"} for i in range(13)]
        with pytest.raises(ValidationError):
            ShotSequenceRequest(anchor="test", base_prompt="test", shots=shots)

    def test_empty_anchor(self):
        """Empty anchor rejected."""
        with pytest.raises(ValidationError):
            ShotSequenceRequest(
                anchor="",
                base_prompt="test",
                shots=[
                    {"shot_index": 0, "shot_type": "wide"},
                    {"shot_index": 1, "shot_type": "medium"},
                ],
            )

    def test_drift_threshold_out_of_range(self):
        """Drift threshold must be in [0, 1]."""
        with pytest.raises(ValidationError):
            ShotSequenceRequest(
                anchor="test",
                base_prompt="test",
                shots=[
                    {"shot_index": 0, "shot_type": "wide"},
                    {"shot_index": 1, "shot_type": "medium"},
                ],
                drift_threshold=1.5,
            )

    def test_drift_threshold_negative(self):
        """Drift threshold must be >= 0."""
        with pytest.raises(ValidationError):
            ShotSequenceRequest(
                anchor="test",
                base_prompt="test",
                shots=[
                    {"shot_index": 0, "shot_type": "wide"},
                    {"shot_index": 1, "shot_type": "medium"},
                ],
                drift_threshold=-0.1,
            )

    def test_non_sequential_indices(self):
        """Shots must have sequential indices starting at 0."""
        with pytest.raises(ValidationError, match="sequential"):
            ShotSequenceRequest(
                anchor="test",
                base_prompt="test",
                shots=[
                    {"shot_index": 0, "shot_type": "wide"},
                    {"shot_index": 2, "shot_type": "medium"},  # skipped 1
                ],
            )

    def test_duplicate_indices(self):
        """Shots must have unique indices."""
        with pytest.raises(ValidationError, match="sequential"):
            ShotSequenceRequest(
                anchor="test",
                base_prompt="test",
                shots=[
                    {"shot_index": 0, "shot_type": "wide"},
                    {"shot_index": 0, "shot_type": "medium"},
                ],
            )


class TestShotResult:
    """Tests for ShotResult model."""

    def test_first_shot_no_drift(self):
        """First shot has no drift_from_previous and is not flagged."""
        from app.schemas.bridge import BridgeResponse
        from app.schemas.prompt import PixVersePrompt

        br = BridgeResponse(
            generation_id="g1",
            original_prompt="test",
            optimized_text="test",
            lpd_prompt=PixVersePrompt(),
            lpd_text="test.",
        )
        result = ShotResult(
            shot_index=0,
            shot_type="wide",
            bridge_response=br,
            drift_from_previous=None,
            flagged=False,
        )
        assert result.drift_from_previous is None
        assert not result.flagged

    def test_flagged_shot(self):
        """Shot with high drift is flagged."""
        from app.schemas.bridge import BridgeResponse
        from app.schemas.prompt import PixVersePrompt

        br = BridgeResponse(
            generation_id="g2",
            original_prompt="test",
            optimized_text="test",
            lpd_prompt=PixVersePrompt(),
            lpd_text="test.",
        )
        result = ShotResult(
            shot_index=2,
            shot_type="close-up",
            bridge_response=br,
            drift_from_previous=0.45,
            flagged=True,
        )
        assert result.flagged
        assert result.drift_from_previous == 0.45


class TestShotSequenceResponse:
    """Tests for ShotSequenceResponse model."""

    def test_valid_response(self):
        """Response with coherence score and flagged shots."""
        resp = ShotSequenceResponse(
            anchor="test anchor",
            shots=[],
            coherence_score=0.85,
            flagged_shots=[2],
        )
        assert resp.coherence_score == 0.85
        assert resp.flagged_shots == [2]
