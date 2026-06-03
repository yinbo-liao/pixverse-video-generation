"""PixVerse V6 Feedback Loop — artifact analysis and iterative prompt refinement.

Implements the 3-Generation Rule:
  1. Generates 3 motion-strength variations (baseline, +10%, -10%).
  2. Analyzes each for 6 artifact types using deterministic text heuristics.
  3. Iteratively refines flagged prompts by applying targeted text fixes.
  4. Selects the best variation by artifact cleanliness, temporal stability,
     and semantic coherence with the original intent.

All analysis is text-based (no actual PixVerse API calls needed).
"""

from __future__ import annotations

import logging
import re

from app.schemas.bridge import (
    BridgeRequest,
    BridgeResponse,
)
from app.schemas.feedback_loop import (
    ArtifactFinding,
    ArtifactReport,
    ArtifactType,
    FeedbackRequest,
    FeedbackResponse,
    VariationResult,
    VariationType,
)
from app.services.prompt_transformer import PromptTransformer
from app.services.semantic_canvas_client import (
    MockSemanticCanvasClient,
    SemanticCanvasClient,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword sets for artifact detection
# ---------------------------------------------------------------------------

_HIGH_MOTION_WORDS = {
    "rapid", "intense", "explosive", "fast", "quick", "violent",
    "chaotic", "frenetic", "frantic", "breakneck", "furious",
}
_FAST_ACTION_WORDS = {
    "running", "sprinting", "chasing", "racing", "dashing", "burst",
    "lunging", "hurtling", "plunging", "darting", "bolting",
}
_CLOSEUP_WORDS = {"close-up", "closeup", "macro", "extreme close"}
_HAND_WORDS = {"hand", "hands", "finger", "fingers", "grasping", "grip", "gripping"}
_SEQUENCE_WORDS = {"shot", "sequence", "multiple", "cut to", "scene", "transition"}
_CHAOS_WORDS = {"crowd", "chaos", "chaotic", "busy", "complex", "cluttered", "many", "swarm"}
_FOCUS_WORDS = {"center-lock", "shallow depth of field", "isolated", "foreground", "focus pull"}
_FLICKER_WORDS = {
    "strobe", "flicker", "flickering", "flashing", "blinking", "pulsing",
    "rapid light", "lightning", "sparkling", "glittering",
}
_LIGHTING_CONFLICT_PAIRS: list[tuple[str, str]] = [
    ("warm", "cold"), ("bright", "dark"), ("sunlight", "moonlight"),
    ("harsh", "soft"), ("daylight", "night"), ("natural", "neon"),
    ("golden", "cool"), ("warm", "cool"), ("dim", "bright"),
    ("shadow", "bright"), ("overcast", "sunlight"),
]

# ---------------------------------------------------------------------------
# Fix application helpers
# ---------------------------------------------------------------------------

_FAST_TO_SLOW: dict[str, str] = {
    "running": "walking slowly",
    "sprinting": "moving deliberately",
    "chasing": "following calmly",
    "racing": "cruising",
    "dashing": "gliding",
    "burst": "emerging steadily",
    "lunging": "stepping",
    "hurtling": "drifting",
    "plunging": "descending",
    "darting": "moving",
    "bolting": "striding",
}


def _extract_keywords(text: str) -> set[str]:
    """Extract lowercase alphabetic keywords for coherence comparison."""
    words = re.findall(r"[a-z]{3,}", text.lower())
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "are", "was",
        "has", "its", "not", "but", "all", "can", "had", "her", "his", "our",
        "out", "she", "some", "than", "them", "then", "were", "will", "when",
        "who", "how", "into", "more", "also",
    }
    return {w for w in words if w not in stop}


# ---------------------------------------------------------------------------
# FeedbackLoop service
# ---------------------------------------------------------------------------


class FeedbackLoop:
    """Orchestrates the PixVerse V6 Feedback Loop pipeline."""

    _MOTION_DELTA: float = 0.10

    def __init__(
        self,
        sc_client: SemanticCanvasClient | MockSemanticCanvasClient,
        transformer: PromptTransformer,
    ) -> None:
        self._sc_client = sc_client
        self._transformer = transformer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, request: FeedbackRequest) -> FeedbackResponse:
        """Execute the full feedback loop pipeline.

        1. Generate 3 motion-strength variations.
        2. For each variation: generate prompt → analyze artifacts → refine.
        3. Select the best variation.
        """
        base_style = request.style
        base_enthusiasm = base_style.enthusiasm

        # Generate the 3 variations
        variation_configs: list[tuple[VariationType, float]] = [
            ("baseline", base_enthusiasm),
            ("high_motion", min(1.0, base_enthusiasm + self._MOTION_DELTA)),
            ("low_motion", max(0.0, base_enthusiasm - self._MOTION_DELTA)),
        ]

        total_iterations = 0
        variation_results: list[VariationResult] = []

        for var_type, enthusiasm in variation_configs:
            var_style = base_style.model_copy(update={"enthusiasm": enthusiasm})
            bridge_req = BridgeRequest(
                prompt=request.prompt,
                sketch_notes=request.sketch_notes,
                constraints=request.constraints,
                style=var_style,
                generation_params=request.generation_params,
            )

            result = await self._refine_variation(
                request, bridge_req, var_type
            )
            total_iterations += result.refinement_iterations
            variation_results.append(result)

        # Select best variation
        original_keywords = _extract_keywords(request.prompt)
        selected, reason = self._select_best(variation_results, original_keywords)

        import hashlib

        gen_id = hashlib.sha256(request.prompt.encode()).hexdigest()[:16]

        return FeedbackResponse(
            generation_id=f"fb-{gen_id}",
            original_prompt=request.prompt,
            variations=variation_results,
            selected_variation=selected,
            selection_reason=reason,
            total_iterations=total_iterations,
        )

    # ------------------------------------------------------------------
    # Variation generation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_variation_request(
        request: FeedbackRequest, enthusiasm: float
    ) -> BridgeRequest:
        """Build a BridgeRequest with the given motion strength."""
        style = request.style.model_copy(update={"enthusiasm": enthusiasm})
        return BridgeRequest(
            prompt=request.prompt,
            sketch_notes=request.sketch_notes,
            constraints=request.constraints,
            style=style,
            generation_params=request.generation_params,
        )

    # ------------------------------------------------------------------
    # Artifact analysis (orchestrator)
    # ------------------------------------------------------------------

    def _analyze_artifacts(self, text: str) -> ArtifactReport:
        """Run all 6 detectors and aggregate findings."""
        detectors = [
            self._detect_motion_smearing,
            self._detect_hand_distortion,
            self._detect_facial_drift,
            self._detect_lighting_inconsistency,
            self._detect_subject_blending,
            self._detect_temporal_flicker,
        ]
        findings = []
        for detector in detectors:
            result = detector(text)
            if result is not None:
                findings.append(result)
        return ArtifactReport(findings=findings)

    # ------------------------------------------------------------------
    # 6 artifact detectors
    # ------------------------------------------------------------------

    def _detect_motion_smearing(self, text: str) -> ArtifactFinding | None:
        """High motion words + fast action verbs → motion smearing risk."""
        text_lower = text.lower()
        motion_hits = [w for w in _HIGH_MOTION_WORDS if w in text_lower]
        action_hits = [w for w in _FAST_ACTION_WORDS if w in text_lower]
        if not motion_hits and not action_hits:
            return None
        severity = 0.8 if motion_hits and action_hits else 0.4
        return ArtifactFinding(
            type=ArtifactType.motion_smearing,
            severity=severity,
            location=", ".join(motion_hits + action_hits),
            suggested_fix=(
                "reduce motion intensity, add 'slow motion' qualifier, "
                "replace fast action words with deliberate movement"
            ),
        )

    def _detect_hand_distortion(self, text: str) -> ArtifactFinding | None:
        """Close-up framing + hand/finger keywords → hand distortion risk."""
        text_lower = text.lower()
        has_closeup = any(w in text_lower for w in _CLOSEUP_WORDS)
        has_hands = any(w in text_lower for w in _HAND_WORDS)
        if not has_closeup or not has_hands:
            return None
        return ArtifactFinding(
            type=ArtifactType.hand_distortion,
            severity=0.85,
            location="close-up framing with hand/finger detail",
            suggested_fix=(
                "switch to medium shot framing, avoid close-up of hands and fingers"
            ),
        )

    def _detect_facial_drift(self, text: str) -> ArtifactFinding | None:
        """Sequence language without strong subject anchoring → drift risk."""
        text_lower = text.lower()
        has_sequence = any(w in text_lower for w in _SEQUENCE_WORDS)
        if not has_sequence:
            return None
        # Check for repeated descriptors (proxy for anchor consistency)
        words = re.findall(r"[a-z]{4,}", text_lower)
        if not words:
            return None
        unique = set(words)
        if len(unique) < 2:
            return None
        # Count occurrences efficiently with a single pass
        from collections import Counter
        counts = Counter(words)
        repeated = {w for w, c in counts.items() if c >= 2}
        # Flag when fewer than 15% of unique words repeat — weak anchoring
        repeat_ratio = len(repeated) / len(unique)
        if repeat_ratio < 0.15:
            return ArtifactFinding(
                type=ArtifactType.facial_drift,
                severity=0.7,
                location="multi-shot language without repeated subject descriptors",
                suggested_fix=(
                    "add repeated physical subject descriptors across shots, "
                    "increase reference image anchoring"
                ),
            )
        return None

    def _detect_lighting_inconsistency(self, text: str) -> ArtifactFinding | None:
        """Conflicting lighting/tone keywords → inconsistency risk."""
        text_lower = text.lower()
        conflicts = []
        for a, b in _LIGHTING_CONFLICT_PAIRS:
            if a in text_lower and b in text_lower:
                conflicts.append(f"{a}/{b}")
        if not conflicts:
            return None
        severity = min(1.0, len(conflicts) * 0.25)
        return ArtifactFinding(
            type=ArtifactType.lighting_inconsistency,
            severity=severity,
            location=", ".join(conflicts),
            suggested_fix=(
                "unify lighting language, use consistent tone descriptors "
                "across the entire prompt"
            ),
        )

    def _detect_subject_blending(self, text: str) -> ArtifactFinding | None:
        """Chaos/crowd words without focus markers → subject blending risk."""
        text_lower = text.lower()
        has_chaos = any(w in text_lower for w in _CHAOS_WORDS)
        has_focus = any(w in text_lower for w in _FOCUS_WORDS)
        if has_chaos and not has_focus:
            return ArtifactFinding(
                type=ArtifactType.subject_blending,
                severity=0.8,
                location="high-complexity scene without focus markers",
                suggested_fix=(
                    "add 'center-lock focus' and 'shallow depth of field' "
                    "to isolate the subject from background"
                ),
            )
        return None

    def _detect_temporal_flicker(self, text: str) -> ArtifactFinding | None:
        """Flicker/strobe/flash keywords → temporal instability risk.

        Uses word-boundary matching so "flickering" matches only "flickering"
        (not also "flicker" as a substring).
        """
        text_lower = text.lower()
        hits = []
        for word in _FLICKER_WORDS:
            if re.search(rf"\b{re.escape(word)}\b", text_lower):
                hits.append(word)
        if not hits:
            return None
        if len(hits) >= 3:
            severity = 0.9
        elif len(hits) == 2:
            severity = 0.7
        else:
            severity = 0.4
        return ArtifactFinding(
            type=ArtifactType.temporal_flicker,
            severity=severity,
            location=", ".join(hits),
            suggested_fix=(
                "stabilize environment lighting, remove rapid light transitions, "
                "use steady illumination instead"
            ),
        )

    # ------------------------------------------------------------------
    # Fix application
    # ------------------------------------------------------------------

    def _apply_fixes(self, text: str, findings: list[ArtifactFinding]) -> str:
        """Apply all suggested fixes to the prompt text."""
        modified = text
        for finding in findings:
            modified = self._apply_single_fix(modified, finding)
        return modified

    def _apply_single_fix(self, text: str, finding: ArtifactFinding) -> str:
        """Dispatch to the appropriate fix method based on artifact type."""
        dispatcher = {
            ArtifactType.motion_smearing: self._fix_motion_smearing,
            ArtifactType.hand_distortion: self._fix_hand_distortion,
            ArtifactType.facial_drift: self._fix_facial_drift,
            ArtifactType.lighting_inconsistency: self._fix_lighting_inconsistency,
            ArtifactType.subject_blending: self._fix_subject_blending,
            ArtifactType.temporal_flicker: self._fix_temporal_flicker,
        }
        fixer = dispatcher.get(finding.type)
        if fixer:
            return fixer(text)
        return text

    @staticmethod
    def _fix_motion_smearing(text: str) -> str:
        """Reduce motion intensity: replace fast verbs, add slow motion qualifier."""
        modified = text
        for fast, slow in _FAST_TO_SLOW.items():
            pattern = re.compile(rf"\b{fast}\b", re.IGNORECASE)
            if pattern.search(modified):
                modified = pattern.sub(slow, modified)
        if "slow motion" not in modified.lower():
            modified = modified.rstrip(".") + ". slow motion, deliberate movement."
        return modified

    @staticmethod
    def _fix_hand_distortion(text: str) -> str:
        """Switch close-up to medium shot for hand-related content."""
        modified = text
        for word in _CLOSEUP_WORDS:
            pattern = re.compile(rf"\b{word}\b", re.IGNORECASE)
            modified = pattern.sub("medium shot", modified)
        # Remove hand-specific detail
        for word in _HAND_WORDS:
            pattern = re.compile(rf"\b{word}\b", re.IGNORECASE)
            if pattern.search(modified):
                modified = pattern.sub("gesture", modified)
        return modified

    @staticmethod
    def _fix_facial_drift(text: str) -> str:
        """Add repeated subject anchoring to prevent facial drift."""
        # Extract likely subject phrases (capitalized or descriptive)
        subject_candidates = re.findall(r"[A-Z][a-z]+(?:\s+[a-z]+){1,4}", text)
        if subject_candidates:
            anchor = subject_candidates[0]
            return f"{text} The {anchor.lower()} remains consistent in appearance throughout."
        return f"{text} Maintain consistent character appearance across all shots."

    @staticmethod
    def _fix_lighting_inconsistency(text: str) -> str:
        """Resolve conflicting lighting by keeping the first tone."""
        text_lower = text.lower()
        # Find all mentioned tones
        found_tones = []
        for a, b in _LIGHTING_CONFLICT_PAIRS:
            if a in text_lower and b in text_lower:
                # Keep first-occurring, remove second
                a_pos = text_lower.find(a)
                b_pos = text_lower.find(b)
                if a_pos < b_pos:
                    found_tones.append((b, a))
                else:
                    found_tones.append((a, b))
        modified = text
        for remove_tone, _keep_tone in found_tones:
            pattern = re.compile(rf"\b{remove_tone}\b", re.IGNORECASE)
            modified = pattern.sub("", modified)
        # Clean up extra spaces
        modified = re.sub(r"\s{2,}", " ", modified).strip()
        if not modified.endswith("."):
            modified += "."
        return modified

    @staticmethod
    def _fix_subject_blending(text: str) -> str:
        """Add focus markers to isolate subject from busy background."""
        if "center-lock focus" not in text.lower():
            text = (
                text.rstrip(".")
                + ". center-lock focus, shallow depth of field isolates the subject."
            )
        return text

    @staticmethod
    def _fix_temporal_flicker(text: str) -> str:
        """Replace flicker keywords with stable lighting terms."""
        replacements = {
            "strobe": "steady", "flicker": "stable", "flickering": "stable",
            "flashing": "constant", "blinking": "steady", "pulsing": "even",
            "sparkling": "smooth", "glittering": "smooth",
        }
        modified = text
        for flicker_word, stable_word in replacements.items():
            pattern = re.compile(rf"\b{flicker_word}\b", re.IGNORECASE)
            modified = pattern.sub(stable_word, modified)
        if "steady illumination" not in modified.lower():
            modified = modified.rstrip(".") + ". steady, consistent illumination throughout."
        return modified

    # ------------------------------------------------------------------
    # Refinement loop
    # ------------------------------------------------------------------

    async def _refine_variation(
        self,
        request: FeedbackRequest,
        bridge_req: BridgeRequest,
        variation_type: VariationType,
    ) -> VariationResult:
        """Generate, analyze, and iteratively refine a single variation."""
        iterations = 0
        history: list[ArtifactReport] = []
        current_text = ""

        # Initial generation
        sc_response = await self._sc_client.generate(bridge_req)
        lpd_prompt = self._transformer.transform(bridge_req, sc_response)
        current_text = lpd_prompt.to_lpd_text()

        # Analyze and refine loop
        report = self._analyze_artifacts(current_text)
        history.append(report)

        while not report.is_clean and iterations < request.max_iterations:
            if request.refinement_mode == "manual":
                break

            # Apply fixes to the LPD text
            current_text = self._apply_fixes(current_text, report.findings)

            # Re-generate through the bridge pipeline with the fixed text as prompt
            updated_req = BridgeRequest(
                prompt=current_text,
                sketch_notes=bridge_req.sketch_notes,
                constraints=bridge_req.constraints,
                style=bridge_req.style,
                generation_params=bridge_req.generation_params,
            )
            sc_response = await self._sc_client.generate(updated_req)
            lpd_prompt = self._transformer.transform(updated_req, sc_response)
            current_text = lpd_prompt.to_lpd_text()

            # Re-analyze
            iterations += 1
            report = self._analyze_artifacts(current_text)
            history.append(report)

        # Build the bridge response from the FINAL state (not re-generating from original)
        bridge_resp = BridgeResponse(
            generation_id=sc_response.get("generation_id", ""),
            original_prompt=bridge_req.prompt,
            optimized_text=sc_response.get("text", ""),
            lpd_prompt=lpd_prompt,
            lpd_text=current_text,
            metadata={
                "sc_metadata": sc_response.get("metadata", {}),
                "cached": sc_response.get("cached", False),
            },
        )

        return VariationResult(
            variation_type=variation_type,
            bridge_response=bridge_resp,
            artifact_report=report,
            refinement_iterations=iterations,
            final_prompt=current_text,
            refinement_history=history,
        )

    # ------------------------------------------------------------------
    # Best variation selection
    # ------------------------------------------------------------------

    def _select_best(
        self,
        variations: list[VariationResult],
        original_keywords: set[str],
    ) -> tuple[VariationResult, str]:
        """Rank variations and return the best with a justification."""
        scored = [(v, self._compute_score(v, original_keywords)) for v in variations]
        scored.sort(key=lambda x: x[1], reverse=True)
        best, score = scored[0]

        # Build justification
        risk = best.artifact_report.overall_risk_score
        temporal = self._temporal_severity(best)
        coherence = self._keyword_coherence(best.final_prompt, original_keywords)

        reasons = []
        if risk == 0:
            reasons.append("no artifacts detected")
        else:
            reasons.append(f"low artifact risk ({risk:.2f})")
        if temporal == 0:
            reasons.append("perfect temporal stability")
        else:
            reasons.append(f"strong temporal stability ({1.0 - temporal:.0%})")
        reasons.append(f"{coherence:.0%} keyword coherence with original intent")

        return best, f"Selected {best.variation_type}: {', '.join(reasons)}."

    def _compute_score(
        self, variation: VariationResult, original_keywords: set[str]
    ) -> float:
        """Composite score: 50% cleanliness + 30% temporal + 20% coherence."""
        cleanliness = 1.0 - variation.artifact_report.overall_risk_score
        temporal = 1.0 - self._temporal_severity(variation)
        coherence = self._keyword_coherence(variation.final_prompt, original_keywords)
        return cleanliness * 0.5 + temporal * 0.3 + coherence * 0.2

    @staticmethod
    def _temporal_severity(variation: VariationResult) -> float:
        """Max severity among temporal artifact types."""
        temporal_types = {ArtifactType.motion_smearing, ArtifactType.temporal_flicker}
        return max(
            (f.severity for f in variation.artifact_report.findings
             if f.type in temporal_types),
            default=0.0,
        )

    @staticmethod
    def _keyword_coherence(text: str, original_keywords: set[str]) -> float:
        """Jaccard similarity of keywords between text and original prompt."""
        text_keywords = _extract_keywords(text)
        if not original_keywords:
            return 1.0
        intersection = len(text_keywords & original_keywords)
        union = len(text_keywords | original_keywords)
        return intersection / union if union > 0 else 0.0
