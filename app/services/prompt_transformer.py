"""Prompt transformation engine — maps Semantic-Canvas output to PixVerse LPD format.

This is the core Phase 1 service. It decomposes a Semantic-Canvas optimized
response into the six PixVerse V6 LPD (Literal Physical Description) components.

Field Mapping Summary
---------------------
| LPD Component  | Input Source            | Rule                                  |
|----------------|-------------------------|---------------------------------------|
| Subject        | constraints.must_include| Join items → phrase; fallback to      |
|                |                         | first sentence of optimized text      |
| ActionMotion   | style.enthusiasm        | 6-tier lookup: slow → explosive       |
| Environment    | sketch_notes            | Up to ~200 chars; first sentence      |
| Lighting       | constraints.tone        | 25-key tone→lighting dictionary;      |
|                |                         | fallback to sketch keyword scan       |
| CameraLens     | style.formality         | 5-tier lookup: handheld → cinematic   |
| Audio          | prompt (original)       | Keyword scan for sound/music/voice;   |
|                |                         | generic ambient fallback              |

All mappings are deterministic — identical inputs always produce identical
outputs (no random.choice). This is essential for caching and reproducibility.
"""

from __future__ import annotations

from app.core.exceptions import PromptTransformationError
from app.schemas.bridge import BridgeRequest
from app.schemas.prompt import (
    ActionMotion,
    Audio,
    CameraLens,
    Environment,
    Lighting,
    PixVersePrompt,
    Subject,
)


class PromptTransformer:
    """Transforms Semantic-Canvas output + BridgeRequest into PixVerse LPD components."""

    # ------------------------------------------------------------------
    # Motion intensity descriptor tiers (keyed on style.enthusiasm)
    # ------------------------------------------------------------------
    _MOTION_TIERS: list[tuple[float, float, list[str]]] = [
        (0.00, 0.15, ["slow motion", "gentle drift", "barely perceptible movement"]),
        (0.15, 0.35, ["slow deliberate movement", "steady", "subtle motion"]),
        (0.35, 0.50, ["relaxed pace", "smooth flowing motion", "natural movement"]),
        (0.50, 0.65, ["steady pace", "fluid", "purposeful movement"]),
        (0.65, 0.85, ["brisk", "dynamic", "energetic movement"]),
        (0.85, 1.01, ["rapid", "intense", "explosive dynamic movement"]),
    ]

    # ------------------------------------------------------------------
    # Camera formality descriptor tiers (keyed on style.formality)
    # ------------------------------------------------------------------
    _CAMERA_TIERS: list[tuple[float, float, list[str]]] = [
        (0.00, 0.15, ["handheld camera", "casual verite style", "natural shake"]),
        (0.15, 0.35, ["semi-handheld", "documentary style", "slight movement"]),
        (0.35, 0.65, ["stable tripod", "smooth pan", "standard framing"]),
        (0.65, 0.85, ["steadicam glide", "professional tracking", "controlled movement"]),
        (
            0.85,
            1.01,
            ["cinematic dolly", "crane shot, precision framing", "professional lens work"],
        ),
    ]

    # ------------------------------------------------------------------
    # Tone → Lighting descriptor dictionary (25 keys)
    # ------------------------------------------------------------------
    _TONE_LIGHTING_MAP: dict[str, str] = {
        "warm": "warm golden light, soft amber tones",
        "cozy": "warm intimate light, soft amber glow",
        "cold": "cool blue light, crisp cold shadows",
        "cool": "cool blue light, crisp shadows",
        "dark": "low-key lighting, deep shadows, chiaroscuro",
        "noir": "high-contrast noir lighting, dramatic shadows",
        "bright": "bright even lighting, high-key illumination",
        "dramatic": "dramatic contrast lighting, theatrical spot",
        "soft": "soft diffused light, gentle fill",
        "natural": "natural daylight, realistic ambient light",
        "moody": "moody atmospheric light, haze and fog",
        "neon": "vibrant neon lighting, colored gels, cyberpunk aesthetic",
        "golden": "golden hour sunlight, warm directional light",
        "sunset": "golden hour sunlight, warm directional glow",
        "harsh": "harsh overhead light, stark defined shadows",
        "romantic": "soft candlelight, warm intimate glow",
        "clinical": "neutral white light, clean even illumination",
        "overcast": "diffuse overcast light, soft shadowless illumination",
        "magical": "ethereal glowing light, sparkling highlights",
        "sunlight": "bright natural sunlight, sharp directional rays",
        "moonlight": "cool silver moonlight, soft lunar illumination",
        "dusk": "twilight blue light, fading ambient glow",
        "dawn": "early morning golden light, soft rising illumination",
        "fluorescent": "cool fluorescent light, flat even illumination",
        "firelight": "flickering warm firelight, dancing orange glow",
    }

    # Light-related keywords for sketch_notes fallback scan
    _LIGHT_KEYWORDS: list[str] = [
        "light", "lit ", "shadow", "glow", "illuminat", "dark", "bright",
        "sun", "moon", "beam", "ray", "lamp", "neon", "candle",
    ]

    # Audio-related keywords for prompt scanning
    _AUDIO_KEYWORDS: list[str] = [
        "sound", "music", "voice", "noise", "audio", "ambience", "ambient",
        "quiet", "loud", "song", "rhythm", "beat", "echo", "silence",
        "melody", "tone", "whisper", "shout", "roar", "crash", "footstep",
        "wind", "rain", "thunder", "engine", "siren", "dialogue", "speech",
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transform(self, request: BridgeRequest, sc_response: dict) -> PixVersePrompt:
        """Orchestrate the full transformation from BridgeRequest + SC response → LPD prompt.

        Args:
            request: The original bridge request with all user-specified parameters.
            sc_response: The raw JSON response dict from Semantic-Canvas /v1/generate.

        Returns:
            A fully populated PixVersePrompt with all six LPD components.

        Raises:
            PromptTransformationError: If the SC response is missing required fields.
        """
        optimized_text = sc_response.get("text", "")
        if not optimized_text:
            raise PromptTransformationError(
                "Semantic-Canvas response contains no optimized text"
            )

        return PixVersePrompt(
            subject=self._build_subject(request.constraints.must_include, optimized_text),
            action_motion=self._build_motion(request.style.enthusiasm),
            environment=self._build_environment(request.sketch_notes),
            lighting=self._build_lighting(request.constraints.tone, request.sketch_notes),
            camera_lens=self._build_camera(request.style.formality),
            audio=self._build_audio(
                request.prompt, request.sketch_notes or "", request.constraints.tone
            ),
        )

    def build_lpd_text(self, prompt: PixVersePrompt) -> str:
        """Render a PixVersePrompt to the final LPD string."""
        return prompt.to_lpd_text()

    # ------------------------------------------------------------------
    # Private builder methods — one per LPD component
    # ------------------------------------------------------------------

    def _build_subject(self, must_include: list[str], optimized_text: str) -> Subject:
        """Build the Subject component from constraints or optimized text."""
        if must_include:
            description = self._join_subject_items(must_include)
        else:
            description = self._first_sentence(optimized_text)
        return Subject(description=description, reference_image_count=0)

    def _build_motion(self, enthusiasm: float) -> ActionMotion:
        """Build the ActionMotion component from the enthusiasm style slider."""
        descriptor = self._pick_from_tiers(enthusiasm, self._MOTION_TIERS)
        return ActionMotion(description=descriptor, motion_strength=enthusiasm)

    def _build_environment(self, sketch_notes: str | None) -> Environment:
        """Build the Environment component from sketch_notes."""
        if not sketch_notes:
            return Environment()
        text = sketch_notes.strip()
        if len(text) <= 200:
            return Environment(description=text)
        # Truncate at sentence boundary within first 200 chars
        truncated = text[:200]
        last_period = truncated.rfind(".")
        if last_period > 50:
            truncated = truncated[: last_period + 1]
        return Environment(description=truncated)

    def _build_lighting(self, tone: str | None, sketch_notes: str | None) -> Lighting:
        """Build the Lighting component from tone mapping or sketch context."""
        # 1. Try exact tone lookup
        if tone:
            matched = self._map_tone_to_lighting(tone)
            if matched:
                return Lighting(description=matched)

        # 2. Try keyword scan in sketch_notes
        if sketch_notes:
            extracted = self._extract_lighting_from_sketch(sketch_notes)
            if extracted:
                return Lighting(description=extracted)

        # 3. Neutral fallback
        return Lighting(description="natural ambient light")

    def _build_camera(self, formality: float) -> CameraLens:
        """Build the CameraLens component from the formality style slider."""
        descriptor = self._pick_from_tiers(formality, self._CAMERA_TIERS)
        return CameraLens(description=descriptor, formality=formality)

    def _build_audio(
        self, prompt: str, sketch_notes: str, tone: str | None
    ) -> Audio:
        """Build the Audio component by scanning the prompt for sound cues."""
        # 1. Scan original prompt for audio keywords
        audio_sentence = self._extract_audio_cues(prompt)
        if audio_sentence:
            return Audio(description=audio_sentence)

        # 2. Scan sketch_notes for ambience hints
        if sketch_notes:
            combined = f"{prompt} {sketch_notes}"
            audio_sentence = self._extract_audio_cues(combined)
            if audio_sentence:
                return Audio(description=audio_sentence)

        # 3. Generic ambient fallback based on tone
        if tone:
            tone_lower = tone.lower()
            if any(t in tone_lower for t in ("noir", "dark", "moody")):
                return Audio(description="subtle ambient atmosphere, low drones")
            if any(t in tone_lower for t in ("bright", "warm", "golden", "romantic")):
                return Audio(description="gentle ambient music, warm tones")
            if any(t in tone_lower for t in ("dramatic", "action", "intense")):
                return Audio(description="dramatic background score, impactful sound design")
            if any(t in tone_lower for t in ("neon", "cyberpunk")):
                return Audio(description="electronic ambient music, subtle synth drones")

        return Audio(description="gentle ambient atmosphere matching the scene")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_from_tiers(value: float, tiers: list) -> str:
        """Select a deterministic descriptor from a tiered list.

        Each tier is (low, high, descriptors[...]). The middle descriptor of
        the matching tier is always chosen (deterministic, no randomness).
        The last tier's upper bound is slightly above 1.0 to be inclusive.
        """
        for low, high, descriptors in tiers:
            if low <= value < high:
                return descriptors[len(descriptors) // 2]
        # Fallback: last descriptor of last tier
        return tiers[-1][2][-1]

    @staticmethod
    def _join_subject_items(items: list[str]) -> str:
        """Join a list of subject keywords into a natural descriptive phrase."""
        if len(items) == 1:
            return items[0]
        return ", ".join(items[:-1]) + f", and {items[-1]}"

    @staticmethod
    def _first_sentence(text: str) -> str:
        """Extract the first sentence from a text block."""
        text = text.strip()
        for end_char in (".", "!", "?"):
            idx = text.find(end_char)
            if idx > 0:
                return text[: idx + 1]
        return text

    def _map_tone_to_lighting(self, tone: str | None) -> str:
        """Look up a tone descriptor in the lighting dictionary.

        Uses case-insensitive substring matching: checks if the dictionary key
        is a substring of the tone string, or vice versa.
        """
        if not tone:
            return ""
        tone_lower = tone.lower().strip()
        # Exact match first
        if tone_lower in self._TONE_LIGHTING_MAP:
            return self._TONE_LIGHTING_MAP[tone_lower]
        # Substring match: key in tone or tone in key
        for key, descriptor in self._TONE_LIGHTING_MAP.items():
            if key in tone_lower or tone_lower in key:
                return descriptor
        return ""

    def _extract_lighting_from_sketch(self, sketch_notes: str) -> str:
        """Scan sketch_notes for lighting-related sentences."""
        text_lower = sketch_notes.lower()
        for keyword in self._LIGHT_KEYWORDS:
            idx = text_lower.find(keyword)
            if idx >= 0:
                # Find the sentence containing this keyword
                sentence_start = text_lower.rfind(".", 0, idx)
                sentence_start = sentence_start + 1 if sentence_start >= 0 else 0
                sentence_end = text_lower.find(".", idx)
                if sentence_end < 0:
                    sentence_end = len(text_lower)
                extracted = sketch_notes[sentence_start:sentence_end].strip().strip(".")
                if len(extracted) > 10:
                    return extracted
        return ""

    def _extract_audio_cues(self, text: str) -> str:
        """Scan text for audio-related sentences."""
        text_lower = text.lower()
        for keyword in self._AUDIO_KEYWORDS:
            idx = text_lower.find(keyword)
            if idx >= 0:
                sentence_start = text_lower.rfind(".", 0, idx)
                sentence_start = sentence_start + 1 if sentence_start >= 0 else 0
                sentence_end = text_lower.find(".", idx)
                if sentence_end < 0:
                    sentence_end = len(text_lower)
                extracted = text[sentence_start:sentence_end].strip().strip(".")
                if len(extracted) > 5:
                    return extracted
        return ""
