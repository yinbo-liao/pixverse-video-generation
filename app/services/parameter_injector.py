"""Dynamic Parameter Injector — maps style vectors to PixVerse V6 parameters.

Translates Semantic-Canvas style vectors (formality, enthusiasm, technical_depth)
into precise PixVerse V6 generation parameters using the preset lookup tables
in pixverse_presets.py.
"""

from __future__ import annotations

from app.schemas.bridge import (
    BridgeRequest,
    BridgeResponse,
)
from app.schemas.parameter_injection import (
    CameraParams,
    LightingParams,
    MotionParams,
    ParameterInjectionRequest,
    ParameterInjectionResponse,
    PixVerseParams,
    RenderParams,
)
from app.services import pixverse_presets as presets
from app.services.prompt_transformer import PromptTransformer
from app.services.semantic_canvas_client import (
    MockSemanticCanvasClient,
    SemanticCanvasClient,
)


class ParameterInjector:
    """Injects style vectors into PixVerse V6 parameters using preset lookup tables.

    The 3 style vectors each control distinct PixVerse parameters:
      - enthusiasm      → motion strength and speed profile
      - formality       → camera type, lens mm, stabilization
      - technical_depth → lighting complexity and render quality
    """

    def __init__(
        self,
        sc_client: SemanticCanvasClient | MockSemanticCanvasClient,
        transformer: PromptTransformer,
    ) -> None:
        self._sc_client = sc_client
        self._transformer = transformer

    async def inject(self, request: ParameterInjectionRequest) -> ParameterInjectionResponse:
        """Generate LPD prompt and inject PixVerse parameters from style vectors.

        1. Generate the LPD prompt through the standard bridge pipeline.
        2. Map style vectors → PixVerse V6 parameters via preset tables.
        3. Return the prompt, parameters, and justifications.
        """
        # Generate the LPD prompt
        bridge_req = BridgeRequest(
            prompt=request.prompt,
            sketch_notes=request.sketch_notes,
            constraints=request.constraints,
            style=request.style,
            generation_params=request.generation_params,
        )
        sc_response = await self._sc_client.generate(bridge_req)
        lpd_prompt = self._transformer.transform(bridge_req, sc_response)

        bridge_resp = BridgeResponse(
            generation_id=sc_response.get("generation_id", ""),
            original_prompt=request.prompt,
            optimized_text=sc_response.get("text", ""),
            lpd_prompt=lpd_prompt,
            lpd_text=lpd_prompt.to_lpd_text(),
            metadata={
                "sc_metadata": sc_response.get("metadata", {}),
                "cached": sc_response.get("cached", False),
            },
        )

        # Inject parameters from style vectors
        style = request.style
        camera = self._inject_camera(style.formality)
        motion = self._inject_motion(style.enthusiasm)
        lighting = self._inject_lighting(style.technical_depth)
        render = self._inject_render(style.technical_depth)

        params = PixVerseParams(
            motion=motion,
            camera=camera,
            lighting=lighting,
            render=render,
            aspect_ratio=request.aspect_ratio,
            duration_seconds=request.target_duration,
        )

        # Build justifications
        justifications = {
            "motion": (
                f"enthusiasm={style.enthusiasm:.2f} → {motion.speed_label} "
                f"at {motion.strength_pct}% strength with {motion.acceleration} acceleration"
            ),
            "camera": (
                f"formality={style.formality:.2f} → {camera.camera_type}, "
                f"{camera.lens_mm}mm lens, {camera.stabilization}"
            ),
            "lighting": (
                f"technical_depth={style.technical_depth:.2f} → "
                f"{lighting.setup_name} ({lighting.complexity})"
            ),
            "render": (
                f"technical_depth={style.technical_depth:.2f} → "
                f"{render.tier} tier: {render.model}, {render.upscale}"
            ),
        }

        import hashlib

        gen_id = hashlib.sha256(request.prompt.encode()).hexdigest()[:16]

        return ParameterInjectionResponse(
            generation_id=f"pi-{gen_id}",
            bridge_response=bridge_resp,
            params=params,
            justifications=justifications,
        )

    # --- Private injectors ---

    @staticmethod
    def _inject_camera(formality: float) -> CameraParams:
        p = presets.get_camera_profile(formality)
        return CameraParams(
            camera_type=p.camera_type,
            lens_mm=p.lens_mm,
            stabilization=p.stabilization,
            movement=p.movement,
        )

    @staticmethod
    def _inject_motion(enthusiasm: float) -> MotionParams:
        p = presets.get_motion_profile(enthusiasm)
        return MotionParams(
            strength_pct=p.strength_pct,
            speed_label=p.speed_label,
            acceleration=p.acceleration,
        )

    @staticmethod
    def _inject_lighting(technical_depth: float) -> LightingParams:
        p = presets.get_lighting_setup(technical_depth)
        return LightingParams(
            setup_name=p.name,
            key_light=p.key_light,
            fill_light=p.fill_light,
            back_light=p.back_light,
            complexity=p.complexity,
        )

    @staticmethod
    def _inject_render(technical_depth: float) -> RenderParams:
        p = presets.get_render_quality(technical_depth)
        return RenderParams(
            tier=p.tier,
            model=p.model,
            upscale=p.upscale,
        )
