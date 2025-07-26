# FamiLator – NES/Famicom ROM Automated Text Extraction, Translation & Reinjection

<p align="center">
  <img src="files/logo/familator_logo.png" alt="FamiLator Logo" width="200"/>
</p>

[![Repo](https://img.shields.io/badge/github-Matt--Retrogamer%2FFamiLator-blue?logo=github)](https://github.com/Matt-Retrogamer/FamiLator)


## 🕹️ Project Overview
**FamiLator** is a Python-based proof of concept for extracting, translating, and reinserting text from NES and Famicom ROMs. It automates the translation process using generative AI (via local LLMs such as OLAMA) to localize retro games with modern tooling.

Initially, the project targets simple NES games (e.g. _Tennis_, _Donkey Kong_), with plans to support more complex and text-heavy titles like _The Legend of Zelda_ and _Final Fantasy_.

## 🎯 Features
- 🧠 **Intelligent text detection** using pattern recognition and configurable encoding tables
- 📤 **Multi-format export** to structured formats (CSV/JSON) with metadata preservation
- 🤖 **LLM-powered translation** with constraint validation (OLAMA-ready)
- 📥 **Smart reinsertion** with automatic pointer updates and space optimization
- 🧪 **Comprehensive testing** including round-trip consistency and ROM integrity validation
- � **Control code handling** for formatting, colors, and special characters
- 📘 **Context-aware translation** using game lore, Wikipedia, and community databases
- 🎯 **Patch generation** for safe ROM distribution and community sharing

## 📁 File Structure
```
FamiLator/
├── roms/
│   ├── tennis.nes              # Sample test ROM (public domain or demo)
│   └── zelda.nes               # Optional: complex test ROM (not included)
├── tables/
│   ├── tennis.tbl              # Text encoding table (byte to char)
│   └── common.tbl              # Common NES character mappings
├── configs/
│   ├── tennis.yaml             # Game-specific configuration
│   ├── zelda.yaml              # Advanced game configuration
│   └── default.yaml            # Default detection parameters
├── src/
│   ├── __init__.py
│   ├── detector.py             # Automatic text pattern detection
│   ├── extractor.py            # ROM text extraction logic
│   ├── reinjector.py           # ROM text reinsertion logic
│   ├── encoding.py             # Table parser and byte-char translation
│   ├── pointer_utils.py        # Pointer parsing and patching
│   ├── validator.py            # ROM integrity and translation validation
│   └── translator_stub.py      # Interface for LLM-based translation (stub)
├── tests/
│   ├── test_extractor.py
│   ├── test_reinjector.py
│   └── test_encoding.py
├── scripts/
│   └── run_pipeline.py         # End-to-end flow: extract → translate → reinsert
├── Taskfile.yml                # Task runner definition
├── README.md
├── requirements.txt
└── pyproject.toml              # Optional project config
```

## 🛠️ Setup & Installation

Install dependencies and tools:

```bash
# Install Python dependencies
task install

# (Optional) Create and activate a virtual environment
python -m venv venv
source venv/bin/activate
```

Install the [task CLI](https://taskfile.dev/installation/) if not already:

```bash
brew install go-task/tap/go-task      # macOS
scoop install go-task                 # Windows
```

## 🚀 Running the Project with Task

```bash
# Run the full extraction → translation → reinsertion flow
task pipeline

# Just extract text from ROM
task extract

# Reinsert translated text into ROM
task inject

# Run all tests
task test
```

### 🎯 Task Targets
| Command          | Description                              |
|------------------|------------------------------------------|
| `task install`   | Install Python dependencies              |
| `task extract`   | Run the extractor on `tennis.nes`        |
| `task inject`    | Reinsert (mock or translated) text       |
| `task pipeline`  | Run full extraction → LLM → injection    |
| `task test`      | Run all automated unit tests             |

## 🧾 Table Files (.tbl Format)
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

## 🔍 ROMs
This project requires test ROMs that are public domain or legally owned.

### Suggested Test ROMs
- `tennis.nes` — minimal text, great for proof of concept
- `donkey_kong.nes` — slightly more strings
- `rygar_jp.nes` — Japanese Famicom game with pointer tables

_❌ No copyrighted ROMs will be included._

## 🤖 LLM Integration (Stub)
Translation will eventually be handled by a local LLM (like LLaMA via OLAMA server). Placeholder code is provided in `translator_stub.py`.

Translation constraints to consider:
- Preserve tags and formatting
- Match or limit output string length
- (Future) Apply tone/style constraints based on game genre

## 🧠 Contextual Enhancement (Planned)
To improve translation quality, **FamiLator** will extract additional context from trusted external sources.

### Planned Enhancement:
- Automatically fetch the **Wikipedia page** of the game in the **target translation language**
- Use this summary to improve translation context with:
  - Plot summaries
  - Character and enemy names
  - Setting and tone
  - Series-specific terms

This provides the LLM with extra narrative cues to ensure consistent and accurate localization.

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

## 🧭 Roadmap

### Phase 1: Foundation (Current)
- [x] Project structure and documentation
- [ ] Basic text extractor for fixed strings
- [ ] Simple encoding table parser (.tbl format)
- [ ] End-to-end test with Tennis ROM

### Phase 2: Core Features
- [ ] Pointer table detection and parsing
- [ ] Control code handling (colors, formatting)
- [ ] Text reinsertion with pointer updates
- [ ] Round-trip validation tests

### Phase 3: AI Integration
- [ ] Local LLM integration (OLAMA)
- [ ] Translation constraint validation
- [ ] Wikipedia context scraping
- [ ] Batch translation workflows

### Phase 4: Advanced Features
- [ ] Automatic text pattern detection
- [ ] Support for compressed text formats
- [ ] Multi-byte character encoding (Japanese games)
- [ ] ROM visualization tools

### Phase 5: Community
- [ ] CLI with game-specific presets
- [ ] Patch generation and distribution
- [ ] Integration with existing ROM hacking tools
- [ ] Documentation for adding new games

## 📜 License
MIT License. See `LICENSE` file for full terms.

## 🙌 Credits
- NESDev Wiki — https://wiki.nesdev.org/
- ROMHacking.net — https://www.romhacking.net/
- DataCrystal Wiki — https://datacrystal.romhacking.net/
- Jackic's translation tooling — https://jackicblog.blogspot.com/2025/03/traduciendo-roms-de-8-bits-con-ai.html