#!/usr/bin/env python3
"""
FamiLator main pipeline script.

Orchestrates the complete extraction → translation → reinsertion workflow.
"""

import argparse
import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import with absolute imports after path modification
import extractor
import reinjector  
import translator_stub
import validator
import yaml

from extractor import TextExtractor
from reinjector import TextReinjector
from translator_stub import TranslatorStub, TranslationRequest
from validator import ROMValidator


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(description='FamiLator ROM translation pipeline')
    parser.add_argument('rom_path', help='Path to input ROM file')
    parser.add_argument('config', help='Path to game configuration file')
    parser.add_argument('--output-dir', '-o', default='output', 
                       help='Output directory (default: output)')
    parser.add_argument('--target-language', '-t', default='Spanish',
                       help='Target language for translation (default: Spanish)')
    parser.add_argument('--mock-translate', action='store_true',
                       help='Use mock translator instead of real LLM')
    parser.add_argument('--extract-only', action='store_true',
                       help='Only extract text, do not translate or reinject')
    parser.add_argument('--skip-validation', action='store_true',
                       help='Skip ROM validation steps')
    
    args = parser.parse_args()
    
    # Validate inputs
    rom_path = Path(args.rom_path)
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)
    
    if not rom_path.exists():
        print(f"Error: ROM file not found: {rom_path}")
        return 1
    
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        return 1
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load configuration
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    game_name = config.get('game', {}).get('name', 'Unknown')
    print(f"🕹️  Processing: {game_name}")
    print(f"📁 ROM: {rom_path}")
    print(f"⚙️  Config: {config_path}")
    print(f"📤 Output: {output_dir}")
    print()
    
    try:
        # Step 1: Extract text
        print("📤 Step 1: Extracting text...")
        extractor = TextExtractor(str(config_path))
        extracted_strings = extractor.extract_from_rom(str(rom_path))
        
        print(f"   ✓ Extracted {len(extracted_strings)} strings")
        
        # Export extraction results
        csv_path = output_dir / f"{game_name.lower().replace(' ', '_')}_extracted.csv"
        json_path = output_dir / f"{game_name.lower().replace(' ', '_')}_extracted.json"
        
        extractor.export_to_csv(str(csv_path))
        extractor.export_to_json(str(json_path))
        
        print(f"   ✓ Exported to {csv_path}")
        print(f"   ✓ Exported to {json_path}")
        
        # Show extraction statistics
        stats = extractor.get_stats()
        print(f"   📊 Total characters: {stats['total_characters']}")
        print(f"   📊 Average length: {stats['average_length']}")
        print()
        
        if args.extract_only:
            print("✅ Extraction complete (extract-only mode)")
            return 0
        
        # Step 2: Translate text
        print("🤖 Step 2: Translating text...")
        
        translator_config = {
            'mock_mode': args.mock_translate,
            'target_language': args.target_language,
            'game_context': f"Video game: {game_name}"
        }
        
        translator = TranslatorStub(translator_config)
        
        if not args.mock_translate and not translator.test_connection():
            print("   ⚠️  LLM service not available, falling back to mock mode")
            translator_config['mock_mode'] = True
            translator = TranslatorStub(translator_config)
        
        # Prepare translation requests
        translation_requests = []
        for string in extracted_strings:
            if string.decoded_text.strip():  # Skip empty strings
                request = TranslationRequest(
                    text=string.decoded_text,
                    context=string.description,
                    max_length=len(string.decoded_text) * 2,  # Allow some expansion
                    target_language=args.target_language
                )
                translation_requests.append(request)
        
        # Perform batch translation
        translation_responses = translator.translate_batch(translation_requests)
        
        print(f"   ✓ Translated {len(translation_responses)} strings")
        
        # Create translation CSV
        translated_csv_path = output_dir / f"{game_name.lower().replace(' ', '_')}_translated.csv"
        
        import csv
        with open(translated_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'string_id', 'address', 'length', 'original_text', 
                'translated_text', 'description', 'pointer_address', 'confidence'
            ])
            writer.writeheader()
            
            for i, (string, response) in enumerate(zip(extracted_strings, translation_responses)):
                writer.writerow({
                    'string_id': string.string_id or f'string_{i+1:03d}',
                    'address': f'0x{string.address:04X}',
                    'length': string.length,
                    'original_text': string.decoded_text,
                    'translated_text': response.translated_text,
                    'description': string.description,
                    'pointer_address': f'0x{string.pointer_address:04X}' if string.pointer_address else '',
                    'confidence': response.confidence
                })
        
        print(f"   ✓ Saved translations to {translated_csv_path}")
        
        # Show translation statistics
        total_confidence = sum(r.confidence for r in translation_responses)
        avg_confidence = total_confidence / len(translation_responses) if translation_responses else 0
        print(f"   📊 Average confidence: {avg_confidence:.2f}")
        print()
        
        # Step 3: Reinject translated text
        print("📥 Step 3: Reinjecting translated text...")
        
        reinjector = TextReinjector(str(config_path))
        reinjector.load_translations_from_csv(str(translated_csv_path))
        
        output_rom_path = output_dir / f"{game_name.lower().replace(' ', '_')}_translated.nes"
        
        reinsertion_results = reinjector.reinject_into_rom(
            str(rom_path), 
            str(output_rom_path)
        )
        
        print(f"   ✓ Created translated ROM: {output_rom_path}")
        print(f"   📊 Processed: {reinsertion_results['strings_processed']} strings")
        
        # Show reinsertion statistics
        reinjection_stats = reinjector.get_stats()
        print(f"   📊 Expansion ratio: {reinjection_stats['expansion_ratio']}")
        print()
        
        # Step 4: Validation
        if not args.skip_validation:
            print("🔍 Step 4: Validating results...")
            
            validator = ROMValidator(config)
            
            # Validate original ROM
            with open(rom_path, 'rb') as f:
                original_data = f.read()
            
            original_results = validator.validate_original_rom(original_data)
            
            # Validate modified ROM
            with open(output_rom_path, 'rb') as f:
                modified_data = f.read()
            
            # Calculate changed regions
            changed_regions = [(s.address, s.address + len(s.translated_bytes)) 
                             for s in reinjector.translated_strings]
            
            modified_results = validator.validate_modified_rom(
                original_data, modified_data, changed_regions
            )
            
            # Validate translations
            original_texts = [s.decoded_text for s in extracted_strings]
            translated_texts = [r.translated_text for r in translation_responses]
            
            translation_results = validator.validate_translation_consistency(
                original_texts, translated_texts
            )
            
            # Generate validation report
            all_results = original_results + modified_results + translation_results
            report = validator.generate_report(all_results)
            
            # Save validation report
            report_path = output_dir / f"{game_name.lower().replace(' ', '_')}_validation_report.txt"
            with open(report_path, 'w') as f:
                f.write(report)
            
            print(f"   ✓ Validation report saved to {report_path}")
            
            # Show summary
            passed = sum(1 for r in all_results if r.passed)
            total = len(all_results)
            print(f"   📊 Validation: {passed}/{total} checks passed")
            print()
        
        # Step 5: Generate patch file
        print("🎯 Step 5: Generating patch file...")
        
        patch_path = output_dir / f"{game_name.lower().replace(' ', '_')}_translation.ips"
        reinjector.generate_patch(str(rom_path), str(output_rom_path), str(patch_path))
        
        print(f"   ✓ IPS patch created: {patch_path}")
        print()
        
        # Final summary
        print("✅ Translation pipeline complete!")
        print(f"📁 All files saved to: {output_dir}")
        print("🎮 Ready for testing!")
        
        return 0
        
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
