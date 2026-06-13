"""xAI (Grok) image generation provider."""

import requests
from openai import OpenAI

from ..models import ImagePrompt
from .base import BaseImageProvider, GenerationResult, ProviderCapabilities

# Capability surface for xAI. xAI takes only an aspect ratio (no size param),
# so `sizes` is empty and there's no validator/bucketer/aspect-map — the size
# methods are all no-ops: validate_size accepts anything, native_size returns
# None, aspect_to_size returns None, max_dim returns None.
XAI_CAPABILITIES = ProviderCapabilities(
    sizes=[],  # xAI uses aspect ratios, not sizes
    aspect_ratios=["20:9", "16:9", "4:3", "3:2", "1:1"],
    quality_levels=None,  # xAI doesn't support quality parameter
    default_size=None,
    default_aspect_ratio="16:9",
)


class XAIProvider(BaseImageProvider):
    """Image generation provider using xAI's Grok API.

    Uses the OpenAI SDK with a custom base URL to interact with xAI's API.
    """

    ENV_KEYS = ["XAI_API_KEY"]
    BASE_URL = "https://api.x.ai/v1"

    # xAI does not support 3:4 and 9:16 aspect ratios
    UNSUPPORTED_ASPECT_RATIOS = ["3:4", "9:16"]

    def __init__(self, api_key: str | None = None):
        """Initialize the xAI provider.

        Args:
            api_key: xAI API key. If not provided, reads from
                     XAI_API_KEY environment variable.
        """
        super().__init__(api_key)
        self._client: OpenAI | None = None

    @property
    def name(self) -> str:
        return "xai"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return XAI_CAPABILITIES

    def _get_client(self) -> OpenAI:
        """Get or create the xAI client (using OpenAI SDK)."""
        if self._client is None:
            api_key = self._get_api_key(self.ENV_KEYS)
            self._client = OpenAI(api_key=api_key, base_url=self.BASE_URL)
        return self._client

    def validate_params(
        self,
        model: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
        quality: str | None = None,
    ) -> None:
        """Validate parameters with specific check for unsupported aspect ratios.

        Raises:
            ValueError: If aspect ratio is not supported by xAI.
        """
        if aspect_ratio in self.UNSUPPORTED_ASPECT_RATIOS:
            raise ValueError(
                f"Aspect ratio '{aspect_ratio}' is not supported by xAI. "
                f"Supported ratios: {self.capabilities.aspect_ratios}"
            )

        # Call parent validation for other checks
        super().validate_params(model=model, size=size, aspect_ratio=aspect_ratio, quality=quality)

    def generate(
        self,
        prompt: ImagePrompt,
        model: str | None = None,
        size: str | None = None,
        aspect_ratio: str | None = None,
        quality: str | None = None,
        output_format: str | None = None,
        output_compression: int | None = None,
    ) -> GenerationResult:
        """Generate an image using xAI API.

        Args:
            prompt: The ImagePrompt containing the full prompt.
            model: xAI model to use.
            size: Not used by xAI (uses aspect_ratio instead).
            aspect_ratio: Aspect ratio (20:9, 16:9, 4:3, 3:2, 1:1).
            quality: Not supported by xAI, will raise error if provided.
            output_format: Not supported by xAI, ignored.
            output_compression: Not supported by xAI, ignored.

        Returns:
            GenerationResult with the generated image.

        Raises:
            ValueError: If aspect_ratio is 3:4 or 9:16 (unsupported by xAI).
        """
        del output_format, output_compression  # Unsupported by xAI.
        # Apply defaults
        caps = self.capabilities
        aspect_ratio = aspect_ratio or caps.default_aspect_ratio

        # Validate parameters (raises if no model was specified, or for
        # unsupported aspect ratios)
        self.validate_params(model=model, aspect_ratio=aspect_ratio, quality=quality)
        assert model is not None  # narrowed: validate_params raises when None

        # Generate the image
        client = self._get_client()

        # xAI returns URLs, not base64 data
        response = client.images.generate(
            model=model,
            prompt=prompt.full_prompt,
            n=1,
            response_format="url",
            # Pass aspect ratio via extra_body since it's not a standard param
            extra_body={"aspect_ratio": aspect_ratio},
        )

        # Download the image from the URL
        if not response.data:
            raise RuntimeError("xAI returned no image data")
        image_url = response.data[0].url
        if not image_url:
            raise RuntimeError("xAI returned no image URL")
        image_response = requests.get(image_url, timeout=60)
        image_response.raise_for_status()

        # Determine mime type from response headers or default to PNG
        content_type = image_response.headers.get("content-type", "image/png")
        if ";" in content_type:
            content_type = content_type.split(";")[0].strip()

        return GenerationResult(
            image_data=image_response.content,
            mime_type=content_type,
            provider=self.name,
            model=model,
            metadata={
                "aspect_ratio": aspect_ratio,
                "image_url": image_url,
            },
        )
