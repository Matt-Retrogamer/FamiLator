"""
Translation project state management.

Manages the entire translation workflow state, allowing resumption
of interrupted work and tracking progress.
"""

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ProjectStatus(Enum):
    """Status of the translation project."""
    
    CREATED = "created"
    ANALYZING = "analyzing"
    EXTRACTING = "extracting"
    TRANSLATING = "translating"
    REINJECTING = "reinjecting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TranslationEntry:
    """A single string translation entry."""
    
    string_id: str
    address: int
    original_text: str
    translated_text: str = ""
    status: str = "pending"  # pending, translated, reviewed, skipped
    confidence: float = 0.0
    notes: str = ""
    max_bytes: int = 0
    pointer_address: Optional[int] = None


@dataclass 
class ProjectConfig:
    """Project configuration settings."""
    
    rom_path: str
    source_language: str
    target_language: str
    output_dir: str
    game_name: str = "Unknown Game"
    encoding_table: str = "tables/common.tbl"
    detection_method: str = "auto_detect"
    llm_provider: str = "ollama"
    llm_model: str = "llama3"
    llm_base_url: str = "http://localhost:11434"
    mock_translation: bool = False
    auto_mode: bool = False


@dataclass
class ProjectState:
    """Complete project state for persistence."""
    
    version: str = "1.0"
    created_at: str = ""
    updated_at: str = ""
    status: str = "created"
    config: Optional[Dict[str, Any]] = None
    rom_analysis: Optional[Dict[str, Any]] = None
    extraction_stats: Optional[Dict[str, Any]] = None
    translation_progress: Dict[str, Any] = field(default_factory=dict)
    validation_results: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)


class TranslationProject:
    """
    Manages a complete ROM translation project.
    
    Handles the full workflow: analysis → extraction → translation → reinjection.
    Supports saving/loading state for resuming interrupted work.
    """
    
    STATE_FILENAME = "project_state.json"
    CONFIG_FILENAME = "project_config.yaml"
    TRANSLATIONS_FILENAME = "translations.json"
    
    def __init__(
        self,
        rom_path: str,
        source_language: str = "Japanese",
        target_language: str = "English",
        output_dir: Optional[str] = None,
        auto_mode: bool = False,
    ):
        """
        Initialize a translation project.
        
        Args:
            rom_path: Path to the input ROM file
            source_language: Source language of the ROM text
            target_language: Target language for translation
            output_dir: Output directory (auto-generated if not specified)
            auto_mode: If True, use automatic defaults for unknown ROMs
        """
        self.rom_path = Path(rom_path).resolve()
        
        if not self.rom_path.exists():
            raise FileNotFoundError(f"ROM file not found: {rom_path}")
        
        # Generate output directory from ROM name if not specified
        if output_dir is None:
            rom_stem = self.rom_path.stem.lower().replace(" ", "_")
            lang_suffix = target_language.lower()[:2]
            output_dir = f"output/{rom_stem}_{lang_suffix}"
        
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize configuration
        self.config = ProjectConfig(
            rom_path=str(self.rom_path),
            source_language=source_language,
            target_language=target_language,
            output_dir=str(self.output_dir),
            game_name=self._derive_game_name(),
            auto_mode=auto_mode,
        )
        
        # Initialize state
        self.state = ProjectState(
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            config=asdict(self.config),
        )
        
        # Translation entries
        self.translations: List[TranslationEntry] = []
        
        # Glossary for consistent terminology
        self.glossary: Dict[str, str] = {}
        
        # Check for existing project state
        self._load_existing_state()
    
    def _derive_game_name(self) -> str:
        """Derive a clean game name from the ROM filename."""
        name = self.rom_path.stem
        # Remove common suffixes
        for suffix in ["(Japan)", "(USA)", "(Europe)", "(J)", "(U)", "(E)"]:
            name = name.replace(suffix, "")
        return name.strip()
    
    def _load_existing_state(self) -> None:
        """Load existing project state if available."""
        state_path = self.output_dir / self.STATE_FILENAME
        
        if state_path.exists():
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                self.state = ProjectState(**data)
                print(f"📂 Loaded existing project state (status: {self.state.status})")
                
                # Load translations if available
                self._load_translations()
                
            except Exception as e:
                print(f"⚠️  Could not load existing state: {e}")
    
    def _load_translations(self) -> None:
        """Load translation entries from file."""
        translations_path = self.output_dir / self.TRANSLATIONS_FILENAME
        
        if translations_path.exists():
            try:
                with open(translations_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                self.translations = [
                    TranslationEntry(**entry) for entry in data.get("entries", [])
                ]
                self.glossary = data.get("glossary", {})
                
                # Count progress
                translated = sum(1 for t in self.translations if t.status == "translated")
                total = len(self.translations)
                print(f"   Loaded {translated}/{total} translations")
                
            except Exception as e:
                print(f"⚠️  Could not load translations: {e}")
    
    def save_state(self) -> None:
        """Save current project state to disk."""
        self.state.updated_at = datetime.now().isoformat()
        
        # Save main state
        state_path = self.output_dir / self.STATE_FILENAME
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.state), f, indent=2, ensure_ascii=False)
        
        # Save config as YAML for easy editing
        config_path = self.output_dir / self.CONFIG_FILENAME
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(asdict(self.config), f, default_flow_style=False)
        
        # Save translations
        self._save_translations()
    
    def _save_translations(self) -> None:
        """Save translation entries to file."""
        translations_path = self.output_dir / self.TRANSLATIONS_FILENAME
        
        data = {
            "entries": [asdict(t) for t in self.translations],
            "glossary": self.glossary,
            "stats": self.get_translation_stats(),
        }
        
        with open(translations_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def update_status(self, status: ProjectStatus) -> None:
        """Update project status."""
        self.state.status = status.value
        self.save_state()
    
    def add_error(self, error: str) -> None:
        """Log an error to the project state."""
        self.state.errors.append(f"[{datetime.now().isoformat()}] {error}")
        self.save_state()
    
    def get_translation_stats(self) -> Dict[str, Any]:
        """Get translation progress statistics."""
        if not self.translations:
            return {"total": 0, "translated": 0, "reviewed": 0, "pending": 0}
        
        stats = {
            "total": len(self.translations),
            "translated": sum(1 for t in self.translations if t.status == "translated"),
            "reviewed": sum(1 for t in self.translations if t.status == "reviewed"),
            "pending": sum(1 for t in self.translations if t.status == "pending"),
            "skipped": sum(1 for t in self.translations if t.status == "skipped"),
        }
        stats["progress_percent"] = round(
            (stats["translated"] + stats["reviewed"]) / stats["total"] * 100, 1
        )
        return stats
    
    def find_or_create_config(self) -> Path:
        """
        Find existing game config or create one from defaults.
        
        Returns:
            Path to the configuration file
        """
        # Check for game-specific config
        game_key = self.config.game_name.lower().replace(" ", "_")
        
        # Look for existing configs that match
        configs_dir = Path("configs")
        for config_file in configs_dir.glob("*.yaml"):
            if game_key in config_file.stem.lower():
                print(f"📋 Found matching config: {config_file}")
                return config_file
        
        # Create project-specific config
        project_config_path = self.output_dir / "game_config.yaml"
        
        if not project_config_path.exists():
            config_data = self._generate_auto_config()
            with open(project_config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False)
            print(f"📝 Generated auto-config: {project_config_path}")
        
        return project_config_path
    
    def _generate_auto_config(self) -> Dict[str, Any]:
        """Generate automatic configuration for unknown ROMs."""
        return {
            "game": {
                "name": self.config.game_name,
                "region": "Unknown",
            },
            "text_detection": {
                "method": "auto_detect",
                "encoding_table": self.config.encoding_table,
                "auto_detect": {
                    "min_string_length": 3,
                    "max_string_length": 200,
                    "confidence_threshold": 0.5,
                    "entropy_min": 2.0,
                    "entropy_max": 6.0,
                    "common_char_threshold": 0.3,
                },
            },
            "translation": {
                "source_language": self.config.source_language,
                "target_language": self.config.target_language,
                "model": self.config.llm_model,
                "base_url": self.config.llm_base_url,
                "temperature": 0.3,
                "game_context": f"Video game: {self.config.game_name}",
            },
            "pointers": {
                "enabled": False,
            },
            "validation": {
                "perform_basic_checks": True,
            },
        }
    
    def get_output_paths(self) -> Dict[str, Path]:
        """Get paths for all output files."""
        base_name = self.config.game_name.lower().replace(" ", "_")
        
        return {
            "extracted_csv": self.output_dir / f"{base_name}_extracted.csv",
            "extracted_json": self.output_dir / f"{base_name}_extracted.json",
            "translated_csv": self.output_dir / f"{base_name}_translated.csv",
            "translated_rom": self.output_dir / f"{base_name}_translated.nes",
            "patch_ips": self.output_dir / f"{base_name}_translation.ips",
            "validation_report": self.output_dir / f"{base_name}_validation_report.txt",
            "project_state": self.output_dir / self.STATE_FILENAME,
            "translations_json": self.output_dir / self.TRANSLATIONS_FILENAME,
        }
    
    def copy_rom_to_output(self) -> Path:
        """Copy the original ROM to output directory for reference."""
        dest = self.output_dir / f"original_{self.rom_path.name}"
        if not dest.exists():
            shutil.copy2(self.rom_path, dest)
        return dest
    
    def __repr__(self) -> str:
        stats = self.get_translation_stats()
        return (
            f"TranslationProject(\n"
            f"  game='{self.config.game_name}',\n"
            f"  rom='{self.rom_path.name}',\n"
            f"  {self.config.source_language} → {self.config.target_language},\n"
            f"  status={self.state.status},\n"
            f"  progress={stats.get('progress_percent', 0)}%\n"
            f")"
        )
