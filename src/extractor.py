"""
Text extraction from ROM files using configuration-driven approach.

Supports both fixed-location and pointer-table based extraction.
"""

import json
import csv
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import yaml

try:
    from .encoding import EncodingTable
    from .detector import TextDetector
except ImportError:
    # Handle case when run as script
    from encoding import EncodingTable
    from detector import TextDetector


@dataclass
class ExtractedString:
    """Represents an extracted text string with metadata."""
    address: int
    original_bytes: bytes
    decoded_text: str
    length: int
    description: str = ""
    pointer_address: Optional[int] = None
    string_id: Optional[str] = None


class TextExtractor:
    """Extract text from ROM files using various methods."""
    
    def __init__(self, config_path: str):
        """Initialize text extractor with configuration.
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config = self._load_config(config_path)
        self.encoding_table = EncodingTable(self.config['text_detection']['encoding_table'])
        self.detector = TextDetector(self.encoding_table)
        self.extracted_strings: List[ExtractedString] = []
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration dictionary
        """
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def extract_from_rom(self, rom_path: str) -> List[ExtractedString]:
        """Extract text from ROM using configured method.
        
        Args:
            rom_path: Path to ROM file
            
        Returns:
            List of extracted strings
        """
        rom_file = Path(rom_path)
        if not rom_file.exists():
            raise FileNotFoundError(f"ROM file not found: {rom_path}")
        
        with open(rom_file, 'rb') as f:
            rom_data = f.read()
        
        # Validate ROM
        self._validate_rom(rom_data)
        
        # Extract based on configured method
        method = self.config['text_detection']['method']
        
        if method == 'fixed_locations':
            self.extracted_strings = self._extract_fixed_locations(rom_data)
        elif method == 'pointer_table':
            self.extracted_strings = self._extract_pointer_table(rom_data)
        elif method == 'auto_detect':
            self.extracted_strings = self._extract_auto_detect(rom_data)
        else:
            raise ValueError(f"Unknown extraction method: {method}")
        
        return self.extracted_strings
    
    def _validate_rom(self, rom_data: bytes) -> None:
        """Validate ROM file matches configuration expectations.
        
        Args:
            rom_data: ROM file data
            
        Raises:
            ValueError: If ROM doesn't match expected format
        """
        validation_config = self.config.get('validation', {})
        
        # Check file size
        expected_size = validation_config.get('expected_size')
        if expected_size and len(rom_data) != expected_size:
            raise ValueError(f"ROM size mismatch: expected {expected_size}, got {len(rom_data)}")
        
        # Check CRC32 if provided
        crc32 = self.config.get('game', {}).get('crc32')
        if crc32:
            import zlib
            actual_crc = zlib.crc32(rom_data) & 0xffffffff
            expected_crc = int(crc32, 16) if isinstance(crc32, str) else crc32
            if actual_crc != expected_crc:
                print(f"Warning: CRC32 mismatch. Expected {expected_crc:08X}, got {actual_crc:08X}")
    
    def _extract_fixed_locations(self, rom_data: bytes) -> List[ExtractedString]:
        """Extract text from fixed memory locations.
        
        Args:
            rom_data: ROM file data
            
        Returns:
            List of extracted strings
        """
        strings = []
        string_configs = self.config['text_detection'].get('strings', [])
        
        for i, string_config in enumerate(string_configs):
            address = string_config['address']
            length = string_config.get('length')
            description = string_config.get('description', f'String {i+1}')
            
            if address >= len(rom_data):
                print(f"Warning: Address 0x{address:04X} is beyond ROM size")
                continue
            
            # Extract bytes
            if length:
                end_address = min(address + length, len(rom_data))
                original_bytes = rom_data[address:end_address]
            else:
                # Extract until terminator
                original_bytes = self._extract_until_terminator(rom_data, address)
            
            if original_bytes:
                decoded_text = self.encoding_table.decode_bytes(original_bytes)
                strings.append(ExtractedString(
                    address=address,
                    original_bytes=original_bytes,
                    decoded_text=decoded_text,
                    length=len(original_bytes),
                    description=description,
                    string_id=f"string_{i+1:03d}"
                ))
        
        return strings
    
    def _extract_pointer_table(self, rom_data: bytes) -> List[ExtractedString]:
        """Extract text using pointer table method.
        
        Args:
            rom_data: ROM file data
            
        Returns:
            List of extracted strings
        """
        strings = []
        pointer_config = self.config['text_detection']['pointer_table']
        
        table_address = pointer_config['address']
        pointer_count = pointer_config['count']
        pointer_format = pointer_config.get('format', 'little_endian_16bit')
        base_offset = pointer_config.get('base_offset', 0)
        
        # Read pointer table
        pointers = self._read_pointer_table(
            rom_data, table_address, pointer_count, pointer_format, base_offset
        )
        
        # Extract strings from each pointer
        for i, pointer in enumerate(pointers):
            if pointer >= len(rom_data):
                print(f"Warning: Pointer {i} (0x{pointer:04X}) is beyond ROM size")
                continue
            
            original_bytes = self._extract_until_terminator(rom_data, pointer)
            if original_bytes:
                decoded_text = self.encoding_table.decode_bytes(original_bytes)
                strings.append(ExtractedString(
                    address=pointer,
                    original_bytes=original_bytes,
                    decoded_text=decoded_text,
                    length=len(original_bytes),
                    description=f"Pointer table string {i+1}",
                    pointer_address=table_address + (i * 2),  # Assuming 16-bit pointers
                    string_id=f"ptr_{i+1:03d}"
                ))
        
        return strings
    
    def _extract_auto_detect(self, rom_data: bytes) -> List[ExtractedString]:
        """Extract text using automatic detection.
        
        Args:
            rom_data: ROM file data
            
        Returns:
            List of extracted strings
        """
        candidates = self.detector.detect_text_regions(rom_data)
        strings = []
        
        for i, candidate in enumerate(candidates):
            original_bytes = rom_data[candidate.address:candidate.address + candidate.length]
            
            strings.append(ExtractedString(
                address=candidate.address,
                original_bytes=original_bytes,
                decoded_text=candidate.sample_text,
                length=candidate.length,
                description=f"Auto-detected (confidence: {candidate.confidence:.2f})",
                string_id=f"auto_{i+1:03d}"
            ))
        
        return strings
    
    def _read_pointer_table(self, rom_data: bytes, address: int, count: int, 
                           format_type: str, base_offset: int) -> List[int]:
        """Read pointer table from ROM.
        
        Args:
            rom_data: ROM file data
            address: Pointer table address
            count: Number of pointers
            format_type: Pointer format ('little_endian_16bit', etc.)
            base_offset: Offset to add to each pointer
            
        Returns:
            List of pointer addresses
        """
        pointers = []
        
        if format_type == 'little_endian_16bit':
            for i in range(count):
                ptr_addr = address + (i * 2)
                if ptr_addr + 1 < len(rom_data):
                    low = rom_data[ptr_addr]
                    high = rom_data[ptr_addr + 1]
                    pointer = (high << 8) | low
                    pointers.append(pointer + base_offset)
        
        elif format_type == 'big_endian_16bit':
            for i in range(count):
                ptr_addr = address + (i * 2)
                if ptr_addr + 1 < len(rom_data):
                    high = rom_data[ptr_addr]
                    low = rom_data[ptr_addr + 1]
                    pointer = (high << 8) | low
                    pointers.append(pointer + base_offset)
        
        else:
            raise ValueError(f"Unsupported pointer format: {format_type}")
        
        return pointers
    
    def _extract_until_terminator(self, rom_data: bytes, start_address: int) -> bytes:
        """Extract bytes until a terminator is found.
        
        Args:
            rom_data: ROM file data
            start_address: Starting address
            
        Returns:
            Extracted bytes (excluding terminator)
        """
        # Common terminators
        terminators = {0x00, 0xFF}
        
        # Add control code terminators
        for byte_val, code in self.encoding_table.control_codes.items():
            if code in ['<END>', '<NULL>']:
                terminators.add(byte_val)
        
        current_pos = start_address
        while current_pos < len(rom_data):
            if rom_data[current_pos] in terminators:
                break
            current_pos += 1
        
        return rom_data[start_address:current_pos]
    
    def export_to_csv(self, output_path: str) -> None:
        """Export extracted strings to CSV file.
        
        Args:
            output_path: Path for output CSV file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['string_id', 'address', 'length', 'original_text', 
                         'translated_text', 'description', 'pointer_address']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for string in self.extracted_strings:
                writer.writerow({
                    'string_id': string.string_id,
                    'address': f"0x{string.address:04X}",
                    'length': string.length,
                    'original_text': string.decoded_text,
                    'translated_text': '',  # Empty for translation
                    'description': string.description,
                    'pointer_address': f"0x{string.pointer_address:04X}" if string.pointer_address else ''
                })
    
    def export_to_json(self, output_path: str) -> None:
        """Export extracted strings to JSON file.
        
        Args:
            output_path: Path for output JSON file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to serializable format
        data = {
            'game_info': self.config.get('game', {}),
            'extraction_method': self.config['text_detection']['method'],
            'strings': []
        }
        
        for string in self.extracted_strings:
            string_data = asdict(string)
            # Convert bytes to hex string for JSON serialization
            string_data['original_bytes'] = string.original_bytes.hex()
            data['strings'].append(string_data)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get extraction statistics.
        
        Returns:
            Statistics dictionary
        """
        if not self.extracted_strings:
            return {'total_strings': 0}
        
        total_chars = sum(len(s.decoded_text) for s in self.extracted_strings)
        avg_length = total_chars / len(self.extracted_strings)
        
        return {
            'total_strings': len(self.extracted_strings),
            'total_characters': total_chars,
            'average_length': round(avg_length, 1),
            'shortest_string': min(len(s.decoded_text) for s in self.extracted_strings),
            'longest_string': max(len(s.decoded_text) for s in self.extracted_strings),
            'encoding_table_stats': self.encoding_table.get_stats()
        }
