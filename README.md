# FamiLator – NES/Famicom ROM Automated Text Extraction, Translation & Reinjection

<p align="center">
  <img src="files/logo/familator_logo.png" alt="FamiLator Logo" width="200"/>
</p>

[![Repo](https://img.shields.io/badge/github-Matt--Retrogamer%2FFamiLator-blue?logo=github)](https://github.com/Matt-Retrogamer/FamiLator)


## 🕹️ Project Overview
**FamiLator** is a Python-based proof of concept for extracting, translating, and reinserting text from NES and Famicom ROMs. It automates the translation process using generative AI (via local LLMs such as OLAMA) to localize retro games with modern tooling.

Initially, the project targets simple NES games (e.g. _Tennis_, _Donkey Kong_), with plans to support more complex and text-heavy titles like _The Legend of Zelda_ and _Final Fantasy_.

## 🎯 Features
- 🧠 Extract in-ROM text using a configurable encoding table
- 📤 Export text to structured formats (CSV/JSON)
- 🤖 Plug-in interface for LLM-based translation (OLAMA-ready)
- 📥 Reinsert translated text with pointer and space validation
- 🧪 Automated test suite for round-trip consistency
- 📘 Future: context-aware translation using game lore and Wikipedia

## 📁 File Structure
```
FamiLator/
├── roms/
│   ├── tennis.nes              # Sample test ROM (public domain or demo)
│   └── zelda.nes               # Optional: complex test ROM (not included)
├── tables/
│   └── tennis.tbl              # Text encoding table (byte to char)
├── src/
│   ├── __init__.py
│   ├── extractor.py            # ROM text extraction logic
│   ├── reinjector.py           # ROM text reinsertion logic
│   ├── encoding.py             # Table parser and byte-char translation
│   ├── pointer_utils.py        # Pointer parsing and patching
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

Table files can be built manually or sourced from community resources like:
- https://www.romhacking.net/
- https://datacrystal.romhacking.net/

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

## 🧭 Roadmap
- [x] Minimal working text extractor
- [x] README and folder structure
- [ ] Text reinsertion with pointer update logic
- [ ] End-to-end test with no-op reinsert
- [ ] Plug in local LLM with translation constraints
- [ ] Add CLI options and presets per game
- [ ] Add Wikipedia-based context scraping for translation enhancement
- [ ] Optional: ROM visualization (hex preview, pointer map, etc.)

## 📜 License
MIT License. See `LICENSE` file for full terms.

## 🙌 Credits
- NESDev Wiki — https://wiki.nesdev.org/
- ROMHacking.net — https://www.romhacking.net/
- DataCrystal Wiki — https://datacrystal.romhacking.net/
- Jackic's translation tooling — https://jackicblog.blogspot.com/2025/03/traduciendo-roms-de-8-bits-con-ai.html