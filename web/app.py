"""Flask application factory for FamiLator Web Interface."""

import logging
import os
from pathlib import Path
from flask import Flask


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the web application.
    
    Args:
        debug: Whether to enable debug logging.
    """
    level = logging.DEBUG if debug else logging.INFO
    
    # Configure root logger for FamiLator
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set specific loggers
    logging.getLogger('src.web').setLevel(level)
    
    # Reduce noise from werkzeug in production
    if not debug:
        logging.getLogger('werkzeug').setLevel(logging.WARNING)


def create_app(config: dict | None = None) -> Flask:
    """Create and configure the Flask application.
    
    Args:
        config: Optional configuration dictionary.
        
    Returns:
        Configured Flask application.
    """
    app = Flask(__name__, 
                template_folder="templates",
                static_folder="static")
    
    # Default configuration
    app.config.update({
        "SECRET_KEY": os.environ.get("SECRET_KEY", "dev-key-change-in-production"),
        "UPLOAD_FOLDER": os.environ.get("UPLOAD_FOLDER", "roms_input"),
        "OUTPUT_FOLDER": os.environ.get("OUTPUT_FOLDER", "output"),
        "MAX_CONTENT_LENGTH": 16 * 1024 * 1024,  # 16 MB max file size
        "ALLOWED_EXTENSIONS": {"nes", "fds"},
    })
    
    # Override with custom config if provided
    if config:
        app.config.update(config)
    
    # Setup logging
    debug = app.config.get("DEBUG", False)
    setup_logging(debug)
    
    logger = logging.getLogger(__name__)
    logger.info("Initializing FamiLator Web Interface")
    
    # Ensure folders exist - only create if paths are absolute
    # Relative paths are resolved in routes.py relative to project root
    upload_folder = Path(app.config["UPLOAD_FOLDER"])
    output_folder = Path(app.config["OUTPUT_FOLDER"])
    
    if upload_folder.is_absolute():
        upload_folder.mkdir(parents=True, exist_ok=True)
    if output_folder.is_absolute():
        output_folder.mkdir(parents=True, exist_ok=True)
    
    logger.debug(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    logger.debug(f"Output folder: {app.config['OUTPUT_FOLDER']}")
    
    # Register blueprints
    from .routes import main_bp, api_bp, projects_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(projects_bp, url_prefix="/projects")
    
    return app
