"""
Enhanced translation system with retry logic, batching, and glossary support.

Provides robust LLM-based translation with:
- Automatic retry on failures
- Batch translation for context preservation
- Per-project glossary management
- Translation memory for consistency
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


@dataclass
class TranslationConfig:
    """Configuration for the translation system."""
    
    source_language: str = "Japanese"
    target_language: str = "English"
    llm_provider: str = "ollama"
    llm_model: str = "llama3"
    llm_base_url: str = "http://localhost:11434"
    temperature: float = 0.3
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 60
    batch_size: int = 5
    game_context: str = ""
    mock_mode: bool = False


@dataclass
class TranslationResult:
    """Result of a single translation."""
    
    original: str
    translated: str
    confidence: float
    warnings: List[str] = field(default_factory=list)
    retries: int = 0
    from_glossary: bool = False
    from_memory: bool = False


@dataclass
class BatchTranslationResult:
    """Result of a batch translation."""
    
    results: List[TranslationResult]
    success_count: int
    failure_count: int
    total_time: float


class Glossary:
    """
    Manages game-specific terminology for consistent translations.
    
    Glossary entries take precedence over LLM translations to ensure
    consistency for important terms like character names, items, etc.
    """
    
    def __init__(self, glossary_path: Optional[str] = None):
        """
        Initialize glossary.
        
        Args:
            glossary_path: Path to glossary JSON file
        """
        self.entries: Dict[str, str] = {}
        self.case_insensitive: Dict[str, str] = {}  # Lowercase key -> original key
        
        if glossary_path:
            self.load(glossary_path)
    
    def load(self, path: str) -> None:
        """Load glossary from JSON file."""
        glossary_file = Path(path)
        if glossary_file.exists():
            with open(glossary_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.entries = data.get("entries", {})
                self._build_case_index()
    
    def save(self, path: str) -> None:
        """Save glossary to JSON file."""
        glossary_file = Path(path)
        glossary_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(glossary_file, "w", encoding="utf-8") as f:
            json.dump({
                "entries": self.entries,
                "count": len(self.entries),
            }, f, indent=2, ensure_ascii=False)
    
    def _build_case_index(self) -> None:
        """Build case-insensitive lookup index."""
        self.case_insensitive = {k.lower(): k for k in self.entries.keys()}
    
    def add(self, source: str, target: str) -> None:
        """Add a glossary entry."""
        self.entries[source] = target
        self.case_insensitive[source.lower()] = source
    
    def remove(self, source: str) -> None:
        """Remove a glossary entry."""
        if source in self.entries:
            del self.entries[source]
            del self.case_insensitive[source.lower()]
    
    def lookup(self, text: str, case_sensitive: bool = True) -> Optional[str]:
        """
        Look up a term in the glossary.
        
        Args:
            text: Text to look up
            case_sensitive: Whether to match case exactly
            
        Returns:
            Translation if found, None otherwise
        """
        if case_sensitive:
            return self.entries.get(text)
        else:
            key = self.case_insensitive.get(text.lower())
            return self.entries.get(key) if key else None
    
    def apply_to_text(self, text: str) -> Tuple[str, List[str]]:
        """
        Apply glossary substitutions to text.
        
        Args:
            text: Text to process
            
        Returns:
            Tuple of (processed text, list of applied terms)
        """
        applied = []
        result = text
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_entries = sorted(self.entries.items(), key=lambda x: len(x[0]), reverse=True)
        
        for source, target in sorted_entries:
            if source in result:
                result = result.replace(source, target)
                applied.append(source)
        
        return result, applied
    
    def get_context_prompt(self) -> str:
        """Get a prompt section describing glossary terms."""
        if not self.entries:
            return ""
        
        lines = ["Important terminology (use these exact translations):"]
        for source, target in list(self.entries.items())[:20]:  # Limit to 20 terms
            lines.append(f"  {source} → {target}")
        
        return "\n".join(lines)


class TranslationMemory:
    """
    Stores previous translations for consistency and reuse.
    
    Helps ensure the same source text gets the same translation
    throughout the project.
    """
    
    def __init__(self, memory_path: Optional[str] = None):
        """
        Initialize translation memory.
        
        Args:
            memory_path: Path to memory JSON file
        """
        self.memory: Dict[str, str] = {}
        self.usage_count: Dict[str, int] = {}
        
        if memory_path:
            self.load(memory_path)
    
    def load(self, path: str) -> None:
        """Load memory from JSON file."""
        memory_file = Path(path)
        if memory_file.exists():
            with open(memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.memory = data.get("translations", {})
                self.usage_count = data.get("usage_count", {})
    
    def save(self, path: str) -> None:
        """Save memory to JSON file."""
        memory_file = Path(path)
        memory_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(memory_file, "w", encoding="utf-8") as f:
            json.dump({
                "translations": self.memory,
                "usage_count": self.usage_count,
                "count": len(self.memory),
            }, f, indent=2, ensure_ascii=False)
    
    def lookup(self, source: str) -> Optional[str]:
        """Look up a previous translation."""
        return self.memory.get(source)
    
    def store(self, source: str, translation: str) -> None:
        """Store a translation in memory."""
        self.memory[source] = translation
        self.usage_count[source] = self.usage_count.get(source, 0) + 1
    
    def get_similar(self, source: str, threshold: float = 0.8) -> List[Tuple[str, str, float]]:
        """
        Find similar previously translated strings.
        
        Args:
            source: Text to find similar translations for
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of (source, translation, similarity) tuples
        """
        # Simple character-based similarity for now
        similar = []
        source_lower = source.lower()
        
        for mem_source, mem_trans in self.memory.items():
            similarity = self._calculate_similarity(source_lower, mem_source.lower())
            if similarity >= threshold:
                similar.append((mem_source, mem_trans, similarity))
        
        return sorted(similar, key=lambda x: x[2], reverse=True)[:5]
    
    def _calculate_similarity(self, a: str, b: str) -> float:
        """Calculate simple character-based similarity."""
        if not a or not b:
            return 0.0
        
        # Use set intersection for simple similarity
        set_a = set(a)
        set_b = set(b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        
        return intersection / union if union > 0 else 0.0


class GameTranslator:
    """
    Enhanced translator with retry logic, batching, and context management.
    
    Features:
    - Automatic retry on LLM failures
    - Batch translation for context preservation
    - Glossary integration for consistent terminology
    - Translation memory for reuse
    """
    
    def __init__(
        self,
        config: TranslationConfig,
        glossary: Optional[Glossary] = None,
        memory: Optional[TranslationMemory] = None,
    ):
        """
        Initialize the translator.
        
        Args:
            config: Translation configuration
            glossary: Optional glossary for terminology
            memory: Optional translation memory
        """
        self.config = config
        self.glossary = glossary or Glossary()
        self.memory = memory or TranslationMemory()
    
    def translate(self, text: str, context: str = "") -> TranslationResult:
        """
        Translate a single string.
        
        Args:
            text: Text to translate
            context: Additional context for the translation
            
        Returns:
            Translation result
        """
        # Check for empty/whitespace text
        if not text or not text.strip():
            return TranslationResult(
                original=text,
                translated=text,
                confidence=1.0,
                warnings=["Empty text, no translation needed"]
            )
        
        # Check glossary first (exact match)
        glossary_result = self.glossary.lookup(text)
        if glossary_result:
            return TranslationResult(
                original=text,
                translated=glossary_result,
                confidence=1.0,
                from_glossary=True
            )
        
        # Check translation memory
        memory_result = self.memory.lookup(text)
        if memory_result:
            return TranslationResult(
                original=text,
                translated=memory_result,
                confidence=0.95,
                from_memory=True
            )
        
        # Use LLM for translation
        if self.config.mock_mode:
            result = self._mock_translate(text)
        else:
            result = self._llm_translate_with_retry(text, context)
        
        # Store in memory for future use
        if result.confidence > 0.5:
            self.memory.store(text, result.translated)
        
        return result
    
    def translate_batch(
        self,
        texts: List[str],
        contexts: Optional[List[str]] = None,
    ) -> BatchTranslationResult:
        """
        Translate multiple strings with context awareness.
        
        Args:
            texts: List of texts to translate
            contexts: Optional list of contexts for each text
            
        Returns:
            Batch translation result
        """
        start_time = time.time()
        results = []
        success_count = 0
        failure_count = 0
        
        # Ensure contexts list matches texts
        if contexts is None:
            contexts = [""] * len(texts)
        elif len(contexts) < len(texts):
            contexts.extend([""] * (len(texts) - len(contexts)))
        
        # Process in batches for context
        batch_size = self.config.batch_size
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_contexts = contexts[i:i + batch_size]
            
            # Build context from previous translations in this batch
            batch_context = self._build_batch_context(results[-5:] if results else [])
            
            for text, context in zip(batch_texts, batch_contexts):
                full_context = f"{batch_context}\n{context}".strip()
                result = self.translate(text, full_context)
                results.append(result)
                
                if result.confidence > 0.5:
                    success_count += 1
                else:
                    failure_count += 1
        
        total_time = time.time() - start_time
        
        return BatchTranslationResult(
            results=results,
            success_count=success_count,
            failure_count=failure_count,
            total_time=total_time
        )
    
    def _build_batch_context(self, previous_results: List[TranslationResult]) -> str:
        """Build context from previous translations in batch."""
        if not previous_results:
            return ""
        
        lines = ["Previous translations in this section:"]
        for result in previous_results:
            if result.translated and result.original != result.translated:
                lines.append(f"  {result.original[:30]}... → {result.translated[:30]}...")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _llm_translate_with_retry(self, text: str, context: str) -> TranslationResult:
        """Translate with automatic retry on failure."""
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                result = self._llm_translate(text, context)
                result.retries = attempt
                return result
                
            except Exception as e:
                last_error = str(e)
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (attempt + 1))
        
        # All retries failed
        return TranslationResult(
            original=text,
            translated=f"[TRANSLATION ERROR: {last_error}]",
            confidence=0.0,
            warnings=[f"Translation failed after {self.config.max_retries} attempts: {last_error}"],
            retries=self.config.max_retries
        )
    
    def _llm_translate(self, text: str, context: str) -> TranslationResult:
        """Perform actual LLM translation."""
        prompt = self._build_prompt(text, context)
        
        payload = {
            "model": self.config.llm_model,
            "prompt": prompt,
            "temperature": self.config.temperature,
            "stream": False,
        }
        
        response = requests.post(
            f"{self.config.llm_base_url}/api/generate",
            json=payload,
            timeout=self.config.timeout
        )
        response.raise_for_status()
        
        result = response.json()
        translated_text = result.get("response", "").strip()
        
        # Clean up the response
        translated_text = self._clean_llm_response(translated_text)
        
        # Apply glossary substitutions to ensure consistency
        translated_text, applied_terms = self.glossary.apply_to_text(translated_text)
        
        warnings = []
        confidence = 0.9
        
        if applied_terms:
            warnings.append(f"Applied glossary terms: {', '.join(applied_terms)}")
        
        return TranslationResult(
            original=text,
            translated=translated_text,
            confidence=confidence,
            warnings=warnings
        )
    
    def _build_prompt(self, text: str, context: str) -> str:
        """Build the translation prompt."""
        parts = [
            "You are a professional video game translator. Translate the following text.",
            "",
            "CRITICAL RULES:",
            "1. Output ONLY the translated text, nothing else",
            "2. NO explanations, notes, or comments",
            "3. Keep translations concise (retro games have limited space)",
            "4. Preserve control codes like <MSG_0A> or <END> exactly as-is",
            "5. Use simple language appropriate for 1980s video games",
            "",
            f"Source language: {self.config.source_language}",
            f"Target language: {self.config.target_language}",
        ]
        
        if self.config.game_context:
            parts.extend(["", f"Game: {self.config.game_context}"])
        
        # Add glossary terms
        glossary_prompt = self.glossary.get_context_prompt()
        if glossary_prompt:
            parts.extend(["", glossary_prompt])
        
        if context:
            parts.extend(["", f"Context: {context}"])
        
        parts.extend([
            "",
            "---INPUT---",
            text,
            "---OUTPUT---"
        ])
        
        return "\n".join(parts)
    
    def _clean_llm_response(self, response: str) -> str:
        """Clean up LLM response to extract just the translation."""
        import re
        
        response = response.strip()
        
        # Remove output delimiter if present
        if "---OUTPUT---" in response:
            response = response.split("---OUTPUT---")[-1].strip()
        
        # Take first non-empty line
        lines = [l.strip() for l in response.split("\n") if l.strip()]
        
        # Filter out explanation lines
        skip_patterns = [
            r'^\(.*\)$',
            r'^Note:',
            r'^Translation:',
            r'^Here is',
            r'^The translation',
            r'^---',
        ]
        
        for line in lines:
            if not any(re.match(p, line, re.IGNORECASE) for p in skip_patterns):
                response = line
                break
        
        # Remove surrounding quotes
        if (response.startswith('"') and response.endswith('"')) or \
           (response.startswith("'") and response.endswith("'")):
            response = response[1:-1]
        
        return response.strip()
    
    def _mock_translate(self, text: str) -> TranslationResult:
        """Mock translation for testing."""
        # Simple mock translations
        mock_dict = {
            # Japanese game terms
            "たから": "treasure",
            "けん": "sword",
            "たて": "shield",
            "ばくだん": "bomb",
            "かぎ": "key",
            "こころ": "heart",
            # English to Spanish
            "START": "INICIO",
            "GAME": "JUEGO",
            "PLAYER": "JUGADOR",
            "SCORE": "PUNTOS",
            "GAME OVER": "FIN",
        }
        
        translated = text
        for source, target in mock_dict.items():
            translated = translated.replace(source, target)
        
        # If no changes, just return original with marker
        if translated == text:
            translated = f"[{text}]"
        
        return TranslationResult(
            original=text,
            translated=translated,
            confidence=0.7,
            warnings=["Mock translation"]
        )
    
    def test_connection(self) -> bool:
        """Test connection to LLM service."""
        if self.config.mock_mode:
            return True
        
        try:
            response = requests.get(
                f"{self.config.llm_base_url}/api/tags",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
