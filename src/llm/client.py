"""
LLM client wrapper supporting OpenAI and Anthropic APIs.

Provides unified interface for both providers with fallback support.
"""

import json
import logging
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel

import config

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client with support for OpenAI and Anthropic."""

    def __init__(
        self,
        prefer_provider: str = "openai",
        temperature: float = 0.1,
        max_tokens: int = 4000
    ):
        """
        Initialize LLM client.

        Args:
            prefer_provider: Preferred provider ("openai" or "anthropic")
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response
        """
        self.prefer_provider = prefer_provider
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Initialize clients
        self.openai_client = None
        self.anthropic_client = None

        if config.OPENAI_API_KEY:
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
                logger.info("OpenAI client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")

        if config.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self.anthropic_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
                logger.info("Anthropic client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic client: {e}")

        if not self.openai_client and not self.anthropic_client:
            raise ValueError(
                "No LLM API keys configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env"
            )

    def complete(
        self,
        prompt: str,
        system_message: Optional[str] = None
    ) -> str:
        """
        Get text completion from LLM.

        Args:
            prompt: User prompt
            system_message: Optional system message

        Returns:
            LLM response text
        """
        # Try preferred provider first
        if self.prefer_provider == "openai" and self.openai_client:
            try:
                return self._complete_openai(prompt, system_message)
            except Exception as e:
                logger.warning(f"OpenAI request failed: {e}")
                # Fall back to Anthropic
                if self.anthropic_client:
                    logger.info("Falling back to Anthropic")
                    return self._complete_anthropic(prompt, system_message)
                raise

        elif self.prefer_provider == "anthropic" and self.anthropic_client:
            try:
                return self._complete_anthropic(prompt, system_message)
            except Exception as e:
                logger.warning(f"Anthropic request failed: {e}")
                # Fall back to OpenAI
                if self.openai_client:
                    logger.info("Falling back to OpenAI")
                    return self._complete_openai(prompt, system_message)
                raise

        else:
            # Use whichever is available
            if self.openai_client:
                return self._complete_openai(prompt, system_message)
            elif self.anthropic_client:
                return self._complete_anthropic(prompt, system_message)
            else:
                raise ValueError("No LLM client available")

    def complete_json(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        response_model: Optional[Type[BaseModel]] = None
    ) -> Dict[str, Any]:
        """
        Get JSON completion from LLM.

        Args:
            prompt: User prompt
            system_message: Optional system message
            response_model: Optional Pydantic model for validation

        Returns:
            Parsed JSON response
        """
        # Enhance prompt to request JSON
        json_prompt = f"{prompt}\n\nRespond with valid JSON only, no additional text."

        if response_model:
            # Add schema to prompt
            schema = response_model.model_json_schema()
            json_prompt += f"\n\nUse this JSON schema:\n{json.dumps(schema, indent=2)}"

        response_text = self.complete(json_prompt, system_message)

        # Extract JSON from response
        json_data = self._extract_json(response_text)

        # Validate with Pydantic if model provided
        if response_model:
            try:
                validated = response_model.model_validate(json_data)
                return validated.model_dump()
            except Exception as e:
                logger.error(f"JSON validation failed: {e}")
                logger.debug(f"Raw JSON: {json_data}")
                raise

        return json_data

    def _complete_openai(
        self,
        prompt: str,
        system_message: Optional[str]
    ) -> str:
        """Get completion from OpenAI."""
        messages = []

        if system_message:
            messages.append({"role": "system", "content": system_message})

        messages.append({"role": "user", "content": prompt})

        response = self.openai_client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        return response.choices[0].message.content

    def _complete_anthropic(
        self,
        prompt: str,
        system_message: Optional[str]
    ) -> str:
        """Get completion from Anthropic."""
        kwargs = {
            "model": config.ANTHROPIC_MODEL,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}]
        }

        if system_message:
            kwargs["system"] = system_message

        response = self.anthropic_client.messages.create(**kwargs)

        return response.content[0].text

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Extract JSON from LLM response.

        Handles cases where LLM wraps JSON in markdown or adds text.
        """
        # Try to find JSON in markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            json_text = text[start:end].strip()
        else:
            json_text = text.strip()

        # Try to parse
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.debug(f"JSON text: {json_text[:500]}...")
            raise
