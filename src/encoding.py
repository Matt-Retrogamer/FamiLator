"""
Encoding table parser for .tbl files used in ROM hacking.

Handles both basic character mappings and advanced control codes.
"""

import re
from pathlib import Path
from typing import Dict, Optional, Tuple


class EncodingTable:
    """Parser and handler for .tbl encoding files."""

    def __init__(self, table_path: Optional[str] = None):
        """Initialize encoding table.

        Args:
            table_path: Path to .tbl file. If None, creates empty table.
        """
        self.byte_to_char: Dict[int, str] = {}
        self.char_to_byte: Dict[str, int] = {}
        self.control_codes: Dict[int, str] = {}
        self.multi_byte_patterns: Dict[str, str] = {}

        if table_path:
            self.load_table(table_path)

    def load_table(self, table_path: str) -> None:
        """Load encoding table from .tbl file.

        Args:
            table_path: Path to .tbl file

        Raises:
            FileNotFoundError: If table file doesn't exist
            ValueError: If table format is invalid
        """
        table_file = Path(table_path)
        if not table_file.exists():
            raise FileNotFoundError(f"Table file not found: {table_path}")

        with open(table_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.rstrip("\n\r")  # Only remove line endings, preserve spaces

                # Skip empty lines and comments
                if not line or line.lstrip().startswith("#"):
                    continue

                try:
                    self._parse_table_line(line)
                except Exception as e:
                    raise ValueError(f"Invalid table format at line {line_num}: {e}")

    def _parse_table_line(self, line: str) -> None:
        """Parse a single line from table file.

        Args:
            line: Line from .tbl file
        """
        if "=" not in line:
            return

        hex_part, char_part = line.split("=", 1)
        hex_part = hex_part.strip()
        # Handle inline comments after character mapping
        char_part = char_part.rstrip("\n\r")  # Only remove line endings

        # Remove inline comments but preserve the character mapping
        if "#" in char_part:
            char_part = char_part.split("#")[0].rstrip()

        # Handle multi-byte patterns (e.g., F0XX=<DELAY:XX>)
        if "XX" in hex_part or "YY" in hex_part:
            self.multi_byte_patterns[hex_part] = char_part
            return

        # Convert hex to int
        try:
            byte_value = int(hex_part, 16)
        except ValueError:
            raise ValueError(f"Invalid hex value: {hex_part}")

        # Handle control codes (e.g., <NEWLINE>, <END>)
        if char_part.startswith("<") and char_part.endswith(">"):
            self.control_codes[byte_value] = char_part
        else:
            # Regular character mapping
            self.byte_to_char[byte_value] = char_part
            # Add reverse mapping for all characters (including empty space)
            self.char_to_byte[char_part] = byte_value

    def decode_byte(self, byte_value: int) -> str:
        """Decode a single byte to character.

        Args:
            byte_value: Byte value to decode

        Returns:
            Decoded character or control code
        """
        if byte_value in self.control_codes:
            return self.control_codes[byte_value]
        elif byte_value in self.byte_to_char:
            return self.byte_to_char[byte_value]
        else:
            return f"<UNK:{byte_value:02X}>"

    def encode_char(self, char: str) -> Optional[int]:
        """Encode a character to byte value.

        Args:
            char: Character to encode

        Returns:
            Byte value or None if not found
        """
        return self.char_to_byte.get(char)

    def decode_bytes(
        self, data: bytes, start: int = 0, length: Optional[int] = None
    ) -> str:
        """Decode a sequence of bytes to string.

        Args:
            data: Byte data to decode
            start: Starting offset
            length: Number of bytes to decode (None for until end marker)

        Returns:
            Decoded string
        """
        result = []
        end = start + length if length else len(data)
        i = start

        while i < end:
            byte_val = data[i]
            decoded = self.decode_byte(byte_val)

            # Stop at end markers
            if decoded in ["<END>", "<NULL>"]:
                break

            result.append(decoded)
            i += 1

        return "".join(result)

    def encode_string(self, text: str) -> bytes:
        """Encode a string to bytes.

        Args:
            text: String to encode

        Returns:
            Encoded byte data

        Raises:
            ValueError: If string contains unrecognized characters
        """
        result = []

        i = 0
        while i < len(text):
            char = text[i]

            # Handle control codes
            if char == "<":
                end_bracket = text.find(">", i)
                if end_bracket != -1:
                    control_code = text[i : end_bracket + 1]
                    # Find byte value for this control code
                    for byte_val, code in self.control_codes.items():
                        if code == control_code:
                            result.append(byte_val)
                            break
                    else:
                        raise ValueError(f"Unknown control code: {control_code}")
                    i = end_bracket + 1
                    continue

            # Regular character
            byte_val = self.encode_char(char)
            if byte_val is None:
                raise ValueError(f"Cannot encode character: {char}")

            result.append(byte_val)
            i += 1

        return bytes(result)

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the loaded table.

        Returns:
            Dictionary with table statistics
        """
        return {
            "characters": len(self.byte_to_char),
            "control_codes": len(self.control_codes),
            "multi_byte_patterns": len(self.multi_byte_patterns),
            "total_mappings": len(self.byte_to_char) + len(self.control_codes),
        }
