"""
Tests for text reinsertion functionality.
"""

import csv
import os
import tempfile
import unittest

from src.reinjector import TextReinjector


class TestTextReinjector(unittest.TestCase):
    """Test cases for TextReinjector class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Create test table file
        self.table_path = os.path.join(self.temp_dir, "test.tbl")
        with open(self.table_path, "w") as f:
            f.write("41=A\n42=B\n43=C\n44=D\n45=E\n20= \nFE=<NEWLINE>\nFF=<END>\n")

        # Create test config file
        self.config_path = os.path.join(self.temp_dir, "test.yaml")
        with open(self.config_path, "w") as f:
            f.write(
                f"""
game:
  name: "Test Game"

text_detection:
  method: "fixed_locations"
  encoding_table: "{self.table_path}"

validation:
  expected_size: 100
"""
            )

        # Create test ROM
        self.rom_data = bytearray(100)
        self.rom_data[0x10:0x15] = b"\x41\x42\x43\x20\xff"  # "ABC <END>"

        self.rom_path = os.path.join(self.temp_dir, "test.rom")
        with open(self.rom_path, "wb") as f:
            f.write(self.rom_data)

        # Create test CSV with translations
        self.csv_path = os.path.join(self.temp_dir, "translations.csv")
        with open(self.csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "string_id",
                    "address",
                    "length",
                    "original_text",
                    "translated_text",
                    "description",
                    "pointer_address",
                ]
            )
            writer.writerow(
                ["string_001", "0x0010", "4", "ABC ", "DEE ", "Test string", ""]
            )

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_reinjector_initialization(self):
        """Test TextReinjector initialization."""
        reinjector = TextReinjector(self.config_path)
        self.assertEqual(reinjector.config["game"]["name"], "Test Game")

    def test_load_translations_from_csv(self):
        """Test loading translations from CSV file."""
        reinjector = TextReinjector(self.config_path)
        reinjector.load_translations_from_csv(self.csv_path)

        self.assertEqual(len(reinjector.translated_strings), 1)
        string = reinjector.translated_strings[0]
        self.assertEqual(string.string_id, "string_001")
        self.assertEqual(string.address, 0x10)
        self.assertEqual(string.original_text, "ABC ")
        self.assertEqual(string.translated_text, "DEE ")

    def test_reinject_fixed_locations(self):
        """Test reinsertion using fixed locations method."""
        reinjector = TextReinjector(self.config_path)
        reinjector.load_translations_from_csv(self.csv_path)

        output_path = os.path.join(self.temp_dir, "output.rom")
        results = reinjector.reinject_into_rom(self.rom_path, output_path)

        self.assertTrue(os.path.exists(output_path))
        self.assertEqual(results["strings_processed"], 1)

        # Verify the translation was actually inserted
        with open(output_path, "rb") as f:
            modified_data = f.read()
            # Should contain "DEE " (0x44, 0x45, 0x45, 0x20)
            self.assertEqual(modified_data[0x10:0x14], b"\x44\x45\x45\x20")

    def test_get_stats(self):
        """Test statistics generation."""
        reinjector = TextReinjector(self.config_path)
        reinjector.load_translations_from_csv(self.csv_path)

        stats = reinjector.get_stats()
        self.assertEqual(stats["total_strings"], 1)
        self.assertGreater(stats["original_characters"], 0)
        self.assertGreater(stats["translated_characters"], 0)


class TestIPSPatchGeneration(unittest.TestCase):
    """Test cases for IPS patch generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test table file
        self.table_path = os.path.join(self.temp_dir, "test.tbl")
        with open(self.table_path, "w") as f:
            f.write("41=A\n42=B\n43=C\n44=D\n45=E\n20= \nFF=<END>\n")
        
        # Create test config
        self.config_path = os.path.join(self.temp_dir, "test.yaml")
        with open(self.config_path, "w") as f:
            f.write(f"""
game:
  name: "Test Game"
text_detection:
  method: "fixed_locations"
  encoding_table: "{self.table_path}"
validation:
  expected_size: 100
""")
        
        # Create original ROM
        self.original_data = bytearray(100)
        self.original_data[0x10:0x14] = b"\x41\x42\x43\x44"  # "ABCD"
        self.original_path = os.path.join(self.temp_dir, "original.rom")
        with open(self.original_path, "wb") as f:
            f.write(self.original_data)
        
        # Create modified ROM
        self.modified_data = bytearray(100)
        self.modified_data[0x10:0x14] = b"\x45\x45\x45\x45"  # "EEEE"
        self.modified_path = os.path.join(self.temp_dir, "modified.rom")
        with open(self.modified_path, "wb") as f:
            f.write(self.modified_data)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_ips_patch_creation(self):
        """Test IPS patch file is created correctly."""
        reinjector = TextReinjector(self.config_path)
        patch_path = os.path.join(self.temp_dir, "test.ips")
        
        reinjector.generate_patch(
            self.original_path,
            self.modified_path,
            patch_path,
            format_type="ips"
        )
        
        self.assertTrue(os.path.exists(patch_path))
    
    def test_ips_patch_header(self):
        """Test IPS patch has correct header."""
        reinjector = TextReinjector(self.config_path)
        patch_path = os.path.join(self.temp_dir, "test.ips")
        
        reinjector.generate_patch(
            self.original_path,
            self.modified_path,
            patch_path,
            format_type="ips"
        )
        
        with open(patch_path, "rb") as f:
            header = f.read(5)
        
        self.assertEqual(header, b"PATCH")
    
    def test_ips_patch_footer(self):
        """Test IPS patch has correct footer."""
        reinjector = TextReinjector(self.config_path)
        patch_path = os.path.join(self.temp_dir, "test.ips")
        
        reinjector.generate_patch(
            self.original_path,
            self.modified_path,
            patch_path,
            format_type="ips"
        )
        
        with open(patch_path, "rb") as f:
            f.seek(-3, 2)  # Seek to last 3 bytes
            footer = f.read(3)
        
        self.assertEqual(footer, b"EOF")
    
    def test_ips_patch_size(self):
        """Test IPS patch is non-empty and reasonable size."""
        reinjector = TextReinjector(self.config_path)
        patch_path = os.path.join(self.temp_dir, "test.ips")
        
        reinjector.generate_patch(
            self.original_path,
            self.modified_path,
            patch_path,
            format_type="ips"
        )
        
        patch_size = os.path.getsize(patch_path)
        # Header (5) + at least one record + footer (3)
        self.assertGreater(patch_size, 8)
        # Should be smaller than full ROM
        self.assertLess(patch_size, 100)


class TestControlCodePreservation(unittest.TestCase):
    """Test control code preservation during reinsertion."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create table with control codes
        self.table_path = os.path.join(self.temp_dir, "test.tbl")
        with open(self.table_path, "w") as f:
            f.write("41=A\n42=B\n43=C\n20= \nFE=<NEWLINE>\nFD=<PAUSE>\nFF=<END>\n")
        
        # Create config
        self.config_path = os.path.join(self.temp_dir, "test.yaml")
        with open(self.config_path, "w") as f:
            f.write(f"""
game:
  name: "Test Game"
text_detection:
  method: "fixed_locations"
  encoding_table: "{self.table_path}"
validation:
  expected_size: 100
""")
        
        # Create ROM with control codes
        self.rom_data = bytearray(100)
        # "A<NEWLINE>B<PAUSE>C<END>"
        self.rom_data[0x10:0x16] = b"\x41\xFE\x42\xFD\x43\xFF"
        self.rom_path = os.path.join(self.temp_dir, "test.rom")
        with open(self.rom_path, "wb") as f:
            f.write(self.rom_data)
        
        # Create CSV with control codes in translation
        self.csv_path = os.path.join(self.temp_dir, "translations.csv")
        with open(self.csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "string_id", "address", "length", "original_text",
                "translated_text", "description", "pointer_address"
            ])
            writer.writerow([
                "string_001", "0x0010", "6",
                "A<NEWLINE>B<PAUSE>C<END>",
                "B<NEWLINE>C<PAUSE>A<END>",
                "Test with control codes", ""
            ])
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_control_codes_preserved_in_output(self):
        """Test that control codes are preserved in reinjected ROM."""
        reinjector = TextReinjector(self.config_path)
        reinjector.load_translations_from_csv(self.csv_path)
        
        output_path = os.path.join(self.temp_dir, "output.rom")
        results = reinjector.reinject_into_rom(self.rom_path, output_path)
        
        with open(output_path, "rb") as f:
            data = f.read()
        
        # Check control codes are present in output
        self.assertIn(b"\xFE", data[0x10:0x16])  # NEWLINE
        self.assertIn(b"\xFD", data[0x10:0x16])  # PAUSE
        self.assertIn(b"\xFF", data[0x10:0x16])  # END


class TestRoundTripConsistency(unittest.TestCase):
    """Test round-trip consistency: extract -> translate -> reinject -> verify."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Simple table
        self.table_path = os.path.join(self.temp_dir, "test.tbl")
        with open(self.table_path, "w") as f:
            f.write("41=A\n42=B\n43=C\n44=D\n45=E\n20= \nFF=<END>\n")
        
        self.config_path = os.path.join(self.temp_dir, "test.yaml")
        with open(self.config_path, "w") as f:
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
        self.rom_data[0x10:0x14] = b"\x41\x42\x43\xff"  # "ABC<END>"
        self.rom_path = os.path.join(self.temp_dir, "test.rom")
        with open(self.rom_path, "wb") as f:
            f.write(self.rom_data)
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_file_size_preserved(self):
        """Test that ROM file size is preserved after reinsertion."""
        # Create translation CSV
        csv_path = os.path.join(self.temp_dir, "translations.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "string_id", "address", "length", "original_text",
                "translated_text", "description", "pointer_address"
            ])
            writer.writerow([
                "string_001", "0x0010", "4", "ABC<END>", "DCB<END>", "Test", ""
            ])
        
        reinjector = TextReinjector(self.config_path)
        reinjector.load_translations_from_csv(csv_path)
        
        output_path = os.path.join(self.temp_dir, "output.rom")
        reinjector.reinject_into_rom(self.rom_path, output_path)
        
        original_size = os.path.getsize(self.rom_path)
        output_size = os.path.getsize(output_path)
        
        self.assertEqual(original_size, output_size)
    
    def test_unmodified_regions_preserved(self):
        """Test that unmodified ROM regions are unchanged."""
        # Add some data outside the text region
        self.rom_data[0x00:0x04] = b"\x01\x02\x03\x04"
        self.rom_data[0x50:0x54] = b"\xAA\xBB\xCC\xDD"
        with open(self.rom_path, "wb") as f:
            f.write(self.rom_data)
        
        # Create translation
        csv_path = os.path.join(self.temp_dir, "translations.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "string_id", "address", "length", "original_text",
                "translated_text", "description", "pointer_address"
            ])
            writer.writerow([
                "string_001", "0x0010", "4", "ABC<END>", "DCB<END>", "Test", ""
            ])
        
        reinjector = TextReinjector(self.config_path)
        reinjector.load_translations_from_csv(csv_path)
        
        output_path = os.path.join(self.temp_dir, "output.rom")
        reinjector.reinject_into_rom(self.rom_path, output_path)
        
        with open(output_path, "rb") as f:
            output_data = f.read()
        
        # Verify unmodified regions
        self.assertEqual(output_data[0x00:0x04], b"\x01\x02\x03\x04")
        self.assertEqual(output_data[0x50:0x54], b"\xAA\xBB\xCC\xDD")


if __name__ == "__main__":
    unittest.main()
