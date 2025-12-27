"""Flask application factory for FamiLator Web Interface."""

import os
from pathlib import Path
from flask import Flask


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
    
    # Ensure folders exist
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["OUTPUT_FOLDER"]).mkdir(parents=True, exist_ok=True)
    
    # Register blueprints
    from .routes import main_bp, api_bp, projects_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(projects_bp, url_prefix="/projects")
    
    return app
