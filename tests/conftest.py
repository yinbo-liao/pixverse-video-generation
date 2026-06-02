"""Shared test fixtures and mocks for PixVerse Bridge tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_settings_dep
from app.config import Settings
from app.main import create_app
from app.schemas.bridge import BridgeRequest


@pytest.fixture
def test_settings() -> Settings:
    """Settings pointing at a fake Semantic-Canvas for safe testing."""
    return Settings(
        semantic_canvas_base_url="http://test-semantic-canvas:9999",
        semantic_canvas_api_key=None,
        semantic_canvas_timeout=5,
        semantic_canvas_mock=False,
        log_level="DEBUG",
        debug=True,
    )


@pytest.fixture
def app(test_settings: Settings):
    """Create a FastAPI app with test settings overridden."""
    app = create_app()
    # Override the DI dependency so all injected code receives test_settings
    app.dependency_overrides[get_settings_dep] = lambda: test_settings
    return app


@pytest.fixture
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client bound to the app via ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---- Sample payload fixtures ----


@pytest.fixture
def sample_bridge_request_dict() -> dict:
    """Minimal valid bridge request payload as a plain dict."""
    return {
        "prompt": "A cyberpunk detective walks through a rainy neon-lit street",
        "sketch_notes": (
            "Narrow alley in future Tokyo. Holographic signs reflecting on wet pavement. "
            "Steam rising from grates. Dim moody atmosphere."
        ),
        "constraints": {
            "tone": "noir",
            "max_length": 800,
            "must_include": ["cyberpunk detective", "trench coat", "neon reflections"],
            "must_exclude": ["daylight", "crowds"],
        },
        "style": {
            "formality": 0.8,
            "enthusiasm": 0.7,
            "technical_depth": 0.6,
        },
        "generation_params": {
            "num_steps": 12,
            "temperature": 0.8,
        },
    }


@pytest.fixture
def sample_bridge_request(sample_bridge_request_dict: dict) -> BridgeRequest:
    """Parsed BridgeRequest model from the sample dict."""
    return BridgeRequest(**sample_bridge_request_dict)


@pytest.fixture
def sample_sc_response() -> dict:
    """Minimal valid Semantic-Canvas /v1/generate response."""
    return {
        "type": "generation.completed",
        "generation_id": "gen-test-001",
        "status": "completed",
        "text": (
            "A cyberpunk detective in a weathered trench coat strides through "
            "a rain-soaked future Tokyo alley. Holographic signs cast neon "
            "reflections across the wet pavement."
        ),
        "latent_trajectory": [],
        "metadata": {
            "input_tokens": 45,
            "output_tokens": 38,
            "generation_time_ms": 520,
            "constraint_compliance": 0.97,
            "num_steps": 12,
        },
        "cached": False,
    }


@pytest.fixture
def sample_sc_response_cached() -> dict:
    """Semantic-Canvas response with cached=True."""
    return {
        "type": "generation.completed",
        "generation_id": "gen-cached-001",
        "status": "completed",
        "text": "A quiet forest at dawn with mist rising through ancient pines.",
        "latent_trajectory": [],
        "metadata": {
            "input_tokens": 12,
            "output_tokens": 15,
            "generation_time_ms": 2,
            "num_steps": 8,
        },
        "cached": True,
    }


@pytest.fixture
def minimal_bridge_request_dict() -> dict:
    """Prompt-only bridge request (no optional fields)."""
    return {
        "prompt": "A quiet forest at dawn with mist rising",
    }


@pytest.fixture
def transformer():
    """PromptTransformer instance for unit tests."""
    from app.services.prompt_transformer import PromptTransformer

    return PromptTransformer()


# ---- Shot sequence fixtures ----


@pytest.fixture
def sample_shot_specs() -> list[dict]:
    """Three standard Anchor-Repeat Protocol shots: wide, medium, close-up."""
    return [
        {"shot_index": 0, "shot_type": "wide", "transition_notes": None},
        {"shot_index": 1, "shot_type": "medium", "transition_notes": "Cut on action"},
        {"shot_index": 2, "shot_type": "close-up", "transition_notes": "Slow dissolve"},
    ]


@pytest.fixture
def sample_shot_sequence_request_dict(sample_shot_specs: list[dict]) -> dict:
    """Valid shot sequence request with anchor, base prompt, and 3 shots."""
    return {
        "anchor": "a cyberpunk detective in a weathered trench coat",
        "base_prompt": "walks through a rain-soaked future Tokyo alley at night",
        "sketch_notes": (
            "Narrow alley. Holographic signs reflecting on wet pavement. "
            "Steam rising from grates."
        ),
        "constraints": {
            "tone": "noir",
            "must_include": ["rain-soaked alley", "neon glow"],
        },
        "style": {"formality": 0.7, "enthusiasm": 0.6},
        "shots": sample_shot_specs,
    }


@pytest.fixture
def shot_chainer(test_settings):
    """ShotChainer instance backed by MockSemanticCanvasClient."""
    from app.services.prompt_transformer import PromptTransformer
    from app.services.semantic_canvas_client import MockSemanticCanvasClient
    from app.services.shot_chainer import ShotChainer

    mock_client = MockSemanticCanvasClient(test_settings)
    transformer = PromptTransformer()
    return ShotChainer(sc_client=mock_client, transformer=transformer)


# ---- Feedback loop fixtures ----


@pytest.fixture
def sample_feedback_request_dict() -> dict:
    """Feedback loop request with a prompt containing intentional artifacts."""
    return {
        "prompt": "A detective runs frantically through a flashing neon alley",
        "sketch_notes": "Narrow alley at night. Flashing neon signs. Steam rising.",
        "constraints": {"tone": "noir", "must_include": ["detective", "trench coat"]},
        "style": {"enthusiasm": 0.7, "formality": 0.6},
        "max_iterations": 3,
    }


@pytest.fixture
def clean_prompt_dict() -> dict:
    """Feedback loop request with a well-crafted, artifact-free prompt."""
    return {
        "prompt": "A person walks slowly through a softly lit forest at dawn",
        "sketch_notes": "Ancient forest. Soft diffused morning light. Mist rising.",
        "constraints": {"tone": "soft"},
        "style": {"enthusiasm": 0.2, "formality": 0.5},
        "max_iterations": 2,
    }


@pytest.fixture
def feedback_loop(test_settings):
    """FeedbackLoop instance backed by MockSemanticCanvasClient."""
    from app.services.feedback_loop import FeedbackLoop
    from app.services.prompt_transformer import PromptTransformer
    from app.services.semantic_canvas_client import MockSemanticCanvasClient

    mock_client = MockSemanticCanvasClient(test_settings)
    transformer = PromptTransformer()
    return FeedbackLoop(sc_client=mock_client, transformer=transformer)


# ---- Phase 4 fixtures ----


@pytest.fixture
def parameter_injector(test_settings):
    """ParameterInjector instance backed by MockSemanticCanvasClient."""
    from app.services.parameter_injector import ParameterInjector
    from app.services.prompt_transformer import PromptTransformer
    from app.services.semantic_canvas_client import MockSemanticCanvasClient

    mock_client = MockSemanticCanvasClient(test_settings)
    transformer = PromptTransformer()
    return ParameterInjector(sc_client=mock_client, transformer=transformer)


@pytest.fixture
def concept_fusion(test_settings):
    """ConceptFusion instance backed by MockSemanticCanvasClient."""
    from app.services.concept_fusion import ConceptFusion
    from app.services.prompt_transformer import PromptTransformer
    from app.services.semantic_canvas_client import MockSemanticCanvasClient

    mock_client = MockSemanticCanvasClient(test_settings)
    transformer = PromptTransformer()
    return ConceptFusion(sc_client=mock_client, transformer=transformer)


@pytest.fixture
def production_pipeline(test_settings):
    """ProductionPipeline backed by MockSemanticCanvasClient."""
    from app.services.concept_fusion import ConceptFusion
    from app.services.feedback_loop import FeedbackLoop
    from app.services.parameter_injector import ParameterInjector
    from app.services.production_pipeline import ProductionPipeline
    from app.services.prompt_transformer import PromptTransformer
    from app.services.semantic_canvas_client import MockSemanticCanvasClient
    from app.services.shot_chainer import ShotChainer

    mock = MockSemanticCanvasClient(test_settings)
    t = PromptTransformer()
    return ProductionPipeline(
        fusion=ConceptFusion(sc_client=mock, transformer=t),
        injector=ParameterInjector(sc_client=mock, transformer=t),
        chainer=ShotChainer(sc_client=mock, transformer=t),
        feedback=FeedbackLoop(sc_client=mock, transformer=t),
    )
