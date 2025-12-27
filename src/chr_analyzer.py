"""
CHR ROM analyzer for NES/Famicom ROMs.

Analyzes the CHR (Character) ROM to detect available tiles/glyphs,
which is essential for determining what characters can be displayed
in a translated ROM.

NES CHR ROM Format:
- Each tile is 8x8 pixels
- Each tile uses 16 bytes (2 bitplanes)
- Tiles are stored sequentially in CHR ROM or CHR RAM
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import struct


class CHRType(Enum):
    """Type of CHR storage."""
    CHR_ROM = "chr_rom"  # Graphics stored in ROM (fixed)
    CHR_RAM = "chr_ram"  # Graphics stored in RAM (programmable)
    UNKNOWN = "unknown"


@dataclass
class TileInfo:
    """Information about a single 8x8 tile."""
    index: int
    offset: int  # Byte offset in CHR ROM
    is_blank: bool = False
    is_solid: bool = False
    unique_colors: int = 0
    pixel_count: int = 0  # Non-zero pixels
    pattern_hash: str = ""  # For deduplication


@dataclass
class FontRegion:
    """A contiguous region of tiles that likely form a font."""
    start_tile: int
    end_tile: int
    tile_count: int
    estimated_chars: int = 0
    char_width: int = 8  # Pixels
    char_height: int = 8  # Pixels
    notes: str = ""


@dataclass
class CHRAnalysis:
    """Complete CHR ROM analysis results."""
    chr_type: CHRType
    chr_size: int  # Total CHR size in bytes
    total_tiles: int
    blank_tiles: int
    unique_tiles: int
    font_regions: List[FontRegion] = field(default_factory=list)
    tile_info: List[TileInfo] = field(default_factory=list)
    available_chars: Set[str] = field(default_factory=set)
    estimated_charset_size: int = 0
    warnings: List[str] = field(default_factory=list)
    
    def has_latin_font(self) -> bool:
        """Check if ROM likely has Latin alphabet support."""
        # Need at least 26 unique tiles for A-Z
        return self.unique_tiles >= 26
    
    def has_extended_charset(self) -> bool:
        """Check if ROM has extended character set (A-Z, a-z, 0-9)."""
        # Need at least 62 unique tiles
        return self.unique_tiles >= 62
    
    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = [
            f"CHR Type: {self.chr_type.value}",
            f"CHR Size: {self.chr_size} bytes ({self.chr_size // 1024}KB)",
            f"Total Tiles: {self.total_tiles}",
            f"Unique Tiles: {self.unique_tiles}",
            f"Blank Tiles: {self.blank_tiles}",
            f"Font Regions: {len(self.font_regions)}",
        ]
        
        if self.font_regions:
            lines.append("\nDetected Font Regions:")
            for i, region in enumerate(self.font_regions, 1):
                lines.append(f"  {i}. Tiles {region.start_tile}-{region.end_tile} "
                           f"({region.tile_count} tiles) - {region.notes}")
        
        if self.warnings:
            lines.append("\nWarnings:")
            for w in self.warnings:
                lines.append(f"  ⚠️ {w}")
        
        return "\n".join(lines)


class CHRAnalyzer:
    """
    Analyzes NES CHR ROM to detect available character tiles.
    
    This is essential for translation projects to understand what
    characters can actually be rendered in the game.
    """
    
    # iNES header constants
    INES_HEADER_SIZE = 16
    INES_MAGIC = b"NES\x1a"
    PRG_ROM_UNIT = 16384  # 16KB per PRG ROM unit
    CHR_ROM_UNIT = 8192   # 8KB per CHR ROM unit
    TILE_SIZE = 16        # 16 bytes per 8x8 tile
    
    def __init__(self):
        """Initialize the CHR analyzer."""
        self.rom_data: bytes = b""
        self.chr_data: bytes = b""
        self.prg_size: int = 0
        self.chr_size: int = 0
        self.mapper: int = 0
    
    def analyze_rom(self, rom_path: str) -> CHRAnalysis:
        """
        Analyze CHR ROM from a NES ROM file.
        
        Args:
            rom_path: Path to NES ROM file
            
        Returns:
            CHRAnalysis with detected tiles and font regions
        """
        rom_file = Path(rom_path)
        if not rom_file.exists():
            raise FileNotFoundError(f"ROM not found: {rom_path}")
        
        with open(rom_file, "rb") as f:
            self.rom_data = f.read()
        
        # Parse iNES header
        if not self._parse_ines_header():
            return CHRAnalysis(
                chr_type=CHRType.UNKNOWN,
                chr_size=0,
                total_tiles=0,
                blank_tiles=0,
                unique_tiles=0,
                warnings=["Failed to parse iNES header"]
            )
        
        # Extract CHR ROM data
        self._extract_chr_data()
        
        # Analyze the CHR data
        return self._analyze_chr()
    
    def _parse_ines_header(self) -> bool:
        """Parse iNES header and extract ROM info."""
        if len(self.rom_data) < self.INES_HEADER_SIZE:
            return False
        
        header = self.rom_data[:self.INES_HEADER_SIZE]
        
        # Check magic number
        if header[:4] != self.INES_MAGIC:
            return False
        
        # Parse header fields
        prg_units = header[4]  # PRG ROM size in 16KB units
        chr_units = header[5]  # CHR ROM size in 8KB units
        flags6 = header[6]
        flags7 = header[7]
        
        self.prg_size = prg_units * self.PRG_ROM_UNIT
        self.chr_size = chr_units * self.CHR_ROM_UNIT
        self.mapper = (flags7 & 0xF0) | (flags6 >> 4)
        
        return True
    
    def _extract_chr_data(self) -> None:
        """Extract CHR ROM data from the ROM."""
        # Skip header and PRG ROM to get to CHR ROM
        chr_start = self.INES_HEADER_SIZE + self.prg_size
        chr_end = chr_start + self.chr_size
        
        if chr_end <= len(self.rom_data):
            self.chr_data = self.rom_data[chr_start:chr_end]
        else:
            self.chr_data = b""
    
    def _analyze_chr(self) -> CHRAnalysis:
        """Perform full CHR analysis."""
        warnings: List[str] = []
        
        # Determine CHR type
        if self.chr_size == 0:
            chr_type = CHRType.CHR_RAM
            warnings.append("CHR RAM detected - graphics are loaded at runtime")
            return CHRAnalysis(
                chr_type=chr_type,
                chr_size=0,
                total_tiles=0,
                blank_tiles=0,
                unique_tiles=0,
                warnings=warnings
            )
        
        chr_type = CHRType.CHR_ROM
        total_tiles = self.chr_size // self.TILE_SIZE
        
        # Analyze each tile
        tiles: List[TileInfo] = []
        pattern_hashes: Set[str] = set()
        blank_count = 0
        
        for tile_idx in range(total_tiles):
            tile_data = self._get_tile_data(tile_idx)
            tile_info = self._analyze_tile(tile_idx, tile_data)
            tiles.append(tile_info)
            
            if tile_info.is_blank:
                blank_count += 1
            else:
                pattern_hashes.add(tile_info.pattern_hash)
        
        unique_tiles = len(pattern_hashes)
        
        # Detect font regions
        font_regions = self._detect_font_regions(tiles)
        
        # Estimate available characters
        available_chars: Set[str] = set()
        estimated_charset = self._estimate_charset_size(font_regions)
        
        return CHRAnalysis(
            chr_type=chr_type,
            chr_size=self.chr_size,
            total_tiles=total_tiles,
            blank_tiles=blank_count,
            unique_tiles=unique_tiles,
            font_regions=font_regions,
            tile_info=tiles,
            available_chars=available_chars,
            estimated_charset_size=estimated_charset,
            warnings=warnings
        )
    
    def _get_tile_data(self, tile_index: int) -> bytes:
        """Get raw tile data for a specific tile index."""
        start = tile_index * self.TILE_SIZE
        end = start + self.TILE_SIZE
        if end > len(self.chr_data):
            # Return empty tile if out of bounds
            return bytes(self.TILE_SIZE)
        return self.chr_data[start:end]
    
    def _analyze_tile(self, tile_index: int, tile_data: bytes) -> TileInfo:
        """Analyze a single tile."""
        offset = tile_index * self.TILE_SIZE
        
        # Handle incomplete tile data
        if len(tile_data) < self.TILE_SIZE:
            return TileInfo(
                index=tile_index,
                offset=offset,
                is_blank=True,
                is_solid=False,
                unique_colors=0,
                pixel_count=0,
                pattern_hash=""
            )
        
        # Decode tile pixels (2 bitplanes)
        pixels = self._decode_tile_pixels(tile_data)
        
        # Calculate statistics
        pixel_count = sum(1 for p in pixels if p > 0)
        unique_colors = len(set(pixels))
        
        # Check if blank (all zeros)
        is_blank = all(b == 0 for b in tile_data)
        
        # Check if solid (all same non-zero value)
        is_solid = len(set(tile_data)) == 1 and not is_blank
        
        # Create hash for deduplication
        pattern_hash = tile_data.hex()
        
        return TileInfo(
            index=tile_index,
            offset=offset,
            is_blank=is_blank,
            is_solid=is_solid,
            unique_colors=unique_colors,
            pixel_count=pixel_count,
            pattern_hash=pattern_hash
        )
    
    def _decode_tile_pixels(self, tile_data: bytes) -> List[int]:
        """
        Decode tile data into pixel values (0-3).
        
        NES tiles use 2 bitplanes:
        - Bytes 0-7: Low bitplane
        - Bytes 8-15: High bitplane
        Each pixel is 2 bits (4 colors).
        """
        pixels: List[int] = []
        
        for row in range(8):
            low_byte = tile_data[row]
            high_byte = tile_data[row + 8]
            
            for col in range(8):
                bit_pos = 7 - col
                low_bit = (low_byte >> bit_pos) & 1
                high_bit = (high_byte >> bit_pos) & 1
                pixel = (high_bit << 1) | low_bit
                pixels.append(pixel)
        
        return pixels
    
    def _detect_font_regions(self, tiles: List[TileInfo]) -> List[FontRegion]:
        """
        Detect contiguous regions that likely contain font tiles.
        
        Font regions typically have:
        - Similar non-blank/non-solid tiles
        - Consistent complexity
        - Contiguous arrangement
        """
        regions: List[FontRegion] = []
        
        if not tiles:
            return regions
        
        # Look for runs of non-blank, non-solid tiles
        current_start: Optional[int] = None
        current_run: List[TileInfo] = []
        
        for tile in tiles:
            if not tile.is_blank and not tile.is_solid:
                if current_start is None:
                    current_start = tile.index
                current_run.append(tile)
            else:
                # End of run
                if len(current_run) >= 16:  # Minimum font size
                    region = self._classify_region(current_start, current_run)
                    if region:
                        regions.append(region)
                current_start = None
                current_run = []
        
        # Handle last run
        if len(current_run) >= 16 and current_start is not None:
            region = self._classify_region(current_start, current_run)
            if region:
                regions.append(region)
        
        return regions
    
    def _classify_region(self, start: int, tiles: List[TileInfo]) -> Optional[FontRegion]:
        """Classify a tile region as potential font."""
        if not tiles:
            return None
        
        end = tiles[-1].index
        count = len(tiles)
        
        # Heuristics for font detection
        avg_pixels = sum(t.pixel_count for t in tiles) / count
        
        notes = []
        
        # Uppercase only (26 tiles)
        if 24 <= count <= 32:
            notes.append("Uppercase alphabet")
        # Full alphabet (52 tiles)
        elif 48 <= count <= 56:
            notes.append("Full alphabet (upper+lower)")
        # Alphanumeric (62+ tiles)
        elif 60 <= count <= 72:
            notes.append("Alphanumeric charset")
        # Extended charset (96+ tiles)
        elif count >= 90:
            notes.append("Extended charset")
        else:
            notes.append("Mixed tiles")
        
        # Check pixel density (fonts typically have moderate density)
        if 10 <= avg_pixels <= 40:
            notes.append("Font-like density")
        
        return FontRegion(
            start_tile=start,
            end_tile=end,
            tile_count=count,
            estimated_chars=count,
            notes=", ".join(notes)
        )
    
    def _estimate_charset_size(self, regions: List[FontRegion]) -> int:
        """Estimate total available character count from font regions."""
        if not regions:
            return 0
        
        # Sum up estimated characters from all regions
        return sum(r.estimated_chars for r in regions)
    
    def get_tile_bitmap(self, tile_index: int) -> List[List[int]]:
        """
        Get a tile as a 2D bitmap (8x8 grid of pixel values 0-3).
        
        Useful for visualization and debugging.
        """
        if tile_index < 0 or tile_index * self.TILE_SIZE >= len(self.chr_data):
            return [[0] * 8 for _ in range(8)]
        
        tile_data = self._get_tile_data(tile_index)
        pixels = self._decode_tile_pixels(tile_data)
        
        # Convert to 2D grid
        bitmap: List[List[int]] = []
        for row in range(8):
            bitmap.append(pixels[row * 8:(row + 1) * 8])
        
        return bitmap
    
    def render_tile_ascii(self, tile_index: int) -> str:
        """Render a tile as ASCII art for debugging."""
        bitmap = self.get_tile_bitmap(tile_index)
        chars = " ░▒█"  # 4 shades for 2-bit color
        
        lines = []
        for row in bitmap:
            line = "".join(chars[min(p, 3)] for p in row)
            lines.append(line)
        
        return "\n".join(lines)


def analyze_chr_rom(rom_path: str) -> CHRAnalysis:
    """
    Convenience function to analyze a ROM's CHR data.
    
    Args:
        rom_path: Path to NES ROM file
        
    Returns:
        CHRAnalysis with detected tiles and font regions
    """
    analyzer = CHRAnalyzer()
    return analyzer.analyze_rom(rom_path)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m src.chr_analyzer <rom_path>")
        sys.exit(1)
    
    rom_path = sys.argv[1]
    analysis = analyze_chr_rom(rom_path)
    print(analysis.get_summary())
