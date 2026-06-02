"""Bridge endpoint — transform narrative concepts into PixVerse LPD prompts.

POST /v1/bridge/generate
------------------------
Accepts a narrative concept with optimization parameters, sends it to
Semantic-Canvas for diffusion-based refinement, decomposes the result
into PixVerse V6 LPD (Literal Physical Description) components, and
returns both the optimized text and the assembled prompt.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_concept_fusion,
    get_feedback_loop,
    get_parameter_injector,
    get_production_pipeline,
    get_sc_client,
    get_shot_chainer,
    get_transformer,
)
from app.schemas.bridge import BridgeRequest, BridgeResponse
from app.schemas.concept_fusion import FusionRequest, FusionResponse
from app.schemas.feedback_loop import FeedbackRequest, FeedbackResponse
from app.schemas.parameter_injection import (
    ParameterInjectionRequest,
    ParameterInjectionResponse,
)
from app.schemas.production_pipeline import PipelineRequest, PipelineResponse
from app.schemas.shot_sequence import ShotSequenceRequest, ShotSequenceResponse
from app.services.concept_fusion import ConceptFusion
from app.services.feedback_loop import FeedbackLoop
from app.services.parameter_injector import ParameterInjector
from app.services.production_pipeline import ProductionPipeline
from app.services.prompt_transformer import PromptTransformer
from app.services.semantic_canvas_client import (
    MockSemanticCanvasClient,
    SemanticCanvasClient,
)
from app.services.shot_chainer import ShotChainer

router = APIRouter()


@router.post(
    "/generate",
    response_model=BridgeResponse,
    summary="Generate optimized PixVerse V6 LPD prompt from a narrative concept",
    description=(
        "Sends the narrative concept to Semantic-Canvas for diffusion-based optimization, "
        "then decomposes the result into the six PixVerse LPD components: "
        "Subject, Action/Motion, Environment, Lighting, Camera/Lens, and Audio. "
        "Returns the original concept, optimized text, and assembled LPD prompt string "
        "ready for PixVerse V6 consumption."
    ),
)
async def bridge_generate(
    request: BridgeRequest,
    sc_client: SemanticCanvasClient
    | MockSemanticCanvasClient = Depends(get_sc_client),  # noqa: B008
    transformer: PromptTransformer = Depends(get_transformer),  # noqa: B008
) -> BridgeResponse:
    """Transform a narrative concept into a PixVerse V6 LPD prompt.

    1. Sends the concept to Semantic-Canvas for diffusion-based optimization.
    2. Decomposes the optimized output into the six LPD components.
    3. Returns the original concept, optimized text, and assembled LPD prompt.
    """
    sc_response = await sc_client.generate(request)

    lpd_prompt = transformer.transform(request, sc_response)
    lpd_text = lpd_prompt.to_lpd_text()

    return BridgeResponse(
        generation_id=sc_response.get("generation_id", ""),
        original_prompt=request.prompt,
        optimized_text=sc_response.get("text", ""),
        lpd_prompt=lpd_prompt,
        lpd_text=lpd_text,
        metadata={
            "sc_metadata": sc_response.get("metadata", {}),
            "cached": sc_response.get("cached", False),
        },
    )


@router.post(
    "/shot-sequence",
    response_model=ShotSequenceResponse,
    summary="Generate a multi-shot video sequence with Anchor-Repeat Protocol",
    description=(
        "Generates an ordered sequence of PixVerse V6 LPD prompts sharing a common "
        "anchor subject. Each shot varies camera distance and framing while keeping "
        "the subject consistent. Includes latent drift analysis between consecutive "
        "shots, flagging any that exceed the coherence threshold for re-prompting."
    ),
)
async def bridge_shot_sequence(
    request: ShotSequenceRequest,
    chainer: ShotChainer = Depends(get_shot_chainer),  # noqa: B008
) -> ShotSequenceResponse:
    """Generate a coherent multi-shot sequence with drift analysis.

    1. For each shot specification, builds a shot-specific BridgeRequest
       merging the shared anchor, base_prompt, and shot-type context.
    2. Generates optimized prompts via Semantic-Canvas.
    3. Transforms each into PixVerse V6 LPD format.
    4. Computes semantic drift between consecutive shots.
    5. Flags shots exceeding the drift threshold.
    6. Returns per-shot results with an overall coherence score.
    """
    return await chainer.chain(request)


@router.post(
    "/feedback-loop",
    response_model=FeedbackResponse,
    summary="Run the 3-Generation Rule with artifact analysis and refinement",
    description=(
        "Generates 3 LPD prompt variations with different motion strengths "
        "(baseline, +10%, -10%), analyzes each for 6 artifact types using "
        "deterministic text heuristics, iteratively refines flagged prompts, "
        "and selects the best variation based on artifact cleanliness, "
        "temporal stability, and semantic coherence."
    ),
)
async def bridge_feedback_loop(
    request: FeedbackRequest,
    feedback_loop: FeedbackLoop = Depends(get_feedback_loop),  # noqa: B008
) -> FeedbackResponse:
    """Execute the full feedback loop pipeline on a narrative concept.

    1. Generates 3 motion-strength variations of the prompt.
    2. Analyzes each for 6 artifact types (motion smearing, hand distortion,
       facial drift, lighting inconsistency, subject blending, temporal flicker).
    3. Iteratively refines flagged prompts by applying targeted text fixes.
    4. Selects the best variation with full audit trail.
    """
    return await feedback_loop.run(request)


@router.post(
    "/parameter-injection",
    response_model=ParameterInjectionResponse,
    summary="Inject style vectors into precise PixVerse V6 generation parameters",
    description=(
        "Maps Semantic-Canvas style vectors (formality, enthusiasm, technical_depth) "
        "to exact PixVerse V6 parameters: motion strength %, camera type + lens mm, "
        "lighting setup complexity, and render quality tier. Returns the LPD prompt "
        "alongside the injected parameters with justifications."
    ),
)
async def bridge_parameter_injection(
    request: ParameterInjectionRequest,
    injector: ParameterInjector = Depends(get_parameter_injector),  # noqa: B008
) -> ParameterInjectionResponse:
    """Inject dynamic parameters from style vectors.

    enthusiasm → motion strength & speed
    formality → camera type, lens, stabilization
    technical_depth → lighting complexity & render quality
    """
    return await injector.inject(request)


@router.post(
    "/concept-fusion",
    response_model=FusionResponse,
    summary="Fuse multiple concepts into a single cohesive PixVerse scene",
    description=(
        "Blends 2-5 independent narrative concepts into one unified PixVerse V6 "
        "prompt. Each concept generates its own optimized text, embeddings are "
        "blended via weighted fusion, and a spatial scene composition directive "
        "preserves subject separation (foreground/background/ambient)."
    ),
)
async def bridge_concept_fusion(
    request: FusionRequest,
    fusion: ConceptFusion = Depends(get_concept_fusion),  # noqa: B008
) -> FusionResponse:
    """Fuse multiple concepts into a unified scene.

    1. Generates LPD prompt for each concept independently.
    2. Computes latent embeddings and blend coherence.
    3. Builds a spatial scene composition from concept roles.
    4. Returns the unified prompt with per-concept audit trail.
    """
    return await fusion.fuse(request)


@router.post(
    "/production-pipeline",
    response_model=PipelineResponse,
    summary="Run the complete end-to-end production pipeline",
    description=(
        "Chains all 4 phases into a single workflow: optional Concept Fusion → "
        "Parameter Injection → Multi-Shot Sequence → Feedback Refinement. "
        "Returns a complete deliverable with all intermediate artifacts, "
        "timing per stage, estimated PixVerse V6 credit cost, and final "
        "LPD prompts ready for generation."
    ),
)
async def bridge_production_pipeline(
    request: PipelineRequest,
    pipeline: ProductionPipeline = Depends(get_production_pipeline),  # noqa: B008
) -> PipelineResponse:
    """Execute the full production pipeline.

    Concept → Fusion → Parameter Injection → Shot Sequence → Feedback → Deliverable
    """
    return await pipeline.run(request)

