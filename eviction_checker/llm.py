"""
LLM client for entity extraction.

Supports:
- Ollama (local, recommended for privacy)
- OpenAI
- Anthropic
"""

import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client supporting Ollama, OpenAI, and Anthropic."""

    def __init__(self, temperature: float = 0.0, max_tokens: int = 4000, preferred_provider: Optional[str] = None):
        """
        Initialize LLM client.
        
        Args:
            temperature: Temperature for generation (default: 0.0)
            max_tokens: Maximum tokens in response (default: 4000)
            preferred_provider: Optional provider to use ("ollama", "openai", "anthropic").
                               If None, uses priority order: Ollama > OpenAI > Anthropic
        """
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.ollama_client = None
        self.ollama_model = None
        self.openai_client = None
        self.anthropic_client = None
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

        if not self.ollama_client and not self.openai_client and not self.anthropic_client:
            raise ValueError(
                "No LLM configured. Set OLLAMA_MODEL for local inference, "
                "or OPENAI_API_KEY / ANTHROPIC_API_KEY for cloud APIs."
            )
        
        # Validate preferred provider if specified
        if self.preferred_provider:
            if self.preferred_provider == "ollama" and not self.ollama_client:
                raise ValueError(f"Preferred provider 'ollama' not available. Available: {providers_initialized}")
            elif self.preferred_provider == "openai" and not self.openai_client:
                raise ValueError(f"Preferred provider 'openai' not available. Available: {providers_initialized}")
            elif self.preferred_provider == "anthropic" and not self.anthropic_client:
                raise ValueError(f"Preferred provider 'anthropic' not available. Available: {providers_initialized}")
            elif self.preferred_provider not in ["ollama", "openai", "anthropic"]:
                raise ValueError(f"Unknown provider '{self.preferred_provider}'. Must be one of: ollama, openai, anthropic")

    def complete(self, prompt: str, system_message: Optional[str] = None) -> str:
        """Get text completion from LLM."""
        # Use preferred provider if specified, otherwise use priority order
        if self.preferred_provider:
            if self.preferred_provider == "ollama" and self.ollama_client:
                return self._complete_ollama(prompt, system_message)
            elif self.preferred_provider == "openai" and self.openai_client:
                return self._complete_openai(prompt, system_message)
            elif self.preferred_provider == "anthropic" and self.anthropic_client:
                return self._complete_anthropic(prompt, system_message)
            else:
                raise ValueError(f"Preferred provider '{self.preferred_provider}' not available")
        
        # Default priority order
        if self.ollama_client:
            return self._complete_ollama(prompt, system_message)
        elif self.openai_client:
            return self._complete_openai(prompt, system_message)
        elif self.anthropic_client:
            return self._complete_anthropic(prompt, system_message)
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
        # Try common model names in order of preference
        default_models = [
            "claude-3-sonnet-20240229",  # Most widely available
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
            "claude-3-5-haiku-20241022"
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
                logger.error("  - claude-3-sonnet-20240229")
                logger.error("  - claude-3-opus-20240229")
                logger.error("  - claude-3-haiku-20240307")
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
                    logger.error("  - claude-3-sonnet-20240229")
                    logger.error("  - claude-3-opus-20240229")
                    logger.error("  - claude-3-haiku-20240307")
            raise

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
        if self.ollama_client:
            return f"ollama ({self.ollama_model})"
        elif self.openai_client:
            return "openai"
        elif self.anthropic_client:
            return "anthropic"
        return "none"
