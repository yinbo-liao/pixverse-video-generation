"""Async HTTP client for the Semantic-Canvas API.

Wraps httpx.AsyncClient to call POST /v1/generate with proper error translation.
Connection failures, timeouts, and upstream errors are all translated into
the SemanticCanvasError hierarchy so callers get typed exceptions.

Also includes MockSemanticCanvasClient for offline development/testing.
When SEMANTIC_CANVAS_MOCK=true, the mock client returns realistic optimized
responses without requiring a running Semantic-Canvas instance.
"""

from __future__ import annotations

import hashlib
import math

import httpx

from app.config import Settings
from app.core.exceptions import (
    SemanticCanvasConnectionError,
    SemanticCanvasResponseError,
    SemanticCanvasTimeoutError,
)
from app.schemas.bridge import BridgeRequest


class SemanticCanvasClient:
    """Async HTTP client for Semantic-Canvas /v1/generate endpoint.

    Created per-request via FastAPI dependency injection. Each instance
    manages its own httpx.AsyncClient context.
    """

    def __init__(self, settings: Settings) -> None:
        self._base_url: str = settings.semantic_canvas_base_url.rstrip("/")
        self._api_key: str | None = settings.semantic_canvas_api_key
        self._timeout: float = float(settings.semantic_canvas_timeout)
        self._generate_url: str = f"{self._base_url}/v1/generate"

    async def generate(self, request: BridgeRequest) -> dict:
        """Send a BridgeRequest to Semantic-Canvas and return the raw response dict.

        Args:
            request: The bridge request with prompt, constraints, style, and gen params.

        Returns:
            The full JSON response from Semantic-Canvas /v1/generate.

        Raises:
            SemanticCanvasConnectionError: Cannot reach the service.
            SemanticCanvasTimeoutError: Request timed out.
            SemanticCanvasResponseError: Upstream returned a non-2xx status.
        """
        payload = self._build_payload(request)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._generate_url, json=payload, headers=headers)
        except httpx.ConnectError as exc:
            raise SemanticCanvasConnectionError(
                f"Cannot connect to Semantic-Canvas at {self._base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise SemanticCanvasTimeoutError(
                f"Semantic-Canvas request timed out after {self._timeout}s"
            ) from exc

        if response.status_code >= 400:
            detail = self._extract_error_detail(response)
            raise SemanticCanvasResponseError(
                status=response.status_code,
                detail=f"Semantic-Canvas returned {response.status_code}: {detail}",
            )

        return response.json()

    def _build_payload(self, request: BridgeRequest) -> dict:
        """Build the Semantic-Canvas GenerateRequest JSON payload from a BridgeRequest."""
        return {
            "prompt": request.prompt,
            "sketch_notes": request.sketch_notes,
            "constraints": {
                "tone": request.constraints.tone,
                "max_length": request.constraints.max_length,
                "must_include": request.constraints.must_include,
                "must_exclude": request.constraints.must_exclude,
                "brand_voice_id": request.constraints.brand_voice_id,
            },
            "style": {
                "formality": request.style.formality,
                "enthusiasm": request.style.enthusiasm,
                "technical_depth": request.style.technical_depth,
                "description": request.style.description,
            },
            "generation_params": {
                "num_steps": request.generation_params.num_steps,
                "temperature": request.generation_params.temperature,
                "seed": request.generation_params.seed,
            },
        }

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str:
        """Extract a human-readable error detail from an upstream error response."""
        try:
            body = response.json()
            return body.get("detail", body.get("message", response.text[:500]))
        except ValueError:
            return response.text[:500]

    async def encode(self, text: str) -> dict:
        """Encode text into a latent embedding vector via Semantic-Canvas.

        POST /v1/encode with {"text": text, "max_length": 512}.
        Returns the raw JSON response with an "embedding" key.
        """
        url = f"{self._base_url}/v1/encode"
        payload = {"text": text, "max_length": 512}
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return await self._post_json(url, payload, headers)

    async def diff(self, text_a: str, text_b: str) -> dict:
        """Compute semantic distance between two texts via Semantic-Canvas.

        POST /v1/diff with {"text_a": text_a, "text_b": text_b}.
        Returns the raw JSON response with a "distance" key in [0, 1].
        """
        url = f"{self._base_url}/v1/diff"
        payload = {"text_a": text_a, "text_b": text_b}
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return await self._post_json(url, payload, headers)

    async def _post_json(self, url: str, payload: dict, headers: dict) -> dict:
        """Shared POST helper with error translation for encode/diff."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.ConnectError as exc:
            raise SemanticCanvasConnectionError(
                f"Cannot connect to Semantic-Canvas at {self._base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise SemanticCanvasTimeoutError(
                f"Semantic-Canvas request timed out after {self._timeout}s"
            ) from exc

        if response.status_code >= 400:
            detail = self._extract_error_detail(response)
            raise SemanticCanvasResponseError(
                status=response.status_code,
                detail=f"Semantic-Canvas returned {response.status_code}: {detail}",
            )

        return response.json()


# ---------------------------------------------------------------------------
# Mock embedding helpers (module-level, deterministic)
# ---------------------------------------------------------------------------

_EMBEDDING_DIMS = 64


def _text_to_embedding(text: str) -> list[float]:
    """Deterministically map text to a 64-dim L2-normalized unit vector.

    Uses SHA-256: the 32 hash bytes are cyclically sampled to produce
    64 float values, each derived from 4-byte windows interpreted as
    signed int32 and scaled to [-1, 1]. The result is L2-normalized.

    Identical texts always produce identical vectors (distance = 0).
    """
    h = hashlib.sha256(text.encode()).digest()
    vec: list[float] = []
    for i in range(_EMBEDDING_DIMS):
        offset = i % len(h)
        window = bytes(h[(offset + j) % len(h)] for j in range(4))
        raw = int.from_bytes(window, "big", signed=True)
        vec.append(raw / (2**31))
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return [0.0] * _EMBEDDING_DIMS
    return [v / norm for v in vec]


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Cosine distance between two unit vectors, mapped to [0, 1].

    For unit vectors, dot product equals cosine similarity.
    Distance = (1 - similarity) / 2 maps similarity=[-1,1] to distance=[1,0].
    """
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    # Clamp to [0, 1] — floating point may push dot slightly above 1.0
    raw = (1.0 - dot) / 2.0
    return max(0.0, min(1.0, raw))


class MockSemanticCanvasClient:
    """Mock client that returns realistic optimized responses without an upstream service.

    Used when SEMANTIC_CANVAS_MOCK=true. Generates deterministic, well-structured
    responses based on the input prompt so the full bridge pipeline can be tested
    without any external dependency.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate(self, request: BridgeRequest) -> dict:
        """Generate a realistic mock SC response from the bridge request.

        The mock enriches the prompt with descriptive details based on the
        style sliders and sketch_notes, simulating what Semantic-Canvas
        would produce in fallback mode.
        """
        # Simulate processing delay (short for mock)
        await self._fake_latency()

        optimized = self._optimize(request)
        hash_id = hashlib.sha256(request.prompt.encode()).hexdigest()[:16]

        return {
            "type": "generation.completed",
            "generation_id": f"mock-{hash_id}",
            "status": "completed",
            "text": optimized,
            "latent_trajectory": [],
            "metadata": {
                "input_tokens": len(request.prompt.split()),
                "output_tokens": len(optimized.split()),
                "generation_time_ms": 12,
                "constraint_compliance": 0.99,
                "num_steps": request.generation_params.num_steps,
                "backend": "mock",
            },
            "cached": False,
        }

    async def _fake_latency(self) -> None:
        """Tiny artificial delay to simulate processing."""
        import asyncio

        await asyncio.sleep(0.01)

    def _optimize(self, request: BridgeRequest) -> str:
        """Build an enriched, optimized version of the prompt.

        Incorporates sketch_notes context and style-aware descriptors
        to produce a natural, polished narrative sentence.
        """
        prompt = request.prompt.strip()
        sketch = (request.sketch_notes or "").strip()
        tone = (request.constraints.tone or "").strip()
        must_include = request.constraints.must_include

        # Start with the core subject
        parts: list[str] = []

        # If must_include has items, weave them in as the subject anchor
        if must_include:
            subject = self._join_phrases(must_include)
            parts.append(f"{subject} is depicted in a scene where {prompt[0].lower()}{prompt[1:]}")
        else:
            parts.append(prompt)

        # Fold in sketch context
        if sketch:
            # Take the first 1-2 sentences for context injection
            sketch_sentences = sketch.replace("!", ".").replace("?", ".").split(".")
            context = ". ".join(s for s in sketch_sentences[:2] if len(s.strip()) > 5)
            if context and context not in prompt:
                parts.append(context.strip())

        # Style-aware enrichment
        if request.style.technical_depth > 0.6:
            parts.append("The scene is rendered with rich visual detail and nuanced composition")
        if request.style.formality > 0.7:
            parts.append("presented with cinematic precision and deliberate framing")
        if request.style.enthusiasm > 0.7:
            parts.append("capturing dynamic energy and fluid motion throughout")

        # Tone-specific flourish
        if tone:
            tone_map = {
                "noir": "Shadows pool in the corners as light cuts through the darkness",
                "warm": "Golden warmth suffuses every surface with amber radiance",
                "cold": "Cool blue tones pervade the atmosphere with crisp clarity",
                "dramatic": "Dramatic contrast heightens every visual element",
                "neon": "Vibrant neon colors bleed across reflective surfaces",
                "soft": "Gentle diffused light wraps the scene in calm serenity",
                "dark": "Deep shadows define the space, punctuated by isolated light",
                "moody": "Atmospheric haze lends a contemplative, brooding quality",
                "golden": "Golden hour light bathes everything in luminous warmth",
            }
            for key, flourish in tone_map.items():
                if key in tone.lower():
                    parts.append(flourish)
                    break

        return ". ".join(parts) + "."

    async def encode(self, text: str) -> dict:
        """Produce a deterministic mock embedding for the given text."""
        await self._fake_latency()
        embedding = _text_to_embedding(text)
        return {
            "text": text,
            "embedding": embedding,
            "dimensions": _EMBEDDING_DIMS,
            "backend": "mock",
        }

    async def diff(self, text_a: str, text_b: str) -> dict:
        """Compute deterministic mock semantic distance between two texts."""
        await self._fake_latency()
        emb_a = _text_to_embedding(text_a)
        emb_b = _text_to_embedding(text_b)
        distance = _cosine_distance(emb_a, emb_b)
        return {
            "text_a": text_a,
            "text_b": text_b,
            "distance": round(distance, 6),
            "backend": "mock",
        }

    @staticmethod
    def _join_phrases(phrases: list[str]) -> str:
        """Join key phrases into a natural descriptive string."""
        if len(phrases) == 1:
            return phrases[0]
        return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"
