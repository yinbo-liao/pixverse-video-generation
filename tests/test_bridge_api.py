"""Integration tests for the bridge API endpoint.

Tests validate the HTTP contract of POST /v1/bridge/generate:
  - 200 on valid requests
  - 422 on invalid requests
  - Error response mapping from upstream failures
  - Metadata preservation
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Successful generation (200)
# ---------------------------------------------------------------------------

class TestGenerateSuccess:
    """Happy-path tests: valid requests that return 200."""

    @patch("app.api.v1.bridge.SemanticCanvasClient.generate", new_callable=AsyncMock)
    async def test_returns_200_with_bridge_response(
        self, mock_generate, async_client, sample_bridge_request_dict, sample_sc_response
    ):
        """A valid request returns 200 with a complete BridgeResponse."""
        mock_generate.return_value = sample_sc_response

        response = await async_client.post(
            "/v1/bridge/generate", json=sample_bridge_request_dict
        )

        assert response.status_code == 200
        body = response.json()
        assert body["generation_id"] == "gen-test-001"
        assert body["original_prompt"] == sample_bridge_request_dict["prompt"]
        assert "optimized_text" in body
        assert "lpd_prompt" in body
        assert "lpd_text" in body
        assert "metadata" in body

    @patch("app.api.v1.bridge.SemanticCanvasClient.generate", new_callable=AsyncMock)
    async def test_lpd_prompt_has_all_components(
        self, mock_generate, async_client, sample_bridge_request_dict, sample_sc_response
    ):
        """The lpd_prompt in the response contains all six LPD components."""
        mock_generate.return_value = sample_sc_response

        response = await async_client.post(
            "/v1/bridge/generate", json=sample_bridge_request_dict
        )
        body = response.json()
        lpd = body["lpd_prompt"]

        components = ("subject", "action_motion", "environment", "lighting", "camera_lens", "audio")
        for component in components:
            assert component in lpd, f"Missing LPD component: {component}"

    @patch("app.api.v1.bridge.SemanticCanvasClient.generate", new_callable=AsyncMock)
    async def test_lpd_text_format(
        self, mock_generate, async_client, sample_bridge_request_dict, sample_sc_response
    ):
        """The lpd_text field is a non-empty string ending with a period."""
        mock_generate.return_value = sample_sc_response

        response = await async_client.post(
            "/v1/bridge/generate", json=sample_bridge_request_dict
        )
        body = response.json()

        lpd_text = body["lpd_text"]
        assert isinstance(lpd_text, str)
        assert len(lpd_text) > 0
        # LPD format always ends with period
        assert lpd_text.endswith(".")

    @patch("app.api.v1.bridge.SemanticCanvasClient.generate", new_callable=AsyncMock)
    async def test_metadata_preserved(
        self, mock_generate, async_client, sample_bridge_request_dict, sample_sc_response
    ):
        """SC metadata is included in the bridge response."""
        mock_generate.return_value = sample_sc_response

        response = await async_client.post(
            "/v1/bridge/generate", json=sample_bridge_request_dict
        )
        body = response.json()

        assert "metadata" in body
        assert "sc_metadata" in body["metadata"]
        assert body["metadata"]["sc_metadata"]["constraint_compliance"] == 0.97
        assert body["metadata"]["cached"] is False

    @patch("app.api.v1.bridge.SemanticCanvasClient.generate", new_callable=AsyncMock)
    async def test_cached_response(
        self, mock_generate, async_client, sample_bridge_request_dict, sample_sc_response_cached
    ):
        """When SC returns cached=True, the bridge metadata reflects it."""
        mock_generate.return_value = sample_sc_response_cached

        response = await async_client.post(
            "/v1/bridge/generate", json=sample_bridge_request_dict
        )
        body = response.json()

        assert body["metadata"]["cached"] is True
        assert body["metadata"]["sc_metadata"]["generation_time_ms"] == 2

    @patch("app.api.v1.bridge.SemanticCanvasClient.generate", new_callable=AsyncMock)
    async def test_minimal_request_succeeds(
        self, mock_generate, async_client, minimal_bridge_request_dict, sample_sc_response
    ):
        """A prompt-only request (no optional fields) returns 200."""
        mock_generate.return_value = sample_sc_response

        response = await async_client.post(
            "/v1/bridge/generate", json=minimal_bridge_request_dict
        )
        assert response.status_code == 200
        body = response.json()
        assert body["original_prompt"] == minimal_bridge_request_dict["prompt"]


# ---------------------------------------------------------------------------
# Validation errors (422)
# ---------------------------------------------------------------------------

class TestValidationErrors:
    """Tests for Pydantic validation on the request body."""

    @pytest.mark.parametrize(
        "payload,expected_field",
        [
            ({}, "prompt"),
            ({"prompt": ""}, "prompt"),
            ({"prompt": "x" * 5000}, "prompt"),
            ({"prompt": "valid", "style": {"enthusiasm": 1.5}}, "enthusiasm"),
            ({"prompt": "valid", "style": {"enthusiasm": -0.1}}, "enthusiasm"),
            ({"prompt": "valid", "style": {"formality": 3.0}}, "formality"),
            ({"prompt": "valid", "generation_params": {"temperature": 0.0}}, "temperature"),
            ({"prompt": "valid", "generation_params": {"num_steps": 3}}, "num_steps"),
            ({"prompt": "valid", "constraints": {"max_length": 0}}, "max_length"),
        ],
    )
    async def test_validation_error(self, async_client, payload, expected_field):
        """Invalid payloads return 422 with the expected validation error."""
        response = await async_client.post("/v1/bridge/generate", json=payload)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Upstream error mapping
# ---------------------------------------------------------------------------

class TestUpstreamErrors:
    """Tests for Semantic-Canvas error translation to bridge HTTP status codes."""

    async def test_connection_error_returns_502(self, async_client, sample_bridge_request_dict):
        """When SC is unreachable, the bridge returns 502."""
        with patch(
            "app.api.v1.bridge.SemanticCanvasClient.generate",
            side_effect=__import__(
                "app.core.exceptions", fromlist=["SemanticCanvasConnectionError"]
            ).SemanticCanvasConnectionError("Cannot connect"),
        ):
            response = await async_client.post(
                "/v1/bridge/generate", json=sample_bridge_request_dict
            )
            assert response.status_code == 502

    async def test_timeout_returns_504(self, async_client, sample_bridge_request_dict):
        """When SC times out, the bridge returns 504."""
        with patch(
            "app.api.v1.bridge.SemanticCanvasClient.generate",
            side_effect=__import__(
                "app.core.exceptions", fromlist=["SemanticCanvasTimeoutError"]
            ).SemanticCanvasTimeoutError("Timed out"),
        ):
            response = await async_client.post(
                "/v1/bridge/generate", json=sample_bridge_request_dict
            )
            assert response.status_code == 504

    async def test_response_error_returns_502(self, async_client, sample_bridge_request_dict):
        """When SC returns an error response, the bridge returns 502."""
        with patch(
            "app.api.v1.bridge.SemanticCanvasClient.generate",
            side_effect=__import__(
                "app.core.exceptions", fromlist=["SemanticCanvasResponseError"]
            ).SemanticCanvasResponseError(status=500, detail="Internal error"),
        ):
            response = await async_client.post(
                "/v1/bridge/generate", json=sample_bridge_request_dict
            )
            assert response.status_code == 502


# ---------------------------------------------------------------------------
# Shot sequence endpoint
# ---------------------------------------------------------------------------


class TestShotSequenceEndpoint:
    """Integration tests for POST /v1/bridge/shot-sequence."""

    @patch(
        "app.api.v1.bridge.SemanticCanvasClient.generate",
        new_callable=AsyncMock,
    )
    async def test_returns_200_with_sequence_response(
        self, mock_generate, async_client, sample_shot_sequence_request_dict, sample_sc_response
    ):
        """Valid shot sequence request returns 200 with ShotSequenceResponse."""
        mock_generate.return_value = sample_sc_response

        response = await async_client.post(
            "/v1/bridge/shot-sequence", json=sample_shot_sequence_request_dict
        )
        assert response.status_code == 200
        body = response.json()
        assert "anchor" in body
        assert "shots" in body
        assert "coherence_score" in body
        assert "flagged_shots" in body

    @patch(
        "app.api.v1.bridge.SemanticCanvasClient.generate",
        new_callable=AsyncMock,
    )
    async def test_response_has_correct_shot_count(
        self, mock_generate, async_client, sample_shot_sequence_request_dict, sample_sc_response
    ):
        """Response contains one shot result per requested shot."""
        mock_generate.return_value = sample_sc_response

        response = await async_client.post(
            "/v1/bridge/shot-sequence", json=sample_shot_sequence_request_dict
        )
        body = response.json()
        assert len(body["shots"]) == 3

    @patch(
        "app.api.v1.bridge.SemanticCanvasClient.generate",
        new_callable=AsyncMock,
    )
    async def test_each_shot_has_bridge_response(
        self, mock_generate, async_client, sample_shot_sequence_request_dict, sample_sc_response
    ):
        """Each shot has a complete bridge_response."""
        mock_generate.return_value = sample_sc_response

        response = await async_client.post(
            "/v1/bridge/shot-sequence", json=sample_shot_sequence_request_dict
        )
        body = response.json()
        for shot in body["shots"]:
            br = shot["bridge_response"]
            assert "generation_id" in br
            assert "optimized_text" in br
            assert "lpd_prompt" in br
            assert "lpd_text" in br

    @patch(
        "app.api.v1.bridge.SemanticCanvasClient.generate",
        new_callable=AsyncMock,
    )
    async def test_first_shot_no_drift(
        self, mock_generate, async_client, sample_shot_sequence_request_dict, sample_sc_response
    ):
        """First shot has drift_from_previous=None and flagged=False."""
        mock_generate.return_value = sample_sc_response

        response = await async_client.post(
            "/v1/bridge/shot-sequence", json=sample_shot_sequence_request_dict
        )
        body = response.json()
        first_shot = body["shots"][0]
        assert first_shot["drift_from_previous"] is None
        assert first_shot["flagged"] is False

    @patch(
        "app.api.v1.bridge.SemanticCanvasClient.generate",
        new_callable=AsyncMock,
    )
    async def test_coherence_score_is_numeric(
        self, mock_generate, async_client, sample_shot_sequence_request_dict, sample_sc_response
    ):
        """Coherence score is a float between 0 and 1."""
        mock_generate.return_value = sample_sc_response

        response = await async_client.post(
            "/v1/bridge/shot-sequence", json=sample_shot_sequence_request_dict
        )
        body = response.json()
        score = body["coherence_score"]
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0

    async def test_validation_missing_anchor(self, async_client):
        """422 when anchor is missing."""
        response = await async_client.post(
            "/v1/bridge/shot-sequence",
            json={
                "base_prompt": "test",
                "shots": [
                    {"shot_index": 0, "shot_type": "wide"},
                    {"shot_index": 1, "shot_type": "medium"},
                ],
            },
        )
        assert response.status_code == 422

    async def test_validation_empty_shots(self, async_client):
        """422 when shots list is empty."""
        response = await async_client.post(
            "/v1/bridge/shot-sequence",
            json={"anchor": "test", "base_prompt": "test", "shots": []},
        )
        assert response.status_code == 422

    async def test_validation_invalid_shot_type(self, async_client):
        """422 when a shot has an invalid shot_type."""
        response = await async_client.post(
            "/v1/bridge/shot-sequence",
            json={
                "anchor": "test",
                "base_prompt": "test",
                "shots": [
                    {"shot_index": 0, "shot_type": "extreme-close-up"},
                    {"shot_index": 1, "shot_type": "wide"},
                ],
            },
        )
        assert response.status_code == 422
