"""
Font compatibility checker for NES/Famicom ROM translations.

Verifies that translated text can be rendered using the game's
available character set (as defined in the encoding table).

This prevents translation failures where characters don't exist
in the game's font/tile set.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from .encoding import EncodingTable
    from .chr_analyzer import CHRAnalyzer, CHRAnalysis, CHRType
except ImportError:
    from encoding import EncodingTable
    from chr_analyzer import CHRAnalyzer, CHRAnalysis, CHRType


@dataclass
class CharacterIssue:
    """Information about a problematic character."""
    character: str
    unicode_name: str
    occurrences: int
    suggested_replacement: Optional[str] = None
    context: str = ""  # Example usage


@dataclass
class FontCheckResult:
    """Result of checking text against available font."""
    text: str
    is_compatible: bool
    missing_chars: Set[str] = field(default_factory=set)
    issues: List[CharacterIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggested_text: Optional[str] = None
    compatibility_score: float = 1.0  # 0.0-1.0
    
    def get_summary(self) -> str:
        """Get human-readable summary."""
        if self.is_compatible:
            return f"✅ Text is compatible ({self.compatibility_score:.0%})"
        
        lines = [
            f"❌ Text has compatibility issues ({self.compatibility_score:.0%})",
            f"   Missing characters: {len(self.missing_chars)}",
        ]
        
        for issue in self.issues[:5]:  # Show first 5 issues
            lines.append(f"   • '{issue.character}' ({issue.unicode_name}) "
                        f"- {issue.occurrences} occurrences")
            if issue.suggested_replacement:
                lines.append(f"     → Suggested: '{issue.suggested_replacement}'")
        
        if len(self.issues) > 5:
            lines.append(f"   ... and {len(self.issues) - 5} more issues")
        
        if self.suggested_text:
            lines.append(f"\n   Suggested text: {self.suggested_text}")
        
        return "\n".join(lines)


@dataclass  
class BatchCheckResult:
    """Result of checking multiple texts."""
    total_texts: int
    compatible_count: int
    incompatible_count: int
    all_missing_chars: Set[str] = field(default_factory=set)
    results: List[FontCheckResult] = field(default_factory=list)
    overall_score: float = 1.0
    
    def get_summary(self) -> str:
        """Get summary of batch check."""
        return (
            f"Font Compatibility: {self.compatible_count}/{self.total_texts} texts OK "
            f"({self.overall_score:.0%})\n"
            f"Missing characters: {len(self.all_missing_chars)}"
        )


class FontChecker:
    """
    Checks if translated text can be rendered with the game's font.
    
    Uses the encoding table to determine available characters,
    and optionally analyzes CHR ROM for additional validation.
    """
    
    # Common character substitutions
    SUBSTITUTIONS: Dict[str, str] = {
        # Punctuation variants
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '—': '-',
        '–': '-',
        '…': '...',
        '×': 'x',
        '÷': '/',
        '·': '.',
        '•': '*',
        '→': '->',
        '←': '<-',
        '↑': '^',
        '↓': 'v',
        '★': '*',
        '☆': '*',
        '♪': '#',
        '♫': '#',
        '♥': '<3',
        '♦': '<>',
        '♠': 'S',
        '♣': 'C',
        
        # Accented characters to ASCII
        'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a', 'å': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'ô': 'o', 'ö': 'o', 'õ': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ý': 'y', 'ÿ': 'y',
        'ñ': 'n',
        'ç': 'c',
        'Á': 'A', 'À': 'A', 'Â': 'A', 'Ä': 'A', 'Ã': 'A', 'Å': 'A',
        'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
        'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
        'Ó': 'O', 'Ò': 'O', 'Ô': 'O', 'Ö': 'O', 'Õ': 'O',
        'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
        'Ý': 'Y',
        'Ñ': 'N',
        'Ç': 'C',
        
        # Currency
        '€': 'E',
        '£': 'L',
        '¥': 'Y',
        '¢': 'c',
        
        # Fractions
        '½': '1/2',
        '¼': '1/4',
        '¾': '3/4',
        
        # Math
        '±': '+/-',
        '≠': '!=',
        '≤': '<=',
        '≥': '>=',
        '∞': 'oo',
        
        # Other
        '©': '(c)',
        '®': '(R)',
        '™': '(TM)',
        '°': 'o',
        '№': 'No.',
    }
    
    def __init__(
        self,
        encoding_table: Optional[EncodingTable] = None,
        table_path: Optional[str] = None,
        chr_analysis: Optional[CHRAnalysis] = None,
    ):
        """
        Initialize font checker.
        
        Args:
            encoding_table: Pre-loaded encoding table
            table_path: Path to .tbl file (alternative to encoding_table)
            chr_analysis: Optional CHR ROM analysis for additional validation
        """
        if encoding_table:
            self.encoding = encoding_table
        elif table_path:
            self.encoding = EncodingTable(table_path)
        else:
            # Create empty table - will accept any character
            self.encoding = EncodingTable()
        
        self.chr_analysis = chr_analysis
        
        # Build set of available characters
        self.available_chars: Set[str] = set(self.encoding.char_to_byte.keys())
        
        # Add control code representations
        for code_str in self.encoding.control_codes.values():
            self.available_chars.add(code_str)
    
    def check_text(self, text: str, auto_fix: bool = False) -> FontCheckResult:
        """
        Check if text can be rendered with available font.
        
        Args:
            text: Text to check
            auto_fix: If True, generate suggested text with substitutions
            
        Returns:
            FontCheckResult with compatibility info
        """
        missing_chars: Set[str] = set()
        char_counts: Dict[str, int] = {}
        
        # Skip checking if no encoding table loaded
        if not self.available_chars:
            return FontCheckResult(
                text=text,
                is_compatible=True,
                warnings=["No encoding table loaded - skipping compatibility check"]
            )
        
        # Check each character
        for char in text:
            if char not in self.available_chars:
                # Check if it's part of a control code
                if not self._is_in_control_code(text, char):
                    missing_chars.add(char)
                    char_counts[char] = char_counts.get(char, 0) + 1
        
        # Build issue list
        issues: List[CharacterIssue] = []
        for char in sorted(missing_chars):
            issue = CharacterIssue(
                character=char,
                unicode_name=self._get_unicode_name(char),
                occurrences=char_counts[char],
                suggested_replacement=self.SUBSTITUTIONS.get(char),
                context=self._get_context(text, char)
            )
            issues.append(issue)
        
        # Calculate compatibility score
        if len(text) > 0:
            missing_count = sum(char_counts.values())
            score = 1.0 - (missing_count / len(text))
        else:
            score = 1.0
        
        # Generate suggested text if requested
        suggested: Optional[str] = None
        if auto_fix and missing_chars:
            suggested = self._auto_substitute(text)
        
        return FontCheckResult(
            text=text,
            is_compatible=len(missing_chars) == 0,
            missing_chars=missing_chars,
            issues=issues,
            compatibility_score=max(0.0, score),
            suggested_text=suggested
        )
    
    def check_batch(
        self,
        texts: List[str],
        auto_fix: bool = False
    ) -> BatchCheckResult:
        """
        Check multiple texts for font compatibility.
        
        Args:
            texts: List of texts to check
            auto_fix: If True, generate suggested texts
            
        Returns:
            BatchCheckResult with all results
        """
        results: List[FontCheckResult] = []
        all_missing: Set[str] = set()
        compatible_count = 0
        
        for text in texts:
            result = self.check_text(text, auto_fix)
            results.append(result)
            
            if result.is_compatible:
                compatible_count += 1
            
            all_missing.update(result.missing_chars)
        
        # Calculate overall score
        if results:
            overall_score = sum(r.compatibility_score for r in results) / len(results)
        else:
            overall_score = 1.0
        
        return BatchCheckResult(
            total_texts=len(texts),
            compatible_count=compatible_count,
            incompatible_count=len(texts) - compatible_count,
            all_missing_chars=all_missing,
            results=results,
            overall_score=overall_score
        )
    
    def auto_fix_text(self, text: str) -> str:
        """
        Automatically substitute incompatible characters.
        
        Args:
            text: Original text
            
        Returns:
            Text with substitutions applied
        """
        return self._auto_substitute(text)
    
    def add_substitution(self, char: str, replacement: str) -> None:
        """
        Add a custom character substitution.
        
        Args:
            char: Character to replace
            replacement: Replacement string
        """
        self.SUBSTITUTIONS[char] = replacement
    
    def get_available_chars(self) -> Set[str]:
        """Get set of all available characters."""
        return self.available_chars.copy()
    
    def get_missing_char_report(self, texts: List[str]) -> str:
        """
        Generate a report of all missing characters across texts.
        
        Args:
            texts: List of texts to analyze
            
        Returns:
            Formatted report string
        """
        result = self.check_batch(texts, auto_fix=True)
        
        lines = [
            "=" * 50,
            "Font Compatibility Report",
            "=" * 50,
            "",
            f"Total texts checked: {result.total_texts}",
            f"Compatible: {result.compatible_count}",
            f"Incompatible: {result.incompatible_count}",
            f"Overall score: {result.overall_score:.1%}",
            "",
        ]
        
        if result.all_missing_chars:
            lines.append("Missing Characters:")
            lines.append("-" * 30)
            
            # Collect all issues
            all_issues: Dict[str, CharacterIssue] = {}
            for r in result.results:
                for issue in r.issues:
                    if issue.character not in all_issues:
                        all_issues[issue.character] = issue
                    else:
                        all_issues[issue.character].occurrences += issue.occurrences
            
            for char in sorted(all_issues.keys()):
                issue = all_issues[char]
                line = f"  '{char}' (U+{ord(char):04X}) - {issue.occurrences}x"
                if issue.suggested_replacement:
                    line += f" → '{issue.suggested_replacement}'"
                lines.append(line)
        else:
            lines.append("✅ All characters are compatible!")
        
        lines.append("")
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def _is_in_control_code(self, text: str, char: str) -> bool:
        """Check if character is part of a control code like <END>."""
        # Find all control code patterns
        import re
        control_pattern = re.compile(r'<[^>]+>')
        
        for match in control_pattern.finditer(text):
            if char in match.group():
                return True
        
        return False
    
    def _get_unicode_name(self, char: str) -> str:
        """Get Unicode name for a character."""
        try:
            import unicodedata
            return unicodedata.name(char, f"U+{ord(char):04X}")
        except ValueError:
            return f"U+{ord(char):04X}"
    
    def _get_context(self, text: str, char: str) -> str:
        """Get context around a character occurrence."""
        idx = text.find(char)
        if idx < 0:
            return ""
        
        start = max(0, idx - 10)
        end = min(len(text), idx + 11)
        context = text[start:end]
        
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        
        return context
    
    def _auto_substitute(self, text: str) -> str:
        """Apply automatic substitutions to text."""
        result = text
        
        for char, replacement in self.SUBSTITUTIONS.items():
            if char in result:
                result = result.replace(char, replacement)
        
        return result


def check_font_compatibility(
    texts: List[str],
    table_path: Optional[str] = None,
    encoding_table: Optional[EncodingTable] = None,
) -> BatchCheckResult:
    """
    Convenience function to check font compatibility.
    
    Args:
        texts: List of texts to check
        table_path: Path to .tbl encoding file
        encoding_table: Pre-loaded encoding table
        
    Returns:
        BatchCheckResult with compatibility info
    """
    checker = FontChecker(
        encoding_table=encoding_table,
        table_path=table_path
    )
    return checker.check_batch(texts, auto_fix=True)


if __name__ == "__main__":
    import sys
    
    # Demo usage
    demo_texts = [
        "Hello World!",
        "Press START to begin…",
        "You found the Treasure™!",
        "Héllo Wörld!",
        "Score: 1,000,000",
    ]
    
    print("Font Compatibility Demo")
    print("=" * 40)
    print()
    
    # Check without table (accepts all)
    checker = FontChecker()
    result = checker.check_batch(demo_texts, auto_fix=True)
    print(result.get_summary())
    print()
    
    for r in result.results:
        print(f"'{r.text}'")
        print(f"  {r.get_summary()}")
        print()
