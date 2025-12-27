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
        self.model_name = self.config.get("model", "gpt-oss:20b")
        self.temperature = self.config.get("temperature", 0.3)
        self.source_language = self.config.get("source_language", "Japanese")
        self.target_language = self.config.get("target_language", "English")
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
            # Japanese to English mock translations (hiragana words)
            japanese_translations = {
                # Common game terms
                "ほ": ".",  # Often used as placeholder/dot in Zelda
                "へ": "'",  # Apostrophe alternative
                # Zelda-specific Japanese terms
                "たから": "treasure",
                "けん": "sword",
                "たて": "shield",
                "ゆみ": "bow",
                "や": "arrow",
                "ばくだん": "bomb",
                "かぎ": "key",
                "ちず": "map",
                "こころ": "heart",
                "いのち": "life",
                "ちから": "power",
                "まほう": "magic",
                "ゆびわ": "ring",
                "ろうそく": "candle",
                "ふえ": "recorder",
                "いかだ": "raft",
                "はしご": "ladder",
                "ブーメラン": "boomerang",
                "ルピー": "rupee",
                "トライフォース": "triforce",
                # Staff/credits
                "せいさく": "production",
                "おんがく": "music",
                "プログラム": "program",
                "デザイン": "design",
            }
            
            # Simple mock translation for English
            english_translations = {
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

            translated = text
            
            # Check if text contains Japanese characters
            has_japanese = any(
                '\u3040' <= c <= '\u309F' or  # Hiragana
                '\u30A0' <= c <= '\u30FF'     # Katakana
                for c in text
            )
            
            if has_japanese:
                # Apply Japanese translations
                for jp, en in japanese_translations.items():
                    translated = translated.replace(jp, en)
                # Clean up remaining hiragana with placeholder
                import re
                # Replace remaining Japanese with [JP] marker for visibility
                translated = re.sub(r'[\u3040-\u309F\u30A0-\u30FF]+', '[JP]', translated)
            else:
                # Apply English translations (for Spanish target)
                translated = text.upper()
                for eng, esp in english_translations.items():
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
            confidence=0.8 if not any('\u3040' <= c <= '\u30FF' for c in text) else 0.6,
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
                f"{self.base_url}/api/generate", json=payload, timeout=120
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
        # Build a strict, focused prompt that discourages explanations
        prompt_parts = [
            "You are a professional video game translator. Your task is to translate text for a retro NES/Famicom game.",
            "",
            "CRITICAL RULES:",
            "1. Output ONLY the translated text, nothing else",
            "2. NO explanations, NO notes, NO comments, NO parentheses with extra info",
            "3. NO phrases like 'Translation:', 'Here is', 'Note:', etc.",
            "4. Keep the translation SHORT - this is for a retro game with limited space",
            "5. If you see control codes like <MSG_0A> or <END>, keep them exactly as-is",
            "6. Use simple, concise language appropriate for 1980s video games",
            "",
            f"Source language: {self.source_language}",
            f"Target language: {self.target_language}",
        ]

        if self.game_context:
            prompt_parts.extend(["", f"Game: {self.game_context}"])

        if request.max_length:
            prompt_parts.extend([
                "",
                f"MAXIMUM LENGTH: {request.max_length} characters (this is a hard limit)"
            ])

        # Add the text to translate with clear delimiters
        prompt_parts.extend([
            "",
            "---INPUT---",
            request.text,
            "---OUTPUT---"
        ])

        return "\n".join(prompt_parts)

    def _extract_translation(self, llm_response: str) -> str:
        """Extract the actual translation from LLM response.

        Args:
            llm_response: Raw response from LLM

        Returns:
            Cleaned translation text
        """
        import re
        
        response = llm_response.strip()
        
        # If response contains our output delimiter, extract only that part
        if "---OUTPUT---" in response:
            response = response.split("---OUTPUT---")[-1].strip()
        
        # Take only the first line if multiple lines (often the actual translation)
        lines = response.split("\n")
        
        # Filter out lines that look like comments/explanations
        clean_lines = []
        for line in lines:
            line = line.strip()
            # Skip empty lines at the start
            if not line and not clean_lines:
                continue
            # Skip lines that look like explanations
            skip_patterns = [
                r'^\(.*\)$',  # Lines that are entirely in parentheses
                r'^Note:',
                r'^Translation:',
                r'^Here is',
                r'^The translation',
                r'^This means',
                r'^In English',
                r'^Translated:',
                r'^---',
                r'^\*\*',  # Markdown bold
                r'^Remember',
                r'^I\'ve ',
                r'^I have ',
            ]
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
                continue
            # Skip lines with common LLM chattiness
            if any(phrase in line.lower() for phrase in [
                'keep in mind', 'please note', 'i hope', 'let me know',
                'here\'s', 'above translation', 'the above', 'as requested'
            ]):
                continue
            clean_lines.append(line)
        
        # If we filtered everything, fall back to first non-empty line
        if not clean_lines:
            for line in lines:
                if line.strip():
                    clean_lines = [line.strip()]
                    break
        
        response = clean_lines[0] if clean_lines else response
        
        # Remove quotes if the entire response is quoted
        if (response.startswith('"') and response.endswith('"')) or (
            response.startswith("'") and response.endswith("'")
        ):
            response = response[1:-1]
        
        # Remove common prefixes
        prefixes_to_remove = [
            "Translation:", "Output:", "Result:",
            "The translation is:", "Here is the translation:",
            "Translated text:", "English:", "Spanish:",
        ]
        for prefix in prefixes_to_remove:
            if response.lower().startswith(prefix.lower()):
                response = response[len(prefix):].strip()
        
        # Remove trailing explanations in parentheses
        response = re.sub(r'\s*\([^)]*\)\s*$', '', response)
        
        # Remove any remaining markdown or special formatting
        response = re.sub(r'\*\*([^*]+)\*\*', r'\1', response)  # Remove **bold**
        response = re.sub(r'\*([^*]+)\*', r'\1', response)  # Remove *italic*
        
        return response.strip()

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
