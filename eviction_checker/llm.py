"""
LLM client for entity extraction.

Supports:
- Ollama (local, recommended for privacy)
- OpenAI
- Anthropic
- Google Gemini
"""

import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client supporting Ollama, OpenAI, and Anthropic."""

    KNOWN_PROVIDERS = ["ollama", "openai", "anthropic", "google"]

    def __init__(self, temperature: float = 0.0, max_tokens: int = 4000, preferred_provider: Optional[str] = None):
        """
        Initialize LLM client.

        Args:
            temperature: Temperature for generation (default: 0.0)
            max_tokens: Maximum tokens in response (default: 4000)
            preferred_provider: Optional provider to use ("ollama", "openai", "anthropic", "google").
                               If None, uses priority order: Ollama > OpenAI > Anthropic > Google
        """
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.ollama_client = None
        self.ollama_model = None
        self.openai_client = None
        self.anthropic_client = None
        self.google_client = None
        self.google_model = None
        self.preferred_provider = preferred_provider.lower() if preferred_provider else None

        # Initialize all available providers
        providers_initialized = []

        # Ollama (local inference)
        ollama_model = os.getenv("OLLAMA_MODEL")
        if ollama_model:
            ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
            try:
                import openai
                self.ollama_client = openai.OpenAI(
                    base_url=ollama_url,
                    api_key="ollama"  # Ollama doesn't require a real key
                )
                self.ollama_model = ollama_model
                providers_initialized.append("ollama")
                logger.info(f"Ollama client initialized: {ollama_model} at {ollama_url}")
            except Exception as e:
                logger.warning(f"Failed to initialize Ollama: {e}")

        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=openai_key)
                providers_initialized.append("openai")
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")

        # Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key)
                providers_initialized.append("anthropic")
                logger.info("Anthropic client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic: {e}")

        # Google Gemini
        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key:
            try:
                from google import genai
                self.google_client = genai.Client(api_key=google_key)
                self.google_model = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
                providers_initialized.append("google")
                logger.info(f"Google Gemini client initialized: {self.google_model}")
            except Exception as e:
                logger.warning(f"Failed to initialize Google Gemini: {e}")

        if not any([self.ollama_client, self.openai_client,
                    self.anthropic_client, self.google_client]):
            raise ValueError(
                "No LLM configured. Set OLLAMA_MODEL for local inference, "
                "or OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY for cloud APIs."
            )

        # Validate preferred provider if specified
        if self.preferred_provider:
            if self.preferred_provider not in self.KNOWN_PROVIDERS:
                raise ValueError(
                    f"Unknown provider '{self.preferred_provider}'. "
                    f"Must be one of: {', '.join(self.KNOWN_PROVIDERS)}"
                )
            client_map = {
                "ollama": self.ollama_client,
                "openai": self.openai_client,
                "anthropic": self.anthropic_client,
                "google": self.google_client,
            }
            if not client_map[self.preferred_provider]:
                raise ValueError(
                    f"Preferred provider '{self.preferred_provider}' not available. "
                    f"Available: {providers_initialized}"
                )

    def complete(self, prompt: str, system_message: Optional[str] = None) -> str:
        """Get text completion from LLM."""
        # Use preferred provider if specified, otherwise use priority order
        if self.preferred_provider:
            dispatch = {
                "ollama":    (self.ollama_client,    self._complete_ollama),
                "openai":    (self.openai_client,    self._complete_openai),
                "anthropic": (self.anthropic_client, self._complete_anthropic),
                "google":    (self.google_client,    self._complete_google),
            }
            client, fn = dispatch[self.preferred_provider]
            if not client:
                raise ValueError(f"Preferred provider '{self.preferred_provider}' not available")
            return fn(prompt, system_message)

        # Default priority order
        if self.ollama_client:
            return self._complete_ollama(prompt, system_message)
        elif self.openai_client:
            return self._complete_openai(prompt, system_message)
        elif self.anthropic_client:
            return self._complete_anthropic(prompt, system_message)
        elif self.google_client:
            return self._complete_google(prompt, system_message)
        raise ValueError("No LLM client available")

    def complete_json(self, prompt: str, system_message: Optional[str] = None) -> Dict[str, Any]:
        """Get JSON completion from LLM."""
        json_prompt = f"{prompt}\n\nRespond with valid JSON only, no markdown formatting."
        response = self.complete(json_prompt, system_message)
        return self._extract_json(response)

    def _complete_ollama(self, prompt: str, system_message: Optional[str]) -> str:
        """Get completion from local Ollama."""
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        response = self.ollama_client.chat.completions.create(
            model=self.ollama_model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        return response.choices[0].message.content

    def _complete_openai(self, prompt: str, system_message: Optional[str]) -> str:
        """Get completion from OpenAI."""
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
        response = self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        return response.choices[0].message.content

    def _list_anthropic_models(self) -> list:
        """List available Anthropic models."""
        try:
            # Anthropic SDK: client.models.list() returns a SyncPage[ModelInfo]
            models_page = self.anthropic_client.models.list()
            return [model.id for model in models_page]
        except Exception as e:
            logger.warning(f"Could not list Anthropic models: {e}")
            return []

    def _complete_anthropic(self, prompt: str, system_message: Optional[str]) -> str:
        """Get completion from Anthropic."""
        # Try common model names in order of preference (active as of 2026; see docs.anthropic.com model deprecations)
        default_models = [
            "claude-sonnet-4-6",
            "claude-sonnet-4-5-20250929",
            "claude-opus-4-6",
            "claude-haiku-4-5-20251001",
        ]
        
        model = os.getenv("ANTHROPIC_MODEL")
        if not model:
            # Try defaults until one works
            last_error = None
            for default_model in default_models:
                try:
                    model = default_model
                    kwargs = {
                        "model": model,
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature,
                        "messages": [{"role": "user", "content": prompt}]
                    }
                    if system_message:
                        kwargs["system"] = system_message
                    
                    response = self.anthropic_client.messages.create(**kwargs)
                    logger.info(f"Successfully using Anthropic model: {model}")
                    return response.content[0].text
                except Exception as e:
                    last_error = e
                    error_msg = str(e)
                    if "404" not in error_msg and "not_found" not in error_msg.lower():
                        # Not a model not found error, re-raise
                        raise
                    # Try next model
                    continue
            
            # All models failed, show available models
            available_models = self._list_anthropic_models()
            logger.error(f"None of the default Anthropic models worked. Last error: {last_error}")
            if available_models:
                logger.error(f"Available models: {', '.join(available_models[:5])}")
            else:
                logger.error("Could not retrieve available models. Check your API key and try:")
                logger.error("  - claude-sonnet-4-6")
                logger.error("  - claude-opus-4-6")
                logger.error("  - claude-haiku-4-5-20251001")
            raise last_error or ValueError("No Anthropic model available")
        
        # Use specified model
        kwargs = {
            "model": model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_message:
            kwargs["system"] = system_message

        try:
            response = self.anthropic_client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "not_found" in error_msg.lower():
                available_models = self._list_anthropic_models()
                logger.error(f"Anthropic model '{model}' not found.")
                if available_models:
                    logger.error(f"Available models: {', '.join(available_models[:5])}")
                else:
                    logger.error("Try setting ANTHROPIC_MODEL to one of:")
                    logger.error("  - claude-sonnet-4-6")
                    logger.error("  - claude-opus-4-6")
                    logger.error("  - claude-haiku-4-5-20251001")
            raise

    def _complete_google(self, prompt: str, system_message: Optional[str]) -> str:
        """Get completion from Google Gemini."""
        from google import genai
        from google.genai import types

        config_kwargs: Dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
        }
        if system_message:
            config_kwargs["system_instruction"] = system_message

        # If a specific model was set via GOOGLE_MODEL, use it directly.
        # Otherwise try a fallback list in order of preference.
        env_model = os.getenv("GOOGLE_MODEL")
        if env_model:
            models_to_try = [env_model]
        else:
            models_to_try = [
                self.google_model,   # configured default (gemini-2.5-flash)
                "gemini-2.5-pro",
                "gemini-2.0-flash-lite",
                "gemini-flash-latest",
            ]

        last_error = None
        for model in models_to_try:
            try:
                response = self.google_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                logger.info(f"Successfully using Google model: {model}")
                self.google_model = model  # cache for next call
                return response.text
            except Exception as e:
                last_error = e
                err = str(e)
                if "404" in err or "NOT_FOUND" in err or "no longer available" in err.lower():
                    logger.warning(f"Google model '{model}' unavailable, trying next...")
                    continue
                raise  # non-404 errors (auth, quota, etc.) bubble up immediately

        raise last_error or RuntimeError("No Google Gemini model available")

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from LLM response."""
        # Handle markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()

        return json.loads(text.strip())

    @property
    def provider(self) -> str:
        """Return the active provider name."""
        if self.preferred_provider:
            if self.preferred_provider == "google":
                return f"google ({self.google_model})"
            return self.preferred_provider
        if self.ollama_client:
            return f"ollama ({self.ollama_model})"
        elif self.openai_client:
            return "openai"
        elif self.anthropic_client:
            return "anthropic"
        elif self.google_client:
            return f"google ({self.google_model})"
        return "none"
