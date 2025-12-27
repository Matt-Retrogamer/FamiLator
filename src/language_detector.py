"""
Language detection and language-aware text analysis.

Provides specialized detection for Japanese, English, and other languages
to improve text extraction accuracy from ROMs.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class Language(Enum):
    """Supported languages for detection."""
    
    JAPANESE = "japanese"
    ENGLISH = "english"
    UNKNOWN = "unknown"


@dataclass
class LanguageAnalysis:
    """Result of language analysis on text or byte data."""
    
    detected_language: Language
    confidence: float
    japanese_ratio: float
    english_ratio: float
    details: Dict[str, any]


class LanguageDetector:
    """
    Detect and analyze language in text and byte data.
    
    Specialized for NES/Famicom ROM text which may be:
    - Japanese (Hiragana, Katakana, Kanji)
    - English (ASCII-range characters)
    - Mixed (common in Japanese games with English menu items)
    """
    
    # Unicode ranges for Japanese characters
    HIRAGANA_RANGE = (0x3040, 0x309F)
    KATAKANA_RANGE = (0x30A0, 0x30FF)
    KANJI_RANGE = (0x4E00, 0x9FFF)
    FULLWIDTH_RANGE = (0xFF00, 0xFFEF)
    
    # Common Japanese particles and endings
    JAPANESE_PARTICLES = {'の', 'は', 'が', 'を', 'に', 'で', 'と', 'も', 'や', 'へ'}
    JAPANESE_ENDINGS = {'です', 'ます', 'した', 'ない', 'ある', 'いる', 'った', 'って'}
    
    # Common English words in games
    ENGLISH_GAME_WORDS = {
        'start', 'game', 'over', 'player', 'score', 'time', 'life', 'lives',
        'level', 'stage', 'world', 'continue', 'select', 'press', 'push',
        'password', 'save', 'load', 'item', 'menu', 'option', 'pause',
        'attack', 'jump', 'run', 'power', 'magic', 'sword', 'shield',
        'the', 'and', 'you', 'your', 'are', 'have', 'this', 'that', 'with'
    }
    
    def __init__(self):
        """Initialize the language detector."""
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        # Pattern for Japanese characters
        self.japanese_pattern = re.compile(
            r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uFF00-\uFFEF]'
        )
        
        # Pattern for ASCII letters
        self.english_pattern = re.compile(r'[A-Za-z]')
        
        # Pattern for control codes in decoded text
        self.control_code_pattern = re.compile(r'<[A-Z_0-9:]+>')
    
    def detect_language(self, text: str) -> LanguageAnalysis:
        """
        Detect the primary language of a text string.
        
        Args:
            text: Decoded text string to analyze
            
        Returns:
            LanguageAnalysis with detection results
        """
        if not text:
            return LanguageAnalysis(
                detected_language=Language.UNKNOWN,
                confidence=0.0,
                japanese_ratio=0.0,
                english_ratio=0.0,
                details={"error": "empty text"}
            )
        
        # Remove control codes for analysis
        clean_text = self.control_code_pattern.sub('', text)
        clean_text = clean_text.strip()
        
        if not clean_text:
            return LanguageAnalysis(
                detected_language=Language.UNKNOWN,
                confidence=0.0,
                japanese_ratio=0.0,
                english_ratio=0.0,
                details={"error": "only control codes"}
            )
        
        # Count character types
        total_chars = len(clean_text)
        japanese_chars = len(self.japanese_pattern.findall(clean_text))
        english_chars = len(self.english_pattern.findall(clean_text))
        
        japanese_ratio = japanese_chars / total_chars if total_chars > 0 else 0
        english_ratio = english_chars / total_chars if total_chars > 0 else 0
        
        # Check for Japanese linguistic features
        has_particles = any(p in clean_text for p in self.JAPANESE_PARTICLES)
        has_endings = any(e in clean_text for e in self.JAPANESE_ENDINGS)
        
        # Check for English words
        text_lower = clean_text.lower()
        english_words_found = sum(1 for w in self.ENGLISH_GAME_WORDS if w in text_lower)
        
        # Determine language
        details = {
            "total_chars": total_chars,
            "japanese_chars": japanese_chars,
            "english_chars": english_chars,
            "has_japanese_particles": has_particles,
            "has_japanese_endings": has_endings,
            "english_words_found": english_words_found,
        }
        
        # Decision logic
        if japanese_ratio > 0.3 or (has_particles and japanese_chars > 0):
            confidence = min(japanese_ratio + (0.2 if has_particles else 0) + (0.1 if has_endings else 0), 1.0)
            return LanguageAnalysis(
                detected_language=Language.JAPANESE,
                confidence=confidence,
                japanese_ratio=japanese_ratio,
                english_ratio=english_ratio,
                details=details
            )
        elif english_ratio > 0.5 or english_words_found >= 2:
            confidence = min(english_ratio + (0.1 * english_words_found), 1.0)
            return LanguageAnalysis(
                detected_language=Language.ENGLISH,
                confidence=confidence,
                japanese_ratio=japanese_ratio,
                english_ratio=english_ratio,
                details=details
            )
        else:
            return LanguageAnalysis(
                detected_language=Language.UNKNOWN,
                confidence=0.3,
                japanese_ratio=japanese_ratio,
                english_ratio=english_ratio,
                details=details
            )
    
    def analyze_byte_patterns(
        self,
        data: bytes,
        encoding_hints: Optional[Dict[int, str]] = None
    ) -> Dict[str, any]:
        """
        Analyze byte patterns to detect likely language/encoding.
        
        This is useful for ROMs where we don't yet have an encoding table.
        
        Args:
            data: Raw byte data to analyze
            encoding_hints: Optional byte->char mappings to test
            
        Returns:
            Analysis results with byte frequency and pattern info
        """
        if not data:
            return {"error": "empty data"}
        
        # Byte frequency analysis
        freq = {}
        for byte in data:
            freq[byte] = freq.get(byte, 0) + 1
        
        total_bytes = len(data)
        
        # Sort by frequency
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        top_bytes = sorted_freq[:20]
        
        # Analyze patterns
        analysis = {
            "total_bytes": total_bytes,
            "unique_bytes": len(freq),
            "top_bytes": [(f"0x{b:02X}", c, c/total_bytes) for b, c in top_bytes],
        }
        
        # Check for common Japanese encoding patterns
        # Many Japanese NES games use specific byte ranges
        japanese_indicators = 0
        
        # Common Japanese text byte ranges in NES games
        # Hiragana often mapped to 0x00-0x50 range
        # Katakana often mapped to 0x50-0xA0 range
        hiragana_range_count = sum(1 for b in data if 0x00 <= b <= 0x50)
        katakana_range_count = sum(1 for b in data if 0x50 <= b <= 0xA0)
        
        # If high concentration in these ranges, likely Japanese
        if hiragana_range_count / total_bytes > 0.3:
            japanese_indicators += 1
        if katakana_range_count / total_bytes > 0.2:
            japanese_indicators += 1
        
        # Check for ASCII-like distribution (English)
        ascii_range_count = sum(1 for b in data if 0x20 <= b <= 0x7E)
        ascii_ratio = ascii_range_count / total_bytes
        
        analysis["ascii_ratio"] = ascii_ratio
        analysis["japanese_indicators"] = japanese_indicators
        analysis["likely_encoding"] = "japanese" if japanese_indicators >= 1 else (
            "ascii" if ascii_ratio > 0.7 else "unknown"
        )
        
        # Look for string terminators
        terminator_candidates = []
        for byte_val in [0x00, 0xFF, 0xFE, 0xFD]:
            if byte_val in freq:
                # Check if it appears at regular intervals (string boundaries)
                positions = [i for i, b in enumerate(data) if b == byte_val]
                if len(positions) > 5:
                    intervals = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                    avg_interval = sum(intervals) / len(intervals)
                    if 3 < avg_interval < 100:  # Reasonable string length
                        terminator_candidates.append({
                            "byte": f"0x{byte_val:02X}",
                            "count": freq[byte_val],
                            "avg_interval": avg_interval
                        })
        
        analysis["terminator_candidates"] = terminator_candidates
        
        return analysis
    
    def detect_from_strings(self, strings: List[str]) -> LanguageAnalysis:
        """
        Detect language from a collection of strings.
        
        Aggregates analysis across multiple strings for better accuracy.
        
        Args:
            strings: List of decoded text strings
            
        Returns:
            Aggregate language analysis
        """
        if not strings:
            return LanguageAnalysis(
                detected_language=Language.UNKNOWN,
                confidence=0.0,
                japanese_ratio=0.0,
                english_ratio=0.0,
                details={"error": "no strings provided"}
            )
        
        # Analyze each string
        analyses = [self.detect_language(s) for s in strings if s.strip()]
        
        if not analyses:
            return LanguageAnalysis(
                detected_language=Language.UNKNOWN,
                confidence=0.0,
                japanese_ratio=0.0,
                english_ratio=0.0,
                details={"error": "no valid strings"}
            )
        
        # Aggregate results
        lang_counts = {Language.JAPANESE: 0, Language.ENGLISH: 0, Language.UNKNOWN: 0}
        total_jp_ratio = 0.0
        total_en_ratio = 0.0
        
        for analysis in analyses:
            lang_counts[analysis.detected_language] += 1
            total_jp_ratio += analysis.japanese_ratio
            total_en_ratio += analysis.english_ratio
        
        # Determine dominant language
        dominant_lang = max(lang_counts, key=lang_counts.get)
        dominant_count = lang_counts[dominant_lang]
        
        confidence = dominant_count / len(analyses)
        avg_jp_ratio = total_jp_ratio / len(analyses)
        avg_en_ratio = total_en_ratio / len(analyses)
        
        return LanguageAnalysis(
            detected_language=dominant_lang,
            confidence=confidence,
            japanese_ratio=avg_jp_ratio,
            english_ratio=avg_en_ratio,
            details={
                "strings_analyzed": len(analyses),
                "language_distribution": {
                    "japanese": lang_counts[Language.JAPANESE],
                    "english": lang_counts[Language.ENGLISH],
                    "unknown": lang_counts[Language.UNKNOWN],
                }
            }
        )
    
    def suggest_source_language(self, strings: List[str]) -> Tuple[str, float]:
        """
        Suggest the source language for translation.
        
        Args:
            strings: Extracted text strings
            
        Returns:
            Tuple of (language_name, confidence)
        """
        analysis = self.detect_from_strings(strings)
        
        if analysis.detected_language == Language.JAPANESE:
            return ("Japanese", analysis.confidence)
        elif analysis.detected_language == Language.ENGLISH:
            return ("English", analysis.confidence)
        else:
            # Default to Japanese for NES/Famicom games
            return ("Japanese", 0.5)
