"""FastAPI dependency injection.

Provides singleton-like access to settings, the Semantic-Canvas HTTP client,
and the prompt transformer. Each dependency is a thin callable that FastAPI
resolves at request time.
"""

from __future__ import annotations

from fastapi import Depends

from app.config import Settings, get_settings
from app.services.prompt_transformer import PromptTransformer
from app.services.semantic_canvas_client import (
    MockSemanticCanvasClient,
    SemanticCanvasClient,
)


def get_settings_dep() -> Settings:
    """Provide the cached Settings singleton."""
    return get_settings()


def get_sc_client(
    settings: Settings = Depends(get_settings_dep),  # noqa: B008
) -> SemanticCanvasClient | MockSemanticCanvasClient:
    """Provide a Semantic-Canvas client — mock or real based on settings."""
    if settings.semantic_canvas_mock:
        return MockSemanticCanvasClient(settings)
    return SemanticCanvasClient(settings)


def get_transformer() -> PromptTransformer:
    """Provide the prompt transformation service."""
    return PromptTransformer()


def get_shot_chainer(
    sc_client: SemanticCanvasClient
    | MockSemanticCanvasClient = Depends(get_sc_client),  # noqa: B008
    transformer: PromptTransformer = Depends(get_transformer),  # noqa: B008
):
    """Provide the multi-shot chainer service."""
    from app.services.shot_chainer import ShotChainer

    return ShotChainer(sc_client=sc_client, transformer=transformer)


def get_feedback_loop(
    sc_client: SemanticCanvasClient
    | MockSemanticCanvasClient = Depends(get_sc_client),  # noqa: B008
    transformer: PromptTransformer = Depends(get_transformer),  # noqa: B008
):
    """Provide the feedback loop service for iterative artifact analysis."""
    from app.services.feedback_loop import FeedbackLoop

    return FeedbackLoop(sc_client=sc_client, transformer=transformer)


def get_parameter_injector(
    sc_client: SemanticCanvasClient
    | MockSemanticCanvasClient = Depends(get_sc_client),  # noqa: B008
    transformer: PromptTransformer = Depends(get_transformer),  # noqa: B008
):
    """Provide the parameter injection service."""
    from app.services.parameter_injector import ParameterInjector

    return ParameterInjector(sc_client=sc_client, transformer=transformer)


def get_concept_fusion(
    sc_client: SemanticCanvasClient
    | MockSemanticCanvasClient = Depends(get_sc_client),  # noqa: B008
    transformer: PromptTransformer = Depends(get_transformer),  # noqa: B008
):
    """Provide the multi-concept fusion service."""
    from app.services.concept_fusion import ConceptFusion

    return ConceptFusion(sc_client=sc_client, transformer=transformer)


def get_production_pipeline(
    sc_client: SemanticCanvasClient
    | MockSemanticCanvasClient = Depends(get_sc_client),  # noqa: B008
    transformer: PromptTransformer = Depends(get_transformer),  # noqa: B008
):
    """Provide the end-to-end production pipeline orchestrator."""
    from app.services.concept_fusion import ConceptFusion
    from app.services.feedback_loop import FeedbackLoop
    from app.services.parameter_injector import ParameterInjector
    from app.services.production_pipeline import ProductionPipeline
    from app.services.shot_chainer import ShotChainer

    return ProductionPipeline(
        fusion=ConceptFusion(sc_client=sc_client, transformer=transformer),
        injector=ParameterInjector(sc_client=sc_client, transformer=transformer),
        chainer=ShotChainer(sc_client=sc_client, transformer=transformer),
        feedback=FeedbackLoop(sc_client=sc_client, transformer=transformer),
    )
