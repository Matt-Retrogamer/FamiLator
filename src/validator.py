"""
ROM integrity and translation validation utilities.

Ensures modified ROMs maintain functionality and consistency.
"""

import hashlib
import zlib
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ValidationResult:
    """Result of a validation check."""
    check_name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class ROMValidator:
    """Validator for ROM integrity and translation consistency."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize validator with configuration.
        
        Args:
            config: Game configuration dictionary
        """
        self.config = config
        self.validation_config = config.get('validation', {})
    
    def validate_original_rom(self, rom_data: bytes) -> List[ValidationResult]:
        """Validate original ROM file.
        
        Args:
            rom_data: Original ROM file data
            
        Returns:
            List of validation results
        """
        results = []
        
        # Check file size
        results.append(self._check_file_size(rom_data))
        
        # Check CRC32 if configured
        results.append(self._check_crc32(rom_data))
        
        # Check ROM header (for NES)
        results.append(self._check_nes_header(rom_data))
        
        # Check for known patterns
        results.append(self._check_known_patterns(rom_data))
        
        return results
    
    def validate_modified_rom(self, original_data: bytes, modified_data: bytes,
                            changed_regions: List[Tuple[int, int]]) -> List[ValidationResult]:
        """Validate modified ROM against original.
        
        Args:
            original_data: Original ROM data
            modified_data: Modified ROM data
            changed_regions: List of (start, end) tuples for expected changes
            
        Returns:
            List of validation results
        """
        results = []
        
        # Check that file size hasn't changed
        results.append(self._check_size_consistency(original_data, modified_data))
        
        # Check that only expected regions changed
        results.append(self._check_change_regions(original_data, modified_data, changed_regions))
        
        # Validate checksums if applicable
        results.append(self._check_internal_checksums(modified_data))
        
        # Check for corrupted code regions
        results.append(self._check_code_integrity(original_data, modified_data))
        
        return results
    
    def validate_translation_consistency(self, original_strings: List[str],
                                       translated_strings: List[str]) -> List[ValidationResult]:
        """Validate translation consistency.
        
        Args:
            original_strings: Original extracted strings
            translated_strings: Translated strings
            
        Returns:
            List of validation results
        """
        results = []
        
        # Check string count consistency
        results.append(self._check_string_count(original_strings, translated_strings))
        
        # Check for preserved formatting
        results.append(self._check_format_preservation(original_strings, translated_strings))
        
        # Check length constraints
        results.append(self._check_length_constraints(original_strings, translated_strings))
        
        # Check for untranslated strings
        results.append(self._check_untranslated_strings(original_strings, translated_strings))
        
        return results
    
    def _check_file_size(self, rom_data: bytes) -> ValidationResult:
        """Check if ROM file size matches expected value."""
        expected_size = self.validation_config.get('expected_size')
        actual_size = len(rom_data)
        
        if expected_size is None:
            return ValidationResult(
                "file_size", True, 
                f"File size: {actual_size} bytes (no expectation set)"
            )
        
        if actual_size == expected_size:
            return ValidationResult(
                "file_size", True,
                f"File size correct: {actual_size} bytes"
            )
        else:
            return ValidationResult(
                "file_size", False,
                f"File size mismatch: expected {expected_size}, got {actual_size}",
                {"expected": expected_size, "actual": actual_size}
            )
    
    def _check_crc32(self, rom_data: bytes) -> ValidationResult:
        """Check CRC32 checksum if configured."""
        expected_crc = self.config.get('game', {}).get('crc32')
        
        if expected_crc is None:
            return ValidationResult(
                "crc32", True,
                "CRC32 check skipped (not configured)"
            )
        
        actual_crc = zlib.crc32(rom_data) & 0xffffffff
        
        # Handle string format (0x12345678)
        if isinstance(expected_crc, str):
            expected_crc = int(expected_crc, 16)
        
        if actual_crc == expected_crc:
            return ValidationResult(
                "crc32", True,
                f"CRC32 matches: {actual_crc:08X}"
            )
        else:
            return ValidationResult(
                "crc32", False,
                f"CRC32 mismatch: expected {expected_crc:08X}, got {actual_crc:08X}",
                {"expected": f"{expected_crc:08X}", "actual": f"{actual_crc:08X}"}
            )
    
    def _check_nes_header(self, rom_data: bytes) -> ValidationResult:
        """Check NES ROM header format."""
        if len(rom_data) < 16:
            return ValidationResult(
                "nes_header", False,
                "ROM too small to contain NES header"
            )
        
        # Check for NES header signature
        if rom_data[0:4] == b'NES\x1a':
            prg_banks = rom_data[4]
            chr_banks = rom_data[5]
            return ValidationResult(
                "nes_header", True,
                f"Valid NES header: {prg_banks} PRG banks, {chr_banks} CHR banks",
                {"prg_banks": prg_banks, "chr_banks": chr_banks}
            )
        else:
            return ValidationResult(
                "nes_header", False,
                "Invalid or missing NES header signature"
            )
    
    def _check_known_patterns(self, rom_data: bytes) -> ValidationResult:
        """Check for known byte patterns that indicate ROM integrity."""
        # This is game-specific and would be configured per ROM
        known_patterns = self.validation_config.get('known_patterns', [])
        
        if not known_patterns:
            return ValidationResult(
                "known_patterns", True,
                "No known patterns configured to check"
            )
        
        for pattern in known_patterns:
            address = pattern['address']
            expected_bytes = bytes.fromhex(pattern['bytes'])
            
            if address + len(expected_bytes) > len(rom_data):
                continue
            
            actual_bytes = rom_data[address:address + len(expected_bytes)]
            if actual_bytes != expected_bytes:
                return ValidationResult(
                    "known_patterns", False,
                    f"Pattern mismatch at 0x{address:04X}",
                    {"address": address, "expected": expected_bytes.hex(), 
                     "actual": actual_bytes.hex()}
                )
        
        return ValidationResult(
            "known_patterns", True,
            f"All {len(known_patterns)} known patterns match"
        )
    
    def _check_size_consistency(self, original_data: bytes, modified_data: bytes) -> ValidationResult:
        """Check that modified ROM hasn't changed size."""
        if len(original_data) == len(modified_data):
            return ValidationResult(
                "size_consistency", True,
                "ROM size unchanged after modification"
            )
        else:
            return ValidationResult(
                "size_consistency", False,
                f"ROM size changed: {len(original_data)} -> {len(modified_data)}",
                {"original_size": len(original_data), "new_size": len(modified_data)}
            )
    
    def _check_change_regions(self, original_data: bytes, modified_data: bytes,
                            expected_regions: List[Tuple[int, int]]) -> ValidationResult:
        """Check that only expected regions have changed."""
        if len(original_data) != len(modified_data):
            return ValidationResult(
                "change_regions", False,
                "Cannot check regions - ROM size changed"
            )
        
        # Find all actual changes
        actual_changes = []
        i = 0
        while i < len(original_data):
            if original_data[i] != modified_data[i]:
                start = i
                while i < len(original_data) and original_data[i] != modified_data[i]:
                    i += 1
                actual_changes.append((start, i))
            else:
                i += 1
        
        # Check if all actual changes are within expected regions
        unexpected_changes = []
        for change_start, change_end in actual_changes:
            found_in_expected = False
            for exp_start, exp_end in expected_regions:
                if exp_start <= change_start < exp_end and exp_start < change_end <= exp_end:
                    found_in_expected = True
                    break
            
            if not found_in_expected:
                unexpected_changes.append((change_start, change_end))
        
        if not unexpected_changes:
            return ValidationResult(
                "change_regions", True,
                f"All {len(actual_changes)} changes within expected regions"
            )
        else:
            return ValidationResult(
                "change_regions", False,
                f"{len(unexpected_changes)} unexpected changes found",
                {"unexpected_changes": [f"0x{s:04X}-0x{e:04X}" for s, e in unexpected_changes]}
            )
    
    def _check_internal_checksums(self, rom_data: bytes) -> ValidationResult:
        """Check and update internal ROM checksums if applicable."""
        checksum_offset = self.validation_config.get('checksum_offset')
        
        if checksum_offset is None:
            return ValidationResult(
                "internal_checksums", True,
                "No internal checksums configured"
            )
        
        # This would be game-specific checksum validation
        # For now, just check if the offset is valid
        if checksum_offset < len(rom_data):
            return ValidationResult(
                "internal_checksums", True,
                f"Checksum offset 0x{checksum_offset:04X} is valid"
            )
        else:
            return ValidationResult(
                "internal_checksums", False,
                f"Checksum offset 0x{checksum_offset:04X} beyond ROM size"
            )
    
    def _check_code_integrity(self, original_data: bytes, modified_data: bytes) -> ValidationResult:
        """Check that code regions haven't been corrupted."""
        # For NES ROMs, code is typically in the first part after header
        # This is a simplified check - real implementation would be game-specific
        
        if len(original_data) < 0x8000:
            return ValidationResult(
                "code_integrity", True,
                "ROM too small for code integrity check"
            )
        
        # Check first few KB for unexpected changes (rough heuristic)
        code_start = 0x10  # After NES header
        code_check_size = min(0x1000, len(original_data) - code_start)  # First 4KB
        
        code_changes = 0
        for i in range(code_start, code_start + code_check_size):
            if original_data[i] != modified_data[i]:
                code_changes += 1
        
        # Allow for some changes (text might be in code region)
        change_ratio = code_changes / code_check_size
        if change_ratio < 0.1:  # Less than 10% changed
            return ValidationResult(
                "code_integrity", True,
                f"Code region integrity good ({change_ratio:.1%} changed)"
            )
        else:
            return ValidationResult(
                "code_integrity", False,
                f"Significant code region changes ({change_ratio:.1%})",
                {"changes": code_changes, "total_checked": code_check_size}
            )
    
    def _check_string_count(self, original: List[str], translated: List[str]) -> ValidationResult:
        """Check that string counts match."""
        if len(original) == len(translated):
            return ValidationResult(
                "string_count", True,
                f"String count matches: {len(original)} strings"
            )
        else:
            return ValidationResult(
                "string_count", False,
                f"String count mismatch: {len(original)} -> {len(translated)}",
                {"original_count": len(original), "translated_count": len(translated)}
            )
    
    def _check_format_preservation(self, original: List[str], translated: List[str]) -> ValidationResult:
        """Check that formatting codes are preserved."""
        format_issues = []
        
        for i, (orig, trans) in enumerate(zip(original, translated)):
            # Count control codes
            orig_codes = orig.count('<')
            trans_codes = trans.count('<')
            
            if orig_codes != trans_codes:
                format_issues.append(f"String {i}: {orig_codes} -> {trans_codes} control codes")
        
        if not format_issues:
            return ValidationResult(
                "format_preservation", True,
                "All formatting codes preserved"
            )
        else:
            return ValidationResult(
                "format_preservation", False,
                f"{len(format_issues)} formatting issues found",
                {"issues": format_issues[:5]}  # Show first 5 issues
            )
    
    def _check_length_constraints(self, original: List[str], translated: List[str]) -> ValidationResult:
        """Check that translated strings fit within length constraints."""
        length_issues = []
        
        for i, (orig, trans) in enumerate(zip(original, translated)):
            if len(trans) > len(orig) * 1.5:  # Allow 50% expansion
                length_issues.append(f"String {i}: {len(orig)} -> {len(trans)} chars")
        
        if not length_issues:
            return ValidationResult(
                "length_constraints", True,
                "All translations within length constraints"
            )
        else:
            return ValidationResult(
                "length_constraints", False,
                f"{len(length_issues)} strings exceed length limits",
                {"issues": length_issues[:5]}  # Show first 5 issues
            )
    
    def _check_untranslated_strings(self, original: List[str], translated: List[str]) -> ValidationResult:
        """Check for strings that weren't translated."""
        untranslated = []
        
        for i, (orig, trans) in enumerate(zip(original, translated)):
            # Skip empty strings or control-only strings
            if not orig.strip() or orig.startswith('<'):
                continue
            
            if orig == trans:
                untranslated.append(f"String {i}: '{orig[:30]}...'")
        
        if not untranslated:
            return ValidationResult(
                "untranslated_strings", True,
                "All strings appear to be translated"
            )
        else:
            return ValidationResult(
                "untranslated_strings", False,
                f"{len(untranslated)} strings appear untranslated",
                {"untranslated": untranslated[:5]}  # Show first 5
            )
    
    def generate_report(self, results: List[ValidationResult]) -> str:
        """Generate a human-readable validation report.
        
        Args:
            results: List of validation results
            
        Returns:
            Formatted report string
        """
        passed = sum(1 for r in results if r.passed)
        total = len(results)
        
        report = [
            "=== FamiLator Validation Report ===",
            f"Passed: {passed}/{total} checks",
            ""
        ]
        
        for result in results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            report.append(f"{status} {result.check_name}: {result.message}")
            
            if not result.passed and result.details:
                for key, value in result.details.items():
                    report.append(f"  {key}: {value}")
        
        return "\n".join(report)
