"""Tests for the chr_analyzer module."""

import pytest
import tempfile
from pathlib import Path
from src.chr_analyzer import (
    CHRAnalyzer,
    CHRAnalysis,
    CHRType,
    TileInfo,
    FontRegion,
    analyze_chr_rom,
)


class TestCHRType:
    """Test CHRType enum."""
    
    def test_chr_type_values(self):
        """Test CHRType enum values."""
        assert CHRType.CHR_ROM.value == "chr_rom"
        assert CHRType.CHR_RAM.value == "chr_ram"
        assert CHRType.UNKNOWN.value == "unknown"


class TestTileInfo:
    """Test TileInfo dataclass."""
    
    def test_tile_info_creation(self):
        """Test creating TileInfo."""
        tile = TileInfo(
            index=0,
            offset=0,
            is_blank=True,
            is_solid=False,
            unique_colors=1,
            pixel_count=0,
            pattern_hash="00" * 16,
        )
        assert tile.index == 0
        assert tile.is_blank is True
        assert tile.pixel_count == 0
    
    def test_tile_info_defaults(self):
        """Test TileInfo default values."""
        tile = TileInfo(index=5, offset=80)
        assert tile.is_blank is False
        assert tile.is_solid is False
        assert tile.unique_colors == 0


class TestFontRegion:
    """Test FontRegion dataclass."""
    
    def test_font_region_creation(self):
        """Test creating FontRegion."""
        region = FontRegion(
            start_tile=0,
            end_tile=25,
            tile_count=26,
            estimated_chars=26,
            notes="Uppercase alphabet",
        )
        assert region.start_tile == 0
        assert region.end_tile == 25
        assert region.tile_count == 26
        assert "alphabet" in region.notes.lower()


class TestCHRAnalysis:
    """Test CHRAnalysis dataclass."""
    
    def test_analysis_creation(self):
        """Test creating CHRAnalysis."""
        analysis = CHRAnalysis(
            chr_type=CHRType.CHR_ROM,
            chr_size=8192,
            total_tiles=512,
            blank_tiles=100,
            unique_tiles=200,
        )
        assert analysis.chr_type == CHRType.CHR_ROM
        assert analysis.chr_size == 8192
        assert analysis.total_tiles == 512
    
    def test_has_latin_font(self):
        """Test Latin font detection."""
        # With enough tiles
        analysis = CHRAnalysis(
            chr_type=CHRType.CHR_ROM,
            chr_size=8192,
            total_tiles=512,
            blank_tiles=0,
            unique_tiles=50,
        )
        assert analysis.has_latin_font() is True
        
        # Without enough tiles
        analysis2 = CHRAnalysis(
            chr_type=CHRType.CHR_ROM,
            chr_size=8192,
            total_tiles=512,
            blank_tiles=0,
            unique_tiles=10,
        )
        assert analysis2.has_latin_font() is False
    
    def test_has_extended_charset(self):
        """Test extended charset detection."""
        # With enough tiles for A-Z, a-z, 0-9
        analysis = CHRAnalysis(
            chr_type=CHRType.CHR_ROM,
            chr_size=8192,
            total_tiles=512,
            blank_tiles=0,
            unique_tiles=70,
        )
        assert analysis.has_extended_charset() is True
        
        # Without enough
        analysis2 = CHRAnalysis(
            chr_type=CHRType.CHR_ROM,
            chr_size=8192,
            total_tiles=512,
            blank_tiles=0,
            unique_tiles=30,
        )
        assert analysis2.has_extended_charset() is False
    
    def test_get_summary(self):
        """Test analysis summary output."""
        analysis = CHRAnalysis(
            chr_type=CHRType.CHR_ROM,
            chr_size=8192,
            total_tiles=512,
            blank_tiles=100,
            unique_tiles=200,
        )
        summary = analysis.get_summary()
        assert "CHR Type:" in summary
        assert "CHR Size:" in summary
        assert "512" in summary


class TestCHRAnalyzer:
    """Test CHRAnalyzer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = CHRAnalyzer()
    
    def test_analyzer_constants(self):
        """Test analyzer constants."""
        assert self.analyzer.INES_HEADER_SIZE == 16
        assert self.analyzer.PRG_ROM_UNIT == 16384
        assert self.analyzer.CHR_ROM_UNIT == 8192
        assert self.analyzer.TILE_SIZE == 16
    
    def test_parse_valid_ines_header(self):
        """Test parsing valid iNES header."""
        # Create minimal valid iNES header
        # NES\x1a + PRG units + CHR units + flags
        header = b"NES\x1a" + bytes([2, 1, 0, 0]) + bytes(8)
        rom_data = header + bytes(2 * 16384 + 1 * 8192)  # PRG + CHR
        
        self.analyzer.rom_data = rom_data
        result = self.analyzer._parse_ines_header()
        
        assert result is True
        assert self.analyzer.prg_size == 2 * 16384
        assert self.analyzer.chr_size == 1 * 8192
    
    def test_parse_invalid_header(self):
        """Test parsing invalid header."""
        self.analyzer.rom_data = b"INVALID"
        result = self.analyzer._parse_ines_header()
        assert result is False
    
    def test_parse_short_header(self):
        """Test parsing too-short data."""
        self.analyzer.rom_data = b"NES"
        result = self.analyzer._parse_ines_header()
        assert result is False
    
    def test_decode_tile_pixels(self):
        """Test tile pixel decoding."""
        # Create a simple tile pattern
        # 8 bytes low plane + 8 bytes high plane
        tile_data = bytes([0xFF] * 8 + [0x00] * 8)  # All color 1
        
        pixels = self.analyzer._decode_tile_pixels(tile_data)
        
        assert len(pixels) == 64  # 8x8 pixels
        assert all(p == 1 for p in pixels)  # All should be color 1
    
    def test_decode_empty_tile(self):
        """Test decoding empty (blank) tile."""
        tile_data = bytes(16)  # All zeros
        pixels = self.analyzer._decode_tile_pixels(tile_data)
        
        assert len(pixels) == 64
        assert all(p == 0 for p in pixels)
    
    def test_get_tile_bitmap(self):
        """Test getting tile as 2D bitmap."""
        # Set up minimal CHR data
        self.analyzer.chr_data = bytes(16)  # One blank tile
        
        bitmap = self.analyzer.get_tile_bitmap(0)
        
        assert len(bitmap) == 8  # 8 rows
        assert all(len(row) == 8 for row in bitmap)  # 8 columns each
    
    def test_get_tile_bitmap_out_of_bounds(self):
        """Test getting tile outside CHR data."""
        self.analyzer.chr_data = bytes(16)  # One tile only
        
        bitmap = self.analyzer.get_tile_bitmap(100)  # Way out of bounds
        
        # Should return empty tile
        assert len(bitmap) == 8
        assert all(all(p == 0 for p in row) for row in bitmap)
    
    def test_render_tile_ascii(self):
        """Test ASCII tile rendering."""
        self.analyzer.chr_data = bytes(16)  # Blank tile
        
        ascii_art = self.analyzer.render_tile_ascii(0)
        
        assert len(ascii_art.split("\n")) == 8  # 8 rows
    
    def test_analyze_tile_blank(self):
        """Test analyzing a blank tile."""
        tile_data = bytes(16)
        tile_info = self.analyzer._analyze_tile(0, tile_data)
        
        assert tile_info.is_blank is True
        assert tile_info.pixel_count == 0
    
    def test_analyze_tile_solid(self):
        """Test analyzing a solid tile."""
        tile_data = bytes([0xFF] * 16)
        tile_info = self.analyzer._analyze_tile(0, tile_data)
        
        assert tile_info.is_solid is True
    
    def test_analyze_rom_not_found(self):
        """Test analyzing non-existent ROM."""
        with pytest.raises(FileNotFoundError):
            self.analyzer.analyze_rom("/nonexistent/path/game.nes")


class TestAnalyzeCHRRomFunction:
    """Test the convenience function."""
    
    def test_analyze_nonexistent_rom(self):
        """Test analyzing non-existent ROM file."""
        with pytest.raises(FileNotFoundError):
            analyze_chr_rom("/nonexistent/rom.nes")


class TestCHRRAMDetection:
    """Test CHR RAM (no CHR ROM) detection."""
    
    def test_chr_ram_detection(self):
        """Test that CHR RAM is properly detected."""
        analyzer = CHRAnalyzer()
        
        # Create iNES header with 0 CHR ROM units
        header = b"NES\x1a" + bytes([2, 0, 0, 0]) + bytes(8)  # 0 CHR units
        rom_data = header + bytes(2 * 16384)  # PRG only, no CHR
        
        analyzer.rom_data = rom_data
        analyzer._parse_ines_header()
        analyzer._extract_chr_data()
        
        assert analyzer.chr_size == 0
        assert len(analyzer.chr_data) == 0


class TestFontRegionDetection:
    """Test font region detection logic."""
    
    def test_detect_font_regions_empty(self):
        """Test font region detection with no tiles."""
        analyzer = CHRAnalyzer()
        regions = analyzer._detect_font_regions([])
        assert len(regions) == 0
    
    def test_classify_region_uppercase(self):
        """Test classifying uppercase alphabet region."""
        analyzer = CHRAnalyzer()
        
        # Create 26 non-blank tiles
        tiles = [
            TileInfo(index=i, offset=i*16, pixel_count=30)
            for i in range(26)
        ]
        
        region = analyzer._classify_region(0, tiles)
        assert region is not None
        assert region.tile_count == 26
        assert "uppercase" in region.notes.lower() or "alphabet" in region.notes.lower()
    
    def test_estimate_charset_size(self):
        """Test charset size estimation."""
        analyzer = CHRAnalyzer()
        
        regions = [
            FontRegion(start_tile=0, end_tile=25, tile_count=26, estimated_chars=26),
            FontRegion(start_tile=32, end_tile=57, tile_count=26, estimated_chars=26),
        ]
        
        size = analyzer._estimate_charset_size(regions)
        assert size == 52  # Total from both regions
