"""Tests for the translator module."""

import pytest
import tempfile
import json
from pathlib import Path
from src.translator import (
    GameTranslator,
    TranslationConfig,
    Glossary,
    TranslationMemory,
    TranslationResult,
    BatchTranslationResult,
)


class TestTranslationConfig:
    """Test TranslationConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = TranslationConfig()
        assert config.source_language == "Japanese"
        assert config.target_language == "English"
        assert config.max_retries == 3
        assert config.batch_size == 5
        assert config.mock_mode is False
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = TranslationConfig(
            source_language="English",
            target_language="Spanish",
            llm_model="gpt-4",
            max_retries=5,
            mock_mode=True,
        )
        assert config.source_language == "English"
        assert config.target_language == "Spanish"
        assert config.llm_model == "gpt-4"
        assert config.max_retries == 5
        assert config.mock_mode is True


class TestGlossary:
    """Test Glossary class."""
    
    def test_empty_glossary(self):
        """Test empty glossary creation."""
        glossary = Glossary()
        assert len(glossary.entries) == 0
    
    def test_add_entry(self):
        """Test adding glossary entries."""
        glossary = Glossary()
        glossary.add("勇者", "Hero")
        assert glossary.lookup("勇者") == "Hero"
    
    def test_lookup_nonexistent(self):
        """Test looking up non-existent entry."""
        glossary = Glossary()
        assert glossary.lookup("unknown") is None
    
    def test_lookup_case_insensitive(self):
        """Test case-insensitive lookup."""
        glossary = Glossary()
        glossary.add("Hero", "勇者")
        # Case insensitive lookup
        result = glossary.lookup("hero", case_sensitive=False)
        assert result == "勇者"
    
    def test_save_and_load(self):
        """Test saving and loading glossary."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        
        try:
            # Create and save glossary
            glossary = Glossary()
            glossary.add("剣", "Sword")
            glossary.add("盾", "Shield")
            glossary.save(temp_path)
            
            # Load into new glossary
            loaded = Glossary(temp_path)
            assert loaded.lookup("剣") == "Sword"
            assert loaded.lookup("盾") == "Shield"
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_remove_entry(self):
        """Test removing entry."""
        glossary = Glossary()
        glossary.add("remove_me", "value")
        glossary.remove("remove_me")
        assert glossary.lookup("remove_me") is None
    
    def test_apply_to_text(self):
        """Test applying glossary to text."""
        glossary = Glossary()
        glossary.add("勇者", "Hero")
        glossary.add("魔王", "Demon King")
        
        text = "勇者は魔王を倒した"
        result, applied = glossary.apply_to_text(text)
        
        assert "Hero" in result
        assert "Demon King" in result
        assert "勇者" in applied
    
    def test_get_context_prompt(self):
        """Test getting context prompt."""
        glossary = Glossary()
        glossary.add("test", "value")
        
        prompt = glossary.get_context_prompt()
        assert "terminology" in prompt.lower()


class TestTranslationMemory:
    """Test TranslationMemory class."""
    
    def test_empty_memory(self):
        """Test empty translation memory."""
        memory = TranslationMemory()
        assert len(memory.memory) == 0
    
    def test_store_and_lookup(self):
        """Test storing and looking up translations."""
        memory = TranslationMemory()
        memory.store("こんにちは", "Hello")
        assert memory.lookup("こんにちは") == "Hello"
    
    def test_lookup_nonexistent(self):
        """Test looking up non-existent translation."""
        memory = TranslationMemory()
        assert memory.lookup("unknown") is None
    
    def test_save_and_load(self):
        """Test saving and loading translation memory."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name
        
        try:
            # Create and save memory
            memory = TranslationMemory()
            memory.store("text1", "translation1")
            memory.store("text2", "translation2")
            memory.save(temp_path)
            
            # Load into new memory
            loaded = TranslationMemory(temp_path)
            assert loaded.lookup("text1") == "translation1"
            assert loaded.lookup("text2") == "translation2"
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_usage_count(self):
        """Test usage count tracking."""
        memory = TranslationMemory()
        memory.store("test", "value")
        memory.store("test", "value")  # Store again
        
        assert memory.usage_count.get("test", 0) == 2


class TestGameTranslator:
    """Test GameTranslator class."""
    
    def test_mock_mode_translation(self):
        """Test translation in mock mode."""
        config = TranslationConfig(mock_mode=True)
        translator = GameTranslator(config)
        
        result = translator.translate("テスト")
        assert result.translated is not None
        assert len(result.translated) > 0
    
    def test_mock_mode_preserves_control_codes(self):
        """Test that mock mode preserves control codes."""
        config = TranslationConfig(mock_mode=True)
        translator = GameTranslator(config)
        
        result = translator.translate("Hello<END>")
        assert "<END>" in result.translated
    
    def test_translate_with_glossary(self):
        """Test translation using glossary."""
        config = TranslationConfig(mock_mode=True)
        glossary = Glossary()
        glossary.add("勇者", "Hero")
        
        translator = GameTranslator(config, glossary)
        result = translator.translate("勇者")
        
        # Should use glossary
        assert result.from_glossary is True or "Hero" in result.translated
    
    def test_translate_with_memory(self):
        """Test translation using translation memory."""
        config = TranslationConfig(mock_mode=True)
        memory = TranslationMemory()
        memory.store("こんにちは", "Hello!")
        
        translator = GameTranslator(config, memory=memory)
        result = translator.translate("こんにちは")
        
        # Should find in memory
        assert result.from_memory is True
        assert result.translated == "Hello!"
    
    def test_batch_translation(self):
        """Test batch translation."""
        config = TranslationConfig(mock_mode=True, batch_size=5)
        translator = GameTranslator(config)
        
        texts = ["text1", "text2", "text3"]
        result = translator.translate_batch(texts)
        
        assert isinstance(result, BatchTranslationResult)
        assert result.success_count == 3
        assert len(result.results) == 3
    
    def test_batch_with_contexts(self):
        """Test batch translation with contexts."""
        config = TranslationConfig(mock_mode=True)
        translator = GameTranslator(config)
        
        texts = ["Hello", "World"]
        contexts = ["greeting", "noun"]
        
        result = translator.translate_batch(texts, contexts)
        assert result.success_count == 2
    
    def test_empty_string_translation(self):
        """Test handling empty string."""
        config = TranslationConfig(mock_mode=True)
        translator = GameTranslator(config)
        
        result = translator.translate("")
        assert result.translated == ""
    
    def test_whitespace_only_translation(self):
        """Test handling whitespace-only string."""
        config = TranslationConfig(mock_mode=True)
        translator = GameTranslator(config)
        
        result = translator.translate("   ")
        # Should return something (likely the whitespace itself)
        assert result is not None


class TestTranslationResult:
    """Test TranslationResult dataclass."""
    
    def test_result_creation(self):
        """Test creating TranslationResult."""
        result = TranslationResult(
            original="test",
            translated="result",
            confidence=0.9,
        )
        assert result.original == "test"
        assert result.translated == "result"
        assert result.confidence == 0.9
    
    def test_default_values(self):
        """Test TranslationResult default values."""
        result = TranslationResult(
            original="test",
            translated="result",
            confidence=1.0,
        )
        assert result.retries == 0
        assert result.from_glossary is False
        assert result.from_memory is False
        assert result.warnings == []


class TestBatchTranslationResult:
    """Test BatchTranslationResult dataclass."""
    
    def test_batch_result_structure(self):
        """Test BatchTranslationResult structure."""
        results = [
            TranslationResult("a", "1", 0.9),
            TranslationResult("b", "2", 0.9),
            TranslationResult("c", "3", 0.5),
        ]
        
        batch = BatchTranslationResult(
            results=results,
            success_count=2,
            failure_count=1,
            total_time=1.5,
        )
        
        assert batch.success_count == 2
        assert batch.failure_count == 1
        assert batch.total_time == 1.5
        assert len(batch.results) == 3
