"""
Table Builder - Manual-assist tool for creating encoding tables.

Helps users visually map CHR tiles to characters by displaying the tiles
and allowing them to assign character values.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TableMapping:
    """A single byte-to-character mapping."""
    
    byte_value: int
    character: str
    tile_index: Optional[int] = None  # CHR tile index if known
    description: str = ""


@dataclass
class TableBuilderResult:
    """Result of table building/saving."""
    
    table_path: str
    mappings_count: int
    control_codes_count: int
    success: bool
    message: str


@dataclass
class TableData:
    """Complete table data for editing."""
    
    name: str
    mappings: Dict[int, str] = field(default_factory=dict)  # byte -> char
    control_codes: Dict[int, str] = field(default_factory=dict)  # byte -> code
    description: str = ""
    

class TableBuilder:
    """
    Manual-assist tool for creating encoding tables from CHR tile analysis.
    
    Workflow:
    1. User views CHR tiles in the tile browser
    2. User identifies font regions and assigns characters to tile indices
    3. Tool generates .tbl file with correct byte mappings
    
    This is a manual process because NES games use completely custom
    encodings - there's no standard mapping we can auto-detect.
    """
    
    def __init__(self, output_dir: str = "tables"):
        """Initialize table builder.
        
        Args:
            output_dir: Directory for generated table files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def create_table(
        self,
        game_name: str,
        mappings: Dict[int, str],
        control_codes: Optional[Dict[int, str]] = None,
        description: str = "",
    ) -> TableBuilderResult:
        """
        Create a new .tbl file from user-provided mappings.
        
        Args:
            game_name: Name for the table file
            mappings: Dict of byte_value -> character
            control_codes: Optional dict of byte_value -> control code (e.g., "<END>")
            description: Optional description for the table header
            
        Returns:
            TableBuilderResult with status and path
        """
        if not mappings and not control_codes:
            return TableBuilderResult(
                table_path="",
                mappings_count=0,
                control_codes_count=0,
                success=False,
                message="No mappings provided",
            )
        
        mappings = mappings or {}
        control_codes = control_codes or {}
        
        # Sanitize filename
        safe_name = self._sanitize_filename(game_name)
        table_path = self.output_dir / f"{safe_name}.tbl"
        
        try:
            self._write_table_file(
                table_path, mappings, control_codes, game_name, description
            )
            
            logger.info(f"Created table {table_path} with {len(mappings)} mappings")
            
            return TableBuilderResult(
                table_path=str(table_path),
                mappings_count=len(mappings),
                control_codes_count=len(control_codes),
                success=True,
                message=f"Table saved to {table_path}",
            )
            
        except Exception as e:
            logger.exception(f"Error creating table for {game_name}")
            return TableBuilderResult(
                table_path="",
                mappings_count=0,
                control_codes_count=0,
                success=False,
                message=str(e),
            )
    
    def load_table(self, table_path: str) -> Optional[TableData]:
        """
        Load an existing table for editing.
        
        Args:
            table_path: Path to .tbl file
            
        Returns:
            TableData or None if load fails
        """
        path = Path(table_path)
        if not path.exists():
            logger.error(f"Table file not found: {table_path}")
            return None
        
        mappings = {}
        control_codes = {}
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue
                    
                    if "=" not in line:
                        continue
                    
                    hex_part, char_part = line.split("=", 1)
                    hex_part = hex_part.strip()
                    
                    # Handle inline comments
                    if "#" in char_part:
                        char_part = char_part.split("#")[0]
                    char_part = char_part.rstrip()
                    
                    try:
                        byte_value = int(hex_part, 16)
                    except ValueError:
                        continue
                    
                    # Determine if it's a control code or regular char
                    if char_part.startswith("<") and char_part.endswith(">"):
                        control_codes[byte_value] = char_part
                    else:
                        mappings[byte_value] = char_part
            
            return TableData(
                name=path.stem,
                mappings=mappings,
                control_codes=control_codes,
            )
            
        except Exception as e:
            logger.exception(f"Error loading table {table_path}")
            return None
    
    def update_table(
        self,
        table_path: str,
        mappings: Dict[int, str],
        control_codes: Optional[Dict[int, str]] = None,
    ) -> TableBuilderResult:
        """
        Update an existing table with new mappings.
        
        Args:
            table_path: Path to existing .tbl file
            mappings: New or updated mappings
            control_codes: New or updated control codes
            
        Returns:
            TableBuilderResult with status
        """
        path = Path(table_path)
        
        # Load existing data if file exists
        existing = self.load_table(table_path)
        if existing:
            # Merge with existing mappings (new values override)
            existing.mappings.update(mappings)
            if control_codes:
                existing.control_codes.update(control_codes)
            final_mappings = existing.mappings
            final_codes = existing.control_codes
        else:
            final_mappings = mappings
            final_codes = control_codes or {}
        
        return self.create_table(
            path.stem,
            final_mappings,
            final_codes,
            description=f"Updated table for {path.stem}",
        )
    
    def get_common_presets(self) -> Dict[str, Dict[int, str]]:
        """
        Get common character mapping presets to help users get started.
        
        Returns:
            Dict of preset_name -> mappings
        """
        return {
            "ascii_uppercase_from_0": {
                i: chr(ord('A') + i) for i in range(26)
            },
            "ascii_lowercase_from_0": {
                i: chr(ord('a') + i) for i in range(26)
            },
            "digits_from_0": {
                i: str(i) for i in range(10)
            },
            "common_control_codes": {
                0xFE: "<NEWLINE>",
                0xFF: "<END>",
                0xFD: "<WAIT>",
                0xFC: "<CLEAR>",
            },
        }
    
    def apply_preset(
        self,
        preset_name: str,
        start_byte: int = 0,
    ) -> Dict[int, str]:
        """
        Get a preset mapping adjusted to start at a specific byte.
        
        Args:
            preset_name: Name of the preset
            start_byte: Starting byte value for the mapping
            
        Returns:
            Dict of byte_value -> character
        """
        presets = self.get_common_presets()
        if preset_name not in presets:
            return {}
        
        base_preset = presets[preset_name]
        
        # Adjust byte values to start at start_byte
        return {
            (start_byte + k): v
            for k, v in base_preset.items()
        }
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize game name for use as filename."""
        safe = name.lower()
        for char in " -()[]{}!@#$%^&*+=<>?,./\\|\"':;":
            safe = safe.replace(char, "_")
        while "__" in safe:
            safe = safe.replace("__", "_")
        return safe.strip("_")
    
    def _write_table_file(
        self,
        path: Path,
        mappings: Dict[int, str],
        control_codes: Dict[int, str],
        game_name: str,
        description: str,
    ) -> None:
        """Write encoding table to file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Encoding table for: {game_name}\n")
            if description:
                f.write(f"# {description}\n")
            f.write("# Created with FamiLator Table Builder\n")
            f.write("#\n")
            f.write("# Format: HexByte=Character\n")
            f.write("# Control codes use angle brackets: FF=<END>\n")
            f.write("#\n\n")
            
            # Write control codes first
            if control_codes:
                f.write("# Control Codes\n")
                for byte_val in sorted(control_codes.keys()):
                    f.write(f"{byte_val:02X}={control_codes[byte_val]}\n")
                f.write("\n")
            
            # Group and write character mappings
            if mappings:
                # Separate by type
                letters = {}
                digits = {}
                punctuation = {}
                japanese = {}
                other = {}
                
                for byte_val, char in mappings.items():
                    if char.isalpha() and ord(char) < 128:
                        letters[byte_val] = char
                    elif char.isdigit():
                        digits[byte_val] = char
                    elif char in " !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~":
                        punctuation[byte_val] = char
                    elif ord(char) > 127:
                        japanese[byte_val] = char
                    else:
                        other[byte_val] = char
                
                if letters:
                    f.write("# Letters\n")
                    for byte_val in sorted(letters.keys()):
                        f.write(f"{byte_val:02X}={letters[byte_val]}\n")
                    f.write("\n")
                
                if digits:
                    f.write("# Digits\n")
                    for byte_val in sorted(digits.keys()):
                        f.write(f"{byte_val:02X}={digits[byte_val]}\n")
                    f.write("\n")
                
                if punctuation:
                    f.write("# Punctuation\n")
                    for byte_val in sorted(punctuation.keys()):
                        char = punctuation[byte_val]
                        if char == " ":
                            f.write(f"{byte_val:02X}=  # space\n")
                        else:
                            f.write(f"{byte_val:02X}={char}\n")
                    f.write("\n")
                
                if japanese:
                    f.write("# Japanese Characters\n")
                    for byte_val in sorted(japanese.keys()):
                        f.write(f"{byte_val:02X}={japanese[byte_val]}\n")
                    f.write("\n")
                
                if other:
                    f.write("# Other Characters\n")
                    for byte_val in sorted(other.keys()):
                        f.write(f"{byte_val:02X}={other[byte_val]}\n")
