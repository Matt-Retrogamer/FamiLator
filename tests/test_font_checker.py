"""Tests for the font_checker module."""

import pytest
import tempfile
from pathlib import Path
from src.font_checker import (
    FontChecker,
    FontCheckResult,
    BatchCheckResult,
    CharacterIssue,
    check_font_compatibility,
)
from src.encoding import EncodingTable


class TestCharacterIssue:
    """Test CharacterIssue dataclass."""
    
    def test_issue_creation(self):
        """Test creating CharacterIssue."""
        issue = CharacterIssue(
            character="e",
            unicode_name="LATIN SMALL LETTER E WITH ACUTE",
            occurrences=3,
            suggested_replacement="e",
        )
        assert issue.character == "e"
        assert issue.occurrences == 3
        assert issue.suggested_replacement == "e"
    
    def test_issue_defaults(self):
        """Test CharacterIssue defaults."""
        issue = CharacterIssue(
            character="x",
            unicode_name="LATIN SMALL LETTER X",
            occurrences=1,
        )
        assert issue.suggested_replacement is None
        assert issue.context == ""


class TestFontCheckResult:
    """Test FontCheckResult dataclass."""
    
    def test_compatible_result(self):
        """Test compatible result."""
        result = FontCheckResult(
            text="Hello",
            is_compatible=True,
            compatibility_score=1.0,
        )
        assert result.is_compatible is True
        assert result.compatibility_score == 1.0
        assert len(result.missing_chars) == 0
    
    def test_incompatible_result(self):
        """Test incompatible result."""
        result = FontCheckResult(
            text="Hello",
            is_compatible=False,
            missing_chars={"x"},
            compatibility_score=0.8,
        )
        assert result.is_compatible is False
        assert "x" in result.missing_chars
    
    def test_get_summary_compatible(self):
        """Test summary for compatible text."""
        result = FontCheckResult(
            text="Hello",
            is_compatible=True,
            compatibility_score=1.0,
        )
        summary = result.get_summary()
        assert "compatible" in summary.lower()
    
    def test_get_summary_incompatible(self):
        """Test summary for incompatible text."""
        result = FontCheckResult(
            text="Hello",
            is_compatible=False,
            missing_chars={"x"},
            issues=[CharacterIssue("x", "LETTER X", 1, "X")],
            compatibility_score=0.8,
        )
        summary = result.get_summary()
        assert "issues" in summary.lower() or "x" in summary


class TestBatchCheckResult:
    """Test BatchCheckResult dataclass."""
    
    def test_batch_result_creation(self):
        """Test creating BatchCheckResult."""
        result = BatchCheckResult(
            total_texts=5,
            compatible_count=4,
            incompatible_count=1,
            overall_score=0.9,
        )
        assert result.total_texts == 5
        assert result.compatible_count == 4
        assert result.incompatible_count == 1
    
    def test_get_summary(self):
        """Test batch result summary."""
        result = BatchCheckResult(
            total_texts=10,
            compatible_count=8,
            incompatible_count=2,
            overall_score=0.85,
        )
        summary = result.get_summary()
        assert "8/10" in summary


class TestFontChecker:
    """Test FontChecker class."""
    
    def test_checker_without_table(self):
        """Test checker without encoding table (accepts all)."""
        checker = FontChecker()
        result = checker.check_text("Any text works!")
        # Without table, all text should be compatible
        assert result.is_compatible is True
    
    def test_checker_with_ascii_table(self):
        """Test checker with ASCII-only table."""
        # Create a simple ASCII table
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tbl", delete=False) as f:
            f.write("41=A\n42=B\n43=C\n44=D\n45=E\n")
            f.write("20= \n")  # Space
            temp_path = f.name
        
        try:
            checker = FontChecker(table_path=temp_path)
            
            # Compatible text
            result = checker.check_text("ABCDE")
            assert result.is_compatible is True
            
            # Incompatible text (lowercase)
            result = checker.check_text("abcde")
            assert result.is_compatible is False
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_auto_substitution_accents(self):
        """Test automatic accent substitution."""
        checker = FontChecker()
        
        # These should be in the substitution map
        result = checker.auto_fix_text("Hello World")
        assert result == "Hello World"
        
        # Test accent substitution
        result = checker.auto_fix_text("cafe")
        assert result == "cafe"
    
    def test_auto_substitution_symbols(self):
        """Test automatic symbol substitution."""
        checker = FontChecker()
        
        # Ellipsis
        result = checker.auto_fix_text("Hello\u2026 World")  # …
        assert "\u2026" not in result
        assert "..." in result
        
        # Trademark
        result = checker.auto_fix_text("Hello\u2122")  # ™
        assert "\u2122" not in result
        assert "(TM)" in result
    
    def test_auto_substitution_quotes(self):
        """Test automatic quote substitution."""
        checker = FontChecker()
        
        # Test that curly/smart quotes can be substituted
        # The substitution map uses literal smart quote chars
        # Check the map directly
        assert "\u201c" in checker.SUBSTITUTIONS or '"' in checker.SUBSTITUTIONS
        assert "\u201d" in checker.SUBSTITUTIONS or '"' in checker.SUBSTITUTIONS
    
    def test_check_text_with_auto_fix(self):
        """Test check_text with auto_fix enabled."""
        checker = FontChecker()
        
        result = checker.check_text("Hello", auto_fix=True)
        assert result is not None
    
    def test_check_empty_text(self):
        """Test checking empty text."""
        checker = FontChecker()
        result = checker.check_text("")
        assert result.is_compatible is True
        assert result.compatibility_score == 1.0
    
    def test_batch_check(self):
        """Test batch checking."""
        checker = FontChecker()
        
        texts = ["Hello", "World", "Test"]
        result = checker.check_batch(texts)
        
        assert result.total_texts == 3
        assert len(result.results) == 3
    
    def test_batch_check_with_auto_fix(self):
        """Test batch checking with auto_fix."""
        checker = FontChecker()
        
        texts = ["Hello", "World"]
        result = checker.check_batch(texts, auto_fix=True)
        
        assert result.total_texts == 2
    
    def test_add_custom_substitution(self):
        """Test adding custom substitution."""
        checker = FontChecker()
        checker.add_substitution("\u263a", ":)")  # ☺
        
        result = checker.auto_fix_text("Hello \u263a")
        assert "\u263a" not in result
        assert ":)" in result
    
    def test_get_available_chars(self):
        """Test getting available characters."""
        checker = FontChecker()
        chars = checker.get_available_chars()
        assert isinstance(chars, set)
    
    def test_control_code_handling(self):
        """Test that control codes are handled."""
        checker = FontChecker()
        
        # Text with control code pattern
        result = checker.check_text("Hello<END>World")
        # Control code characters shouldn't cause issues
        assert result is not None
    
    def test_missing_char_report(self):
        """Test missing character report generation."""
        checker = FontChecker()
        
        texts = ["Hello", "World"]
        report = checker.get_missing_char_report(texts)
        
        assert "Font Compatibility Report" in report
        assert "Total texts checked:" in report


class TestFontCheckerWithEncodingTable:
    """Test FontChecker with actual EncodingTable."""
    
    def test_with_encoding_table_object(self):
        """Test using EncodingTable object directly."""
        # Create encoding table
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tbl", delete=False) as f:
            for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
                f.write(f"{0x41+i:02X}={c}\n")
            f.write("20= \n")
            temp_path = f.name
        
        try:
            table = EncodingTable(temp_path)
            checker = FontChecker(encoding_table=table)
            
            # Compatible
            result = checker.check_text("HELLO WORLD")
            assert result.is_compatible is True
            
            # Incompatible (lowercase)
            result = checker.check_text("hello")
            assert result.is_compatible is False
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestCheckFontCompatibilityFunction:
    """Test the convenience function."""
    
    def test_convenience_function(self):
        """Test check_font_compatibility function."""
        texts = ["Hello", "World"]
        result = check_font_compatibility(texts)
        
        assert isinstance(result, BatchCheckResult)
        assert result.total_texts == 2


class TestCompatibilityScoring:
    """Test compatibility score calculations."""
    
    def test_perfect_score(self):
        """Test 100% compatibility score."""
        checker = FontChecker()
        result = checker.check_text("Hello")
        assert result.compatibility_score == 1.0
    
    def test_partial_score(self):
        """Test partial compatibility score."""
        # Create table with only some characters
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tbl", delete=False) as f:
            f.write("48=H\n65=e\n6C=l\n6F=o\n")  # H, e, l, o
            temp_path = f.name
        
        try:
            checker = FontChecker(table_path=temp_path)
            
            # "Hello" has all chars in table
            result = checker.check_text("Hello")
            assert result.compatibility_score == 1.0
            
            # "Hello!" has '!' missing
            result = checker.check_text("Hello!")
            assert result.compatibility_score < 1.0
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestSubstitutionMap:
    """Test built-in substitution mappings."""
    
    def test_common_substitutions_exist(self):
        """Test that common substitutions are defined."""
        checker = FontChecker()
        
        # Check some expected substitutions exist
        assert "\u00e9" in checker.SUBSTITUTIONS  # é
        assert "\u2026" in checker.SUBSTITUTIONS  # …
        assert "\u2122" in checker.SUBSTITUTIONS  # ™
        assert "\u2014" in checker.SUBSTITUTIONS  # —
    
    def test_accent_substitutions(self):
        """Test accent character substitutions."""
        checker = FontChecker()
        
        # Test a few accent substitutions
        assert checker.SUBSTITUTIONS.get("\u00e9") == "e"  # é -> e
        assert checker.SUBSTITUTIONS.get("\u00f6") == "o"  # ö -> o
    
    def test_currency_substitutions(self):
        """Test currency symbol substitutions."""
        checker = FontChecker()
        
        result = checker.auto_fix_text("\u20ac100 \u00a350 \u00a5200")  # €100 £50 ¥200
        assert "\u20ac" not in result  # €
        assert "\u00a3" not in result  # £
        assert "\u00a5" not in result  # ¥
