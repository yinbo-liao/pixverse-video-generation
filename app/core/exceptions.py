"""Custom exception hierarchy for PixVerse Bridge.

All bridge exceptions extend PixVerseBridgeError so the FastAPI exception
handler in main.py catches them uniformly and returns structured JSON errors.
"""

from __future__ import annotations


class PixVerseBridgeError(Exception):
    """Base exception for all PixVerse Bridge errors."""

    status_code: int = 500
    detail: str

    def __init__(self, detail: str = "Internal bridge error") -> None:
        self.detail = detail
        super().__init__(detail)


class SemanticCanvasError(PixVerseBridgeError):
    """Upstream Semantic-Canvas service returned an error or is unreachable."""

    status_code: int = 502


class SemanticCanvasConnectionError(SemanticCanvasError):
    """Cannot connect to Semantic-Canvas at all (DNS, refused connection)."""

    def __init__(self, detail: str = "Cannot connect to Semantic-Canvas service") -> None:
        super().__init__(detail)


class SemanticCanvasTimeoutError(SemanticCanvasError):
    """Semantic-Canvas request timed out."""

    status_code: int = 504

    def __init__(self, detail: str = "Semantic-Canvas request timed out") -> None:
        super().__init__(detail)


class SemanticCanvasResponseError(SemanticCanvasError):
    """Semantic-Canvas returned a non-2xx response or an invalid body."""

    def __init__(
        self, status: int = 502, detail: str = "Semantic-Canvas returned an error response"
    ) -> None:
        super().__init__(detail)
        self.upstream_status = status


class PromptTransformationError(PixVerseBridgeError):
    """Failed to transform a Semantic-Canvas response into a valid LPD prompt."""

    def __init__(self, detail: str = "Failed to transform prompt into LPD format") -> None:
        super().__init__(detail)
