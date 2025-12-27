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
    from .translator import GameTranslator, TranslationConfig, Glossary, TranslationMemory
    from .language_detector import LanguageDetector, Language
    from .font_checker import FontChecker, FontCheckResult
    from .chr_analyzer import CHRAnalyzer, CHRAnalysis
    from .validator import ROMValidator
except ImportError:
    from project import ProjectStatus, TranslationProject, TranslationEntry
    from extractor import TextExtractor
    from reinjector import TextReinjector
    from translator import GameTranslator, TranslationConfig, Glossary, TranslationMemory
    from language_detector import LanguageDetector, Language
    from font_checker import FontChecker, FontCheckResult
    from chr_analyzer import CHRAnalyzer, CHRAnalysis
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
        self.translator: Optional[GameTranslator] = None
        self.chr_analysis: Optional[CHRAnalysis] = None
    
    def _analyze_chr_rom(self) -> Optional[CHRAnalysis]:
        """
        Analyze the ROM's CHR data to detect available fonts/tiles.
        
        Returns:
            CHRAnalysis or None if analysis failed
        """
        try:
            analyzer = CHRAnalyzer()
            self.chr_analysis = analyzer.analyze_rom(str(self.project.rom_path))
            return self.chr_analysis
        except Exception as e:
            self.project.add_error(f"CHR analysis warning: {e}")
            return None

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
            
            # Detect source language
            if extracted:
                detector = LanguageDetector()
                texts = [s.decoded_text for s in extracted if s.decoded_text.strip()]
                lang_analysis = detector.detect_from_strings(texts)
                
                detected_lang = lang_analysis.detected_language.value.capitalize()
                print(f"   🌐 Detected language: {detected_lang} (confidence: {lang_analysis.confidence:.0%})")
                
                # Update project if we detected a different language
                if lang_analysis.confidence > 0.7:
                    if lang_analysis.detected_language == Language.JAPANESE:
                        self.project.config.source_language = "Japanese"
                    elif lang_analysis.detected_language == Language.ENGLISH:
                        self.project.config.source_language = "English"
            
            # Analyze CHR ROM for font information
            chr_analysis = self._analyze_chr_rom()
            if chr_analysis and chr_analysis.font_regions:
                print(f"   🎨 Found {len(chr_analysis.font_regions)} font regions "
                      f"({chr_analysis.unique_tiles} unique tiles)")
            
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
        Run the translation stage using the enhanced translator.
        
        Returns:
            Pipeline result
        """
        print("🤖 Stage 2: Translating text...")
        self.project.update_status(ProjectStatus.TRANSLATING)
        
        try:
            # Initialize glossary and translation memory
            paths = self.project.get_output_paths()
            glossary_path = self.project.output_dir / "glossary.json"
            memory_path = self.project.output_dir / "translation_memory.json"
            
            glossary = Glossary(str(glossary_path) if glossary_path.exists() else None)
            memory = TranslationMemory(str(memory_path) if memory_path.exists() else None)
            
            # Build translator config
            config = TranslationConfig(
                source_language=self.project.config.source_language,
                target_language=self.project.config.target_language,
                llm_provider="ollama",
                llm_model=self.project.config.llm_model,
                llm_base_url=self.project.config.llm_base_url,
                temperature=0.3,
                max_retries=3,
                retry_delay=1.0,
                timeout=60,
                batch_size=5,
                game_context=self.project.config.game_name,
                mock_mode=self.project.config.mock_translation,
            )
            
            # Initialize enhanced translator
            translator = GameTranslator(config, glossary, memory)
            
            # Test connection if not mock mode
            if not config.mock_mode:
                if not translator.test_connection():
                    print("   ⚠️  LLM service not available, using mock mode")
                    config.mock_mode = True
                    translator = GameTranslator(config, glossary, memory)
            
            # Prepare texts for batch translation
            texts = []
            contexts = []
            valid_indices = []
            
            for i, entry in enumerate(self.project.translations):
                if entry.original_text.strip():
                    texts.append(entry.original_text)
                    contexts.append(f"Game dialogue, max {entry.max_bytes} bytes")
                    valid_indices.append(i)
                else:
                    entry.status = "skipped"
            
            total = len(texts)
            print(f"   📝 Processing {total} strings...")
            
            # Translate in batches
            batch_result = translator.translate_batch(texts, contexts)
            
            # Apply results
            for idx, result in zip(valid_indices, batch_result.results):
                entry = self.project.translations[idx]
                entry.translated_text = result.translated
                entry.confidence = result.confidence
                entry.status = "translated" if result.confidence > 0.3 else "pending"
                
                notes = []
                if result.from_glossary:
                    notes.append("From glossary")
                if result.from_memory:
                    notes.append("From memory")
                if result.retries > 0:
                    notes.append(f"Retried {result.retries}x")
                if result.warnings:
                    notes.extend(result.warnings)
                
                entry.notes = "; ".join(notes) if notes else ""
            
            print(f"   ✓ Translated {batch_result.success_count}/{total} strings")
            print(f"   ⏱️  Time: {batch_result.total_time:.1f}s")
            
            if batch_result.failure_count > 0:
                print(f"   ⚠️  {batch_result.failure_count} strings failed")
            
            # Check font compatibility and auto-fix if needed
            font_issues = self._check_font_compatibility()
            if font_issues > 0:
                print(f"   🔤 Fixed {font_issues} character compatibility issues")
            
            # Save glossary and memory for future use
            glossary.save(str(glossary_path))
            memory.save(str(memory_path))
            
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
    
    def _check_font_compatibility(self) -> int:
        """
        Check translated text for font compatibility and auto-fix issues.
        
        Returns:
            Number of strings that were modified
        """
        # Try to load encoding table for font checking
        table_path = None
        config_path = self.project.find_or_create_config()
        
        if config_path:
            import yaml
            try:
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                    if config and "table_file" in config:
                        table_path = config["table_file"]
            except Exception:
                pass
        
        # Initialize font checker
        font_checker = FontChecker(table_path=table_path)
        
        # Check and fix each translation
        fixed_count = 0
        for entry in self.project.translations:
            if entry.translated_text:
                result = font_checker.check_text(entry.translated_text, auto_fix=True)
                
                if not result.is_compatible and result.suggested_text:
                    # Apply the auto-fixed version
                    entry.translated_text = result.suggested_text
                    
                    # Add note about substitutions
                    if entry.notes:
                        entry.notes += "; Font compatibility fix applied"
                    else:
                        entry.notes = "Font compatibility fix applied"
                    
                    fixed_count += 1
        
        return fixed_count

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
