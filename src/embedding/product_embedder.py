"""Product Embedder - Pluggable multi-provider text embeddings.

Delegates to a registered *embedding provider*. Supported out of the box:
OpenAI, Gemini. (Anthropic exposes no first-party embeddings endpoint, so it is
intentionally not registered here.)

Two reliability features are built into the facade:
  * token rotation - configure several API keys and, on a rate-limit error, the
    embedder switches to the next key before falling back to waiting.
  * rate-limit retry - when every key is throttled it sleeps for the delay the
    provider suggests, then retries, so a bulk ingest completes.

Adding a new provider is an open/closed change - subclass and register:

    @register_embedding_provider("myprovider")
    class MyEmbeddingProvider(BaseEmbeddingProvider):
        api_key_env = "MYPROVIDER_API_KEY"

        def setup(self, api_key: str) -> None:
            self.client = ...

        def embed_batch(self, texts, model, output_dim=None): ...
"""
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar

from src.utils.helpers import as_key_list, is_rate_limit_error, retry_delay_seconds


class BaseEmbeddingProvider(ABC):
    """Common interface every embedding provider must implement."""

    #: Environment variable that holds this provider's API key.
    api_key_env: ClassVar[str] = ""

    def __init__(self) -> None:
        self.client = None  # Initialized in setup()

    @abstractmethod
    def setup(self, api_key: str) -> None:
        """Initialize the underlying SDK client."""

    @abstractmethod
    def embed_batch(
        self, texts: list[str], model: str, output_dim: int | None = None
    ) -> list[list[float]]:
        """Return one embedding vector per input text.

        ``output_dim`` optionally requests a specific embedding size (providers
        that support it must truncate/project to that dimension).
        """


# --- Provider registry -----------------------------------------------------

_EMBEDDING_PROVIDERS: dict[str, type[BaseEmbeddingProvider]] = {}


def register_embedding_provider(
    name: str,
) -> Callable[[type[BaseEmbeddingProvider]], type[BaseEmbeddingProvider]]:
    """Class decorator: register an embedding provider under ``name``."""

    def wrapper(cls: type[BaseEmbeddingProvider]) -> type[BaseEmbeddingProvider]:
        _EMBEDDING_PROVIDERS[name] = cls
        return cls

    return wrapper


def available_embedding_providers() -> list[str]:
    """Return the sorted list of registered embedding provider names."""
    return sorted(_EMBEDDING_PROVIDERS)


# --- Concrete providers ----------------------------------------------------

@register_embedding_provider("openai")
class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI embeddings via the ``openai`` SDK."""

    api_key_env = "OPENAI_API_KEY"

    def setup(self, api_key: str) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)

    def embed_batch(
        self, texts: list[str], model: str, output_dim: int | None = None
    ) -> list[list[float]]:
        kwargs: dict = {"model": model, "input": texts}
        if output_dim:
            # Supported by text-embedding-3-* models.
            kwargs["dimensions"] = output_dim
        response = self.client.embeddings.create(**kwargs)
        return [d.embedding for d in response.data]


@register_embedding_provider("gemini")
class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Google Gemini embeddings via the ``google-genai`` SDK.

    Use model ``gemini-embedding-001`` (the current GA embedding model). It
    supports Matryoshka output sizes (e.g. 768 / 1536 / 3072) via
    ``output_dimensionality``.
    """

    api_key_env = "GEMINI_API_KEY"

    def setup(self, api_key: str) -> None:
        from google import genai

        self.client = genai.Client(api_key=api_key)

    def embed_batch(
        self, texts: list[str], model: str, output_dim: int | None = None
    ) -> list[list[float]]:
        config = None
        if output_dim:
            from google.genai import types

            config = types.EmbedContentConfig(output_dimensionality=output_dim)
        response = self.client.models.embed_content(
            model=model, contents=texts, config=config
        )
        return [list(e.values) for e in response.embeddings]


# --- Facade (public, backward-compatible API) ------------------------------

class ProductEmbedder:
    """Generate embeddings for product chunks via a registered provider."""

    # provider name -> API key env var. Built from the registry so it stays
    # in sync automatically when new providers are registered above.
    PROVIDER_API_KEY_ENV: ClassVar[dict[str, str]] = {
        name: cls.api_key_env for name, cls in _EMBEDDING_PROVIDERS.items()
    }

    def __init__(
        self,
        model_name: str = "text-embedding-3-small",
        provider: str = "openai",
        embedding_dim: int | None = None,
        max_retries: int = 6,
    ):
        if provider not in _EMBEDDING_PROVIDERS:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Available: {available_embedding_providers()}"
            )
        self.model_name = model_name
        self.provider = provider
        # Desired output dimension; passed through to providers that support it
        # so the vectors match the vector-store column size.
        self.embedding_dim = embedding_dim
        # How many times to wait-for-quota (after exhausting all keys) before
        # giving up on a batch.
        self.max_retries = max_retries
        self._impl: BaseEmbeddingProvider = _EMBEDDING_PROVIDERS[provider]()
        self._keys: list[str] = [""]
        self._key_idx: int = 0

    def setup(self, api_key: str | list[str]) -> None:
        """Initialize the embedding client.

        ``api_key`` may be a single key or a list of keys (or a comma/space
        separated string). Extra keys are used for rotation on rate limits.
        """
        self._keys = as_key_list(api_key)
        self._key_idx = 0
        self._impl.setup(self._keys[0])

    def embed_text(self, text: str) -> list[float]:
        """Generate an embedding for a single text."""
        return self._embed_with_retry([text])[0]

    def embed_batch(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        """Generate embeddings for a batch of texts (rotation + retry aware)."""
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            all_embeddings.extend(self._embed_with_retry(batch))
        return all_embeddings

    def _rotate_key(self) -> bool:
        """Switch the client to the next configured key. False if only one key."""
        if len(self._keys) <= 1:
            return False
        self._key_idx = (self._key_idx + 1) % len(self._keys)
        self._impl.setup(self._keys[self._key_idx])
        return True

    def _embed_with_retry(self, batch: list[str]) -> list[list[float]]:
        """Embed a batch, rotating keys then waiting on rate-limit / quota errors.

        On a rate-limit error it first tries the remaining keys; only when they
        are all throttled does it sleep for the provider-suggested delay and
        start another round (up to ``max_retries`` waits).
        """
        waits = 0
        rotations = 0
        while True:
            try:
                return self._impl.embed_batch(batch, self.model_name, self.embedding_dim)
            except Exception as exc:
                if not is_rate_limit_error(exc):
                    raise
                if rotations < len(self._keys) - 1 and self._rotate_key():
                    rotations += 1
                    continue
                if waits >= self.max_retries:
                    raise
                time.sleep(retry_delay_seconds(exc))
                waits += 1
                rotations = 0

    @property
    def client(self):
        """Expose the underlying SDK client (backward compatibility)."""
        return self._impl.client
