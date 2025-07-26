"""
Tests for text extraction functionality.
"""

import unittest
import tempfile
import os
from pathlib import Path

from src.extractor import TextExtractor
from src.encoding import EncodingTable


class TestTextExtractor(unittest.TestCase):
    """Test cases for TextExtractor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test table file
        self.table_path = os.path.join(self.temp_dir, 'test.tbl')
        with open(self.table_path, 'w') as f:
            f.write("41=A\n42=B\n43=C\n20= \nFF=<END>\n")
        
        # Create test config file
        self.config_path = os.path.join(self.temp_dir, 'test.yaml')
        with open(self.config_path, 'w') as f:
            f.write(f"""
game:
  name: "Test Game"
  crc32: "0x12345678"

text_detection:
  method: "fixed_locations"
  encoding_table: "{self.table_path}"
  strings:
    - address: 0x10
      length: 5
      description: "Test string"

validation:
  expected_size: 100
""")
        
        # Create test ROM data
        self.rom_data = bytearray(100)
        self.rom_data[0x10:0x15] = b'\x41\x42\x43\x20\xFF'  # "ABC <END>"
        
        self.rom_path = os.path.join(self.temp_dir, 'test.rom')
        with open(self.rom_path, 'wb') as f:
            f.write(self.rom_data)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_extractor_initialization(self):
        """Test TextExtractor initialization."""
        extractor = TextExtractor(self.config_path)
        self.assertIsInstance(extractor.encoding_table, EncodingTable)
        self.assertEqual(extractor.config['game']['name'], "Test Game")
    
    def test_extract_fixed_locations(self):
        """Test extraction using fixed locations method."""
        extractor = TextExtractor(self.config_path)
        strings = extractor.extract_from_rom(self.rom_path)
        
        self.assertEqual(len(strings), 1)
        self.assertEqual(strings[0].address, 0x10)
        self.assertEqual(strings[0].decoded_text, "ABC ")
        self.assertEqual(strings[0].length, 5)  # Including terminator in original bytes
    
    def test_export_to_csv(self):
        """Test CSV export functionality."""
        extractor = TextExtractor(self.config_path)
        strings = extractor.extract_from_rom(self.rom_path)
        
        csv_path = os.path.join(self.temp_dir, 'output.csv')
        extractor.export_to_csv(csv_path)
        
        self.assertTrue(os.path.exists(csv_path))
        
        # Read and verify CSV content
        with open(csv_path, 'r') as f:
            content = f.read()
            self.assertIn('string_id', content)
            self.assertIn('ABC', content)
    
    def test_export_to_json(self):
        """Test JSON export functionality."""
        extractor = TextExtractor(self.config_path)
        strings = extractor.extract_from_rom(self.rom_path)
        
        json_path = os.path.join(self.temp_dir, 'output.json')
        extractor.export_to_json(json_path)
        
        self.assertTrue(os.path.exists(json_path))
        
        # Read and verify JSON content
        import json
        with open(json_path, 'r') as f:
            data = json.load(f)
            self.assertIn('strings', data)
            self.assertEqual(len(data['strings']), 1)
    
    def test_get_stats(self):
        """Test statistics generation."""
        extractor = TextExtractor(self.config_path)
        strings = extractor.extract_from_rom(self.rom_path)
        
        stats = extractor.get_stats()
        self.assertEqual(stats['total_strings'], 1)
        self.assertGreater(stats['total_characters'], 0)
        self.assertIn('encoding_table_stats', stats)


if __name__ == '__main__':
    unittest.main()
