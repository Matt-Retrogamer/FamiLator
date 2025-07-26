"""
Tests for text reinsertion functionality.
"""

import unittest
import tempfile
import os
import csv

from src.reinjector import TextReinjector


class TestTextReinjector(unittest.TestCase):
    """Test cases for TextReinjector class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test table file
        self.table_path = os.path.join(self.temp_dir, 'test.tbl')
        with open(self.table_path, 'w') as f:
            f.write("41=A\n42=B\n43=C\n44=D\n45=E\n20= \nFF=<END>\n")
        
        # Create test config file
        self.config_path = os.path.join(self.temp_dir, 'test.yaml')
        with open(self.config_path, 'w') as f:
            f.write(f"""
game:
  name: "Test Game"

text_detection:
  method: "fixed_locations"
  encoding_table: "{self.table_path}"

validation:
  expected_size: 100
""")
        
        # Create test ROM
        self.rom_data = bytearray(100)
        self.rom_data[0x10:0x15] = b'\x41\x42\x43\x20\xFF'  # "ABC <END>"
        
        self.rom_path = os.path.join(self.temp_dir, 'test.rom')
        with open(self.rom_path, 'wb') as f:
            f.write(self.rom_data)
        
        # Create test CSV with translations
        self.csv_path = os.path.join(self.temp_dir, 'translations.csv')
        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['string_id', 'address', 'length', 'original_text', 
                           'translated_text', 'description', 'pointer_address'])
            writer.writerow(['string_001', '0x0010', '4', 'ABC ', 'DEE ', 
                           'Test string', ''])
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_reinjector_initialization(self):
        """Test TextReinjector initialization."""
        reinjector = TextReinjector(self.config_path)
        self.assertEqual(reinjector.config['game']['name'], "Test Game")
    
    def test_load_translations_from_csv(self):
        """Test loading translations from CSV file."""
        reinjector = TextReinjector(self.config_path)
        reinjector.load_translations_from_csv(self.csv_path)
        
        self.assertEqual(len(reinjector.translated_strings), 1)
        string = reinjector.translated_strings[0]
        self.assertEqual(string.string_id, 'string_001')
        self.assertEqual(string.address, 0x10)
        self.assertEqual(string.original_text, 'ABC ')
        self.assertEqual(string.translated_text, 'DEE ')
    
    def test_reinject_fixed_locations(self):
        """Test reinsertion using fixed locations method."""
        reinjector = TextReinjector(self.config_path)
        reinjector.load_translations_from_csv(self.csv_path)
        
        output_path = os.path.join(self.temp_dir, 'output.rom')
        results = reinjector.reinject_into_rom(self.rom_path, output_path)
        
        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(results['strings_processed'], 1)
        
        # Verify the translation was actually inserted
        with open(output_path, 'rb') as f:
            modified_data = f.read()
            # Should contain "DEE " (0x44, 0x45, 0x45, 0x20)
            self.assertEqual(modified_data[0x10:0x14], b'\x44\x45\x45\x20')
    
    def test_get_stats(self):
        """Test statistics generation."""
        reinjector = TextReinjector(self.config_path)
        reinjector.load_translations_from_csv(self.csv_path)
        
        stats = reinjector.get_stats()
        self.assertEqual(stats['total_strings'], 1)
        self.assertGreater(stats['original_characters'], 0)
        self.assertGreater(stats['translated_characters'], 0)


if __name__ == '__main__':
    unittest.main()
