"""
Translation interface for LLM-based translation services.

Provides a stub interface for local LLM integration (OLLAMA, etc.).
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class TranslationRequest:
    """Request for translation of a text string."""

    text: str
    context: str = ""
    max_length: Optional[int] = None
    preserve_formatting: bool = True
    source_language: str = "en"
    target_language: str = "en"


@dataclass
class TranslationResponse:
    """Response from translation service."""

    original_text: str
    translated_text: str
    confidence: float
    warnings: List[str]
    metadata: Dict[str, Any]


class TranslatorStub:
    """Stub interface for LLM-based translation services."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize translator with configuration.

        Args:
            config: Translation configuration
        """
        self.config = config or {}
        self.base_url = self.config.get("base_url", "http://localhost:11434")
        self.model_name = self.config.get("model", "llama2")
        self.temperature = self.config.get("temperature", 0.3)
        self.source_language = self.config.get("source_language", "English")
        self.target_language = self.config.get("target_language", "Spanish")
        self.game_context = self.config.get("game_context", "")

    def translate_string(self, request: TranslationRequest) -> TranslationResponse:
        """Translate a single string.

        Args:
            request: Translation request

        Returns:
            Translation response
        """
        # For now, return a mock translation
        if self.config.get("mock_mode", True):
            return self._mock_translate(request)

        # Real LLM integration would go here
        try:
            return self._ollama_translate(request)
        except Exception as e:
            # Fallback to mock if real service fails
            return TranslationResponse(
                original_text=request.text,
                translated_text=f"[TRANSLATION ERROR: {e}]",
                confidence=0.0,
                warnings=[f"Translation service failed: {e}"],
                metadata={"error": str(e)},
            )

    def translate_batch(
        self, requests: List[TranslationRequest]
    ) -> List[TranslationResponse]:
        """Translate multiple strings as a batch.

        Args:
            requests: List of translation requests

        Returns:
            List of translation responses
        """
        responses = []

        for request in requests:
            response = self.translate_string(request)
            responses.append(response)

        return responses

    def _mock_translate(self, request: TranslationRequest) -> TranslationResponse:
        """Mock translation for testing purposes.

        Args:
            request: Translation request

        Returns:
            Mock translation response
        """
        text = request.text
        warnings = []

        # Mock translation logic
        if text.strip() == "":
            translated = text
        elif text.startswith("<") and text.endswith(">"):
            # Control codes - don't translate
            translated = text
        else:
            # Simple mock translation
            mock_translations = {
                "START": "INICIO",
                "GAME": "JUEGO",
                "PLAYER": "JUGADOR",
                "SCORE": "PUNTUACION",
                "TIME": "TIEMPO",
                "LEVEL": "NIVEL",
                "LIVES": "VIDAS",
                "CONTINUE": "CONTINUAR",
                "GAME OVER": "FIN DEL JUEGO",
                "HIGH SCORE": "RECORD",
                "PRESS START": "PRESIONA START",
                "SELECT": "SELECCIONAR",
            }

            translated = text.upper()
            for eng, esp in mock_translations.items():
                translated = translated.replace(eng, esp)

            # Preserve case pattern
            if text.islower():
                translated = translated.lower()
            elif text.isupper():
                translated = translated.upper()
            elif text.istitle():
                translated = translated.title()

        # Check length constraints
        if request.max_length and len(translated) > request.max_length:
            warnings.append(
                f"Translation exceeds max length "
                f"({len(translated)} > {request.max_length})"
            )

        return TranslationResponse(
            original_text=text,
            translated_text=translated,
            confidence=0.8,  # Mock confidence
            warnings=warnings,
            metadata={"method": "mock", "model": "mock_translator"},
        )

    def _ollama_translate(self, request: TranslationRequest) -> TranslationResponse:
        """Translate using OLLAMA local LLM service.

        Args:
            request: Translation request

        Returns:
            Translation response
        """
        # Build prompt for translation
        prompt = self._build_translation_prompt(request)

        # Make request to OLLAMA API
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "temperature": self.temperature,
            "stream": False,
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/generate", json=payload, timeout=30
            )
            response.raise_for_status()

            result = response.json()
            translated_text = result.get("response", "").strip()

            # Extract just the translation (remove any explanations)
            translated_text = self._extract_translation(translated_text)

            warnings = []
            confidence = 0.9  # Default confidence for successful LLM response

            # Validate translation
            if request.max_length and len(translated_text) > request.max_length:
                warnings.append(f"Translation exceeds length limit")
                confidence *= 0.7

            if request.preserve_formatting:
                if not self._check_formatting_preserved(request.text, translated_text):
                    warnings.append("Formatting codes may not be preserved")
                    confidence *= 0.8

            return TranslationResponse(
                original_text=request.text,
                translated_text=translated_text,
                confidence=confidence,
                warnings=warnings,
                metadata={
                    "method": "ollama",
                    "model": self.model_name,
                    "temperature": self.temperature,
                },
            )

        except requests.RequestException as e:
            raise Exception(f"OLLAMA API request failed: {e}")
        except Exception as e:
            raise Exception(f"Translation processing failed: {e}")

    def _build_translation_prompt(self, request: TranslationRequest) -> str:
        """Build prompt for LLM translation.

        Args:
            request: Translation request

        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            f"Translate the following text from {self.source_language} "
            f"to {self.target_language}.",
            "",
        ]

        if self.game_context:
            prompt_parts.extend(
                [f"Context: This text is from a video game: {self.game_context}", ""]
            )

        if request.context:
            prompt_parts.extend([f"Additional context: {request.context}", ""])

        constraints = []

        if request.preserve_formatting:
            constraints.append(
                "- Preserve any formatting codes in angle brackets "
                "(e.g., <NEWLINE>, <END>)"
            )

        if request.max_length:
            constraints.append(
                f"- Keep translation under {request.max_length} characters"
            )

        constraints.extend(
            [
                "- Maintain the tone and style appropriate for a video game",
                "- Only provide the translation, no explanations",
            ]
        )

        if constraints:
            prompt_parts.extend(["Constraints:", *constraints, ""])

        prompt_parts.extend([f"Text to translate: {request.text}", "", "Translation:"])

        return "\n".join(prompt_parts)

    def _extract_translation(self, llm_response: str) -> str:
        """Extract the actual translation from LLM response.

        Args:
            llm_response: Raw response from LLM

        Returns:
            Cleaned translation text
        """
        # Remove common prefixes/suffixes that LLMs might add
        response = llm_response.strip()

        # Remove quotes if the entire response is quoted
        if (response.startswith('"') and response.endswith('"')) or (
            response.startswith("'") and response.endswith("'")
        ):
            response = response[1:-1]

        # Remove explanation prefixes
        prefixes_to_remove = [
            "Translation:",
            "The translation is:",
            "Here is the translation:",
            "Translated text:",
        ]

        for prefix in prefixes_to_remove:
            if response.lower().startswith(prefix.lower()):
                response = response[len(prefix) :].strip()

        return response

    def _check_formatting_preserved(self, original: str, translated: str) -> bool:
        """Check if formatting codes are preserved in translation.

        Args:
            original: Original text
            translated: Translated text

        Returns:
            True if formatting appears preserved
        """
        # Count angle bracket pairs
        original_codes = original.count("<")
        translated_codes = translated.count("<")

        return original_codes == translated_codes

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages.

        Returns:
            List of language codes/names
        """
        # This would query the actual service in a real implementation
        return [
            "English",
            "Spanish",
            "French",
            "German",
            "Italian",
            "Portuguese",
            "Japanese",
            "Korean",
            "Chinese",
        ]

    def test_connection(self) -> bool:
        """Test connection to translation service.

        Returns:
            True if service is available
        """
        if self.config.get("mock_mode", True):
            return True

        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    def enhance_with_context(self, game_name: str) -> Dict[str, Any]:
        """Enhance translation context with game information.

        Args:
            game_name: Name of the game being translated

        Returns:
            Enhanced context information
        """
        # This would integrate with Wikipedia, game databases, etc.
        # For now, return basic context
        context = {
            "game_name": game_name,
            "genre": "unknown",
            "characters": [],
            "terms": {},
            "style_guide": (
                "Keep translations concise and appropriate for the game's era"
            ),
        }

        # Game-specific context could be loaded from a database
        game_contexts = {
            "tennis": {
                "genre": "sports",
                "terms": {"SERVE": "SAQUE", "MATCH": "PARTIDO", "SET": "SET"},
                "style_guide": "Use standard tennis terminology",
            },
            "zelda": {
                "genre": "adventure/rpg",
                "characters": ["Link", "Zelda", "Ganon"],
                "terms": {"SWORD": "ESPADA", "HEART": "CORAZON", "RUPEE": "RUPIA"},
                "style_guide": "Maintain fantasy adventure tone",
            },
        }

        game_key = game_name.lower()
        if game_key in game_contexts:
            context.update(game_contexts[game_key])

        return context
