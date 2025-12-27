#!/usr/bin/env python3
"""
FamiLator Command Line Interface.

Provides a unified CLI for the complete ROM translation workflow.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from project import ProjectStatus, TranslationProject, TranslationEntry


def print_banner():
    """Print the FamiLator banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║  _____ _    __  __ ___ _        _                             ║
║ |  ___/ \\  |  \\/  |_ _| |   __ | |_ ___  _ __                 ║
║ | |_ / _ \\ | |\\/| || || |  / _`| __/ _ \\| '__|                ║
║ |  _/ ___ \\| |  | || || |_| (_|| || (_) | |                   ║
║ |_|/_/   \\_\\_|  |_|___|___|\\__,_\\__\\___/|_|                   ║
║                                                               ║
║  NES/Famicom ROM Translation Tool                             ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="familator",
        description="FamiLator - NES/Famicom ROM Translation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Translate a Japanese ROM to English (automatic mode)
  familator translate --rom game.nes --source japanese --target english --auto

  # Resume an existing project
  familator translate --rom game.nes --resume

  # Extract text only (for manual review)
  familator extract --rom game.nes --source japanese

  # Apply translations from edited CSV
  familator apply --project output/game_en/

  # Validate a translated ROM
  familator validate --rom output/game_en/game_translated.nes
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # === TRANSLATE command ===
    translate_parser = subparsers.add_parser(
        "translate",
        help="Run complete translation pipeline",
        description="Extract, translate, and patch a ROM in one command.",
    )
    translate_parser.add_argument(
        "--rom", "-r",
        required=True,
        help="Path to input ROM file",
    )
    translate_parser.add_argument(
        "--source", "-s",
        default="Japanese",
        help="Source language (default: Japanese)",
    )
    translate_parser.add_argument(
        "--target", "-t",
        default="English",
        help="Target language (default: English)",
    )
    translate_parser.add_argument(
        "--output", "-o",
        help="Output directory (auto-generated if not specified)",
    )
    translate_parser.add_argument(
        "--config", "-c",
        help="Path to game-specific config file (optional)",
    )
    translate_parser.add_argument(
        "--auto",
        action="store_true",
        help="Use automatic detection for unknown ROMs",
    )
    translate_parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock translator (for testing without LLM)",
    )
    translate_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an existing project",
    )
    translate_parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Only extract text, do not translate",
    )
    translate_parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ROM validation steps",
    )
    translate_parser.add_argument(
        "--llm-model",
        default="llama3",
        help="LLM model to use (default: llama3)",
    )
    translate_parser.add_argument(
        "--llm-url",
        default="http://localhost:11434",
        help="LLM service URL (default: http://localhost:11434)",
    )
    
    # === EXTRACT command ===
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract text from ROM only",
        description="Extract translatable text without translating.",
    )
    extract_parser.add_argument(
        "--rom", "-r",
        required=True,
        help="Path to input ROM file",
    )
    extract_parser.add_argument(
        "--source", "-s",
        default="Japanese",
        help="Source language hint (default: Japanese)",
    )
    extract_parser.add_argument(
        "--output", "-o",
        help="Output directory",
    )
    extract_parser.add_argument(
        "--config", "-c",
        help="Path to game-specific config file",
    )
    extract_parser.add_argument(
        "--auto",
        action="store_true",
        help="Use automatic text detection",
    )
    
    # === APPLY command ===
    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply translations from edited files",
        description="Re-inject translations after manual editing.",
    )
    apply_parser.add_argument(
        "--project", "-p",
        required=True,
        help="Path to project directory",
    )
    apply_parser.add_argument(
        "--csv",
        help="Path to translations CSV (optional, uses project default)",
    )
    apply_parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ROM validation",
    )
    
    # === VALIDATE command ===
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a ROM or project",
        description="Run validation checks on ROM or translation project.",
    )
    validate_parser.add_argument(
        "--rom", "-r",
        help="Path to ROM file to validate",
    )
    validate_parser.add_argument(
        "--project", "-p",
        help="Path to project directory to validate",
    )
    
    # === STATUS command ===
    status_parser = subparsers.add_parser(
        "status",
        help="Show project status",
        description="Display the current status of a translation project.",
    )
    status_parser.add_argument(
        "--project", "-p",
        required=True,
        help="Path to project directory",
    )
    
    # === LIST command ===
    list_parser = subparsers.add_parser(
        "list",
        help="List available projects or ROMs",
        description="List translation projects or ROMs in a directory.",
    )
    list_parser.add_argument(
        "--projects",
        action="store_true",
        help="List projects in output directory",
    )
    list_parser.add_argument(
        "--roms",
        action="store_true",
        help="List ROMs in input directory",
    )
    list_parser.add_argument(
        "--dir", "-d",
        help="Directory to scan",
    )
    
    return parser


def cmd_translate(args) -> int:
    """Execute the translate command."""
    from pipeline import TranslationPipeline
    
    print_banner()
    print(f"🎮 Starting translation project...")
    print(f"   ROM: {args.rom}")
    print(f"   {args.source} → {args.target}")
    print()
    
    try:
        # Create or load project
        project = TranslationProject(
            rom_path=args.rom,
            source_language=args.source,
            target_language=args.target,
            output_dir=args.output,
            auto_mode=args.auto,
        )
        
        # Update config with CLI args
        project.config.mock_translation = args.mock
        project.config.llm_model = args.llm_model
        project.config.llm_base_url = args.llm_url
        
        if args.config:
            project.config.encoding_table = args.config
        
        print(project)
        print()
        
        # Run pipeline
        pipeline = TranslationPipeline(project)
        
        if args.extract_only:
            result = pipeline.run_extraction()
        else:
            result = pipeline.run_full_pipeline(
                skip_validation=args.skip_validation
            )
        
        if result.success:
            print()
            print("✅ Translation pipeline completed successfully!")
            print(f"📁 Output files in: {project.output_dir}")
            print()
            print("📋 Generated files:")
            for name, path in project.get_output_paths().items():
                if path.exists():
                    print(f"   • {path.name}")
            print()
            print("🎮 To test: Load the translated ROM in your emulator")
            print("📝 To refine: Edit the translated CSV and run 'familator apply'")
            return 0
        else:
            print()
            print(f"❌ Pipeline failed: {result.error}")
            return 1
            
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_extract(args) -> int:
    """Execute the extract command."""
    from pipeline import TranslationPipeline
    
    print_banner()
    print(f"📤 Extracting text from ROM...")
    print(f"   ROM: {args.rom}")
    print()
    
    try:
        project = TranslationProject(
            rom_path=args.rom,
            source_language=args.source,
            target_language="English",  # Placeholder for extract-only
            output_dir=args.output,
            auto_mode=args.auto,
        )
        
        pipeline = TranslationPipeline(project)
        result = pipeline.run_extraction()
        
        if result.success:
            print()
            print("✅ Extraction complete!")
            print(f"📁 Output: {project.output_dir}")
            stats = project.get_translation_stats()
            print(f"📊 Extracted {stats['total']} strings")
            return 0
        else:
            print(f"❌ Extraction failed: {result.error}")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_apply(args) -> int:
    """Execute the apply command."""
    from pipeline import TranslationPipeline
    
    print_banner()
    print(f"📥 Applying translations from project...")
    print(f"   Project: {args.project}")
    print()
    
    try:
        # Load existing project
        project_dir = Path(args.project)
        state_file = project_dir / "project_state.json"
        
        if not state_file.exists():
            print(f"❌ No project found at: {project_dir}")
            return 1
        
        # Load project state to get ROM path
        import json
        with open(state_file, "r") as f:
            state = json.load(f)
        
        config = state.get("config", {})
        
        project = TranslationProject(
            rom_path=config["rom_path"],
            source_language=config["source_language"],
            target_language=config["target_language"],
            output_dir=str(project_dir),
        )
        
        pipeline = TranslationPipeline(project)
        result = pipeline.run_reinjection(
            csv_path=args.csv,
            skip_validation=args.skip_validation,
        )
        
        if result.success:
            print()
            print("✅ Translations applied successfully!")
            paths = project.get_output_paths()
            print(f"🎮 Translated ROM: {paths['translated_rom']}")
            print(f"📄 IPS Patch: {paths['patch_ips']}")
            return 0
        else:
            print(f"❌ Apply failed: {result.error}")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_validate(args) -> int:
    """Execute the validate command."""
    print_banner()
    
    if args.rom:
        print(f"🔍 Validating ROM: {args.rom}")
        # TODO: Implement ROM validation
        print("   ROM validation not yet implemented")
        return 0
    
    if args.project:
        print(f"🔍 Validating project: {args.project}")
        # TODO: Implement project validation
        print("   Project validation not yet implemented")
        return 0
    
    print("❌ Please specify --rom or --project")
    return 1


def cmd_status(args) -> int:
    """Execute the status command."""
    import json
    
    project_dir = Path(args.project)
    state_file = project_dir / "project_state.json"
    
    if not state_file.exists():
        print(f"❌ No project found at: {project_dir}")
        return 1
    
    with open(state_file, "r") as f:
        state = json.load(f)
    
    config = state.get("config", {})
    
    print_banner()
    print(f"📂 Project: {project_dir.name}")
    print(f"   Status: {state.get('status', 'unknown')}")
    print(f"   Game: {config.get('game_name', 'Unknown')}")
    print(f"   Languages: {config.get('source_language')} → {config.get('target_language')}")
    print(f"   Created: {state.get('created_at', 'Unknown')}")
    print(f"   Updated: {state.get('updated_at', 'Unknown')}")
    
    # Load translations for progress
    translations_file = project_dir / "translations.json"
    if translations_file.exists():
        with open(translations_file, "r") as f:
            trans_data = json.load(f)
        stats = trans_data.get("stats", {})
        print()
        print(f"📊 Progress:")
        print(f"   Total strings: {stats.get('total', 0)}")
        print(f"   Translated: {stats.get('translated', 0)}")
        print(f"   Reviewed: {stats.get('reviewed', 0)}")
        print(f"   Pending: {stats.get('pending', 0)}")
        print(f"   Progress: {stats.get('progress_percent', 0)}%")
    
    errors = state.get("errors", [])
    if errors:
        print()
        print(f"⚠️  Errors ({len(errors)}):")
        for error in errors[-5:]:  # Show last 5 errors
            print(f"   • {error}")
    
    return 0


def cmd_list(args) -> int:
    """Execute the list command."""
    print_banner()
    
    if args.projects:
        output_dir = Path(args.dir or "output")
        print(f"📁 Projects in {output_dir}:")
        print()
        
        if not output_dir.exists():
            print("   (no output directory found)")
            return 0
        
        for item in sorted(output_dir.iterdir()):
            if item.is_dir() and (item / "project_state.json").exists():
                # Load basic info
                try:
                    import json
                    with open(item / "project_state.json", "r") as f:
                        state = json.load(f)
                    config = state.get("config", {})
                    status = state.get("status", "unknown")
                    game = config.get("game_name", "Unknown")
                    print(f"   📂 {item.name}")
                    print(f"      Game: {game} | Status: {status}")
                except:
                    print(f"   📂 {item.name} (could not read state)")
        return 0
    
    if args.roms:
        roms_dir = Path(args.dir or "roms_input")
        print(f"🎮 ROMs in {roms_dir}:")
        print()
        
        if not roms_dir.exists():
            print("   (no ROMs directory found)")
            return 0
        
        for rom in sorted(roms_dir.glob("*.nes")):
            size = rom.stat().st_size
            size_kb = size // 1024
            print(f"   🎮 {rom.name} ({size_kb} KB)")
        
        return 0
    
    print("Please specify --projects or --roms")
    return 1


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Dispatch to command handler
    commands = {
        "translate": cmd_translate,
        "extract": cmd_extract,
        "apply": cmd_apply,
        "validate": cmd_validate,
        "status": cmd_status,
        "list": cmd_list,
    }
    
    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
