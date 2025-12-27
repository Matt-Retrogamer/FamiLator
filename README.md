# FamiLator – NES/Famicom ROM Automated Text Extraction, Translation & Reinjection

<p align="center">
  <img src="files/logo/familator_logo.png" alt="FamiLator Logo" width="200"/>
</p>

[![Repo](https://img.shields.io/badge/github-Matt--Retrogamer%2FFamiLator-blue?logo=github)](https://github.com/Matt-Retrogamer/FamiLator)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![UV](https://img.shields.io/badge/package%20manager-UV-blue)](https://github.com/astral-sh/uv)
[![Tests](https://img.shields.io/badge/tests-15%20passing-green)](tests/)


## 🕹️ Project Overview
**FamiLator** is a complete Python-based system for extracting, translating, and reinserting text from NES and Famicom ROMs. It automates the translation process using modern AI (local LLMs via OLLAMA) to localize retro games with professional-grade tooling.

The project supports both simple games (_Tennis_) and complex titles with pointer tables (_The Legend of Zelda_), providing a comprehensive ROM hacking and translation workflow.

## 🎯 Features
- ⚡ **One-command workflow** — Select ROM, specify languages, get translated patch automatically
- 📂 **Project management** — Save/resume projects, track progress, edit and re-apply translations
- 🌐 **Language detection** — Automatic Japanese/English detection from extracted text
- 🎨 **CHR ROM analysis** — Detect available tiles, font regions, and character sets
- 🔤 **Font compatibility** — Validate and auto-fix translations for available glyphs
- 🧠 **Intelligent text detection** using pattern recognition and configurable encoding tables
- 📤 **Multi-format export** to structured formats (CSV/JSON) with metadata preservation
- 🤖 **LLM-powered translation** with retry logic, batch processing, and constraint validation
- 📚 **Glossary & translation memory** — Per-project terminology management and caching
- 📥 **Smart reinsertion** with automatic pointer updates and space optimization
- 🧪 **Comprehensive testing** including round-trip consistency and ROM integrity validation
- 🎛️ **Control code handling** for formatting, colors, and special characters
- 📘 **Context-aware translation** using game lore, Wikipedia, and community databases
- 🎯 **Patch generation** for safe ROM distribution and community sharing

## 📁 File Structure
```
FamiLator/
├── pyproject.toml             # UV project configuration with hatchling build system
├── uv.lock                    # UV lockfile for reproducible builds
├── Taskfile.yml               # Task automation (install, test, format, lint, demo)
├── README.md                  # Project documentation
├── requirements-dev.txt       # Development dependencies (legacy fallback)
├── roms_input/               # Input ROMs directory
│   ├── PUT_YOUR_ROMS_HERE   # Placeholder for user ROMs
│   └── test.nes             # Test ROM for development
├── configs/                  # Game-specific configuration files
│   ├── default.yaml         # Default extraction settings
│   ├── tennis.yaml          # Tennis-specific configuration
│   ├── test.yaml            # Test ROM configuration
│   └── zelda.yaml           # Legend of Zelda configuration
├── tables/                   # Character encoding tables
│   ├── common.tbl           # Standard NES character mappings
│   └── tennis.tbl           # Tennis-specific character table
├── src/                      # Core FamiLator modules
│   ├── __init__.py          # Package initialization
│   ├── cli.py               # Unified command-line interface
│   ├── pipeline.py          # Translation pipeline orchestration
│   ├── project.py           # Project state management
│   ├── chr_analyzer.py      # CHR ROM tile/font analysis
│   ├── detector.py          # Text detection algorithms (entropy, frequency, terminators)
│   ├── encoding.py          # Character encoding/decoding with .tbl support
│   ├── extractor.py         # ROM text extraction with metadata preservation
│   ├── font_checker.py      # Font compatibility validation & auto-fix
│   ├── language_detector.py # Automatic Japanese/English language detection
│   ├── pointer_utils.py     # Pointer table manipulation utilities
│   ├── reinjector.py        # Text reinsertion with pointer updates
│   ├── translator.py        # Enhanced LLM translation with glossary & memory
│   ├── translator_stub.py   # OLLAMA LLM integration and mock translation (legacy)
│   └── validator.py         # ROM integrity and translation validation
├── tests/                    # Comprehensive test suite (15 tests)
│   ├── test_encoding.py     # Encoding/decoding tests
│   ├── test_extractor.py    # Text extraction tests
│   └── test_reinjector.py   # Reinsertion and validation tests
├── scripts/                  # Automation and pipeline scripts
│   └── run_pipeline.py      # Complete extraction → translation → reinsertion workflow
├── output/                   # Generated files and results
│   ├── test_rom_extracted.csv        # Extracted text in CSV format
│   ├── test_rom_extracted.json       # Extracted text in JSON format
│   ├── test_rom_translated.csv       # Translated text data
│   ├── test_rom_translated.nes       # Final translated ROM
│   ├── test_rom_translation.ips      # IPS patch file
│   └── test_rom_validation_report.txt # Validation analysis
└── files/                    # Project assets
    └── logo/
        └── familator_logo.png # Project logo
```
## 🛠️ Setup & Installation

### Prerequisites
- **Python 3.9+** (required)
- **UV Package Manager** (recommended for fast dependency management)
- **Task CLI** (for task automation)

### Quick Start with UV (Recommended)

```bash
# Install UV package manager (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/Matt-Retrogamer/FamiLator.git
cd FamiLator

# Install dependencies with UV
task install-dev

# Run the complete pipeline
task demo
```

### Alternative Setup (Traditional)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements-dev.txt

# Install in development mode
pip install -e .
```

### Install Task CLI

```bash
brew install go-task/tap/go-task      # macOS
scoop install go-task                 # Windows
# or download from: https://taskfile.dev/installation/
```

## 🚀 Running FamiLator

### ⚡ Quick Start — One Command Translation
```bash
# Translate any ROM with a single command!
familator translate --rom game.nes --source japanese --target english --auto

# Or use the task shortcut
task tr -- game.nes
```

This will automatically:
1. 📊 Analyze the ROM structure
2. 📤 Extract all translatable text
3. 🤖 Translate via LLM (or mock mode)
4. 📥 Reinject translations into ROM
5. 🎯 Generate IPS patch for distribution
6. ✅ Validate ROM integrity

### Demo with Test ROM
```bash
# Run demo with included test ROM
task demo

# Output files in: output/test_en/
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `familator translate --rom X --source X --target X` | Full translation pipeline |
| `familator extract --rom X` | Extract text only (for manual review) |
| `familator apply --project X` | Re-apply edited translations |
| `familator status --project X` | Show project progress |
| `familator list --projects` | List all translation projects |
| `familator list --roms` | List available ROMs |

### Task Runner Shortcuts

| Command | Description |
|---------|-------------|
| `task demo` | Run demo with test ROM |
| `task tr -- game.nes` | Quick translate (auto + mock mode) |
| `task projects` | List all translation projects |
| `task roms` | List available ROMs |
| `task project-status -- output/proj` | Show project status |
| `task apply-translations -- output/proj` | Apply edited translations |
| `task test` | Run all 15 unit tests |
| `task format` | Format code with Black and isort |
| `task lint` | Run flake8 linter |
| `task clean` | Clean output files |

### Development Workflow
```bash
# Set up development environment
task install-dev

# Make code changes...

# Check formatting and run tests
task format-check
task lint  
task type-check
task test

# Auto-format if needed
task format

# Test full pipeline
task demo
```

## 📂 Project Management

FamiLator now supports persistent project management, allowing you to pause and resume translation work.

### Project Structure
Each translation creates a project folder with:
```
output/game_name_en/
├── project_state.json       # Project status and metadata
├── project_config.yaml      # Editable configuration
├── translations.json        # All strings with progress tracking
├── glossary.json            # Per-project terminology (auto-updated)
├── translation_memory.json  # Cached translations for reuse
├── game_config.yaml         # Auto-generated game settings
├── game_name_extracted.csv  # Extracted text
├── game_name_translated.csv # Translations (editable!)
├── game_name_translated.nes # Patched ROM
└── game_name_translation.ips # IPS patch for distribution
```

### Resume Interrupted Work
```bash
# Check project status
familator status --project output/my_game_en

# Continue where you left off
familator translate --rom game.nes --resume
```

### Edit and Re-apply Translations
```bash
# 1. Run initial translation
familator translate --rom game.nes --source japanese --target english --auto

# 2. Edit the CSV file manually to fix translations
# Open: output/game_en/game_translated.csv

# 3. Re-apply your edits
familator apply --project output/game_en

# New ROM and IPS patch are generated with your fixes!
```

## � Test Coverage & Validation

FamiLator includes comprehensive testing to ensure reliability and data integrity.

### Test Suite (15 Tests - All Passing ✅)
```bash
# Run all tests
task test

# Tests include:
# - Encoding/decoding with various character tables
# - Text extraction from different ROM formats  
# - Pointer table manipulation and updates
# - Translation workflow validation
# - ROM integrity verification
# - Round-trip consistency checks
```

### Validation Features
- ✅ **CRC32 checksums** to detect ROM corruption
- ✅ **File size validation** against expected ROM sizes
- ✅ **Header verification** for NES ROM format compliance
- ✅ **Memory boundary checks** to prevent overwrites
- ✅ **Control code preservation** ensuring format integrity
- ✅ **Translation length validation** against memory constraints
- ✅ **Round-trip testing** (extract → translate → reinject → verify)

### Example Validation Report
```
ROM Validation Report
===================
Original ROM: test.nes (32KB)
Translated ROM: output/test_rom_translated.nes (32KB)
IPS Patch: output/test_rom_translation.ips (157 bytes)

✅ File size matches expected: 32768 bytes
✅ NES header validation passed
✅ CRC32 integrity check passed
✅ All 12 text strings successfully processed
✅ Pointer table consistency verified
✅ No code region overwrites detected
✅ Control codes preserved in translation

Translation Summary:
- Original strings: 12
- Successfully translated: 12
- Average confidence: 98.5%
- Total text expansion: +2.3% (within limits)
```

## �🧾 Table Files (.tbl Format)
NES games use custom byte encodings. Table files describe these encodings.

Example `tennis.tbl`:
```
41=A
42=B
43=C
20= 
FF=<END>
```

**Enhanced table format** for control codes:
```
# Basic characters
41=A
42=B
43=C
20= 

# Control codes
FE=<NEWLINE>
FD=<PAUSE>
FC=<COLOR:RED>
FB=<COLOR:BLUE>
FF=<END>

# Multi-byte sequences
F0XX=<DELAY:XX>
F1XXYY=<GOTO:XXYY>
```

Table files can be built manually or sourced from community resources like:
- https://www.romhacking.net/
- https://datacrystal.romhacking.net/

## ⚙️ Game Configuration Files
Each game needs a YAML configuration describing its text storage structure.

Example `configs/tennis.yaml`:
```yaml
game:
  name: "Tennis"
  region: "USA"
  crc32: "0x12345678"

text_detection:
  method: "fixed_locations"
  encoding_table: "tables/tennis.tbl"
  
  # Known text locations
  strings:
    - address: 0x8000
      length: 20
      description: "Game title"
    - address: 0x8050
      length: 15
      description: "Player names"

pointers:
  enabled: false  # Tennis has no pointer tables

validation:
  checksum_offset: 0x7FFF
  expected_size: 32768
```

Example `configs/zelda.yaml` (more complex):
```yaml
game:
  name: "The Legend of Zelda"
  region: "USA"
  crc32: "0x87654321"

text_detection:
  method: "pointer_table"
  encoding_table: "tables/zelda.tbl"
  
  # Pointer table location
  pointer_table:
    address: 0x17B73
    count: 124
    format: "little_endian_16bit"
    base_offset: 0x18000

  # Control codes
  control_codes:
    0xFE: "<NEWLINE>"
    0xFD: "<PAUSE>"
    0xFC: "<PLAYER_NAME>"
    0xFF: "<END>"

validation:
  checksum_offset: 0x7FFF
  expected_size: 131072
```

## 🎮 ROM Requirements & Testing

### Included Test ROMs
- ✅ **test.nes** — Development test ROM with known text patterns
- 📋 **PUT_YOUR_ROMS_HERE** — Placeholder for user-provided ROMs

### Supported ROM Types
- ✅ **iNES format** (.nes files) with proper headers
- ✅ **Fixed-location text** (simple games like Tennis)
- ✅ **Pointer table text** (complex games like Zelda)
- ✅ **Mixed text storage** (combination of both methods)

### ROM Testing Workflow
```bash
# Test with included test ROM
task demo

# Test with your own ROM
cp your_game.nes roms_input/
# Configure in configs/your_game.yaml
task extract GAME=your_game
```

### Legal Compliance
- ✅ **IPS patch generation** for safe distribution
- ✅ **No copyrighted ROMs** included in repository
- ✅ **Patch-only workflow** respects copyright holders
- ✅ **Community standards** following ROM hacking best practices

## 🤖 LLM Translation System
FamiLator includes a complete translation system supporting both local LLMs and mock translation for development.

### OLLAMA Integration
```bash
# Install OLLAMA (if not installed)
curl -fsSL https://ollama.ai/install.sh | sh

# Download a model (e.g., llama2)
ollama pull llama2

# Start OLLAMA server
ollama serve

# FamiLator will automatically use OLLAMA for translation
task translate
```

### Translation Features
- ✅ **Context-aware prompts** with game information and lore
- ✅ **Length constraint validation** to fit memory limits
- ✅ **Format preservation** for control codes and special characters
- ✅ **Confidence scoring** with warning system for questionable translations
- ✅ **Mock mode** for testing without LLM dependency
- ✅ **Batch processing** for efficient translation of multiple strings

### Translation Workflow
1. **Extract** text with metadata (address, length, context)
2. **Analyze** constraints (character limits, formatting requirements)
3. **Generate** context-aware prompts with game-specific information
4. **Translate** via OLLAMA or mock system
5. **Validate** output against constraints and format requirements
6. **Score** confidence and flag potential issues

## 🧠 Contextual Translation Enhancement
FamiLator provides rich context to improve translation quality and consistency.

### Current Context Sources
- ✅ **Game configuration** with title, region, and technical details
- ✅ **Text metadata** including memory address and string purpose
- ✅ **Control code preservation** for formatting and special characters
- ✅ **Length constraints** based on available memory space
- ✅ **Character encoding** limitations from .tbl files

### Enhanced Context (Future)
- 📋 **Wikipedia integration** for plot summaries and character names
- 📋 **Community databases** for established translation conventions
- 📋 **Glossary management** for consistent terminology
- 📋 **Translation memory** for reusing previous work

### Context-Aware Translation Process
1. **Analyze** source string for technical constraints and formatting
2. **Gather** game-specific context and established terminology
3. **Generate** rich prompts with cultural and technical context
4. **Validate** translations against format and length requirements
5. **Score** confidence based on constraint compliance and context usage

## ⚠️ Technical Challenges & Considerations

### Text Detection Challenges
- **Variable text locations**: Not all games store text in predictable locations
- **Graphics vs byte text**: Some games render text as tile graphics rather than character data
- **Compressed formats**: Advanced games may use compression algorithms
- **Bank switching**: Large ROMs may spread text across multiple memory banks

### Translation Constraints
- **Byte-accurate limits**: Translated text must fit exact memory spaces, not just character counts
- **Font limitations**: Target ROM may not contain all characters needed for translation
- **Cultural adaptation**: Direct translation may not convey intended meaning
- **Technical terminology**: Game-specific terms need consistent translation

### Reinsertion Complexity
- **Pointer chain updates**: Changing text length affects multiple pointer references
- **Memory fragmentation**: Longer translations may require text relocation
- **Control code preservation**: Formatting and special characters must be maintained
- **Checksum validation**: Some ROMs have integrity checks that must be updated

### Legal & Distribution
- **Patch vs ROM distribution**: Generate IPS/BPS patches instead of modified ROMs
- **Fair use compliance**: Ensure translation work falls under fair use provisions
- **Community standards**: Follow established ROM hacking community practices

## 🧭 Current Implementation Status

### ✅ Phase 1: Foundation (COMPLETED)
- ✅ **Project structure** and comprehensive documentation
- ✅ **UV package manager** with modern build system (hatchling)
- ✅ **Text extractor** supporting fixed strings and pointer tables
- ✅ **Encoding table parser** (.tbl format) with control code support
- ✅ **End-to-end testing** with test ROM and 15 unit tests
- ✅ **Task automation** with 20+ development and production commands

### ✅ Phase 2: Core Features (COMPLETED)
- ✅ **Pointer table detection** and parsing (16-bit little/big endian)
- ✅ **Control code handling** (colors, formatting, special sequences)
- ✅ **Text reinsertion** with automatic pointer updates
- ✅ **Round-trip validation** ensuring data integrity
- ✅ **Memory protection** preventing code region overwrites
- ✅ **IPS patch generation** for community-friendly distribution

### ✅ Phase 3: AI Integration (COMPLETED)
- ✅ **Local LLM integration** (OLLAMA) with mock translation fallback
- ✅ **Translation constraint validation** (length limits, format preservation)
- ✅ **Context-aware prompts** with game-specific information
- ✅ **Batch translation workflows** with confidence scoring
- ✅ **Comprehensive validation** of translated content

### ✅ Phase 4: Advanced Features (COMPLETED)
- ✅ **Automatic text pattern detection** using entropy and frequency analysis
- ✅ **Multi-format export** (CSV, JSON) with metadata preservation
- ✅ **Professional development workflow** with code quality tools
- ✅ **ROM integrity validation** (CRC32, size checks, headers)
- ✅ **Configurable game profiles** (Tennis, Zelda, custom configurations)

### ✅ Phase 5: Streamlined Workflow (COMPLETED)
- ✅ **Unified CLI** (`familator translate/extract/apply/status/list`)
- ✅ **One-command translation** — ROM + languages → translated patch
- ✅ **Project management** — save/resume projects, track progress
- ✅ **Edit & re-apply workflow** — manually refine translations
- ✅ **Auto-config generation** for unknown ROMs
- ✅ **Task runner shortcuts** for common operations

### ✅ Phase 6: Enhanced Detection & Translation (COMPLETED)
- ✅ **Language detection** — automatic Japanese/English detection via Unicode ranges
- ✅ **Enhanced LLM translation** with retry logic (max 3 attempts) and exponential backoff
- ✅ **Batch translation** — process multiple strings with context preservation
- ✅ **Glossary support** — per-project terminology management with auto-save
- ✅ **Translation memory** — cache and reuse previous translations
- ✅ **Confidence scoring** — track translation quality metrics
- ✅ **Progress tracking** — detailed timing and success/failure counts

### ✅ Phase 7: Font & Character Analysis (COMPLETED)
- ✅ **CHR ROM analysis** — detect tile count, font regions, and CHR type (ROM/RAM)
- ✅ **Font compatibility checking** — validate translations against available characters
- ✅ **Auto-substitution** — replace incompatible characters (accents, symbols, punctuation)
- ✅ **Character mapping report** — identify missing glyphs with suggestions

### 🔄 Phase 8: Web Interface (Planned)
- 📋 **Web-based UI** for non-technical users
- 📋 **Visual tile/font browser**
- 📋 **Interactive translation editor**
- 📋 **Project sharing and collaboration**

## 🚀 Quick Start Summary

```bash
# 1. Setup with UV (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/Matt-Retrogamer/FamiLator.git
cd FamiLator
task install-dev

# 2. Translate a ROM (one command!)
familator translate --rom roms_input/game.nes --source japanese --target english --auto

# Or run demo with test ROM
task demo

# 3. Check your project
familator list --projects
familator status --project output/game_en

# 4. Edit translations and re-apply
# (edit the CSV file manually, then:)
familator apply --project output/game_en
```

**FamiLator is production-ready** with all core features implemented, comprehensive testing, and professional development workflow. Ready for ROM translation projects! 🎯

## �📜 License
MIT License. See `LICENSE` file for full terms.

## 🙌 Credits
- NESDev Wiki — https://wiki.nesdev.org/
- ROMHacking.net — https://www.romhacking.net/
- DataCrystal Wiki — https://datacrystal.romhacking.net/
- Jackic's translation tooling — https://jackicblog.blogspot.com/2025/03/traduciendo-roms-de-8-bits-con-ai.html