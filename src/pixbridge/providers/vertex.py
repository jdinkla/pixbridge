"""Vertex AI image generation provider.

Uses the same google-genai SDK as Gemini but authenticates via
Application Default Credentials instead of API keys.
"""

import os

from google import genai

from .gemini import GeminiProvider


class VertexProvider(GeminiProvider):
    """Image generation provider using Google's Vertex AI.

    Requires:
        - GOOGLE_CLOUD_PROJECT env var
        - GOOGLE_CLOUD_LOCATION env var (optional, defaults to global)
        - Application Default Credentials (gcloud auth application-default login)
    """

    ENV_KEYS: list[str] = []  # No API key needed — uses ADC

    def __init__(self, api_key: str | None = None):
        # Skip GeminiProvider.__init__ API-key lookup; call grandparent directly
        super(GeminiProvider, self).__init__(api_key=None)
        self._client: genai.Client | None = None
        self._project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not self._project:
            raise OSError(
                "GOOGLE_CLOUD_PROJECT environment variable is required for the vertex provider"
            )
        self._location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    @property
    def name(self) -> str:
        return "vertex"

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(
                vertexai=True,
                project=self._project,
                location=self._location,
            )
        return self._client
