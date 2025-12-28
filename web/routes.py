"""Flask route blueprints for FamiLator Web Interface."""

import csv
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

# Configure logging
logger = logging.getLogger(__name__)

# Import FamiLator modules
import sys

# Add project root to path for src imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.chr_analyzer import CHRAnalyzer
from src.encoding import EncodingTable
from src.extractor import TextExtractor
from src.font_checker import FontChecker
from src.language_detector import Language, LanguageDetector
from src.reinjector import TextReinjector
from src.table_builder import TableBuilder
from src.translator import GameTranslator, Glossary, TranslationConfig, TranslationMemory
from src.validator import ROMValidator

# Main blueprint for page routes
main_bp = Blueprint("main", __name__)

# API blueprint for AJAX endpoints
api_bp = Blueprint("api", __name__)

# Projects blueprint
projects_bp = Blueprint("projects", __name__)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )


def find_rom_file(filename: str) -> Optional[Path]:
    """Find a ROM file by filename, handling URL encoding and spaces.
    
    Args:
        filename: The filename to search for (may be URL encoded or sanitized)
        
    Returns:
        Path to the ROM file if found, None otherwise
    """
    rom_folder = get_rom_folder()
    if not rom_folder.exists():
        return None
    
    # Try exact match first
    exact_path = rom_folder / filename
    if exact_path.exists():
        return exact_path
    
    # Try with secure_filename (for uploaded files)
    secure_path = rom_folder / secure_filename(filename)
    if secure_path.exists():
        return secure_path
    
    # Search for matching ROM files (case-insensitive, handle spaces/special chars)
    search_name = filename.lower().replace("_", " ").replace("-", " ")
    for rom_file in rom_folder.glob("*.nes"):
        rom_name = rom_file.name.lower().replace("_", " ").replace("-", " ")
        if search_name == rom_name or secure_filename(rom_file.name) == filename:
            return rom_file
    
    # Also try .fds files
    for rom_file in rom_folder.glob("*.fds"):
        rom_name = rom_file.name.lower().replace("_", " ").replace("-", " ")
        if search_name == rom_name or secure_filename(rom_file.name) == filename:
            return rom_file
    
    return None


def get_rom_folder() -> Path:
    """Get the ROM input folder path, resolved to project root."""
    # The upload folder is relative to project root
    project_root = Path(__file__).parent.parent
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    
    # If it's an absolute path, use it directly
    if Path(upload_folder).is_absolute():
        return Path(upload_folder)
    
    # Otherwise, resolve relative to project root
    return project_root / upload_folder


def get_output_folder() -> Path:
    """Get the output folder path, resolved to project root."""
    project_root = Path(__file__).parent.parent
    output_folder = current_app.config["OUTPUT_FOLDER"]
    
    # If it's an absolute path, use it directly
    if Path(output_folder).is_absolute():
        return Path(output_folder)
    
    # Otherwise, resolve relative to project root
    return project_root / output_folder


def get_project_list() -> list[dict]:
    """Get list of all projects in the output folder."""
    output_folder = get_output_folder()
    projects = []

    if not output_folder.exists():
        logger.warning(f"Output folder does not exist: {output_folder}")
        return projects

    # Look for project directories (have extracted.json files)
    for item in output_folder.iterdir():
        if item.is_dir():
            extracted_files = list(item.glob("*_extracted.json"))
            if extracted_files:
                projects.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "files": {
                            "extracted": len(list(item.glob("*_extracted.*"))),
                            "translated": len(list(item.glob("*_translated.*"))),
                            "patches": len(list(item.glob("*.ips"))),
                        },
                    }
                )

    # Also check for files directly in output folder
    for json_file in output_folder.glob("*_extracted.json"):
        if json_file.parent == output_folder:
            base_name = json_file.stem.replace("_extracted", "")
            projects.append(
                {
                    "name": base_name,
                    "path": str(output_folder),
                    "files": {
                        "extracted": 1,
                        "translated": (
                            1
                            if (output_folder / f"{base_name}_translated.csv").exists()
                            else 0
                        ),
                        "patches": (
                            1
                            if (output_folder / f"{base_name}_translation.ips").exists()
                            else 0
                        ),
                    },
                }
            )

    logger.debug(f"Found {len(projects)} projects")
    return projects


def get_available_tables() -> List[Dict[str, str]]:
    """Get list of available encoding tables.
    
    Returns:
        List of dicts with 'name' and 'path' keys
    """
    project_root = Path(__file__).parent.parent
    tables_dir = project_root / "tables"
    
    tables = []
    if tables_dir.exists():
        for tbl_file in sorted(tables_dir.glob("*.tbl")):
            tables.append({
                "name": tbl_file.stem.replace("_", " ").title(),
                "path": f"tables/{tbl_file.name}",
            })
    
    logger.debug(f"Found {len(tables)} encoding tables")
    return tables


def create_temp_config(
    rom_path: str,
    table_file: str = "tables/common.tbl",
    method: str = "auto_detect",
) -> str:
    """Create a temporary configuration file for extraction/reinjection.

    The backend expects YAML config files, but the web UI works with
    individual parameters. This function bridges that gap.

    Args:
        rom_path: Path to the ROM file
        table_file: Path to the encoding table file
        method: Extraction method (fixed_locations, pointer_table, auto_detect)

    Returns:
        Path to the temporary config file
    """
    project_root = Path(__file__).parent.parent
    
    # Resolve table file path
    if not Path(table_file).is_absolute():
        table_path = project_root / table_file
    else:
        table_path = Path(table_file)

    config = {
        "game": {
            "name": Path(rom_path).stem,
            "platform": "nes",
        },
        "text_detection": {
            "method": method,
            "encoding_table": str(table_path),
        },
        "validation": {
            "check_crc": False,
        },
    }

    # Create temp file
    fd, temp_path = tempfile.mkstemp(suffix=".yaml", prefix="familator_config_")
    with os.fdopen(fd, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    logger.debug(f"Created temporary config at {temp_path}")
    return temp_path


def cleanup_temp_config(config_path: str) -> None:
    """Clean up a temporary configuration file."""
    try:
        if config_path and os.path.exists(config_path):
            os.unlink(config_path)
            logger.debug(f"Cleaned up temporary config: {config_path}")
    except Exception as e:
        logger.warning(f"Failed to clean up temp config {config_path}: {e}")


# ============================================================================
# Main Page Routes
# ============================================================================


@main_bp.route("/")
def index():
    """Home page with project overview."""
    projects = get_project_list()
    rom_folder = get_rom_folder()
    rom_files = list(rom_folder.glob("*.nes")) if rom_folder.exists() else []
    logger.debug(f"Index page: {len(projects)} projects, {len(rom_files)} ROMs")
    return render_template("index.html", projects=projects, rom_files=rom_files)


@main_bp.route("/upload", methods=["GET", "POST"])
def upload():
    """ROM upload page."""
    if request.method == "POST":
        if "rom_file" not in request.files:
            flash("No file selected", "error")
            return redirect(request.url)

        file = request.files["rom_file"]
        if file.filename == "":
            flash("No file selected", "error")
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            rom_folder = get_rom_folder()
            rom_folder.mkdir(parents=True, exist_ok=True)
            filepath = rom_folder / filename
            file.save(filepath)
            logger.info(f"ROM uploaded: {filename}")
            flash(f"ROM '{filename}' uploaded successfully!", "success")
            return redirect(url_for("main.analyze", filename=filename))
        else:
            flash("Invalid file type. Only .nes and .fds files allowed.", "error")

    return render_template("upload.html")


@main_bp.route("/analyze/<filename>")
def analyze(filename: str):
    """ROM analysis page showing CHR tiles and text extraction preview."""
    rom_path = find_rom_file(filename)

    logger.debug(f"Analyzing ROM: {filename} -> {rom_path}")

    if not rom_path:
        rom_folder = get_rom_folder()
        logger.error(f"ROM file not found: {filename} in {rom_folder}")
        flash(f"ROM file '{filename}' not found in {rom_folder}", "error")
        return redirect(url_for("main.index"))

    try:
        # Perform CHR analysis
        chr_analyzer = CHRAnalyzer()
        chr_analysis_raw = chr_analyzer.analyze_rom(rom_path)
        
        # Convert CHRAnalysis dataclass to JSON-serializable dict
        chr_analysis = {
            "chr_type": chr_analysis_raw.chr_type.value,
            "chr_size": chr_analysis_raw.chr_size,
            "total_tiles": chr_analysis_raw.total_tiles,
            "blank_tiles": chr_analysis_raw.blank_tiles,
            "unique_tiles": chr_analysis_raw.unique_tiles,
            "font_regions": [
                {
                    "start_tile": r.start_tile,
                    "end_tile": r.end_tile,
                    "tile_count": r.tile_count,
                    "estimated_chars": r.estimated_chars,
                    "char_width": r.char_width,
                    "char_height": r.char_height,
                    "notes": r.notes,
                }
                for r in chr_analysis_raw.font_regions
            ],
            "available_chars": list(chr_analysis_raw.available_chars),  # Convert set to list
            "estimated_charset_size": chr_analysis_raw.estimated_charset_size,
            "warnings": chr_analysis_raw.warnings,
            "has_latin_font": chr_analysis_raw.has_latin_font(),
            "has_extended_charset": chr_analysis_raw.has_extended_charset(),
        }

        # Detect language from ROM byte patterns
        lang_detector = LanguageDetector()
        with open(rom_path, "rb") as f:
            rom_data = f.read()
        byte_analysis = lang_detector.analyze_byte_patterns(rom_data)
        
        # Build a JSON-serializable dict with attributes the template expects
        likely_encoding = byte_analysis.get("likely_encoding", "unknown")
        if likely_encoding == "japanese":
            detected_lang = Language.JAPANESE
            confidence = 0.7
        elif likely_encoding == "ascii":
            detected_lang = Language.ENGLISH
            confidence = byte_analysis.get("ascii_ratio", 0.5)
        else:
            detected_lang = Language.UNKNOWN
            confidence = 0.3
        
        # Create a dict-based object that supports both attribute and key access for template
        class AttrDict(dict):
            """Dict that allows attribute access for Jinja2 template compatibility."""
            def __getattr__(self, key):
                try:
                    return self[key]
                except KeyError:
                    raise AttributeError(key)
        
        # Nested dict for primary_language to support .value access in template
        primary_language = AttrDict({"value": detected_lang.value})
        
        lang_analysis = AttrDict({
            "primary_language": primary_language,
            "detected_language": primary_language,  # alias
            "confidence": confidence,
            "japanese_ratio": byte_analysis.get("japanese_indicators", 0) / 2,
            "english_ratio": byte_analysis.get("ascii_ratio", 0),
            "details": byte_analysis,
            "hiragana_count": 0,
            "katakana_count": 0,
            "kanji_count": 0,
            "ascii_count": int(byte_analysis.get("ascii_ratio", 0) * byte_analysis.get("total_bytes", 0)),
        })

        logger.info(f"Analysis complete for {filename}")
        return render_template(
            "analyze.html",
            filename=filename,
            chr_analysis=chr_analysis,
            lang_analysis=lang_analysis,
        )
    except Exception as e:
        logger.exception(f"Error analyzing ROM {filename}")
        flash(f"Error analyzing ROM: {e}", "error")
        return redirect(url_for("main.index"))


@main_bp.route("/translate/<project_name>")
def translate(project_name: str):
    """Translation editor page."""
    output_folder = get_output_folder()

    # Find project folder or file
    project_path = output_folder / project_name
    if project_path.is_dir():
        extracted_files = list(project_path.glob("*_extracted.json"))
        if extracted_files:
            extracted_file = extracted_files[0]
        else:
            flash(f"No extracted data found for project '{project_name}'", "error")
            return redirect(url_for("main.index"))
    else:
        extracted_file = output_folder / f"{project_name}_extracted.json"

    if not extracted_file.exists():
        logger.error(f"Project not found: {project_name}")
        flash(f"Project '{project_name}' not found", "error")
        return redirect(url_for("main.index"))

    # Load extracted strings
    with open(extracted_file) as f:
        extracted_data = json.load(f)

    # Load translations if they exist
    translated_csv = extracted_file.with_name(
        extracted_file.name.replace("_extracted.json", "_translated.csv")
    )
    translations = {}
    if translated_csv.exists():
        with open(translated_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                translations[row.get("address", row.get("Address", ""))] = row.get(
                    "translated_text", row.get("Translated Text", "")
                )

    logger.debug(f"Loaded project {project_name} with {len(translations)} translations")
    return render_template(
        "translate.html",
        project_name=project_name,
        extracted_data=extracted_data,
        translations=translations,
    )


@main_bp.route("/tiles/<project_name>")
def tile_browser(project_name: str):
    """Visual tile browser for CHR ROM inspection."""
    rom_path = None

    # Try to find associated ROM
    rom_folder = get_rom_folder()
    if rom_folder.exists():
        for rom_file in rom_folder.glob("*.nes"):
            if project_name.lower() in rom_file.stem.lower():
                rom_path = rom_file
                break

    chr_analysis = None
    if rom_path:
        try:
            chr_analyzer = CHRAnalyzer()
            chr_analysis_raw = chr_analyzer.analyze_rom(rom_path)
            
            # Convert CHRAnalysis dataclass to JSON-serializable dict
            chr_analysis = {
                "chr_type": chr_analysis_raw.chr_type.value,
                "chr_size": chr_analysis_raw.chr_size,
                "total_tiles": chr_analysis_raw.total_tiles,
                "blank_tiles": chr_analysis_raw.blank_tiles,
                "unique_tiles": chr_analysis_raw.unique_tiles,
                "font_regions": [
                    {
                        "start_tile": r.start_tile,
                        "end_tile": r.end_tile,
                        "tile_count": r.tile_count,
                        "estimated_chars": r.estimated_chars,
                        "char_width": r.char_width,
                        "char_height": r.char_height,
                        "notes": r.notes,
                    }
                    for r in chr_analysis_raw.font_regions
                ],
                "available_chars": list(chr_analysis_raw.available_chars),
                "estimated_charset_size": chr_analysis_raw.estimated_charset_size,
                "warnings": chr_analysis_raw.warnings,
                "has_latin_font": chr_analysis_raw.has_latin_font(),
                "has_extended_charset": chr_analysis_raw.has_extended_charset(),
            }
        except Exception as e:
            logger.error(f"Error analyzing CHR for {project_name}: {e}")

    return render_template(
        "tiles.html", project_name=project_name, chr_analysis=chr_analysis
    )


@main_bp.route("/table-builder")
@main_bp.route("/table-builder/<rom_filename>")
def table_builder(rom_filename: str = None):
    """Table builder page for creating encoding tables."""
    rom_files = []
    chr_analysis = None
    
    # Get list of available ROMs
    rom_folder = get_rom_folder()
    if rom_folder.exists():
        rom_files = [f.name for f in rom_folder.glob("*.nes")]
    
    # Get list of existing tables
    tables = get_available_tables()
    
    # If a ROM is specified, analyze it
    if rom_filename:
        rom_path = find_rom_file(rom_filename)
        if rom_path:
            try:
                chr_analyzer = CHRAnalyzer()
                chr_analysis_raw = chr_analyzer.analyze_rom(rom_path)
                chr_analysis = {
                    "chr_type": chr_analysis_raw.chr_type.value,
                    "total_tiles": chr_analysis_raw.total_tiles,
                    "font_regions": [
                        {
                            "start_tile": r.start_tile,
                            "end_tile": r.end_tile,
                            "tile_count": r.tile_count,
                        }
                        for r in chr_analysis_raw.font_regions
                    ],
                }
            except Exception as e:
                logger.error(f"Error analyzing CHR for table builder: {e}")
    
    return render_template(
        "table_builder.html",
        rom_filename=rom_filename,
        rom_files=rom_files,
        tables=tables,
        chr_analysis=chr_analysis,
    )


# ============================================================================
# API Routes
# ============================================================================


@api_bp.route("/tables", methods=["GET"])
def api_list_tables():
    """List available encoding tables."""
    tables = get_available_tables()
    return jsonify({"tables": tables})


@api_bp.route("/generate-table", methods=["POST"])
def api_generate_table():
    """Create an empty table template for a ROM - user fills in mappings manually."""
    data = request.get_json()
    rom_filename = data.get("rom_filename")
    game_name = data.get("game_name")
    
    if not rom_filename and not game_name:
        logger.warning("Generate table API called without ROM filename or game name")
        return jsonify({"error": "ROM filename or game name required"}), 400
    
    if not game_name:
        rom_path = find_rom_file(rom_filename)
        if rom_path:
            game_name = rom_path.stem
        else:
            game_name = rom_filename.replace(".nes", "")
    
    try:
        logger.info(f"Creating empty table template for {game_name}")
        
        builder = TableBuilder()
        
        # Create a starter table with common control codes only
        # User will add character mappings via the Table Builder UI
        result = builder.create_table(
            game_name,
            mappings={},  # Empty - user fills in
            control_codes={
                0xFF: "<END>",
                0xFE: "<NEWLINE>",
            },
            description="Edit this table in the Table Builder to add character mappings",
        )
        
        logger.info(f"Created table template: {result.table_path}")
        
        return jsonify({
            "success": result.success,
            "table_path": result.table_path,
            "mappings_count": result.mappings_count,
            "control_codes_count": result.control_codes_count,
            "message": result.message,
        })
    
    except Exception as e:
        logger.exception(f"Error creating table for {game_name}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/table/save", methods=["POST"])
def api_save_table():
    """Save character mappings to a table file."""
    data = request.get_json()
    table_name = data.get("table_name")
    mappings = data.get("mappings", {})
    control_codes = data.get("control_codes", {})
    
    if not table_name:
        return jsonify({"error": "Table name required"}), 400
    
    try:
        # Convert string keys to int (JSON keys are always strings)
        int_mappings = {int(k, 16) if isinstance(k, str) else k: v for k, v in mappings.items()}
        int_codes = {int(k, 16) if isinstance(k, str) else k: v for k, v in control_codes.items()}
        
        builder = TableBuilder()
        result = builder.create_table(
            table_name,
            int_mappings,
            int_codes,
        )
        
        logger.info(f"Saved table: {result.table_path} with {result.mappings_count} mappings")
        
        return jsonify({
            "success": result.success,
            "table_path": result.table_path,
            "mappings_count": result.mappings_count,
            "control_codes_count": result.control_codes_count,
            "message": result.message,
        })
    
    except Exception as e:
        logger.exception(f"Error saving table {table_name}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/table/load/<table_name>")
def api_load_table(table_name: str):
    """Load a table file for editing."""
    project_root = Path(__file__).parent.parent
    table_path = project_root / "tables" / f"{table_name}.tbl"
    
    if not table_path.exists():
        return jsonify({"error": f"Table not found: {table_name}"}), 404
    
    try:
        builder = TableBuilder()
        table_data = builder.load_table(str(table_path))
        
        if not table_data:
            return jsonify({"error": "Failed to load table"}), 500
        
        # Convert int keys to hex strings for JSON
        hex_mappings = {f"{k:02X}": v for k, v in table_data.mappings.items()}
        hex_codes = {f"{k:02X}": v for k, v in table_data.control_codes.items()}
        
        return jsonify({
            "success": True,
            "name": table_data.name,
            "mappings": hex_mappings,
            "control_codes": hex_codes,
        })
    
    except Exception as e:
        logger.exception(f"Error loading table {table_name}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/table/presets")
def api_table_presets():
    """Get available mapping presets."""
    builder = TableBuilder()
    presets = builder.get_common_presets()
    
    # Convert to JSON-friendly format
    result = {}
    for name, mappings in presets.items():
        result[name] = {f"{k:02X}": v for k, v in mappings.items()}
    
    return jsonify({"presets": result})


@api_bp.route("/extract", methods=["POST"])
def api_extract():
    """Extract text from ROM."""
    data = request.get_json()
    rom_filename = data.get("rom_filename")
    table_file = data.get("table_file", "tables/common.tbl")
    output_name = data.get("output_name")

    if not rom_filename:
        logger.warning("Extract API called without ROM filename")
        return jsonify({"error": "No ROM filename provided"}), 400

    rom_path = find_rom_file(rom_filename)
    if not rom_path:
        logger.error(f"ROM file not found: {rom_filename}")
        return jsonify({"error": f"ROM file '{rom_filename}' not found"}), 404

    config_path = None
    try:
        # Create temporary config for extraction
        config_path = create_temp_config(str(rom_path), table_file, method="auto_detect")

        # Initialize extractor with config
        extractor = TextExtractor(config_path)
        strings = extractor.extract_from_rom(str(rom_path))

        # Determine output path
        output_folder = get_output_folder()
        if output_name:
            output_dir = output_folder / secure_filename(output_name)
            output_dir.mkdir(parents=True, exist_ok=True)
            base_name = output_name
        else:
            output_dir = output_folder
            base_name = rom_path.stem

        # Save extracted data using the extractor's export methods
        json_path = output_dir / f"{base_name}_extracted.json"
        csv_path = output_dir / f"{base_name}_extracted.csv"

        extractor.export_to_json(str(json_path))
        extractor.export_to_csv(str(csv_path))

        logger.info(f"Extracted {len(strings)} strings from {rom_filename}")
        return jsonify(
            {
                "success": True,
                "strings_found": len(strings),
                "json_path": str(json_path),
                "csv_path": str(csv_path),
                "project_name": base_name if not output_name else output_name,
            }
        )

    except Exception as e:
        logger.exception(f"Error extracting from {rom_filename}")
        return jsonify({"error": str(e)}), 500

    finally:
        cleanup_temp_config(config_path)


@api_bp.route("/translate", methods=["POST"])
def api_translate():
    """Translate extracted strings using LLM."""
    data = request.get_json()
    project_name = data.get("project_name")
    use_mock = data.get("use_mock", True)
    source_lang = data.get("source_lang", "Japanese")
    target_lang = data.get("target_lang", "English")

    if not project_name:
        logger.warning("Translate API called without project name")
        return jsonify({"error": "No project name provided"}), 400

    output_folder = get_output_folder()

    # Find extracted file
    project_path = output_folder / project_name
    if project_path.is_dir():
        extracted_files = list(project_path.glob("*_extracted.json"))
        extracted_file = extracted_files[0] if extracted_files else None
    else:
        extracted_file = output_folder / f"{project_name}_extracted.json"

    if not extracted_file or not extracted_file.exists():
        logger.error(f"No extracted data found for '{project_name}'")
        return jsonify({"error": f"No extracted data found for '{project_name}'"}), 404

    try:
        # Load extracted strings
        with open(extracted_file) as f:
            extracted_data = json.load(f)

        # Get strings from the extracted data
        strings_data = extracted_data.get("strings", [])
        if not strings_data:
            return jsonify({"error": "No strings found in extracted data"}), 400

        # Configure translator with correct parameter name (mock_mode, not use_mock)
        config = TranslationConfig(
            source_language=source_lang,
            target_language=target_lang,
            mock_mode=use_mock,  # Correct parameter name
        )
        translator = GameTranslator(config)

        # Extract texts for translation
        texts = [item.get("decoded_text", "") for item in strings_data]

        # Translate batch
        result = translator.translate_batch(texts)

        # Update extracted data with translations
        for i, item in enumerate(strings_data):
            if i < len(result.results):
                item["translated_text"] = result.results[i].translated

        # Save as CSV
        csv_path = extracted_file.with_name(
            extracted_file.name.replace("_extracted.json", "_translated.csv")
        )

        # Write CSV with proper field names
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "string_id",
                "address",
                "length",
                "original_text",
                "translated_text",
                "description",
                "pointer_address",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for item in strings_data:
                writer.writerow(
                    {
                        "string_id": item.get("string_id", ""),
                        "address": (
                            f"0x{item['address']:04X}"
                            if isinstance(item.get("address"), int)
                            else item.get("address", "")
                        ),
                        "length": item.get("length", ""),
                        "original_text": item.get("decoded_text", ""),
                        "translated_text": item.get("translated_text", ""),
                        "description": item.get("description", ""),
                        "pointer_address": (
                            f"0x{item['pointer_address']:04X}"
                            if item.get("pointer_address")
                            else ""
                        ),
                    }
                )

        logger.info(f"Translated {len(result.results)} strings for {project_name}")
        return jsonify(
            {
                "success": True,
                "translated_count": result.success_count,
                "failed_count": result.failure_count,
                "csv_path": str(csv_path),
            }
        )

    except Exception as e:
        logger.exception(f"Error translating {project_name}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/save_translation", methods=["POST"])
def api_save_translation():
    """Save a single translation edit."""
    data = request.get_json()
    project_name = data.get("project_name")
    address = data.get("address") or data.get("offset")
    translated_text = data.get("translated_text")

    if not all([project_name, address, translated_text is not None]):
        return jsonify({"error": "Missing required fields"}), 400

    output_folder = get_output_folder()

    # Find CSV file
    project_path = output_folder / project_name
    if project_path.is_dir():
        csv_files = list(project_path.glob("*_translated.csv"))
        csv_file = csv_files[0] if csv_files else None
    else:
        csv_file = output_folder / f"{project_name}_translated.csv"

    if not csv_file or not csv_file.exists():
        logger.error(f"Translation file not found for {project_name}")
        return jsonify({"error": "Translation file not found"}), 404

    try:
        # Read existing data
        rows = []
        with open(csv_file) as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)

        # Update the matching row
        updated = False
        for row in rows:
            row_address = row.get("address", row.get("Address", row.get("offset", "")))
            if str(row_address) == str(address):
                if "translated_text" in row:
                    row["translated_text"] = translated_text
                elif "Translated Text" in row:
                    row["Translated Text"] = translated_text
                updated = True
                break

        if not updated:
            logger.warning(f"Address {address} not found in {project_name}")
            return jsonify({"error": f"Address {address} not found"}), 404

        # Write back
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        logger.debug(f"Saved translation for address {address} in {project_name}")
        return jsonify({"success": True})

    except Exception as e:
        logger.exception(f"Error saving translation for {project_name}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/check_font", methods=["POST"])
def api_check_font():
    """Check font compatibility for translation text."""
    data = request.get_json()
    text = data.get("text", "")
    table_file = data.get("table_file")

    try:
        project_root = Path(__file__).parent.parent
        
        # Load encoding table if specified
        encoding_table = None
        if table_file:
            table_path = table_file
            if not Path(table_file).is_absolute():
                table_path = project_root / table_file
            if Path(table_path).exists():
                encoding_table = EncodingTable(str(table_path))

        checker = FontChecker(encoding_table=encoding_table)
        result = checker.check_text(text)

        return jsonify(
            {
                "compatible": result.is_compatible,
                "issues": [
                    {
                        "char": issue.character,
                        "occurrences": issue.occurrences,
                        "suggestion": issue.suggested_replacement,
                    }
                    for issue in result.issues
                ],
                "suggested_fix": result.suggested_text if not result.is_compatible else text,
                "compatibility_score": result.compatibility_score,
            }
        )

    except Exception as e:
        logger.exception("Error checking font compatibility")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/build_patch", methods=["POST"])
def api_build_patch():
    """Build IPS patch from translations."""
    data = request.get_json()
    project_name = data.get("project_name")

    if not project_name:
        logger.warning("Build patch API called without project name")
        return jsonify({"error": "No project name provided"}), 400

    output_folder = get_output_folder()
    rom_folder = get_rom_folder()

    # Find project files
    project_path = output_folder / project_name
    if project_path.is_dir():
        csv_files = list(project_path.glob("*_translated.csv"))
        csv_file = csv_files[0] if csv_files else None
    else:
        csv_file = output_folder / f"{project_name}_translated.csv"

    if not csv_file or not csv_file.exists():
        logger.error(f"Translation file not found for {project_name}")
        return jsonify({"error": "Translation file not found"}), 404

    # Find original ROM
    rom_file = None
    if rom_folder.exists():
        for rom in rom_folder.glob("*.nes"):
            # Match ROM by normalized name
            rom_stem = rom.stem.lower().replace(" ", "_").replace("-", "_")
            project_stem = project_name.lower().replace(" ", "_").replace("-", "_")
            if project_stem in rom_stem or rom_stem in project_stem:
                rom_file = rom
                break

    if not rom_file:
        logger.error(f"Original ROM not found for {project_name}")
        return jsonify({"error": "Original ROM not found. Please upload the ROM first."}), 404

    config_path = None
    try:
        # Determine output paths
        output_dir = project_path if project_path.is_dir() else output_folder
        base_name = csv_file.stem.replace("_translated", "")

        # Create temporary config for reinjection
        config_path = create_temp_config(str(rom_file), method="auto_detect")

        # Initialize reinjector with config path
        reinjector = TextReinjector(config_path)

        # Load translations from CSV
        reinjector.load_translations_from_csv(str(csv_file))

        output_rom = output_dir / f"{base_name}_translated.nes"
        ips_file = output_dir / f"{base_name}_translation.ips"

        # Reinject into ROM
        results = reinjector.reinject_into_rom(str(rom_file), str(output_rom))

        # Generate IPS patch
        reinjector.generate_patch(str(rom_file), str(output_rom), str(ips_file))

        logger.info(f"Built patch for {project_name}")
        return jsonify(
            {
                "success": True,
                "rom_path": str(output_rom),
                "ips_path": str(ips_file),
                "stats": results,
            }
        )

    except Exception as e:
        logger.exception(f"Error building patch for {project_name}")
        return jsonify({"error": str(e)}), 500

    finally:
        cleanup_temp_config(config_path)


@api_bp.route("/validate", methods=["POST"])
def api_validate():
    """Validate translated ROM."""
    data = request.get_json()
    project_name = data.get("project_name")

    if not project_name:
        logger.warning("Validate API called without project name")
        return jsonify({"error": "No project name provided"}), 400

    output_folder = get_output_folder()

    # Find translated ROM
    project_path = output_folder / project_name
    if project_path.is_dir():
        rom_files = list(project_path.glob("*_translated.nes"))
        translated_rom = rom_files[0] if rom_files else None
    else:
        translated_rom = output_folder / f"{project_name}_translated.nes"

    if not translated_rom or not translated_rom.exists():
        logger.error(f"Translated ROM not found for {project_name}")
        return jsonify({"error": "Translated ROM not found"}), 404

    try:
        # ROMValidator expects a config dict, not a path
        validator_config = {
            "validation": {
                "check_crc": False,
            }
        }
        validator = ROMValidator(validator_config)

        # Read ROM data
        with open(translated_rom, "rb") as f:
            rom_data = f.read()

        # Validate ROM
        results = validator.validate_original_rom(rom_data)

        # Convert results to JSON-serializable format
        issues = []
        warnings = []
        all_passed = True

        for result in results:
            if not result.passed:
                all_passed = False
                issues.append(
                    {
                        "check": result.check_name,
                        "message": result.message,
                        "details": result.details,
                    }
                )
            elif result.details:
                warnings.append(
                    {
                        "check": result.check_name,
                        "message": result.message,
                    }
                )

        logger.info(f"Validated ROM for {project_name}: {'PASS' if all_passed else 'FAIL'}")
        return jsonify(
            {
                "valid": all_passed,
                "issues": issues,
                "warnings": warnings,
            }
        )

    except Exception as e:
        logger.exception(f"Error validating {project_name}")
        return jsonify({"error": str(e)}), 500


@api_bp.route("/chr_tiles/<filename>")
def api_chr_tiles(filename: str):
    """Get CHR tile data."""
    rom_path = find_rom_file(filename)

    if not rom_path:
        logger.error(f"ROM not found for CHR tiles: {filename}")
        return jsonify({"error": "ROM not found"}), 404

    try:
        chr_analyzer = CHRAnalyzer()
        analysis = chr_analyzer.analyze_rom(rom_path)

        # Return tile metadata
        return jsonify(
            {
                "chr_type": analysis.chr_type.value,
                "chr_size": analysis.chr_size,
                "total_tiles": analysis.total_tiles,
                "unique_tiles": analysis.unique_tiles,
                "blank_tiles": analysis.blank_tiles,
                "font_regions": [
                    {
                        "start": region.start_tile,
                        "end": region.end_tile,
                        "tile_count": region.tile_count,
                        "notes": region.notes,
                    }
                    for region in analysis.font_regions
                ],
                "has_latin": analysis.has_latin_font(),
                "has_extended": analysis.has_extended_charset(),
                "warnings": analysis.warnings,
            }
        )

    except Exception as e:
        logger.exception(f"Error analyzing CHR tiles for {filename}")
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Project Management Routes
# ============================================================================


@projects_bp.route("/")
def list_projects():
    """List all projects."""
    logger.debug("Listing projects")
    projects = get_project_list()
    logger.info(f"Found {len(projects)} projects")
    return render_template("projects.html", projects=projects)


@projects_bp.route("/<project_name>")
def view_project(project_name: str):
    """View project details - redirects to translate page."""
    logger.info(f"Viewing project: {project_name}")
    
    # Check if project exists
    output_folder = get_output_folder()
    project_path = output_folder / project_name
    
    if project_path.is_dir():
        logger.debug(f"Project directory exists: {project_path}")
        return redirect(url_for("main.translate", project_name=project_name))
    
    # Check for legacy single-file projects
    extracted_file = output_folder / f"{project_name}_extracted.json"
    if extracted_file.exists():
        logger.debug(f"Legacy project file exists: {extracted_file}")
        return redirect(url_for("main.translate", project_name=project_name))
    
    logger.warning(f"Project not found: {project_name}")
    flash(f"Project '{project_name}' not found", "error")
    return redirect(url_for("projects.list_projects"))


@projects_bp.route("/new", methods=["GET", "POST"])
def new_project():
    """Create new project from ROM."""
    if request.method == "POST":
        rom_filename = request.form.get("rom_file")
        project_name = request.form.get("project_name")
        table_file = request.form.get("table_file", "tables/common.tbl")
        
        logger.info(f"Creating new project: {project_name} from ROM: {rom_filename}")

        if not rom_filename or not project_name:
            logger.warning("Missing ROM file or project name")
            flash("ROM file and project name are required", "error")
            return redirect(request.url)

        # Create project directory
        output_folder = get_output_folder()
        project_dir = output_folder / secure_filename(project_name)
        project_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created project directory: {project_dir}")

        # Extract strings
        rom_folder = get_rom_folder()
        rom_path = rom_folder / rom_filename

        if not rom_path.exists():
            flash(f"ROM file '{rom_filename}' not found", "error")
            return redirect(request.url)

        config_path = None
        try:
            # Create temporary config for extraction
            config_path = create_temp_config(str(rom_path), table_file, method="auto_detect")

            # Initialize extractor with config
            extractor = TextExtractor(config_path)
            strings = extractor.extract_from_rom(str(rom_path))

            base_name = rom_path.stem.lower().replace(" ", "_").replace("-", "_")
            extractor.export_to_json(str(project_dir / f"{base_name}_extracted.json"))
            extractor.export_to_csv(str(project_dir / f"{base_name}_extracted.csv"))

            logger.info(f"Created project '{project_name}' with {len(strings)} strings")
            flash(
                f"Project '{project_name}' created with {len(strings)} strings extracted!",
                "success",
            )
            return redirect(url_for("main.translate", project_name=project_name))

        except Exception as e:
            logger.exception(f"Error creating project {project_name}")
            flash(f"Error creating project: {e}", "error")
            return redirect(request.url)

        finally:
            cleanup_temp_config(config_path)

    # GET: Show form
    rom_folder = get_rom_folder()
    rom_files = list(rom_folder.glob("*.nes")) if rom_folder.exists() else []
    
    project_root = Path(__file__).parent.parent
    tables_folder = project_root / "tables"
    table_files = list(tables_folder.glob("*.tbl")) if tables_folder.exists() else []
    
    return render_template("new_project.html", rom_files=rom_files, table_files=table_files)


@projects_bp.route("/<project_name>/delete", methods=["POST"])
def delete_project(project_name: str):
    """Delete a project."""
    import shutil

    output_folder = get_output_folder()
    project_path = output_folder / secure_filename(project_name)

    if project_path.is_dir():
        shutil.rmtree(project_path)
        logger.info(f"Deleted project: {project_name}")
        flash(f"Project '{project_name}' deleted", "success")
    else:
        flash(f"Project '{project_name}' not found", "error")

    return redirect(url_for("projects.list_projects"))


@projects_bp.route("/<project_name>/download/<file_type>")
def download_file(project_name: str, file_type: str):
    """Download project file."""
    output_folder = get_output_folder()
    project_path = output_folder / secure_filename(project_name)

    file_patterns = {
        "json": "*_extracted.json",
        "csv": "*_translated.csv",
        "rom": "*_translated.nes",
        "ips": "*_translation.ips",
        "report": "*_validation_report.txt",
    }

    pattern = file_patterns.get(file_type)
    if not pattern:
        flash("Invalid file type", "error")
        return redirect(url_for("projects.list_projects"))

    # Find file
    search_path = project_path if project_path.is_dir() else output_folder
    files = list(search_path.glob(pattern))

    if not files:
        flash("File not found", "error")
        return redirect(url_for("projects.list_projects"))

    return send_file(files[0], as_attachment=True)
