"""End-to-End Production Pipeline — chains all 4 phases into one workflow.

Orchestrates: Concept Fusion → Parameter Injection → Shot Sequence → Feedback Loop
"""

from __future__ import annotations

import time

from app.schemas.bridge import BridgeConstraints, BridgeGenerationParams
from app.schemas.concept_fusion import FusionRequest
from app.schemas.feedback_loop import FeedbackRequest
from app.schemas.parameter_injection import ParameterInjectionRequest
from app.schemas.production_pipeline import (
    PipelineRequest,
    PipelineResponse,
    PipelineStage,
)
from app.schemas.shot_sequence import ShotSequenceRequest
from app.services.concept_fusion import ConceptFusion
from app.services.feedback_loop import FeedbackLoop
from app.services.parameter_injector import ParameterInjector
from app.services.shot_chainer import ShotChainer

_SHOT_TYPE_CYCLE = ["medium", "wide", "medium", "close-up"]


def _rotate_shot_type(index: int) -> str:
    """Pick a varied shot type for an interior shot in the sequence."""
    return _SHOT_TYPE_CYCLE[(index - 1) % len(_SHOT_TYPE_CYCLE)]


class ProductionPipeline:
    """Orchestrates the full production workflow across all 4 phases."""

    def __init__(
        self,
        fusion: ConceptFusion,
        injector: ParameterInjector,
        chainer: ShotChainer,
        feedback: FeedbackLoop,
    ) -> None:
        self._fusion = fusion
        self._injector = injector
        self._chainer = chainer
        self._feedback = feedback

    async def run(self, request: PipelineRequest) -> PipelineResponse:
        """Execute the full production pipeline end-to-end."""
        stages: list[PipelineStage] = []
        t0 = time.perf_counter()

        import hashlib
        gen_id = hashlib.sha256(request.prompt.encode()).hexdigest()[:12]

        # --- Stage 1: Concept Fusion (optional) ---
        fusion_result = None
        unified_prompt = request.prompt

        if request.concepts and len(request.concepts) >= 2:
            t1 = time.perf_counter()
            fusion_result = await self._fusion.fuse(
                FusionRequest(
                    concepts=request.concepts,
                    unifying_theme=request.unifying_theme,
                    style=request.style,
                )
            )
            unified_prompt = fusion_result.unified_prompt.lpd_text
            stages.append(PipelineStage(
                stage="fusion", status="completed",
                duration_ms=round((time.perf_counter() - t1) * 1000, 1),
            ))
        else:
            stages.append(PipelineStage(stage="fusion", status="skipped"))

        # --- Stage 2: Parameter Injection ---
        t2 = time.perf_counter()
        param_result = await self._injector.inject(
            ParameterInjectionRequest(
                prompt=unified_prompt,
                sketch_notes=request.sketch_notes,
                constraints=request.constraints or BridgeConstraints(),
                style=request.style,
                generation_params=request.generation_params or BridgeGenerationParams(),
                target_duration=request.target_duration,
                aspect_ratio=request.aspect_ratio,
            )
        )
        stages.append(PipelineStage(
            stage="parameter_injection", status="completed",
            duration_ms=round((time.perf_counter() - t2) * 1000, 1),
        ))

        # --- Stage 3: Shot Sequence ---
        t3 = time.perf_counter()
        shot_types = (
            [{"shot_index": 0, "shot_type": "wide"}]
            + [
                {"shot_index": i, "shot_type": _rotate_shot_type(i)}
                for i in range(1, request.shot_count - 1)
            ]
            + [{"shot_index": request.shot_count - 1, "shot_type": "close-up"}]
        ) if request.shot_count >= 3 else [
            {"shot_index": 0, "shot_type": "wide"},
            {"shot_index": 1, "shot_type": "close-up"},
        ][:request.shot_count]

        shot_result = await self._chainer.chain(
            ShotSequenceRequest(
                anchor=request.prompt[:100],
                base_prompt=unified_prompt,
                sketch_notes=request.sketch_notes,
                constraints=request.constraints,
                style=request.style,
                generation_params=request.generation_params,
                shots=shot_types,
            )
        )
        stages.append(PipelineStage(
            stage="shot_sequence", status="completed",
            duration_ms=round((time.perf_counter() - t3) * 1000, 1),
        ))

        # --- Stage 4: Feedback Loop (on first shot as representative) ---
        t4 = time.perf_counter()
        if request.max_feedback_iterations > 0 and shot_result.shots:
            first_shot = shot_result.shots[0]
            fb_result = await self._feedback.run(
                FeedbackRequest(
                    prompt=first_shot.bridge_response.lpd_text,
                    sketch_notes=request.sketch_notes,
                    constraints=request.constraints or BridgeConstraints(),
                    style=request.style,
                    generation_params=request.generation_params or BridgeGenerationParams(),
                    max_iterations=request.max_feedback_iterations,
                )
            )
        else:
            fb_result = None
        stages.append(PipelineStage(
            stage="feedback", status="completed" if fb_result else "skipped",
            duration_ms=round((time.perf_counter() - t4) * 1000, 1),
        ))

        # --- Assembly ---
        final_prompts: list[str] = []
        if fb_result:
            final_prompts.append(fb_result.selected_variation.final_prompt)
        for shot in shot_result.shots:
            text = shot.bridge_response.lpd_text
            if text not in final_prompts:
                final_prompts.append(text)

        # Estimate credits: ~23 credits/sec for 1080p+audio
        est_credits = round(request.target_duration * 23 * len(final_prompts), 1)

        return PipelineResponse(
            generation_id=f"pipeline-{gen_id}",
            fusion_result=fusion_result,
            parameter_result=param_result,
            shot_sequence_result=shot_result,
            feedback_result=fb_result,
            stages=stages,
            total_duration_ms=round((time.perf_counter() - t0) * 1000, 1),
            estimated_credits=est_credits,
            final_lpd_prompts=final_prompts,
        )
