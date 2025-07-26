"""
Tests for encoding table functionality.
"""

import unittest
import tempfile
import os

from src.encoding import EncodingTable


class TestEncodingTable(unittest.TestCase):
    """Test cases for EncodingTable class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test table file
        self.table_path = os.path.join(self.temp_dir, 'test.tbl')
        with open(self.table_path, 'w') as f:
            f.write("""# Test encoding table
41=A
42=B
43=C
20= 
FE=<NEWLINE>
FF=<END>
# Multi-byte pattern
F0XX=<DELAY:XX>
""")
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_table_loading(self):
        """Test loading table from file."""
        table = EncodingTable(self.table_path)
        
        # Check character mappings
        self.assertEqual(table.decode_byte(0x41), 'A')
        self.assertEqual(table.decode_byte(0x42), 'B')
        self.assertEqual(table.decode_byte(0x20), ' ')
        
        # Check control codes
        self.assertEqual(table.decode_byte(0xFE), '<NEWLINE>')
        self.assertEqual(table.decode_byte(0xFF), '<END>')
        
        # Check reverse mapping
        self.assertEqual(table.encode_char('A'), 0x41)
        self.assertEqual(table.encode_char(' '), 0x20)
    
    def test_decode_bytes(self):
        """Test decoding byte sequences."""
        table = EncodingTable(self.table_path)
        
        # Test simple decoding
        data = b'\x41\x42\x43'  # ABC
        result = table.decode_bytes(data)
        self.assertEqual(result, 'ABC')
        
        # Test with terminator
        data = b'\x41\x42\x43\xFF'  # ABC<END>
        result = table.decode_bytes(data)
        self.assertEqual(result, 'ABC')  # Should stop at terminator
    
    def test_encode_string(self):
        """Test encoding strings to bytes."""
        table = EncodingTable(self.table_path)
        
        # Test simple encoding
        result = table.encode_string('ABC')
        self.assertEqual(result, b'\x41\x42\x43')
        
        # Test with control codes
        result = table.encode_string('A<NEWLINE>B')
        self.assertEqual(result, b'\x41\xFE\x42')
    
    def test_unknown_bytes(self):
        """Test handling of unknown bytes."""
        table = EncodingTable(self.table_path)
        
        # Unknown byte should return <UNK:XX> format
        result = table.decode_byte(0x99)
        self.assertEqual(result, '<UNK:99>')
    
    def test_get_stats(self):
        """Test statistics generation."""
        table = EncodingTable(self.table_path)
        stats = table.get_stats()
        
        self.assertEqual(stats['characters'], 4)  # A, B, C, space
        self.assertEqual(stats['control_codes'], 2)  # NEWLINE, END
        self.assertEqual(stats['multi_byte_patterns'], 1)  # DELAY pattern
        self.assertGreater(stats['total_mappings'], 0)
    
    def test_empty_table(self):
        """Test behavior with empty table."""
        table = EncodingTable()
        
        # Should handle unknown bytes gracefully
        result = table.decode_byte(0x41)
        self.assertEqual(result, '<UNK:41>')
        
        # Should return None for unknown characters
        result = table.encode_char('A')
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
