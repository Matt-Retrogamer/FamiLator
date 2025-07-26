"""
Automatic text pattern detection in ROM files.

Uses various heuristics to identify potential text regions.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from .encoding import EncodingTable
except ImportError:
    from encoding import EncodingTable


@dataclass
class TextCandidate:
    """Represents a potential text region in a ROM."""

    address: int
    length: int
    confidence: float
    sample_text: str
    encoding_used: str
    description: str = ""


class TextDetector:
    """Automatic detection of text patterns in ROM data."""

    def __init__(self, encoding_table: EncodingTable):
        """Initialize text detector.

        Args:
            encoding_table: Encoding table to use for detection
        """
        self.encoding_table = encoding_table
        self.min_string_length = 3
        self.max_string_length = 100
        self.confidence_threshold = 0.6

    def detect_text_regions(self, rom_data: bytes) -> List[TextCandidate]:
        """Detect potential text regions in ROM data.

        Args:
            rom_data: ROM file data

        Returns:
            List of text candidates sorted by confidence
        """
        candidates = []

        # Method 1: Entropy-based detection
        candidates.extend(self._detect_by_entropy(rom_data))

        # Method 2: Character frequency analysis
        candidates.extend(self._detect_by_frequency(rom_data))

        # Method 3: String terminator patterns
        candidates.extend(self._detect_by_terminators(rom_data))

        # Remove duplicates and sort by confidence
        candidates = self._deduplicate_candidates(candidates)
        candidates.sort(key=lambda x: x.confidence, reverse=True)

        return [c for c in candidates if c.confidence >= self.confidence_threshold]

    def _detect_by_entropy(self, rom_data: bytes) -> List[TextCandidate]:
        """Detect text using entropy analysis.

        Text typically has different entropy than graphics or code.
        """
        candidates = []
        window_size = 32
        step_size = 16

        for i in range(0, len(rom_data) - window_size, step_size):
            window = rom_data[i : i + window_size]
            entropy = self._calculate_entropy(window)

            # Text entropy is typically in a specific range
            if 2.0 < entropy < 6.0:  # Heuristic values
                confidence = self._calculate_text_confidence(window)
                if confidence > 0.3:
                    sample_text = self.encoding_table.decode_bytes(window, length=16)
                    candidates.append(
                        TextCandidate(
                            address=i,
                            length=window_size,
                            confidence=confidence,
                            sample_text=sample_text,
                            encoding_used="entropy_detection",
                            description=f"Entropy: {entropy:.2f}",
                        )
                    )

        return candidates

    def _detect_by_frequency(self, rom_data: bytes) -> List[TextCandidate]:
        """Detect text using character frequency analysis."""
        candidates = []

        # Common text characters (space, common letters)
        common_chars = set()
        for char in " ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            byte_val = self.encoding_table.encode_char(char)
            if byte_val is not None:
                common_chars.add(byte_val)

        if not common_chars:
            return candidates

        window_size = 20
        for i in range(0, len(rom_data) - window_size, 4):
            window = rom_data[i : i + window_size]

            # Count common characters
            common_count = sum(1 for byte in window if byte in common_chars)
            frequency_ratio = common_count / window_size

            if frequency_ratio > 0.4:  # At least 40% common characters
                confidence = min(frequency_ratio * 1.5, 1.0)
                sample_text = self.encoding_table.decode_bytes(window, length=16)
                candidates.append(
                    TextCandidate(
                        address=i,
                        length=window_size,
                        confidence=confidence,
                        sample_text=sample_text,
                        encoding_used="frequency_analysis",
                        description=f"Common chars: {frequency_ratio:.1%}",
                    )
                )

        return candidates

    def _detect_by_terminators(self, rom_data: bytes) -> List[TextCandidate]:
        """Detect text by looking for string terminators."""
        candidates = []

        # Common string terminators
        terminators = []
        for code_name in ["<END>", "<NULL>"]:
            for byte_val, code in self.encoding_table.control_codes.items():
                if code == code_name:
                    terminators.append(byte_val)

        # Also check for null bytes (0x00) and 0xFF
        terminators.extend([0x00, 0xFF])

        for terminator in terminators:
            for i, byte_val in enumerate(rom_data):
                if byte_val == terminator:
                    # Look backwards for potential string start
                    start = max(0, i - self.max_string_length)
                    potential_string = rom_data[start:i]

                    if len(potential_string) >= self.min_string_length:
                        confidence = self._calculate_text_confidence(potential_string)
                        if confidence > 0.4:
                            sample_text = self.encoding_table.decode_bytes(
                                potential_string
                            )
                            candidates.append(
                                TextCandidate(
                                    address=start,
                                    length=len(potential_string),
                                    confidence=confidence,
                                    sample_text=sample_text,
                                    encoding_used="terminator_detection",
                                    description=f"Terminator: 0x{terminator:02X}",
                                )
                            )

        return candidates

    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of byte sequence."""
        if len(data) == 0:
            return 0.0

        # Count byte frequencies
        frequencies = {}
        for byte in data:
            frequencies[byte] = frequencies.get(byte, 0) + 1

        # Calculate entropy
        entropy = 0.0
        data_len = len(data)
        for count in frequencies.values():
            probability = count / data_len
            if probability > 0:
                entropy -= probability * math.log2(probability)

        return entropy

    def _calculate_text_confidence(self, data: bytes) -> float:
        """Calculate confidence that data represents text."""
        if len(data) == 0:
            return 0.0

        score = 0.0
        total_chars = len(data)

        # Check for recognizable characters
        recognized_chars = 0
        control_codes = 0

        for byte in data:
            if byte in self.encoding_table.byte_to_char:
                recognized_chars += 1
                char = self.encoding_table.byte_to_char[byte]

                # Bonus for common text characters
                if char.isalpha() or char.isspace():
                    score += 0.1
                elif char in ".,!?":
                    score += 0.05

            elif byte in self.encoding_table.control_codes:
                control_codes += 1
                score += 0.05

        # Base score from recognition rate
        recognition_rate = (recognized_chars + control_codes) / total_chars
        score += recognition_rate * 0.8

        # Penalty for too many unrecognized bytes
        if recognition_rate < 0.5:
            score *= 0.5

        # Bonus for reasonable length
        if self.min_string_length <= total_chars <= 50:
            score += 0.1

        return min(score, 1.0)

    def _deduplicate_candidates(
        self, candidates: List[TextCandidate]
    ) -> List[TextCandidate]:
        """Remove overlapping or duplicate candidates."""
        if not candidates:
            return candidates

        # Sort by address
        candidates.sort(key=lambda x: x.address)

        result = []
        for candidate in candidates:
            # Check if this candidate overlaps significantly with existing ones
            overlaps = False
            for existing in result:
                overlap_start = max(candidate.address, existing.address)
                overlap_end = min(
                    candidate.address + candidate.length,
                    existing.address + existing.length,
                )
                overlap_length = max(0, overlap_end - overlap_start)

                # If more than 50% overlap, keep the higher confidence one
                if overlap_length > min(candidate.length, existing.length) * 0.5:
                    if candidate.confidence > existing.confidence:
                        result.remove(existing)
                    else:
                        overlaps = True
                    break

            if not overlaps:
                result.append(candidate)

        return result

    def analyze_rom(self, rom_path: str) -> Dict:
        """Analyze a ROM file and return text detection results.

        Args:
            rom_path: Path to ROM file

        Returns:
            Analysis results dictionary
        """
        rom_file = Path(rom_path)
        if not rom_file.exists():
            raise FileNotFoundError(f"ROM file not found: {rom_path}")

        with open(rom_file, "rb") as f:
            rom_data = f.read()

        candidates = self.detect_text_regions(rom_data)

        return {
            "rom_path": rom_path,
            "rom_size": len(rom_data),
            "candidates_found": len(candidates),
            "high_confidence": len([c for c in candidates if c.confidence > 0.8]),
            "medium_confidence": len(
                [c for c in candidates if 0.6 <= c.confidence <= 0.8]
            ),
            "candidates": candidates[:20],  # Top 20 candidates
        }
