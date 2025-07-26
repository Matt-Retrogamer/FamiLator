"""
Text reinsertion into ROM files with pointer updates and validation.

Handles the complex process of putting translated text back into ROMs.
"""

import csv
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

try:
    from .encoding import EncodingTable
    from .pointer_utils import PointerUtils, PointerInfo
    from .validator import ROMValidator
except ImportError:
    from encoding import EncodingTable
    from pointer_utils import PointerUtils, PointerInfo
    from validator import ROMValidator


@dataclass
class TranslatedString:
    """Represents a translated string ready for reinsertion."""
    string_id: str
    address: int
    original_text: str
    translated_text: str
    original_bytes: bytes
    translated_bytes: bytes
    pointer_address: Optional[int] = None
    description: str = ""


class TextReinjector:
    """Reinsert translated text into ROM files."""
    
    def __init__(self, config_path: str):
        """Initialize text reinjector with configuration.
        
        Args:
            config_path: Path to YAML configuration file
        """
        import yaml
        
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.encoding_table = EncodingTable(self.config['text_detection']['encoding_table'])
        self.validator = ROMValidator(self.config)
        self.translated_strings: List[TranslatedString] = []
    
    def load_translations_from_csv(self, csv_path: str) -> None:
        """Load translated strings from CSV file.
        
        Args:
            csv_path: Path to CSV file with translations
        """
        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"Translation CSV not found: {csv_path}")
        
        self.translated_strings = []
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Skip rows without translations
                if not row.get('translated_text') or row['translated_text'].strip() == '':
                    continue
                
                try:
                    # Parse address
                    address_str = row['address'].replace('0x', '')
                    address = int(address_str, 16)
                    
                    # Parse pointer address if present
                    pointer_address = None
                    if row.get('pointer_address') and row['pointer_address'].strip():
                        ptr_str = row['pointer_address'].replace('0x', '')
                        pointer_address = int(ptr_str, 16)
                    
                    # Encode original and translated text
                    original_bytes = self.encoding_table.encode_string(row['original_text'])
                    translated_bytes = self.encoding_table.encode_string(row['translated_text'])
                    
                    self.translated_strings.append(TranslatedString(
                        string_id=row['string_id'],
                        address=address,
                        original_text=row['original_text'],
                        translated_text=row['translated_text'],
                        original_bytes=original_bytes,
                        translated_bytes=translated_bytes,
                        pointer_address=pointer_address,
                        description=row.get('description', '')
                    ))
                    
                except Exception as e:
                    print(f"Warning: Skipping row {row.get('string_id', '?')}: {e}")
    
    def load_translations_from_json(self, json_path: str) -> None:
        """Load translated strings from JSON file.
        
        Args:
            json_path: Path to JSON file with translations
        """
        json_file = Path(json_path)
        if not json_file.exists():
            raise FileNotFoundError(f"Translation JSON not found: {json_path}")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.translated_strings = []
        
        for string_data in data.get('strings', []):
            # Skip if no translation provided
            if 'translated_text' not in string_data:
                continue
            
            try:
                # Convert hex string back to bytes
                original_bytes = bytes.fromhex(string_data['original_bytes'])
                translated_bytes = self.encoding_table.encode_string(string_data['translated_text'])
                
                self.translated_strings.append(TranslatedString(
                    string_id=string_data['string_id'],
                    address=string_data['address'],
                    original_text=string_data['decoded_text'],
                    translated_text=string_data['translated_text'],
                    original_bytes=original_bytes,
                    translated_bytes=translated_bytes,
                    pointer_address=string_data.get('pointer_address'),
                    description=string_data.get('description', '')
                ))
                
            except Exception as e:
                print(f"Warning: Skipping string {string_data.get('string_id', '?')}: {e}")
    
    def reinject_into_rom(self, input_rom_path: str, output_rom_path: str) -> Dict[str, Any]:
        """Reinject translated text into ROM file.
        
        Args:
            input_rom_path: Path to original ROM file
            output_rom_path: Path for output ROM file
            
        Returns:
            Dictionary with reinsertion results
        """
        # Load original ROM
        input_file = Path(input_rom_path)
        if not input_file.exists():
            raise FileNotFoundError(f"Input ROM not found: {input_rom_path}")
        
        with open(input_file, 'rb') as f:
            original_data = f.read()
        
        # Create mutable copy
        modified_data = bytearray(original_data)
        
        # Validate original ROM
        validation_results = self.validator.validate_original_rom(original_data)
        
        # Perform reinsertion
        reinsertion_method = self.config['text_detection']['method']
        
        if reinsertion_method == 'fixed_locations':
            results = self._reinject_fixed_locations(modified_data)
        elif reinsertion_method == 'pointer_table':
            results = self._reinject_pointer_table(modified_data)
        else:
            raise ValueError(f"Unsupported reinsertion method: {reinsertion_method}")
        
        # Validate modified ROM
        changed_regions = [(s.address, s.address + len(s.translated_bytes)) 
                          for s in self.translated_strings]
        
        validation_results.extend(
            self.validator.validate_modified_rom(original_data, bytes(modified_data), changed_regions)
        )
        
        # Write output ROM
        output_file = Path(output_rom_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'wb') as f:
            f.write(modified_data)
        
        return {
            'input_rom': input_rom_path,
            'output_rom': output_rom_path,
            'strings_processed': len(self.translated_strings),
            'validation_results': validation_results,
            'reinsertion_results': results
        }
    
    def _reinject_fixed_locations(self, rom_data: bytearray) -> Dict[str, Any]:
        """Reinject text using fixed location method.
        
        Args:
            rom_data: ROM data to modify
            
        Returns:
            Reinsertion results
        """
        results = {
            'method': 'fixed_locations',
            'successful': 0,
            'failed': 0,
            'issues': []
        }
        
        for string in self.translated_strings:
            try:
                # Check if translated text fits in original space
                if len(string.translated_bytes) > len(string.original_bytes):
                    # Try to find space or truncate
                    if self._can_expand_string(rom_data, string):
                        self._expand_string_space(rom_data, string)
                    else:
                        # Truncate translation to fit
                        max_length = len(string.original_bytes)
                        truncated_text = self._truncate_translation(string.translated_text, max_length)
                        string.translated_bytes = self.encoding_table.encode_string(truncated_text)
                        results['issues'].append(
                            f"String {string.string_id} truncated to fit space"
                        )
                
                # Write translated bytes
                end_addr = string.address + len(string.translated_bytes)
                rom_data[string.address:end_addr] = string.translated_bytes
                
                # Add terminator if there's space
                if end_addr < len(rom_data):
                    # Find appropriate terminator
                    terminator = 0xFF  # Default
                    for byte_val, code in self.encoding_table.control_codes.items():
                        if code == '<END>':
                            terminator = byte_val
                            break
                    
                    rom_data[end_addr] = terminator
                
                results['successful'] += 1
                
            except Exception as e:
                results['failed'] += 1
                results['issues'].append(f"String {string.string_id}: {e}")
        
        return results
    
    def _reinject_pointer_table(self, rom_data: bytearray) -> Dict[str, Any]:
        """Reinject text using pointer table method.
        
        Args:
            rom_data: ROM data to modify
            
        Returns:
            Reinsertion results
        """
        results = {
            'method': 'pointer_table',
            'successful': 0,
            'failed': 0,
            'issues': [],
            'pointers_updated': 0
        }
        
        # Read pointer configuration
        pointer_config = self.config['text_detection']['pointer_table']
        
        # Read existing pointer table
        pointers = PointerUtils.read_pointer_table(
            bytes(rom_data),
            pointer_config['address'],
            pointer_config['count'],
            pointer_config.get('format', 'little_endian_16bit'),
            pointer_config.get('base_offset', 0)
        )
        
        # Group strings by their current addresses
        strings_by_address = {s.address: s for s in self.translated_strings}
        
        # Prepare new string data
        new_strings_data = []
        for pointer in pointers:
            if pointer.target_address in strings_by_address:
                string = strings_by_address[pointer.target_address]
                # Add terminator to string data
                string_data = string.translated_bytes + b'\xFF'  # Default terminator
                new_strings_data.append(string_data)
            else:
                # Extract original string data
                original_data = self._extract_original_string(rom_data, pointer.target_address)
                new_strings_data.append(original_data)
        
        try:
            # Compact strings and get address mapping
            address_mapping = PointerUtils.compact_pointer_targets(
                rom_data, pointers, new_strings_data
            )
            
            # Update pointer table
            PointerUtils.update_pointer_table(rom_data, pointers, address_mapping)
            
            results['successful'] = len([s for s in self.translated_strings])
            results['pointers_updated'] = len(address_mapping)
            
        except Exception as e:
            results['failed'] = len(self.translated_strings)
            results['issues'].append(f"Pointer table update failed: {e}")
        
        return results
    
    def _can_expand_string(self, rom_data: bytearray, string: TranslatedString) -> bool:
        """Check if string can be expanded in place.
        
        Args:
            rom_data: ROM data
            string: String to check
            
        Returns:
            True if string can be expanded
        """
        needed_space = len(string.translated_bytes) - len(string.original_bytes)
        if needed_space <= 0:
            return True
        
        # Check if there's free space after the string
        check_start = string.address + len(string.original_bytes)
        check_end = min(check_start + needed_space, len(rom_data))
        
        # Look for null bytes or padding
        for i in range(check_start, check_end):
            if rom_data[i] not in [0x00, 0xFF]:
                return False
        
        return True
    
    def _expand_string_space(self, rom_data: bytearray, string: TranslatedString) -> None:
        """Expand space for a string by using following null bytes.
        
        Args:
            rom_data: ROM data to modify
            string: String to expand space for
        """
        # This is a simplified implementation
        # In practice, you'd need more sophisticated space management
        pass
    
    def _truncate_translation(self, text: str, max_bytes: int) -> str:
        """Truncate translation to fit within byte limit.
        
        Args:
            text: Translation text
            max_bytes: Maximum number of bytes allowed
            
        Returns:
            Truncated text that fits within limit
        """
        # Try progressively shorter versions
        for length in range(len(text), 0, -1):
            truncated = text[:length]
            try:
                encoded = self.encoding_table.encode_string(truncated)
                if len(encoded) <= max_bytes:
                    return truncated
            except:
                continue
        
        return ""  # Fallback to empty string
    
    def _extract_original_string(self, rom_data: bytearray, address: int) -> bytes:
        """Extract original string data from ROM.
        
        Args:
            rom_data: ROM data
            address: Starting address
            
        Returns:
            Original string bytes including terminator
        """
        current_pos = address
        while current_pos < len(rom_data):
            byte_val = rom_data[current_pos]
            # Check for common terminators
            if byte_val in [0x00, 0xFF] or byte_val in self.encoding_table.control_codes:
                if self.encoding_table.control_codes.get(byte_val) in ['<END>', '<NULL>']:
                    return rom_data[address:current_pos + 1]
            current_pos += 1
        
        # No terminator found, return rest of data
        return rom_data[address:]
    
    def generate_patch(self, original_rom_path: str, modified_rom_path: str, 
                      patch_path: str, format_type: str = 'ips') -> None:
        """Generate a patch file for the translation.
        
        Args:
            original_rom_path: Path to original ROM
            modified_rom_path: Path to modified ROM
            patch_path: Path for output patch file
            format_type: Patch format ('ips' or 'bps')
        """
        if format_type == 'ips':
            self._generate_ips_patch(original_rom_path, modified_rom_path, patch_path)
        else:
            raise ValueError(f"Unsupported patch format: {format_type}")
    
    def _generate_ips_patch(self, original_path: str, modified_path: str, patch_path: str) -> None:
        """Generate IPS patch file.
        
        Args:
            original_path: Path to original ROM
            modified_path: Path to modified ROM
            patch_path: Path for IPS patch file
        """
        with open(original_path, 'rb') as f:
            original_data = f.read()
        
        with open(modified_path, 'rb') as f:
            modified_data = f.read()
        
        if len(original_data) != len(modified_data):
            raise ValueError("ROM files must be same size for IPS patch")
        
        patch_data = bytearray()
        patch_data.extend(b'PATCH')  # IPS header
        
        # Find differences
        i = 0
        while i < len(original_data):
            if original_data[i] != modified_data[i]:
                # Start of a difference
                start_offset = i
                
                # Find end of difference
                while i < len(original_data) and original_data[i] != modified_data[i]:
                    i += 1
                
                length = i - start_offset
                
                # Add to patch (simplified IPS format)
                patch_data.extend(start_offset.to_bytes(3, 'big'))  # Offset
                patch_data.extend(length.to_bytes(2, 'big'))        # Length
                patch_data.extend(modified_data[start_offset:i])    # Data
            else:
                i += 1
        
        patch_data.extend(b'EOF')  # IPS footer
        
        # Write patch file
        patch_file = Path(patch_path)
        patch_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(patch_file, 'wb') as f:
            f.write(patch_data)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get reinsertion statistics.
        
        Returns:
            Statistics dictionary
        """
        if not self.translated_strings:
            return {'total_strings': 0}
        
        total_original_chars = sum(len(s.original_text) for s in self.translated_strings)
        total_translated_chars = sum(len(s.translated_text) for s in self.translated_strings)
        
        expansion_ratio = total_translated_chars / total_original_chars if total_original_chars > 0 else 0
        
        return {
            'total_strings': len(self.translated_strings),
            'original_characters': total_original_chars,
            'translated_characters': total_translated_chars,
            'expansion_ratio': round(expansion_ratio, 2),
            'strings_with_pointers': sum(1 for s in self.translated_strings if s.pointer_address),
            'encoding_table_stats': self.encoding_table.get_stats()
        }
