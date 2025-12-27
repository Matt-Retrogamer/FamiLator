"""Flask route blueprints for FamiLator Web Interface."""

import json
import os
from pathlib import Path
from flask import (
    Blueprint, render_template, request, jsonify, 
    send_file, current_app, redirect, url_for, flash
)
from werkzeug.utils import secure_filename

# Import FamiLator modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.extractor import TextExtractor as ROMExtractor
from src.reinjector import TextReinjector as ROMReinjector
from src.validator import ROMValidator as TranslationValidator
from src.chr_analyzer import CHRAnalyzer
from src.font_checker import FontChecker
from src.language_detector import LanguageDetector
from src.translator import GameTranslator, TranslationConfig, Glossary, TranslationMemory


# Main blueprint for page routes
main_bp = Blueprint("main", __name__)

# API blueprint for AJAX endpoints
api_bp = Blueprint("api", __name__)

# Projects blueprint
projects_bp = Blueprint("projects", __name__)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return (
        "." in filename and 
        filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]
    )


def get_project_list() -> list[dict]:
    """Get list of all projects in the output folder."""
    output_folder = Path(current_app.config["OUTPUT_FOLDER"])
    projects = []
    
    # Look for project directories (have extracted.json files)
    for item in output_folder.iterdir():
        if item.is_dir():
            extracted_files = list(item.glob("*_extracted.json"))
            if extracted_files:
                projects.append({
                    "name": item.name,
                    "path": str(item),
                    "files": {
                        "extracted": len(list(item.glob("*_extracted.*"))),
                        "translated": len(list(item.glob("*_translated.*"))),
                        "patches": len(list(item.glob("*.ips"))),
                    }
                })
    
    # Also check for files directly in output folder
    for json_file in output_folder.glob("*_extracted.json"):
        if json_file.parent == output_folder:
            base_name = json_file.stem.replace("_extracted", "")
            projects.append({
                "name": base_name,
                "path": str(output_folder),
                "files": {
                    "extracted": 1,
                    "translated": 1 if (output_folder / f"{base_name}_translated.csv").exists() else 0,
                    "patches": 1 if (output_folder / f"{base_name}_translation.ips").exists() else 0,
                }
            })
    
    return projects


# ============================================================================
# Main Page Routes
# ============================================================================

@main_bp.route("/")
def index():
    """Home page with project overview."""
    projects = get_project_list()
    rom_files = list(Path(current_app.config["UPLOAD_FOLDER"]).glob("*.nes"))
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
            filepath = Path(current_app.config["UPLOAD_FOLDER"]) / filename
            file.save(filepath)
            flash(f"ROM '{filename}' uploaded successfully!", "success")
            return redirect(url_for("main.analyze", filename=filename))
        else:
            flash("Invalid file type. Only .nes and .fds files allowed.", "error")
    
    return render_template("upload.html")


@main_bp.route("/analyze/<filename>")
def analyze(filename: str):
    """ROM analysis page showing CHR tiles and text extraction preview."""
    rom_path = Path(current_app.config["UPLOAD_FOLDER"]) / secure_filename(filename)
    
    if not rom_path.exists():
        flash(f"ROM file '{filename}' not found", "error")
        return redirect(url_for("main.index"))
    
    # Perform CHR analysis
    chr_analyzer = CHRAnalyzer()
    chr_analysis = chr_analyzer.analyze_rom(rom_path)
    
    # Detect language
    lang_detector = LanguageDetector()
    with open(rom_path, "rb") as f:
        rom_data = f.read()
    lang_analysis = lang_detector.analyze(rom_data)
    
    return render_template(
        "analyze.html",
        filename=filename,
        chr_analysis=chr_analysis,
        lang_analysis=lang_analysis
    )


@main_bp.route("/translate/<project_name>")
def translate(project_name: str):
    """Translation editor page."""
    output_folder = Path(current_app.config["OUTPUT_FOLDER"])
    
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
        import csv
        with open(translated_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                translations[row.get("offset", row.get("Offset"))] = row.get(
                    "translated_text", row.get("Translated Text", "")
                )
    
    return render_template(
        "translate.html",
        project_name=project_name,
        extracted_data=extracted_data,
        translations=translations
    )


@main_bp.route("/tiles/<project_name>")
def tile_browser(project_name: str):
    """Visual tile browser for CHR ROM inspection."""
    rom_path = None
    
    # Try to find associated ROM
    rom_folder = Path(current_app.config["UPLOAD_FOLDER"])
    for rom_file in rom_folder.glob("*.nes"):
        if project_name.lower() in rom_file.stem.lower():
            rom_path = rom_file
            break
    
    chr_analysis = None
    if rom_path:
        chr_analyzer = CHRAnalyzer()
        chr_analysis = chr_analyzer.analyze_rom(rom_path)
    
    return render_template(
        "tiles.html",
        project_name=project_name,
        chr_analysis=chr_analysis
    )


# ============================================================================
# API Routes
# ============================================================================

@api_bp.route("/extract", methods=["POST"])
def api_extract():
    """Extract text from ROM."""
    data = request.get_json()
    rom_filename = data.get("rom_filename")
    table_file = data.get("table_file", "tables/common.tbl")
    output_name = data.get("output_name")
    
    if not rom_filename:
        return jsonify({"error": "No ROM filename provided"}), 400
    
    rom_path = Path(current_app.config["UPLOAD_FOLDER"]) / secure_filename(rom_filename)
    if not rom_path.exists():
        return jsonify({"error": f"ROM file '{rom_filename}' not found"}), 404
    
    try:
        extractor = ROMExtractor(str(rom_path), table_file)
        strings = extractor.extract_strings()
        
        # Determine output path
        if output_name:
            output_dir = Path(current_app.config["OUTPUT_FOLDER"]) / secure_filename(output_name)
            output_dir.mkdir(parents=True, exist_ok=True)
            base_name = output_name
        else:
            output_dir = Path(current_app.config["OUTPUT_FOLDER"])
            base_name = rom_path.stem
        
        # Save extracted data
        json_path = output_dir / f"{base_name}_extracted.json"
        csv_path = output_dir / f"{base_name}_extracted.csv"
        
        extractor.save_json(strings, str(json_path))
        extractor.save_csv(strings, str(csv_path))
        
        return jsonify({
            "success": True,
            "strings_found": len(strings),
            "json_path": str(json_path),
            "csv_path": str(csv_path),
            "project_name": base_name if not output_name else output_name
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/translate", methods=["POST"])
def api_translate():
    """Translate extracted strings."""
    data = request.get_json()
    project_name = data.get("project_name")
    use_mock = data.get("use_mock", True)
    source_lang = data.get("source_lang", "Japanese")
    target_lang = data.get("target_lang", "English")
    
    if not project_name:
        return jsonify({"error": "No project name provided"}), 400
    
    output_folder = Path(current_app.config["OUTPUT_FOLDER"])
    
    # Find extracted file
    project_path = output_folder / project_name
    if project_path.is_dir():
        extracted_files = list(project_path.glob("*_extracted.json"))
        extracted_file = extracted_files[0] if extracted_files else None
    else:
        extracted_file = output_folder / f"{project_name}_extracted.json"
    
    if not extracted_file or not extracted_file.exists():
        return jsonify({"error": f"No extracted data found for '{project_name}'"}), 404
    
    try:
        # Load extracted strings
        with open(extracted_file) as f:
            extracted_data = json.load(f)
        
        # Configure translator
        config = TranslationConfig(
            source_language=source_lang,
            target_language=target_lang,
            use_mock=use_mock
        )
        translator = GameTranslator(config)
        
        # Translate
        texts = [item["text"] for item in extracted_data]
        result = translator.translate_batch(texts)
        
        # Update extracted data with translations
        for i, item in enumerate(extracted_data):
            if i < len(result.results):
                item["translated_text"] = result.results[i].translated_text
        
        # Save as CSV
        csv_path = extracted_file.with_name(
            extracted_file.name.replace("_extracted.json", "_translated.csv")
        )
        
        import csv
        with open(csv_path, "w", newline="") as f:
            if extracted_data:
                writer = csv.DictWriter(f, fieldnames=extracted_data[0].keys())
                writer.writeheader()
                writer.writerows(extracted_data)
        
        return jsonify({
            "success": True,
            "translated_count": len(result.results),
            "csv_path": str(csv_path)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/save_translation", methods=["POST"])
def api_save_translation():
    """Save a single translation edit."""
    data = request.get_json()
    project_name = data.get("project_name")
    offset = data.get("offset")
    translated_text = data.get("translated_text")
    
    if not all([project_name, offset, translated_text is not None]):
        return jsonify({"error": "Missing required fields"}), 400
    
    output_folder = Path(current_app.config["OUTPUT_FOLDER"])
    
    # Find CSV file
    project_path = output_folder / project_name
    if project_path.is_dir():
        csv_files = list(project_path.glob("*_translated.csv"))
        csv_file = csv_files[0] if csv_files else None
    else:
        csv_file = output_folder / f"{project_name}_translated.csv"
    
    if not csv_file or not csv_file.exists():
        return jsonify({"error": "Translation file not found"}), 404
    
    try:
        import csv
        
        # Read existing data
        rows = []
        with open(csv_file) as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        
        # Update the matching row
        updated = False
        for row in rows:
            row_offset = row.get("offset", row.get("Offset"))
            if str(row_offset) == str(offset):
                if "translated_text" in row:
                    row["translated_text"] = translated_text
                elif "Translated Text" in row:
                    row["Translated Text"] = translated_text
                updated = True
                break
        
        if not updated:
            return jsonify({"error": f"Offset {offset} not found"}), 404
        
        # Write back
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        return jsonify({"success": True})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/check_font", methods=["POST"])
def api_check_font():
    """Check font compatibility for translation text."""
    data = request.get_json()
    text = data.get("text", "")
    table_file = data.get("table_file")
    
    checker = FontChecker(table_file) if table_file else FontChecker()
    result = checker.check_text(text)
    
    return jsonify({
        "compatible": result.is_compatible,
        "issues": [
            {
                "char": issue.character,
                "position": issue.position,
                "suggestion": issue.suggestion
            }
            for issue in result.issues
        ],
        "suggested_fix": checker.auto_fix_text(text) if not result.is_compatible else text
    })


@api_bp.route("/build_patch", methods=["POST"])
def api_build_patch():
    """Build IPS patch from translations."""
    data = request.get_json()
    project_name = data.get("project_name")
    
    if not project_name:
        return jsonify({"error": "No project name provided"}), 400
    
    output_folder = Path(current_app.config["OUTPUT_FOLDER"])
    rom_folder = Path(current_app.config["UPLOAD_FOLDER"])
    
    # Find project files
    project_path = output_folder / project_name
    if project_path.is_dir():
        csv_files = list(project_path.glob("*_translated.csv"))
        csv_file = csv_files[0] if csv_files else None
    else:
        csv_file = output_folder / f"{project_name}_translated.csv"
    
    if not csv_file or not csv_file.exists():
        return jsonify({"error": "Translation file not found"}), 404
    
    # Find original ROM
    rom_file = None
    for rom in rom_folder.glob("*.nes"):
        if project_name.lower() in rom.stem.lower().replace(" ", "_").replace("-", "_"):
            rom_file = rom
            break
    
    if not rom_file:
        return jsonify({"error": "Original ROM not found"}), 404
    
    try:
        # Determine output paths
        output_dir = project_path if project_path.is_dir() else output_folder
        base_name = csv_file.stem.replace("_translated", "")
        
        reinjector = ROMReinjector(
            original_rom=str(rom_file),
            translated_csv=str(csv_file),
            table_file="tables/common.tbl"
        )
        
        output_rom = output_dir / f"{base_name}_translated.nes"
        ips_file = output_dir / f"{base_name}_translation.ips"
        
        reinjector.create_patched_rom(str(output_rom))
        reinjector.create_ips_patch(str(ips_file))
        
        return jsonify({
            "success": True,
            "rom_path": str(output_rom),
            "ips_path": str(ips_file)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/validate", methods=["POST"])
def api_validate():
    """Validate translated ROM."""
    data = request.get_json()
    project_name = data.get("project_name")
    
    if not project_name:
        return jsonify({"error": "No project name provided"}), 400
    
    output_folder = Path(current_app.config["OUTPUT_FOLDER"])
    
    # Find translated ROM
    project_path = output_folder / project_name
    if project_path.is_dir():
        rom_files = list(project_path.glob("*_translated.nes"))
        translated_rom = rom_files[0] if rom_files else None
    else:
        translated_rom = output_folder / f"{project_name}_translated.nes"
    
    if not translated_rom or not translated_rom.exists():
        return jsonify({"error": "Translated ROM not found"}), 404
    
    try:
        validator = TranslationValidator(str(translated_rom))
        report = validator.validate()
        
        return jsonify({
            "valid": report["valid"],
            "header_valid": report.get("header_valid", True),
            "issues": report.get("issues", []),
            "warnings": report.get("warnings", [])
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/chr_tiles/<filename>")
def api_chr_tiles(filename: str):
    """Get CHR tile data as base64 images."""
    rom_path = Path(current_app.config["UPLOAD_FOLDER"]) / secure_filename(filename)
    
    if not rom_path.exists():
        return jsonify({"error": "ROM not found"}), 404
    
    try:
        chr_analyzer = CHRAnalyzer()
        analysis = chr_analyzer.analyze_rom(rom_path)
        
        # Return tile metadata (actual rendering done client-side)
        return jsonify({
            "chr_type": analysis.chr_type.value,
            "tile_count": analysis.tile_count,
            "font_regions": [
                {
                    "start": region.start_tile,
                    "end": region.end_tile,
                    "is_latin": region.is_latin_font
                }
                for region in analysis.font_regions
            ],
            "has_latin": analysis.has_latin_font,
            "has_extended": analysis.has_extended_charset
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Project Management Routes
# ============================================================================

@projects_bp.route("/")
def list_projects():
    """List all projects."""
    projects = get_project_list()
    return render_template("projects.html", projects=projects)


@projects_bp.route("/new", methods=["GET", "POST"])
def new_project():
    """Create new project from ROM."""
    if request.method == "POST":
        rom_filename = request.form.get("rom_file")
        project_name = request.form.get("project_name")
        table_file = request.form.get("table_file", "tables/common.tbl")
        
        if not rom_filename or not project_name:
            flash("ROM file and project name are required", "error")
            return redirect(request.url)
        
        # Create project directory
        project_dir = Path(current_app.config["OUTPUT_FOLDER"]) / secure_filename(project_name)
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract strings
        rom_path = Path(current_app.config["UPLOAD_FOLDER"]) / rom_filename
        try:
            extractor = ROMExtractor(str(rom_path), table_file)
            strings = extractor.extract_strings()
            
            base_name = rom_path.stem.lower().replace(" ", "_").replace("-", "_")
            extractor.save_json(strings, str(project_dir / f"{base_name}_extracted.json"))
            extractor.save_csv(strings, str(project_dir / f"{base_name}_extracted.csv"))
            
            flash(f"Project '{project_name}' created with {len(strings)} strings extracted!", "success")
            return redirect(url_for("main.translate", project_name=project_name))
        
        except Exception as e:
            flash(f"Error creating project: {e}", "error")
            return redirect(request.url)
    
    # GET: Show form
    rom_files = list(Path(current_app.config["UPLOAD_FOLDER"]).glob("*.nes"))
    table_files = list(Path("tables").glob("*.tbl"))
    return render_template("new_project.html", rom_files=rom_files, table_files=table_files)


@projects_bp.route("/<project_name>/delete", methods=["POST"])
def delete_project(project_name: str):
    """Delete a project."""
    import shutil
    
    project_path = Path(current_app.config["OUTPUT_FOLDER"]) / secure_filename(project_name)
    
    if project_path.is_dir():
        shutil.rmtree(project_path)
        flash(f"Project '{project_name}' deleted", "success")
    else:
        flash(f"Project '{project_name}' not found", "error")
    
    return redirect(url_for("projects.list_projects"))


@projects_bp.route("/<project_name>/download/<file_type>")
def download_file(project_name: str, file_type: str):
    """Download project file."""
    output_folder = Path(current_app.config["OUTPUT_FOLDER"])
    project_path = output_folder / secure_filename(project_name)
    
    file_patterns = {
        "json": "*_extracted.json",
        "csv": "*_translated.csv",
        "rom": "*_translated.nes",
        "ips": "*_translation.ips",
        "report": "*_validation_report.txt"
    }
    
    pattern = file_patterns.get(file_type)
    if not pattern:
        flash("Invalid file type", "error")
        return redirect(url_for("projects.list_projects"))
    
    # Find file
    search_path = project_path if project_path.is_dir() else output_folder
    files = list(search_path.glob(pattern))
    
    if not files:
        flash(f"File not found", "error")
        return redirect(url_for("projects.list_projects"))
    
    return send_file(files[0], as_attachment=True)
