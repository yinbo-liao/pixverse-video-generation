"""Unit tests for the ShotChainer service.

Tests use MockSemanticCanvasClient (no upstream dependency) and
verify the complete chainer pipeline: shot generation, anchor injection,
drift computation, flagging, and coherence scoring.
"""

from __future__ import annotations

import pytest

from app.schemas.shot_sequence import ShotSequenceRequest, ShotSequenceResponse
from app.services.semantic_canvas_client import _cosine_distance, _text_to_embedding

# ---------------------------------------------------------------------------
# Mock embedding helpers
# ---------------------------------------------------------------------------


class TestMockEmbedding:
    """Verify deterministic mock embedding behavior."""

    def test_identical_texts_zero_distance(self):
        """Same text → same vector → distance = 0."""
        a = _text_to_embedding("hello world")
        b = _text_to_embedding("hello world")
        assert _cosine_distance(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_different_texts_nonzero_distance(self):
        """Different texts produce nonzero distance."""
        a = _text_to_embedding("a cyberpunk detective in a trench coat")
        b = _text_to_embedding("a sunny meadow with butterflies")
        distance = _cosine_distance(a, b)
        assert distance > 0.01

    def test_similar_texts_lower_distance(self):
        """Texts sharing an anchor have lower distance."""
        text_a = "Wide establishing shot: detective in trench coat. Walks through alley."
        text_b = "Medium detail shot: detective in trench coat. Walks through alley."
        text_c = "A completely unrelated scene about baking bread in a sunny kitchen."
        dist_similar = _cosine_distance(
            _text_to_embedding(text_a), _text_to_embedding(text_b)
        )
        dist_different = _cosine_distance(
            _text_to_embedding(text_a), _text_to_embedding(text_c)
        )
        assert dist_similar < dist_different, (
            f"Similar texts should be closer ({dist_similar}) than unrelated ({dist_different})"
        )

    def test_distance_in_zero_one_range(self):
        """All distances are in [0, 1]."""
        for text_a, text_b in [
            ("hello", "world"),
            ("x" * 1000, "y" * 1000),
            ("a", "a"),
            ("short", "a very long text with many words"),
        ]:
            dist = _cosine_distance(
                _text_to_embedding(text_a), _text_to_embedding(text_b)
            )
            assert 0.0 <= dist <= 1.0, f"Distance {dist} out of range for {text_a!r} vs {text_b!r}"


# ---------------------------------------------------------------------------
# ShotChainer orchestration
# ---------------------------------------------------------------------------


class TestChainerOrchestration:
    """Integration-level tests for ShotChainer.chain()."""

    async def test_chains_three_shots_successfully(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """A 3-shot sequence produces 3 ShotResults."""
        request = ShotSequenceRequest(**sample_shot_sequence_request_dict)
        response = await shot_chainer.chain(request)

        assert isinstance(response, ShotSequenceResponse)
        assert len(response.shots) == 3

    async def test_each_shot_has_bridge_response(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """Each shot result contains a complete BridgeResponse."""
        request = ShotSequenceRequest(**sample_shot_sequence_request_dict)
        response = await shot_chainer.chain(request)

        for shot in response.shots:
            assert shot.bridge_response.generation_id
            assert shot.bridge_response.optimized_text
            assert shot.bridge_response.lpd_prompt
            assert shot.bridge_response.lpd_text.endswith(".")

    async def test_anchor_in_every_shot_subject(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """The anchor appears in every shot's LPD Subject."""
        request = ShotSequenceRequest(**sample_shot_sequence_request_dict)
        response = await shot_chainer.chain(request)

        anchor_keywords = "detective"  # from "a cyberpunk detective in a weathered trench coat"
        for shot in response.shots:
            assert anchor_keywords in shot.bridge_response.lpd_prompt.subject.description.lower()

    async def test_shot_type_in_prompt(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """Each shot's original prompt includes the shot type prefix."""
        request = ShotSequenceRequest(**sample_shot_sequence_request_dict)
        response = await shot_chainer.chain(request)

        for i, shot in enumerate(response.shots):
            original = shot.bridge_response.original_prompt
            assert request.shots[i].shot_type in original.lower(), (
                f"Shot {i} prompt missing '{request.shots[i].shot_type}': {original}"
            )

    async def test_first_shot_no_drift(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """The first shot has None drift and is not flagged."""
        request = ShotSequenceRequest(**sample_shot_sequence_request_dict)
        response = await shot_chainer.chain(request)

        assert response.shots[0].drift_from_previous is None
        assert not response.shots[0].flagged

    async def test_consecutive_shots_have_drift(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """Shots after the first have drift values in [0, 1]."""
        request = ShotSequenceRequest(**sample_shot_sequence_request_dict)
        response = await shot_chainer.chain(request)

        for shot in response.shots[1:]:
            assert shot.drift_from_previous is not None
            assert 0.0 <= shot.drift_from_previous <= 1.0

    async def test_coherence_score_range(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """Coherence score is in [0, 1]."""
        request = ShotSequenceRequest(**sample_shot_sequence_request_dict)
        response = await shot_chainer.chain(request)

        assert 0.0 <= response.coherence_score <= 1.0

    async def test_coherence_score_formula(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """coherence_score = 1.0 - avg(drifts)."""
        request = ShotSequenceRequest(**sample_shot_sequence_request_dict)
        response = await shot_chainer.chain(request)

        drifts = [
            s.drift_from_previous
            for s in response.shots
            if s.drift_from_previous is not None
        ]
        expected = round(1.0 - sum(drifts) / len(drifts), 4)
        assert response.coherence_score == expected

    async def test_no_flagging_at_default_threshold(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """At threshold 1.0, no shots should be flagged."""
        data = dict(sample_shot_sequence_request_dict)
        data["drift_threshold"] = 1.0
        request = ShotSequenceRequest(**data)
        response = await shot_chainer.chain(request)

        assert len(response.flagged_shots) == 0
        for shot in response.shots:
            assert not shot.flagged

    async def test_flagging_at_very_low_threshold(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """With a tiny threshold (0.001), consecutive shots should be flagged."""
        data = dict(sample_shot_sequence_request_dict)
        data["drift_threshold"] = 0.001
        request = ShotSequenceRequest(**data)
        response = await shot_chainer.chain(request)

        # At least one consecutive shot pair should have nonzero drift
        assert len(response.flagged_shots) > 0
        # All flagged shots have drift > 0.001
        for idx in response.flagged_shots:
            assert response.shots[idx].drift_from_previous > 0.001

    async def test_style_overrides_per_shot(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """Shot-level style overrides change the LPD output."""
        data = dict(sample_shot_sequence_request_dict)
        data["shots"] = [
            {"shot_index": 0, "shot_type": "wide", "style_overrides": {"enthusiasm": 0.1}},
            {"shot_index": 1, "shot_type": "close-up", "style_overrides": {"enthusiasm": 0.9}},
        ]
        request = ShotSequenceRequest(**data)
        response = await shot_chainer.chain(request)

        # Wide shot with low enthusiasm → gentle motion
        motion_0 = response.shots[0].bridge_response.lpd_prompt.action_motion
        assert motion_0.motion_strength == 0.1
        # Close-up shot with high enthusiasm → dynamic motion
        motion_1 = response.shots[1].bridge_response.lpd_prompt.action_motion
        assert motion_1.motion_strength == 0.9

    async def test_transition_notes_appear_in_environment(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """Transition notes are folded into sketch_notes."""
        data = dict(sample_shot_sequence_request_dict)
        data["shots"] = [
            {"shot_index": 0, "shot_type": "wide", "transition_notes": "Fade in from black"},
            {"shot_index": 1, "shot_type": "medium"},
        ]
        request = ShotSequenceRequest(**data)
        response = await shot_chainer.chain(request)

        # The first shot's bridge request includes transition in sketch_notes.
        # Verify the environment description includes the transition text.
        env = response.shots[0].bridge_response.lpd_prompt.environment.description
        assert "Fade in" in env

    async def test_minimal_request_succeeds(
        self, shot_chainer
    ):
        """Minimal request (only anchor + base_prompt + shots) succeeds."""
        request = ShotSequenceRequest(
            anchor="a silver car",
            base_prompt="driving at sunset",
            shots=[
                {"shot_index": 0, "shot_type": "wide"},
                {"shot_index": 1, "shot_type": "close-up"},
            ],
        )
        response = await shot_chainer.chain(request)
        assert len(response.shots) == 2
        assert response.coherence_score > 0

    async def test_deterministic_output(self, shot_chainer):
        """Same input produces identical output (mock mode)."""
        request = ShotSequenceRequest(
            anchor="a silver car",
            base_prompt="driving at sunset",
            shots=[
                {"shot_index": 0, "shot_type": "wide"},
                {"shot_index": 1, "shot_type": "close-up"},
            ],
        )
        r1 = await shot_chainer.chain(request)
        r2 = await shot_chainer.chain(request)

        assert r1.coherence_score == r2.coherence_score
        assert r1.flagged_shots == r2.flagged_shots
        for s1, s2 in zip(r1.shots, r2.shots, strict=False):
            assert s1.drift_from_previous == s2.drift_from_previous
            assert s1.flagged == s2.flagged
            assert s1.bridge_response.optimized_text == s2.bridge_response.optimized_text

    async def test_generation_error_propagates(self, shot_chainer):
        """If SC generate fails, the chainer propagates the error."""
        # Use a client that raises on generate
        from app.core.exceptions import SemanticCanvasConnectionError

        shot_chainer._sc_client.generate = _make_raising_mock(
            SemanticCanvasConnectionError("Simulated failure")
        )

        request = ShotSequenceRequest(
            anchor="test",
            base_prompt="test",
            shots=[
                {"shot_index": 0, "shot_type": "wide"},
                {"shot_index": 1, "shot_type": "medium"},
            ],
        )
        with pytest.raises(SemanticCanvasConnectionError):
            await shot_chainer.chain(request)

    async def test_drift_error_uses_fallback(
        self, shot_chainer, sample_shot_sequence_request_dict
    ):
        """If SC diff fails, the chainer uses a 0.5 fallback drift."""
        shot_chainer._sc_client.diff = _make_raising_mock(
            RuntimeError("Simulated diff failure")
        )

        request = ShotSequenceRequest(**sample_shot_sequence_request_dict)
        response = await shot_chainer.chain(request)

        # Should still complete successfully
        assert len(response.shots) == 3
        # The first non-first shot should have the 0.5 fallback drift
        assert response.shots[1].drift_from_previous == 0.5

    async def test_shot_type_default_formality(self, shot_chainer):
        """Shot-type formality defaults are applied when no style is set."""
        request = ShotSequenceRequest(
            anchor="a person",
            base_prompt="standing in a field",
            shots=[
                {"shot_index": 0, "shot_type": "wide"},
                {"shot_index": 1, "shot_type": "medium"},
                {"shot_index": 2, "shot_type": "close-up"},
            ],
        )
        response = await shot_chainer.chain(request)

        # Wide → 0.5, medium → 0.6, close-up → 0.7
        expected = [0.5, 0.6, 0.7]
        for i, shot in enumerate(response.shots):
            cam = shot.bridge_response.lpd_prompt.camera_lens
            assert cam.formality == expected[i], (
                f"Shot {i} ({request.shots[i].shot_type}): "
                f"expected formality={expected[i]}, got {cam.formality}"
            )

    async def test_base_style_overrides_shot_type_default(self, shot_chainer):
        """When base style is set, it overrides shot-type formality defaults."""
        request = ShotSequenceRequest(
            anchor="a person",
            base_prompt="standing in a field",
            style={"formality": 0.9, "enthusiasm": 0.3},
            shots=[
                {"shot_index": 0, "shot_type": "wide"},
                {"shot_index": 1, "shot_type": "close-up"},
            ],
        )
        response = await shot_chainer.chain(request)

        for shot in response.shots:
            assert shot.bridge_response.lpd_prompt.camera_lens.formality == 0.9
            assert shot.bridge_response.lpd_prompt.action_motion.motion_strength == 0.3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raising_mock(exc: Exception):
    """Create an async mock function that raises the given exception."""

    async def raiser(*args, **kwargs):
        raise exc

    return raiser
