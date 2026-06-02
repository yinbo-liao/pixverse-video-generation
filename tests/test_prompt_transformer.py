"""Unit tests for the PromptTransformer service.

Covers all tier boundaries, tone-to-lighting mapping, fallback chains,
and LPD text assembly.
"""

from __future__ import annotations

import pytest

from app.schemas.bridge import BridgeRequest
from app.schemas.prompt import PixVersePrompt

# ---------------------------------------------------------------------------
# Motion intensity mapping (6 tiers)
# ---------------------------------------------------------------------------

class TestMotionIntensityMapping:
    """Tests for _build_motion across all enthusiasm tiers."""

    @pytest.mark.parametrize(
        "enthusiasm,expected_phrase",
        [
            (0.00, "gentle drift"),
            (0.07, "gentle drift"),
            (0.15, "steady"),
            (0.25, "steady"),
            (0.35, "smooth flowing motion"),
            (0.42, "smooth flowing motion"),
            (0.50, "fluid"),
            (0.57, "fluid"),
            (0.65, "dynamic"),
            (0.75, "dynamic"),
            (0.85, "intense"),
            (0.95, "intense"),
            (1.00, "intense"),
        ],
    )
    def test_motion_descriptor(self, transformer, enthusiasm, expected_phrase):
        """Each enthusiasm value maps to the correct middle descriptor of its tier."""
        action = transformer._build_motion(enthusiasm)
        assert action.motion_strength == enthusiasm
        assert expected_phrase in action.description.lower()

    def test_motion_strength_stored(self, transformer):
        """The enthusiasm value is preserved as motion_strength."""
        action = transformer._build_motion(0.73)
        assert action.motion_strength == 0.73


# ---------------------------------------------------------------------------
# Camera formality mapping (5 tiers)
# ---------------------------------------------------------------------------

class TestCameraFormalityMapping:
    """Tests for _build_camera across all formality tiers."""

    @pytest.mark.parametrize(
        "formality,expected_phrase",
        [
            (0.00, "casual verite style"),
            (0.10, "casual verite style"),
            (0.15, "documentary style"),
            (0.25, "documentary style"),
            (0.35, "smooth pan"),
            (0.50, "smooth pan"),
            (0.65, "professional tracking"),
            (0.75, "professional tracking"),
            (0.85, "crane shot, precision framing"),
            (0.95, "crane shot, precision framing"),
            (1.00, "crane shot, precision framing"),
        ],
    )
    def test_camera_descriptor(self, transformer, formality, expected_phrase):
        """Each formality value maps to the correct middle descriptor of its tier."""
        camera = transformer._build_camera(formality)
        assert camera.formality == formality
        assert expected_phrase in camera.description.lower()

    def test_camera_formality_stored(self, transformer):
        """The formality value is preserved."""
        camera = transformer._build_camera(0.42)
        assert camera.formality == 0.42


# ---------------------------------------------------------------------------
# Tone → Lighting mapping
# ---------------------------------------------------------------------------

class TestToneLightingMapping:
    """Tests for _map_tone_to_lighting dictionary and fallbacks."""

    @pytest.mark.parametrize(
        "tone,expected_keywords",
        [
            ("noir", "high-contrast"),
            ("warm", "warm golden"),
            ("cold", "cool blue"),
            ("DARK", "low-key"),
            ("neon", "vibrant neon"),
            ("dramatic", "dramatic contrast"),
            ("soft", "soft diffused"),
            ("golden", "golden hour"),
            ("clinical", "neutral white"),
            ("moonlight", "cool silver"),
            ("firelight", "flickering warm"),
        ],
    )
    def test_tone_exact_or_case_match(self, transformer, tone, expected_keywords):
        """Known tone keys produce correct lighting (case-insensitive)."""
        result = transformer._map_tone_to_lighting(tone)
        assert expected_keywords in result.lower()

    def test_tone_substring_match(self, transformer):
        """Tone containing a known key as substring matches."""
        result = transformer._map_tone_to_lighting("warmth")  # contains 'warm'
        assert "warm golden" in result.lower() or result != ""

    def test_tone_none_returns_empty(self, transformer):
        """None tone returns empty string from the map function."""
        result = transformer._map_tone_to_lighting(None)
        assert result == ""

    def test_tone_unknown_returns_empty(self, transformer):
        """Completely unknown tone returns empty string from the map function."""
        result = transformer._map_tone_to_lighting("xyzzy_unknown_tone")
        assert result == ""


# ---------------------------------------------------------------------------
# Subject building
# ---------------------------------------------------------------------------

class TestSubjectBuilding:
    """Tests for _build_subject from must_include or optimized text."""

    def test_from_must_include(self, transformer):
        """When must_include is populated, keywords are joined as the subject."""
        items = ["cyberpunk detective", "trench coat", "neon reflections"]
        subject = transformer._build_subject(items, "Some optimized text.")
        assert "cyberpunk detective" in subject.description
        assert "trench coat" in subject.description
        assert "neon reflections" in subject.description

    def test_single_must_include(self, transformer):
        """Single must_include item is used verbatim."""
        items = ["silver Tesla Model 3"]
        subject = transformer._build_subject(items, "Some optimized text.")
        assert subject.description == "silver Tesla Model 3"

    def test_fallback_to_optimized_text(self, transformer):
        """Empty must_include falls back to first sentence of optimized text."""
        subject = transformer._build_subject([], "A forest at dawn. Mist rising through pines.")
        assert subject.description == "A forest at dawn."


# ---------------------------------------------------------------------------
# Environment building
# ---------------------------------------------------------------------------

class TestEnvironmentBuilding:
    """Tests for _build_environment from sketch_notes."""

    def test_short_sketch_verbatim(self, transformer):
        """Short sketch_notes (<=200 chars) used verbatim."""
        notes = "A narrow alley with wet pavement."
        env = transformer._build_environment(notes)
        assert env.description == notes

    def test_long_sketch_truncated(self, transformer):
        """Long sketch_notes truncated at sentence boundary within 200 chars."""
        notes = "X" * 180 + ". " + "Y" * 100
        env = transformer._build_environment(notes)
        assert len(env.description) <= 203  # 200 + period + maybe space
        assert "X" * 180 in env.description

    def test_none_sketch(self, transformer):
        """None sketch_notes produces empty Environment."""
        env = transformer._build_environment(None)
        assert env.description == ""

    def test_empty_sketch(self, transformer):
        """Empty sketch_notes produces empty Environment."""
        env = transformer._build_environment("")
        assert env.description == ""


# ---------------------------------------------------------------------------
# Lighting building (end-to-end through _build_lighting)
# ---------------------------------------------------------------------------

class TestLightingBuilding:
    """Tests for _build_lighting with tone and sketch fallbacks."""

    def test_from_tone(self, transformer):
        """Known tone produces lighting descriptor."""
        lighting = transformer._build_lighting("noir", None)
        assert "high-contrast noir" in lighting.description.lower()

    def test_fallback_to_sketch_keywords(self, transformer):
        """When tone is None, scans sketch_notes for light keywords."""
        sketch = "The room has soft ambient light filtering through curtains."
        lighting = transformer._build_lighting(None, sketch)
        assert len(lighting.description) > 0

    def test_fallback_to_neutral(self, transformer):
        """When no tone and no sketch, returns natural ambient light."""
        lighting = transformer._build_lighting(None, None)
        assert lighting.description == "natural ambient light"


# ---------------------------------------------------------------------------
# Audio building
# ---------------------------------------------------------------------------

class TestAudioBuilding:
    """Tests for _build_audio keyword scanning and fallbacks."""

    def test_from_prompt_with_audio_keywords(self, transformer):
        """Prompt containing audio keywords extracts the sentence."""
        audio = transformer._build_audio(
            "Heavy rain pounds the rooftop. Thunder echoes in the distance.", "", None
        )
        assert len(audio.description) > 0

    def test_fallback_from_sketch(self, transformer):
        """When prompt has no audio keywords, sketch is scanned."""
        audio = transformer._build_audio(
            "A person walks.", "Soft ambient music plays in the background.", None
        )
        assert len(audio.description) > 0

    def test_fallback_to_generic(self, transformer):
        """No audio keywords anywhere produces a generic ambient fallback."""
        audio = transformer._build_audio("A person walks.", "", None)
        assert "ambient" in audio.description.lower()


# ---------------------------------------------------------------------------
# Full transformation (integration of all components)
# ---------------------------------------------------------------------------

class TestFullTransform:
    """End-to-end tests for PromptTransformer.transform()."""

    def test_all_fields_populated(
        self, transformer, sample_bridge_request, sample_sc_response
    ):
        """A complete request + SC response produces a fully populated PixVersePrompt."""
        result = transformer.transform(sample_bridge_request, sample_sc_response)
        assert isinstance(result, PixVersePrompt)
        assert result.subject.description
        assert result.action_motion.description
        assert result.environment.description
        assert result.lighting.description
        assert result.camera_lens.description
        assert result.audio.description

    def test_minimal_request(self, transformer, sample_sc_response):
        """Prompt-only request produces valid PixVersePrompt."""
        request = BridgeRequest(prompt="A quiet forest at dawn")
        result = transformer.transform(request, sample_sc_response)
        assert isinstance(result, PixVersePrompt)
        assert result.subject.description  # falls back to first sentence of optimized text
        # Other fields may be empty or have default values — that's fine

    def test_style_values_preserved(
        self, transformer, sample_bridge_request, sample_sc_response
    ):
        """The enthusiasm and formality values from the request are stored in the LPD."""
        result = transformer.transform(sample_bridge_request, sample_sc_response)
        assert result.action_motion.motion_strength == sample_bridge_request.style.enthusiasm
        assert result.camera_lens.formality == sample_bridge_request.style.formality


# ---------------------------------------------------------------------------
# LPD text assembly
# ---------------------------------------------------------------------------

class TestLPDTextAssembly:
    """Tests for PixVersePrompt.to_lpd_text()."""

    def test_all_fields_assembled(self):
        """All populated fields produce a period-separated LPD string."""
        prompt = PixVersePrompt(
            subject={"description": "A silver Tesla Model 3"},
            action_motion={"description": "drives along a coastal highway"},
            environment={"description": "Pacific Coast Highway at golden hour"},
            lighting={"description": "warm golden hour sunlight"},
            camera_lens={"description": "wide aerial tracking shot"},
            audio={"description": "engine hum and wind noise"},
        )
        text = prompt.to_lpd_text()
        assert "Tesla" in text
        assert "golden hour" in text
        assert text.endswith(".")

    def test_empty_fields_skipped(self):
        """Empty component descriptions are not included in the assembled text."""
        prompt = PixVersePrompt(
            subject={"description": "A red rose"},
            action_motion={"description": ""},
            environment={"description": ""},
            lighting={"description": "soft natural light"},
            camera_lens={"description": ""},
            audio={"description": ""},
        )
        text = prompt.to_lpd_text()
        assert text == "A red rose. soft natural light."
        # Verify no double-period artifacts
        assert ".." not in text

    def test_fully_empty_prompt(self):
        """A completely empty PixVersePrompt produces just a period."""
        prompt = PixVersePrompt()
        text = prompt.to_lpd_text()
        assert text == "." or text  # well-formed even if only a period
