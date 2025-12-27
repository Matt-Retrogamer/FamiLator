"""
Translation pipeline orchestration.

Coordinates the complete extraction → translation → reinjection workflow.
"""

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Handle imports
try:
    from .project import ProjectStatus, TranslationProject, TranslationEntry
    from .extractor import TextExtractor
    from .reinjector import TextReinjector
    from .translator_stub import TranslatorStub, TranslationRequest
    from .validator import ROMValidator
except ImportError:
    from project import ProjectStatus, TranslationProject, TranslationEntry
    from extractor import TextExtractor
    from reinjector import TextReinjector
    from translator_stub import TranslatorStub, TranslationRequest
    from validator import ROMValidator


@dataclass
class PipelineResult:
    """Result of a pipeline operation."""
    
    success: bool
    stage: str
    error: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None


class TranslationPipeline:
    """
    Orchestrates the complete ROM translation workflow.
    
    Stages:
    1. Analysis - Analyze ROM structure and detect text
    2. Extraction - Extract translatable strings
    3. Translation - Translate via LLM
    4. Reinjection - Put translations back into ROM
    5. Validation - Verify ROM integrity
    """
    
    def __init__(self, project: TranslationProject):
        """
        Initialize the pipeline.
        
        Args:
            project: The translation project to process
        """
        self.project = project
        self.extractor: Optional[TextExtractor] = None
        self.reinjector: Optional[TextReinjector] = None
        self.translator: Optional[TranslatorStub] = None
    
    def run_full_pipeline(self, skip_validation: bool = False) -> PipelineResult:
        """
        Run the complete translation pipeline.
        
        Args:
            skip_validation: If True, skip ROM validation
            
        Returns:
            Pipeline result
        """
        print("🚀 Starting full translation pipeline...")
        print()
        
        # Stage 1: Extraction
        result = self.run_extraction()
        if not result.success:
            return result
        
        # Stage 2: Translation
        result = self.run_translation()
        if not result.success:
            return result
        
        # Stage 3: Reinjection
        result = self.run_reinjection(skip_validation=skip_validation)
        if not result.success:
            return result
        
        # Stage 4: Generate patch
        result = self.run_patch_generation()
        if not result.success:
            return result
        
        # Mark complete
        self.project.update_status(ProjectStatus.COMPLETED)
        
        return PipelineResult(
            success=True,
            stage="complete",
            stats=self.project.get_translation_stats(),
        )
    
    def run_extraction(self) -> PipelineResult:
        """
        Run the extraction stage.
        
        Returns:
            Pipeline result
        """
        print("📤 Stage 1: Extracting text...")
        self.project.update_status(ProjectStatus.EXTRACTING)
        
        try:
            # Find or create config
            config_path = self.project.find_or_create_config()
            
            # Initialize extractor
            self.extractor = TextExtractor(str(config_path))
            
            # Extract strings
            extracted = self.extractor.extract_from_rom(str(self.project.rom_path))
            
            print(f"   ✓ Extracted {len(extracted)} strings")
            
            # Convert to translation entries
            self.project.translations = []
            for i, string in enumerate(extracted):
                entry = TranslationEntry(
                    string_id=string.string_id or f"string_{i+1:03d}",
                    address=string.address,
                    original_text=string.decoded_text,
                    translated_text="",
                    status="pending",
                    max_bytes=len(string.original_bytes),
                    pointer_address=string.pointer_address,
                )
                self.project.translations.append(entry)
            
            # Export to files
            paths = self.project.get_output_paths()
            self.extractor.export_to_csv(str(paths["extracted_csv"]))
            self.extractor.export_to_json(str(paths["extracted_json"]))
            
            print(f"   ✓ Exported to {paths['extracted_csv'].name}")
            print(f"   ✓ Exported to {paths['extracted_json'].name}")
            
            # Save stats
            stats = self.extractor.get_stats()
            self.project.state.extraction_stats = stats
            print(f"   📊 Total characters: {stats.get('total_characters', 0)}")
            print(f"   📊 Average length: {stats.get('average_length', 0)}")
            
            # Save project state
            self.project.save_state()
            print()
            
            return PipelineResult(
                success=True,
                stage="extraction",
                stats=stats,
            )
            
        except Exception as e:
            self.project.add_error(f"Extraction failed: {e}")
            self.project.update_status(ProjectStatus.FAILED)
            return PipelineResult(
                success=False,
                stage="extraction",
                error=str(e),
            )
    
    def run_translation(self) -> PipelineResult:
        """
        Run the translation stage.
        
        Returns:
            Pipeline result
        """
        print("🤖 Stage 2: Translating text...")
        self.project.update_status(ProjectStatus.TRANSLATING)
        
        try:
            # Build translator config
            translator_config = {
                "mock_mode": self.project.config.mock_translation,
                "target_language": self.project.config.target_language,
                "source_language": self.project.config.source_language,
                "game_context": f"Video game: {self.project.config.game_name}",
                "model": self.project.config.llm_model,
                "base_url": self.project.config.llm_base_url,
                "temperature": 0.3,
            }
            
            self.translator = TranslatorStub(translator_config)
            
            # Test connection if not mock mode
            if not self.project.config.mock_translation:
                if not self.translator.test_connection():
                    print("   ⚠️  LLM service not available, using mock mode")
                    translator_config["mock_mode"] = True
                    self.translator = TranslatorStub(translator_config)
            
            # Translate each entry
            total = len(self.project.translations)
            translated_count = 0
            failed_count = 0
            
            for i, entry in enumerate(self.project.translations):
                # Skip empty strings
                if not entry.original_text.strip():
                    entry.status = "skipped"
                    continue
                
                # Progress indicator
                if (i + 1) % 10 == 0 or i == 0:
                    print(f"   Translating {i+1}/{total}...", end="\r")
                
                try:
                    request = TranslationRequest(
                        text=entry.original_text,
                        context=f"Game dialogue, max {entry.max_bytes} bytes",
                        max_length=entry.max_bytes * 2,  # Allow expansion
                        target_language=self.project.config.target_language,
                        source_language=self.project.config.source_language,
                    )
                    
                    response = self.translator.translate_string(request)
                    
                    entry.translated_text = response.translated_text
                    entry.confidence = response.confidence
                    entry.status = "translated"
                    
                    if response.warnings:
                        entry.notes = "; ".join(response.warnings)
                    
                    translated_count += 1
                    
                except Exception as e:
                    entry.status = "pending"
                    entry.notes = f"Translation error: {e}"
                    failed_count += 1
            
            print(f"   ✓ Translated {translated_count}/{total} strings" + " " * 20)
            
            if failed_count > 0:
                print(f"   ⚠️  {failed_count} strings failed")
            
            # Export translated CSV
            self._export_translations_csv()
            
            # Save project state
            self.project.state.translation_progress = self.project.get_translation_stats()
            self.project.save_state()
            print()
            
            return PipelineResult(
                success=True,
                stage="translation",
                stats=self.project.get_translation_stats(),
            )
            
        except Exception as e:
            self.project.add_error(f"Translation failed: {e}")
            self.project.update_status(ProjectStatus.FAILED)
            return PipelineResult(
                success=False,
                stage="translation",
                error=str(e),
            )
    
    def _export_translations_csv(self) -> None:
        """Export translations to CSV file."""
        paths = self.project.get_output_paths()
        
        with open(paths["translated_csv"], "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "string_id", "address", "length", "original_text",
                "translated_text", "description", "pointer_address", "confidence"
            ])
            writer.writeheader()
            
            for entry in self.project.translations:
                writer.writerow({
                    "string_id": entry.string_id,
                    "address": f"0x{entry.address:04X}",
                    "length": entry.max_bytes,
                    "original_text": entry.original_text,
                    "translated_text": entry.translated_text,
                    "description": entry.notes,
                    "pointer_address": f"0x{entry.pointer_address:04X}" if entry.pointer_address else "",
                    "confidence": entry.confidence,
                })
        
        print(f"   ✓ Saved translations to {paths['translated_csv'].name}")
    
    def run_reinjection(
        self,
        csv_path: Optional[str] = None,
        skip_validation: bool = False,
    ) -> PipelineResult:
        """
        Run the reinjection stage.
        
        Args:
            csv_path: Optional path to translations CSV
            skip_validation: If True, skip validation
            
        Returns:
            Pipeline result
        """
        print("📥 Stage 3: Reinjecting translations...")
        self.project.update_status(ProjectStatus.REINJECTING)
        
        try:
            # Find config
            config_path = self.project.find_or_create_config()
            
            # Initialize reinjector
            self.reinjector = TextReinjector(str(config_path))
            
            # Load translations
            paths = self.project.get_output_paths()
            translations_csv = csv_path or str(paths["translated_csv"])
            
            if not Path(translations_csv).exists():
                raise FileNotFoundError(f"Translations CSV not found: {translations_csv}")
            
            self.reinjector.load_translations_from_csv(translations_csv)
            
            print(f"   ✓ Loaded {len(self.reinjector.translated_strings)} translations")
            
            # Reinject into ROM
            result = self.reinjector.reinject_into_rom(
                str(self.project.rom_path),
                str(paths["translated_rom"]),
            )
            
            print(f"   ✓ Created translated ROM: {paths['translated_rom'].name}")
            print(f"   📊 Processed: {result['strings_processed']} strings")
            
            # Validation
            if not skip_validation:
                print()
                print("🔍 Stage 4: Validating results...")
                self.project.update_status(ProjectStatus.VALIDATING)
                
                validation_results = result.get("validation_results", [])
                passed = sum(1 for r in validation_results if r.passed)
                total = len(validation_results)
                
                # Generate report
                validator = ROMValidator({"validation": {}})
                report = validator.generate_report(validation_results)
                
                with open(paths["validation_report"], "w") as f:
                    f.write(report)
                
                print(f"   ✓ Validation: {passed}/{total} checks passed")
                print(f"   ✓ Report saved to {paths['validation_report'].name}")
                
                self.project.state.validation_results = {
                    "passed": passed,
                    "total": total,
                }
            
            # Save project state
            self.project.save_state()
            print()
            
            return PipelineResult(
                success=True,
                stage="reinjection",
                stats=result,
            )
            
        except Exception as e:
            self.project.add_error(f"Reinjection failed: {e}")
            self.project.update_status(ProjectStatus.FAILED)
            return PipelineResult(
                success=False,
                stage="reinjection",
                error=str(e),
            )
    
    def run_patch_generation(self) -> PipelineResult:
        """
        Generate IPS patch file.
        
        Returns:
            Pipeline result
        """
        print("🎯 Stage 5: Generating patch file...")
        
        try:
            paths = self.project.get_output_paths()
            
            if self.reinjector is None:
                config_path = self.project.find_or_create_config()
                self.reinjector = TextReinjector(str(config_path))
            
            self.reinjector.generate_patch(
                str(self.project.rom_path),
                str(paths["translated_rom"]),
                str(paths["patch_ips"]),
            )
            
            print(f"   ✓ IPS patch created: {paths['patch_ips'].name}")
            print()
            
            return PipelineResult(
                success=True,
                stage="patch_generation",
            )
            
        except Exception as e:
            self.project.add_error(f"Patch generation failed: {e}")
            return PipelineResult(
                success=False,
                stage="patch_generation",
                error=str(e),
            )
