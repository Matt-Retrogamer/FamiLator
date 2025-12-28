"""Tests for the TableBuilder manual-assist tool."""

import os
import tempfile
from pathlib import Path

import pytest

from src.table_builder import TableBuilder, TableData, TableMapping, TableBuilderResult


class TestTableBuilder:
    """Tests for the TableBuilder class."""

    @pytest.fixture
    def temp_tables_dir(self):
        """Create a temporary tables directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def builder(self, temp_tables_dir):
        """Create a TableBuilder with temp directory."""
        return TableBuilder(output_dir=str(temp_tables_dir))

    # === Table Creation Tests ===

    def test_create_table_with_mappings(self, builder, temp_tables_dir):
        """Test creating a table with initial mappings."""
        mappings = {0x41: "A", 0x42: "B", 0x43: "C"}
        result = builder.create_table("alphabet", mappings=mappings)

        assert result.success is True
        assert result.mappings_count == 3

        # Read the file and verify
        content = (temp_tables_dir / "alphabet.tbl").read_text()
        assert "41=A" in content
        assert "42=B" in content
        assert "43=C" in content

    def test_create_table_with_control_codes(self, builder, temp_tables_dir):
        """Test creating a table with control codes."""
        mappings = {0x41: "A"}
        control_codes = {0xFF: "<END>", 0xFE: "<NEWLINE>"}
        result = builder.create_table(
            "with_controls", mappings=mappings, control_codes=control_codes
        )

        assert result.success is True

        content = (temp_tables_dir / "with_controls.tbl").read_text()
        assert "FF=<END>" in content
        assert "FE=<NEWLINE>" in content
        assert "41=A" in content

    def test_create_table_empty_fails(self, builder):
        """Test that creating a table with no mappings fails."""
        result = builder.create_table("empty", mappings={})
        assert result.success is False

    # === Table Loading Tests ===

    def test_load_existing_table(self, builder, temp_tables_dir):
        """Test loading an existing table file."""
        # Create a table file manually
        table_content = """# Test table
41=A
42=B
FF=<END>
"""
        (temp_tables_dir / "existing.tbl").write_text(table_content)

        result = builder.load_table(str(temp_tables_dir / "existing.tbl"))

        assert result is not None
        assert result.name == "existing"
        assert len(result.mappings) == 2
        assert result.mappings[0x41] == "A"
        assert result.mappings[0x42] == "B"
        assert len(result.control_codes) == 1
        assert result.control_codes[0xFF] == "<END>"

    def test_load_nonexistent_table(self, builder):
        """Test loading a table that doesn't exist."""
        result = builder.load_table("/nonexistent/path.tbl")
        assert result is None

    def test_load_table_ignores_comments(self, builder, temp_tables_dir):
        """Test that comments and empty lines are ignored when loading."""
        table_content = """# This is a comment
41=A

# Another comment
42=B
"""
        (temp_tables_dir / "commented.tbl").write_text(table_content)

        result = builder.load_table(str(temp_tables_dir / "commented.tbl"))

        assert result is not None
        assert len(result.mappings) == 2

    def test_load_table_handles_malformed_lines(self, builder, temp_tables_dir):
        """Test that malformed lines are skipped gracefully."""
        table_content = """41=A
bad line without equals
42=B
=no hex
ZZ=invalid hex
43=C
"""
        (temp_tables_dir / "malformed.tbl").write_text(table_content)

        result = builder.load_table(str(temp_tables_dir / "malformed.tbl"))

        assert result is not None
        # Should only get valid lines
        assert len(result.mappings) == 3

    # === Table Update Tests ===

    def test_update_table(self, builder, temp_tables_dir):
        """Test updating mappings in existing table."""
        # Create initial table
        builder.create_table("updatable", mappings={0x41: "A"})

        # Update with more mappings
        result = builder.update_table(
            str(temp_tables_dir / "updatable.tbl"),
            mappings={0x41: "A", 0x42: "B", 0x43: "C"}
        )

        assert result.success is True

        content = (temp_tables_dir / "updatable.tbl").read_text()
        assert "41=A" in content
        assert "42=B" in content
        assert "43=C" in content

    def test_update_nonexistent_table_creates_new(self, builder, temp_tables_dir):
        """Test that updating a nonexistent table creates a new one."""
        # When the table doesn't exist, update_table creates it
        result = builder.update_table(
            str(temp_tables_dir / "new_from_update.tbl"),
            mappings={0x41: "A"}
        )
        # Creates the file since it doesn't exist
        assert result.success is True
        assert (temp_tables_dir / "new_from_update.tbl").exists()

    # === Preset Tests ===

    def test_get_common_presets(self, builder):
        """Test that common presets are returned."""
        presets = builder.get_common_presets()

        assert "ascii_uppercase_from_0" in presets
        assert "ascii_lowercase_from_0" in presets
        assert "digits_from_0" in presets
        assert len(presets["ascii_uppercase_from_0"]) == 26
        assert len(presets["ascii_lowercase_from_0"]) == 26
        assert len(presets["digits_from_0"]) == 10

    def test_apply_preset_uppercase(self, builder):
        """Test applying uppercase preset."""
        mappings = builder.apply_preset("ascii_uppercase_from_0", start_byte=0x00)

        assert len(mappings) == 26
        assert mappings[0x00] == "A"
        assert mappings[0x19] == "Z"  # 0x19 = 25 = 'Z'

    def test_apply_preset_with_offset(self, builder):
        """Test applying preset with custom start byte."""
        mappings = builder.apply_preset("ascii_uppercase_from_0", start_byte=0x41)

        assert mappings[0x41] == "A"  # ASCII-like mapping
        assert mappings[0x5A] == "Z"  # 0x41 + 25 = 0x5A

    def test_apply_preset_digits(self, builder):
        """Test applying digits preset."""
        mappings = builder.apply_preset("digits_from_0", start_byte=0x30)

        assert mappings[0x30] == "0"
        assert mappings[0x39] == "9"

    def test_apply_invalid_preset(self, builder):
        """Test applying nonexistent preset returns empty dict."""
        mappings = builder.apply_preset("nonexistent", start_byte=0x00)
        assert mappings == {}

    # === Edge Cases ===

    def test_special_characters_in_mapping(self, builder, temp_tables_dir):
        """Test mappings with special characters."""
        mappings = {0x20: " ", 0x21: "!", 0x3F: "?"}
        result = builder.create_table("specials", mappings=mappings)

        assert result.success is True

        content = (temp_tables_dir / "specials.tbl").read_text()
        assert "20= " in content  # space
        assert "21=!" in content
        assert "3F=?" in content

    def test_unicode_in_mapping(self, builder, temp_tables_dir):
        """Test mappings with unicode characters (for Japanese games)."""
        mappings = {0x00: "あ", 0x01: "い", 0x02: "う"}
        result = builder.create_table("japanese", mappings=mappings)

        assert result.success is True

        content = (temp_tables_dir / "japanese.tbl").read_text(encoding="utf-8")
        assert "00=あ" in content
        assert "01=い" in content
        assert "02=う" in content


class TestTableData:
    """Tests for TableData dataclass."""

    def test_create_table_data(self):
        """Test creating TableData."""
        data = TableData(
            name="test",
            mappings={0x41: "A", 0x42: "B"},
            control_codes={0xFF: "<END>"},
        )

        assert data.name == "test"
        assert data.mappings[0x41] == "A"
        assert data.control_codes[0xFF] == "<END>"


class TestTableMapping:
    """Tests for TableMapping dataclass."""

    def test_create_mapping(self):
        """Test creating TableMapping."""
        mapping = TableMapping(byte_value=0x41, character="A")

        assert mapping.byte_value == 0x41
        assert mapping.character == "A"

    def test_mapping_with_tile_index(self):
        """Test creating mapping with tile index."""
        mapping = TableMapping(byte_value=0x41, character="A", tile_index=100)

        assert mapping.tile_index == 100

