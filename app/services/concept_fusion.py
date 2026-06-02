"""Multi-Concept Fusion — blends independent concepts into a unified scene.

Fuses 2-5 concepts by:
  1. Generating an optimized LPD prompt for each concept independently.
  2. Computing mock latent embeddings for each concept.
  3. Weighted blending of embeddings into a unified latent vector.
  4. Composing a scene composition directive from concept roles and weights.
  5. Building a unified prompt that preserves subject separation.
"""

from __future__ import annotations

import logging

from app.schemas.bridge import BridgeRequest, BridgeResponse
from app.schemas.concept_fusion import (
    ConceptResult,
    FusionRequest,
    FusionResponse,
)
from app.services.prompt_transformer import PromptTransformer
from app.services.semantic_canvas_client import (
    MockSemanticCanvasClient,
    SemanticCanvasClient,
    _cosine_distance,
    _text_to_embedding,
)

logger = logging.getLogger(__name__)


class ConceptFusion:
    """Blends multiple concepts into a unified PixVerse prompt."""

    def __init__(
        self,
        sc_client: SemanticCanvasClient | MockSemanticCanvasClient,
        transformer: PromptTransformer,
    ) -> None:
        self._sc_client = sc_client
        self._transformer = transformer

    async def fuse(self, request: FusionRequest) -> FusionResponse:
        """Fuse multiple concepts into one cohesive scene.

        1. Generate LPD prompt for each concept independently.
        2. Compute embeddings and pairwise coherence.
        3. Weighted blend into unified latent.
        4. Compose spatial scene directive.
        5. Generate unified prompt.
        """
        # --- Phase 1: Generate each concept independently ---
        concept_results: list[ConceptResult] = []
        embeddings: list[list[float]] = []
        prompts: list[str] = []

        for i, concept in enumerate(request.concepts):
            bridge_req = BridgeRequest(
                prompt=concept.prompt,
                style=request.style,
                generation_params=request.generation_params,
            )
            sc_response = await self._sc_client.generate(bridge_req)
            optimized = sc_response.get("text", concept.prompt)

            concept_results.append(ConceptResult(
                concept_index=i,
                concept_prompt=concept.prompt,
                optimized_text=optimized,
                weight=concept.weight,
                role=concept.role,
            ))

            emb = _text_to_embedding(optimized)
            embeddings.append(emb)
            prompts.append(optimized)

        # --- Phase 2: Blend embeddings ---
        blend_coherence = self._compute_blend_coherence(embeddings)
        scene_composition = self._compose_scene(request)

        # --- Phase 3: Build unified prompt ---
        unified_text = self._build_unified_prompt(
            concept_results=concept_results,
            unifying_theme=request.unifying_theme,
            scene_composition=scene_composition,
        )

        # Generate through bridge for the unified prompt
        unified_req = BridgeRequest(
            prompt=unified_text,
            style=request.style,
            generation_params=request.generation_params,
        )
        sc_response = await self._sc_client.generate(unified_req)
        lpd_prompt = self._transformer.transform(unified_req, sc_response)

        import hashlib

        gen_id = hashlib.sha256(unified_text.encode()).hexdigest()[:16]

        unified_bridge = BridgeResponse(
            generation_id=sc_response.get("generation_id", f"fusion-{gen_id}"),
            original_prompt=unified_text,
            optimized_text=sc_response.get("text", unified_text),
            lpd_prompt=lpd_prompt,
            lpd_text=lpd_prompt.to_lpd_text(),
            metadata={
                "sc_metadata": sc_response.get("metadata", {}),
                "cached": sc_response.get("cached", False),
            },
        )

        return FusionResponse(
            generation_id=f"fusion-{gen_id}",
            unified_prompt=unified_bridge,
            concept_results=concept_results,
            blend_coherence=round(blend_coherence, 4),
            scene_composition=scene_composition,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_blend_coherence(embeddings: list[list[float]]) -> float:
        """Average pairwise cosine similarity across all concept embeddings."""
        if len(embeddings) < 2:
            return 1.0
        similarities: list[float] = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                dist = _cosine_distance(embeddings[i], embeddings[j])
                similarities.append(1.0 - dist)
        return sum(similarities) / len(similarities)

    @staticmethod
    def _compose_scene(request: FusionRequest) -> str:
        """Build a spatial scene composition directive from concept roles."""
        foreground_items: list[str] = []
        background_items: list[str] = []
        ambient_items: list[str] = []

        for c in request.concepts:
            desc = f"{c.prompt} (weight: {c.weight:.1f})"
            if c.role == "foreground":
                foreground_items.append(desc)
            elif c.role == "background":
                background_items.append(desc)
            else:
                ambient_items.append(desc)

        parts: list[str] = []
        if foreground_items:
            parts.append(f"Foreground: {', '.join(foreground_items)}")
        if background_items:
            parts.append(f"Background: {', '.join(background_items)}")
        if ambient_items:
            parts.append(f"Ambient atmosphere: {', '.join(ambient_items)}")
        if request.unifying_theme:
            parts.append(f"Unifying theme: {request.unifying_theme}")

        return ". ".join(parts) + "."

    @staticmethod
    def _build_unified_prompt(
        concept_results: list[ConceptResult],
        unifying_theme: str,
        scene_composition: str,
    ) -> str:
        """Assemble a unified scene prompt from concept results."""
        parts: list[str] = []

        # Sort by role: foreground first, then background, then ambient
        role_order = {"foreground": 0, "background": 1, "ambient": 2}
        sorted_concepts = sorted(concept_results, key=lambda c: role_order.get(c.role, 9))

        for c in sorted_concepts:
            if c.role == "foreground":
                parts.append(f"In the foreground: {c.optimized_text}")
            elif c.role == "background":
                parts.append(f"In the background: {c.optimized_text}")
            else:
                parts.append(f"Atmospheric quality: {c.optimized_text}")

        if unifying_theme:
            parts.append(f"Unified by: {unifying_theme}")

        parts.append(f"Scene composition: {scene_composition}")

        return ". ".join(parts) + "."
