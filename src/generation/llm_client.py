"""LLM Client - Unified interface for multiple LLM providers."""


class LLMClient:
    """Unified LLM client supporting Anthropic, OpenAI, and Gemini."""

    PROVIDER_API_KEY_ENV = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }

    def __init__(self, provider: str = "anthropic", model: str = "claude-sonnet-4-6"):
        self.provider = provider
        self.model = model
        self.client = None

    def setup(self, api_key: str) -> None:
        """Initialize the LLM client for the configured provider."""
        if self.provider == "anthropic":
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key)
        elif self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        elif self.provider == "gemini":
            from google import genai
            self.client = genai.Client(api_key=api_key)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> str:
        """Generate a response from the LLM."""
        if self.provider == "anthropic":
            return self._generate_anthropic(prompt, system_prompt, max_tokens, temperature)
        elif self.provider == "openai":
            return self._generate_openai(prompt, system_prompt, max_tokens, temperature)
        elif self.provider == "gemini":
            return self._generate_gemini(prompt, system_prompt, max_tokens, temperature)
        raise ValueError(f"Unsupported provider: {self.provider}")

    def _generate_anthropic(
        self, prompt: str, system_prompt: str, max_tokens: int, temperature: float,
    ) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _generate_openai(
        self, prompt: str, system_prompt: str, max_tokens: int, temperature: float,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content

    def _generate_gemini(
        self, prompt: str, system_prompt: str, max_tokens: int, temperature: float,
    ) -> str:
        from google.genai import types

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return response.text
