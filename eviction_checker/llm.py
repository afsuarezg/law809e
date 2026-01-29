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

    def __init__(self, temperature: float = 0.0, max_tokens: int = 4000):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.ollama_client = None
        self.ollama_model = None
        self.openai_client = None
        self.anthropic_client = None

        # Priority 1: Ollama (local inference)
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
                logger.info(f"Ollama client initialized: {ollama_model} at {ollama_url}")
            except Exception as e:
                logger.warning(f"Failed to initialize Ollama: {e}")

        # Priority 2: OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=openai_key)
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")

        # Priority 3: Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key)
                logger.info("Anthropic client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic: {e}")

        if not self.ollama_client and not self.openai_client and not self.anthropic_client:
            raise ValueError(
                "No LLM configured. Set OLLAMA_MODEL for local inference, "
                "or OPENAI_API_KEY / ANTHROPIC_API_KEY for cloud APIs."
            )

    def complete(self, prompt: str, system_message: Optional[str] = None) -> str:
        """Get text completion from LLM."""
        # Try providers in priority order
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

    def _complete_anthropic(self, prompt: str, system_message: Optional[str]) -> str:
        """Get completion from Anthropic."""
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
        kwargs = {
            "model": model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_message:
            kwargs["system"] = system_message

        response = self.anthropic_client.messages.create(**kwargs)
        return response.content[0].text

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
