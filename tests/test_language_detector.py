"""Tests for the language_detector module."""

import pytest
from src.language_detector import LanguageDetector, Language, LanguageAnalysis


class TestLanguageDetector:
    """Test cases for LanguageDetector class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.detector = LanguageDetector()
    
    # Japanese detection tests
    def test_detect_hiragana(self):
        """Test detection of Hiragana text."""
        text = "こんにちは"
        result = self.detector.detect_language(text)
        assert result.detected_language == Language.JAPANESE
        assert result.confidence >= 0.8
    
    def test_detect_katakana(self):
        """Test detection of Katakana text."""
        text = "コンニチハ"
        result = self.detector.detect_language(text)
        assert result.detected_language == Language.JAPANESE
        assert result.confidence >= 0.8
    
    def test_detect_kanji(self):
        """Test detection of Kanji text."""
        text = "日本語"
        result = self.detector.detect_language(text)
        assert result.detected_language == Language.JAPANESE
        assert result.confidence >= 0.8
    
    def test_detect_mixed_japanese(self):
        """Test detection of mixed Japanese text."""
        text = "今日はいい天気ですね"
        result = self.detector.detect_language(text)
        assert result.detected_language == Language.JAPANESE
        assert result.confidence >= 0.7
    
    # English detection tests
    def test_detect_english(self):
        """Test detection of English text."""
        text = "Hello, how are you?"
        result = self.detector.detect_language(text)
        assert result.detected_language == Language.ENGLISH
        assert result.confidence >= 0.5
    
    def test_detect_english_uppercase(self):
        """Test detection of uppercase English."""
        text = "PRESS START TO BEGIN"
        result = self.detector.detect_language(text)
        assert result.detected_language == Language.ENGLISH
        assert result.confidence >= 0.5
    
    def test_detect_english_game_words(self):
        """Test detection using game-specific words."""
        text = "GAME OVER - CONTINUE?"
        result = self.detector.detect_language(text)
        assert result.detected_language == Language.ENGLISH
        assert result.confidence >= 0.5
    
    # Edge cases
    def test_empty_string(self):
        """Test handling of empty string."""
        result = self.detector.detect_language("")
        assert result.detected_language == Language.UNKNOWN
        assert result.confidence == 0.0
    
    def test_numbers_only(self):
        """Test handling of numbers only."""
        result = self.detector.detect_language("12345")
        assert result.detected_language == Language.UNKNOWN
        assert result.confidence <= 0.5
    
    def test_symbols_only(self):
        """Test handling of symbols only."""
        result = self.detector.detect_language("!@#$%")
        assert result.detected_language == Language.UNKNOWN
    
    # Batch detection tests
    def test_detect_from_strings_japanese(self):
        """Test batch detection of Japanese strings."""
        texts = [
            "こんにちは",
            "さようなら",
            "ありがとう",
        ]
        result = self.detector.detect_from_strings(texts)
        assert result.detected_language == Language.JAPANESE
        assert result.confidence >= 0.8
    
    def test_detect_from_strings_english(self):
        """Test batch detection of English strings."""
        texts = [
            "Hello World",
            "Press Start",
            "Game Over",
        ]
        result = self.detector.detect_from_strings(texts)
        assert result.detected_language == Language.ENGLISH
        assert result.confidence >= 0.5
    
    def test_detect_from_strings_mixed(self):
        """Test batch detection of mixed strings."""
        texts = [
            "Hello",
            "こんにちは",
            "World",
            "世界",
        ]
        result = self.detector.detect_from_strings(texts)
        # Should handle mixed gracefully
        assert result.detected_language in [Language.JAPANESE, Language.ENGLISH, Language.UNKNOWN]
    
    def test_detect_from_empty_list(self):
        """Test batch detection with empty list."""
        result = self.detector.detect_from_strings([])
        assert result.detected_language == Language.UNKNOWN
        assert result.confidence == 0.0
    
    # Byte pattern tests
    def test_analyze_byte_patterns_basic(self):
        """Test basic byte pattern analysis."""
        byte_data = bytes([0x41, 0x42, 0x43, 0x44, 0x45])  # ABCDE
        result = self.detector.analyze_byte_patterns(byte_data)
        assert "total_bytes" in result
        assert result["total_bytes"] == 5
    
    def test_analyze_byte_patterns_high_values(self):
        """Test analysis of high byte values."""
        byte_data = bytes([0x80, 0x81, 0x82, 0x83, 0x84])
        result = self.detector.analyze_byte_patterns(byte_data)
        assert result is not None
        assert "unique_bytes" in result


class TestLanguageAnalysis:
    """Test the LanguageAnalysis dataclass."""
    
    def test_analysis_creation(self):
        """Test creating LanguageAnalysis."""
        analysis = LanguageAnalysis(
            detected_language=Language.JAPANESE,
            confidence=0.95,
            japanese_ratio=0.9,
            english_ratio=0.1,
            details={}
        )
        assert analysis.detected_language == Language.JAPANESE
        assert analysis.confidence == 0.95
        assert analysis.japanese_ratio == 0.9
    
    def test_analysis_with_details(self):
        """Test LanguageAnalysis with details."""
        analysis = LanguageAnalysis(
            detected_language=Language.ENGLISH,
            confidence=0.85,
            japanese_ratio=0.2,
            english_ratio=0.8,
            details={"english_words_found": 3}
        )
        assert analysis.english_ratio == 0.8
        assert analysis.details["english_words_found"] == 3


class TestLanguageEnum:
    """Test the Language enum."""
    
    def test_language_values(self):
        """Test Language enum values."""
        assert Language.JAPANESE.value == "japanese"
        assert Language.ENGLISH.value == "english"
        assert Language.UNKNOWN.value == "unknown"
