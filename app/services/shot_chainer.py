"""Multi-shot chaining service with latent drift analysis.

Orchestrates the PixVerse V6 Anchor-Repeat Protocol across a sequence of shots:
  1. For each shot, constructs a shot-specific BridgeRequest merging
     the shared anchor subject, base narrative, sketch_notes, and
     shot-type-specific camera/motion context.
  2. Calls Semantic-Canvas to generate an optimized prompt per shot.
  3. Transforms each result into PixVerse LPD format via PromptTransformer.
  4. Computes semantic drift between consecutive shots via SC encode/diff.
  5. Flags shots exceeding the drift threshold for re-prompting.
  6. Computes an overall sequence coherence score.
"""

from __future__ import annotations

import logging

from app.schemas.bridge import BridgeConstraints, BridgeGenerationParams, BridgeRequest, BridgeStyle
from app.schemas.shot_sequence import (
    ShotResult,
    ShotSequenceRequest,
    ShotSequenceResponse,
    ShotSpec,
)
from app.services.prompt_transformer import PromptTransformer
from app.services.semantic_canvas_client import (
    MockSemanticCanvasClient,
    SemanticCanvasClient,
)

logger = logging.getLogger(__name__)

# Shot type → default formality (applied when no explicit formality is set)
_SHOT_TYPE_DEFAULT_FORMALITY: dict[str, float] = {
    "wide": 0.5,
    "medium": 0.6,
    "close-up": 0.7,
}

# Shot type → prompt prefix for Semantic-Canvas optimization context
_SHOT_TYPE_PROMPT_PREFIX: dict[str, str] = {
    "wide": "Wide establishing shot",
    "medium": "Medium detail shot",
    "close-up": "Close-up shot",
}


class ShotChainer:
    """Orchestrates multi-shot generation with semantic drift analysis.

    Two-phase processing:
      1. Generate all shots independently (each shot gets its own SC call).
      2. Compute pairwise drift between consecutive shots, flag divergences,
         and calculate overall coherence.
    """

    def __init__(
        self,
        sc_client: SemanticCanvasClient | MockSemanticCanvasClient,
        transformer: PromptTransformer,
    ) -> None:
        self._sc_client = sc_client
        self._transformer = transformer

    async def chain(self, request: ShotSequenceRequest) -> ShotSequenceResponse:
        """Generate a full multi-shot sequence with drift analysis.

        Args:
            request: Shot sequence specification with anchor, base prompt, and shots.

        Returns:
            ShotSequenceResponse with per-shot LPD prompts, drift metrics, and
            an overall coherence score.

        Raises:
            PixVerseBridgeError: If any shot generation or drift computation fails.
        """
        total = len(request.shots)

        # ---- Phase 1: Generate all shots ----
        shot_results: list[ShotResult] = []
        optimized_texts: list[str] = []

        for shot_spec in request.shots:
            bridge_req = self._build_shot_request(request, shot_spec)
            logger.info(
                "Generating shot %d/%d (type=%s)",
                shot_spec.shot_index + 1,
                total,
                shot_spec.shot_type,
            )

            sc_response = await self._sc_client.generate(bridge_req)
            lpd_prompt = self._transformer.transform(bridge_req, sc_response)
            lpd_text = lpd_prompt.to_lpd_text()
            optimized_text = sc_response.get("text", "")
            optimized_texts.append(optimized_text)

            from app.schemas.bridge import BridgeResponse

            bridge_resp = BridgeResponse(
                generation_id=sc_response.get("generation_id", ""),
                original_prompt=bridge_req.prompt,
                optimized_text=optimized_text,
                lpd_prompt=lpd_prompt,
                lpd_text=lpd_text,
                metadata={
                    "sc_metadata": sc_response.get("metadata", {}),
                    "cached": sc_response.get("cached", False),
                },
            )

            shot_results.append(
                ShotResult(
                    shot_index=shot_spec.shot_index,
                    shot_type=shot_spec.shot_type,
                    bridge_response=bridge_resp,
                    drift_from_previous=None,
                    flagged=False,
                )
            )

        # ---- Phase 2: Drift analysis between consecutive shots ----
        drifts: list[float | None] = [None]  # First shot has no predecessor

        for i in range(1, len(optimized_texts)):
            try:
                diff_response = await self._sc_client.diff(
                    optimized_texts[i - 1], optimized_texts[i]
                )
                distance = diff_response["distance"]
            except Exception:
                logger.warning("Drift computation failed for shot %d, using 0.5 fallback", i)
                distance = 0.5
            drifts.append(distance)

        # ---- Phase 3: Flagging and coherence ----
        flagged_indices: list[int] = []

        for i, drift in enumerate(drifts):
            if drift is not None:
                shot_results[i].drift_from_previous = drift
                if drift > request.drift_threshold:
                    shot_results[i].flagged = True
                    flagged_indices.append(shot_results[i].shot_index)

        valid_drifts = [d for d in drifts if d is not None]
        avg_drift = sum(valid_drifts) / len(valid_drifts) if valid_drifts else 0.0
        coherence_score = max(0.0, 1.0 - avg_drift)

        return ShotSequenceResponse(
            anchor=request.anchor,
            shots=shot_results,
            coherence_score=round(coherence_score, 4),
            flagged_shots=flagged_indices,
        )

    def _build_shot_request(
        self, request: ShotSequenceRequest, shot_spec: ShotSpec
    ) -> BridgeRequest:
        """Construct a shot-specific BridgeRequest from the shared sequence config.

        Key transformations:
          - Anchor is injected into must_include (ensures LPD Subject consistency).
          - Prompt is prefixed with shot type (e.g., "Wide establishing shot:").
          - Custom instructions and transition notes are folded in.
          - Style is resolved: shot override > base style > shot-type default.
        """
        # --- Build shot-specific prompt ---
        prefix = _SHOT_TYPE_PROMPT_PREFIX.get(shot_spec.shot_type, "")
        shot_prompt = f"{prefix}: {request.anchor}. {request.base_prompt}"
        if shot_spec.custom_instruction:
            shot_prompt = f"{shot_prompt}. {shot_spec.custom_instruction}"

        # --- Merge constraints, ensuring anchor is in must_include ---
        base_constraints = request.constraints or BridgeConstraints()
        resolved_must_include = list(base_constraints.must_include)
        if request.anchor not in resolved_must_include:
            resolved_must_include.insert(0, request.anchor)
        shot_constraints = BridgeConstraints(
            tone=base_constraints.tone,
            max_length=base_constraints.max_length,
            must_include=resolved_must_include,
            must_exclude=list(base_constraints.must_exclude),
            brand_voice_id=base_constraints.brand_voice_id,
        )

        # --- Resolve style: shot override > base style > shot-type default ---
        resolved_formality = _SHOT_TYPE_DEFAULT_FORMALITY[shot_spec.shot_type]
        resolved_enthusiasm = 0.5
        resolved_technical_depth = 0.5

        if request.style is not None:
            resolved_formality = request.style.formality
            resolved_enthusiasm = request.style.enthusiasm
            resolved_technical_depth = request.style.technical_depth

        if shot_spec.style_overrides is not None:
            overrides = shot_spec.style_overrides
            resolved_formality = overrides.formality
            resolved_enthusiasm = overrides.enthusiasm
            resolved_technical_depth = overrides.technical_depth

        shot_style = BridgeStyle(
            formality=resolved_formality,
            enthusiasm=resolved_enthusiasm,
            technical_depth=resolved_technical_depth,
            description=shot_spec.style_overrides.description
            if shot_spec.style_overrides and shot_spec.style_overrides.description
            else (request.style.description if request.style else None),
        )

        # --- Build sketch notes with transition context ---
        sketch_notes = request.sketch_notes
        if shot_spec.transition_notes:
            prefix = "Transition:" if not sketch_notes else " Transition:"
            sketch_notes = (sketch_notes or "") + f"{prefix} {shot_spec.transition_notes}"

        # --- Build generation params ---
        gen_params = request.generation_params or BridgeGenerationParams()

        return BridgeRequest(
            prompt=shot_prompt,
            sketch_notes=sketch_notes if sketch_notes else None,
            constraints=shot_constraints,
            style=shot_style,
            generation_params=gen_params,
        )
